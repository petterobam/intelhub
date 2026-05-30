"""Subscriptions API — 订阅中心 CRUD

路由:
  GET    /api/v1/subscriptions              — 列出所有订阅
  GET    /api/v1/subscriptions/report-tasks — 获取可订阅的报告任务列表
  POST   /api/v1/subscriptions              — 新增订阅
  PUT    /api/v1/subscriptions/<id>         — 更新订阅
  DELETE /api/v1/subscriptions/<id>         — 删除订阅
  POST   /api/v1/subscriptions/<id>/test    — 发送测试邮件给该订阅者
"""

import logging

from flask import Blueprint, request

from app import db
from app.models.subscription import Subscription
from app.models.task import ScheduledTask
from app.models.user import User
from app.utils.helpers import standard_response, error_response
from app.utils.auth import login_required, admin_required
from flask import g

logger = logging.getLogger(__name__)

bp = Blueprint('subscriptions', __name__, url_prefix='/api/v1/subscriptions')


def _sub_to_dict(s):
    d = s.to_dict()
    if s.task_id:
        task = db.session.get(ScheduledTask, s.task_id)
        d['task_name'] = task.name if task else '(已删除)'
        d['task_module'] = task.module if task else ''
    else:
        d['task_name'] = ''
        d['task_module'] = ''
    matched = User.query.filter_by(email=s.email.lower()).first()
    d['has_user'] = matched is not None
    if matched:
        d['user_id'] = matched.id
        d['user_display_name'] = matched.display_name
    # 填充渠道名称
    channel_ids = s.channel_ids or []
    labels = []
    if channel_ids:
        real_ids = [cid for cid in channel_ids if cid != '_email']
        if '_email' in channel_ids:
            labels.append({'id': '_email', 'name': f'邮件 ({s.email})', 'type': 'email', 'label': '邮件'})
        if real_ids:
            from app.models.push_channel import PushChannel
            ch_list = PushChannel.query.filter(PushChannel.id.in_(real_ids)).all()
            ch_map = {c.id: c for c in ch_list}
            for c_id in real_ids:
                c = ch_map.get(c_id)
                if c:
                    labels.append({'id': c.id, 'name': c.name, 'type': c.channel_type, 'label': c.CHANNEL_TYPES.get(c.channel_type, c.channel_type)})
    if not labels:
        labels.append({'id': '_email', 'name': f'邮件 ({s.email})', 'type': 'email', 'label': '邮件'})
    d['channel_labels'] = labels
    return d


@bp.route('', methods=['GET'])
@login_required
def list_subscriptions():
    subs = Subscription.query.order_by(Subscription.created_at.desc()).all()
    return standard_response([_sub_to_dict(s) for s in subs])


@bp.route('/report-tasks', methods=['GET'])
@login_required
def report_tasks():
    """返回所有 report 类型的任务，供订阅选择"""
    tasks = ScheduledTask.query.filter_by(task_type='report').order_by(ScheduledTask.name).all()
    return standard_response([
        {'id': t.id, 'name': t.name, 'module': t.module, 'enabled': t.enabled}
        for t in tasks
    ])


@bp.route('', methods=['POST'])
@login_required
def create_subscription():
    data = request.get_json(silent=True) or {}

    email = (data.get('email') or '').strip().lower()
    name = (data.get('name') or '').strip()

    task_id = (data.get('task_id') or '').strip()

    if not email or '@' not in email:
        return error_response(400, 'Valid email is required')

    if not task_id:
        return error_response(400, '请选择要订阅的报告任务')

    task = db.session.get(ScheduledTask, task_id)
    if not task or task.task_type != 'report':
        return error_response(400, '选择的任务不存在或不是报告类型')

    existing = Subscription.query.filter_by(email=email, task_id=task_id).first()
    if existing:
        return error_response(409, f'{email} 已订阅该任务')

    sub = Subscription(email=email, name=name, task_id=task_id, channel_ids=data.get('channel_ids', []))
    db.session.add(sub)
    db.session.commit()

    return standard_response(_sub_to_dict(sub))


@bp.route('/<sub_id>', methods=['PUT'])
@login_required
def update_subscription(sub_id):
    sub = db.session.get(Subscription, sub_id)
    if not sub:
        return error_response(404, 'Subscription not found')

    data = request.get_json(silent=True) or {}
    if 'name' in data:
        sub.name = data['name'].strip()
    if 'email' in data:
        email = data['email'].strip().lower()
        if '@' not in email:
            return error_response(400, 'Invalid email')
        sub.email = email
    if 'task_id' in data:
        task_id = data['task_id']
        task = db.session.get(ScheduledTask, task_id)
        if not task or task.task_type != 'report':
            return error_response(400, '无效的任务')
        sub.task_id = task_id
    if 'enabled' in data:
        sub.enabled = bool(data['enabled'])
    if 'channel_ids' in data:
        sub.channel_ids = data['channel_ids']

    db.session.commit()

    d = sub.to_dict()
    if sub.task_id:
        task = db.session.get(ScheduledTask, sub.task_id)
        d['task_name'] = task.name if task else '(已删除)'
        d['task_module'] = task.module if task else ''
    return standard_response(d)


@bp.route('/<sub_id>', methods=['DELETE'])
@login_required
def delete_subscription(sub_id):
    sub = db.session.get(Subscription, sub_id)
    if not sub:
        return standard_response({'deleted': True})
    db.session.delete(sub)
    db.session.commit()
    return standard_response({'deleted': True})


@bp.route('/<sub_id>/test', methods=['POST'])
@login_required
def test_subscription(sub_id):
    """向该订阅者的所有关联渠道发送测试消息"""
    sub = db.session.get(Subscription, sub_id)
    if not sub:
        return error_response(404, 'Subscription not found')

    task_name = '测试报告'
    if sub.task_id:
        task = db.session.get(ScheduledTask, sub.task_id)
        if task:
            task_name = task.name

    test_html = (
        f'<h2>订阅测试</h2><p>你好{(" " + sub.name) if sub.name else ""}，</p>'
        f'<p>你已成功订阅 IntelHub 报告推送，订阅任务: <strong>{task_name}</strong></p>'
        f'<p style="color:#888;font-size:12px;">此为测试消息，由系统自动发送。</p>'
    )

    from app.services.push_channels import PushDispatcher
    dispatcher = PushDispatcher()
    result = dispatcher.dispatch(test_html, '', 'heartbeat', [sub])

    sent = result['sent']
    failed = result['failed']
    if sent > 0:
        return standard_response({'message': f'测试消息已发送 ({sent} 个渠道成功, {failed} 个失败)'})
    return error_response(500, f'发送失败: {"; ".join(d.get("error","") for d in result.get("details",[]))}')
