"""推送渠道管理 API"""
import uuid
from flask import Blueprint, request
from app import db
from app.utils.helpers import standard_response, error_response
from app.utils.auth import login_required, admin_required
from flask import g
from app.models.push_channel import PushChannel
from app.services.push_channels import PushDispatcher

bp = Blueprint('push_channels', __name__, url_prefix='/api/v1/push-channels')


@bp.route('/all-users', methods=['GET'])
@admin_required
def list_users_with_channels():
    """管理员: 列出所有用户及其推送渠道"""
    from app.models.user import User
    users = User.query.filter_by(enabled=True).all()
    result = []
    for u in users:
        channels = PushChannel.query.filter_by(user_id=u.id, enabled=True).all()
        result.append({
            'id': u.id,
            'email': u.email,
            'display_name': u.display_name or u.email,
            'channels': [c.to_dict() for c in channels],
        })
    return standard_response({'users': result})


@bp.route('', methods=['GET'])
@login_required
def list_channels():
    target_user_id = request.args.get('user_id', '')
    if target_user_id:
        channels = PushChannel.query.filter_by(user_id=target_user_id).order_by(PushChannel.created_at.desc()).all()
    else:
        channels = PushChannel.query.order_by(PushChannel.created_at.desc()).all()
    return standard_response({'channels': [c.to_dict() for c in channels], 'total': len(channels)})


@bp.route('', methods=['POST'])
@login_required
def create_channel():
    user = g.current_user
    data = request.get_json() or {}

    channel_type = data.get('channel_type', '')
    name = data.get('name', '')
    config = data.get('config', {})

    if channel_type not in PushChannel.CHANNEL_TYPES:
        return error_response(400, f'不支持的渠道类型: {channel_type}')
    if not name:
        return error_response(400, '名称不能为空')

    ch = PushChannel(
        id=uuid.uuid4().hex[:8],
        user_id=user.id,
        channel_type=channel_type,
        name=name,
        enabled=True,
        is_alert=data.get('is_alert', False),
    )
    ch.set_config(config)
    db.session.add(ch)
    db.session.commit()
    return standard_response(ch.to_dict()), 201


@bp.route('/<ch_id>', methods=['PUT'])
@login_required
def update_channel(ch_id):
    ch = PushChannel.query.filter_by(id=ch_id).first()
    if not ch:
        return error_response(404, '渠道不存在')

    data = request.get_json() or {}
    if 'name' in data:
        ch.name = data['name']
    if 'config' in data:
        ch.set_config(data['config'])
    if 'enabled' in data:
        ch.enabled = data['enabled']
    if 'is_alert' in data:
        ch.is_alert = data['is_alert']
    db.session.commit()
    return standard_response(ch.to_dict())


@bp.route('/<ch_id>', methods=['DELETE'])
@login_required
def delete_channel(ch_id):
    ch = PushChannel.query.filter_by(id=ch_id).first()
    if not ch:
        return error_response(404, '渠道不存在')
    db.session.delete(ch)
    db.session.commit()
    return standard_response({'deleted': ch_id})


@bp.route('/<ch_id>/test', methods=['POST'])
@login_required
def test_channel(ch_id):
    ch = PushChannel.query.filter_by(id=ch_id).first()
    if not ch:
        return error_response(404, '渠道不存在')

    dispatcher = PushDispatcher()
    ok, err = dispatcher.send_test(ch.channel_type, ch.get_config())
    if ok:
        return standard_response({'status': 'ok', 'message': '测试消息已发送'})
    else:
        return error_response(400, f'发送失败: {err}')
