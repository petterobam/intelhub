"""User Sources API — 用户内容订阅源管理

路由:
  GET  /api/v1/user-sources         — 列出当前用户的源
  POST /api/v1/user-sources         — 新增源 (v3+)
  PUT  /api/v1/user-sources/<id>    — 修改源 (v3+)
  DELETE /api/v1/user-sources/<id>  — 删除源 (v3+)
  POST /api/v1/user-sources/<id>/fetch — 手动采集 (v3+)
  GET  /api/v1/user-sources/quota   — 查看配额 (v3+)
"""

import logging

from flask import Blueprint, request, g

from app import db
from app.models.user_source import UserSource
from app.utils.auth import login_required, tier_required
from app.utils.helpers import standard_response, error_response

logger = logging.getLogger(__name__)

bp = Blueprint('user_sources', __name__, url_prefix='/api/v1/user-sources')

TIER_SOURCE_LIMITS = {
    'free': 0, 'v1': 0, 'v2': 0,
    'v3': 10, 'v4': 30, 'v5': 100,
}

SUPPORTED_TYPES = ['rss', 'bilibili', 'youtube']


@bp.route('', methods=['GET'])
@login_required
def list_sources():
    sources = UserSource.query.filter_by(user_id=g.current_user.id).order_by(UserSource.created_at.desc()).all()
    return standard_response([s.to_dict() for s in sources])


@bp.route('', methods=['POST'])
@login_required
@tier_required('v3')
def create_source():
    data = request.get_json(silent=True) or {}
    src_type = data.get('type', '').strip().lower()
    source_id = (data.get('source_id') or '').strip()
    display_name = (data.get('display_name') or '').strip()

    if not src_type or not source_id:
        return error_response(400, 'type 和 source_id 不能为空')
    if src_type not in SUPPORTED_TYPES:
        return error_response(400, f'不支持的类型，可选: {", ".join(SUPPORTED_TYPES)}')

    # Check quota
    user_tier = g.current_user.effective_tier
    limit = TIER_SOURCE_LIMITS.get(user_tier, 0)
    current = UserSource.query.filter_by(user_id=g.current_user.id).count()
    if current >= limit:
        return error_response(403, f'已达到 {user_tier} 等级的源数量上限 ({limit} 个)')

    # Check duplicate
    if UserSource.query.filter_by(user_id=g.current_user.id, type=src_type, source_id=source_id).first():
        return error_response(409, '该源已存在')

    # Validate source
    try:
        from crawlers.user_sources.dispatcher import get_adapter
        adapter = get_adapter(src_type)
        result = adapter.validate(source_id)
        if not result.get('valid'):
            return error_response(400, result.get('error', '源验证失败'))
        if not display_name:
            display_name = result.get('display_name', source_id)
    except Exception as e:
        return error_response(400, f'验证失败: {str(e)[:200]}')

    source = UserSource(
        user_id=g.current_user.id,
        type=src_type,
        source_id=source_id,
        display_name=display_name,
    )
    db.session.add(source)
    db.session.commit()
    return standard_response(source.to_dict()), 201


@bp.route('/<source_uid>', methods=['PUT'])
@login_required
@tier_required('v3')
def update_source(source_uid):
    source = db.session.get(UserSource, source_uid)
    if not source or source.user_id != g.current_user.id:
        return error_response(404, '源不存在')

    data = request.get_json(silent=True) or {}
    if 'display_name' in data:
        source.display_name = data['display_name']
    if 'enabled' in data:
        source.enabled = bool(data['enabled'])
    db.session.commit()
    return standard_response(source.to_dict())


@bp.route('/<source_uid>', methods=['DELETE'])
@login_required
@tier_required('v3')
def delete_source(source_uid):
    source = db.session.get(UserSource, source_uid)
    if not source or source.user_id != g.current_user.id:
        return error_response(404, '源不存在')
    db.session.delete(source)
    db.session.commit()
    return standard_response({'deleted': True})


@bp.route('/<source_uid>/fetch', methods=['POST'])
@login_required
@tier_required('v3')
def fetch_source(source_uid):
    source = db.session.get(UserSource, source_uid)
    if not source or source.user_id != g.current_user.id:
        return error_response(404, '源不存在')

    try:
        from app.scheduler.user_source_scheduler import fetch_user_source
        fetch_user_source(source)
        return standard_response(source.to_dict())
    except Exception as e:
        return error_response(500, f'采集失败: {str(e)[:200]}')


@bp.route('/quota', methods=['GET'])
@login_required
@tier_required('v3')
def get_quota():
    user_tier = g.current_user.effective_tier
    limit = TIER_SOURCE_LIMITS.get(user_tier, 0)
    current = UserSource.query.filter_by(user_id=g.current_user.id).count()
    return standard_response({
        'tier': user_tier,
        'limit': limit,
        'used': current,
        'remaining': max(0, limit - current),
    })
