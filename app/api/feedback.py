"""Feedback API — 用户反馈"""
from flask import Blueprint, request, g
from app.utils.helpers import standard_response, error_response, bj_now
from app.utils.auth import login_required, admin_required
from app import db

bp = Blueprint('feedback', __name__, url_prefix='/api/v1/feedback')

VALID_STATUSES = ('pending', 'replied', 'scheduled', 'evaluating', 'archived')


@bp.route('', methods=['POST'])
@login_required
def create_feedback():
    """提交反馈"""
    user = g.current_user
    data = request.get_json() or {}
    content = (data.get('content') or '').strip()
    category = data.get('category', 'general') or 'general'

    if not content:
        return error_response(400, '请输入反馈内容')
    if len(content) > 2000:
        return error_response(400, '反馈内容不能超过 2000 字')

    from app.models.feedback import Feedback
    fb = Feedback(
        user_id=user.id,
        content=content,
        category=category,
    )
    db.session.add(fb)
    db.session.commit()

    return standard_response(fb.to_dict(include_reply=True))


@bp.route('', methods=['GET'])
def list_feedback():
    """获取公开反馈列表（排除已归档，最新 N 条）"""
    from app.models.feedback import Feedback
    limit = min(request.args.get('limit', 5, type=int), 20)
    fbs = Feedback.query.filter(Feedback.status != 'archived')\
        .order_by(Feedback.created_at.desc()).limit(limit).all()
    return standard_response([f.to_dict() for f in fbs])


@bp.route('/mine', methods=['GET'])
@login_required
def my_feedback():
    """查看所有反馈（open-source 版本无用户隔离）"""
    from app.models.feedback import Feedback
    fbs = Feedback.query\
        .order_by(Feedback.created_at.desc()).limit(50).all()
    return standard_response([f.to_dict(include_reply=True) for f in fbs])


@bp.route('/admin', methods=['GET'])
@admin_required
def admin_list():
    """管理员查看所有反馈"""
    from app.models.feedback import Feedback
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    status_filter = request.args.get('status', '')

    query = Feedback.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    total = query.count()
    fbs = query.order_by(Feedback.created_at.desc())\
        .offset((page - 1) * per_page).limit(per_page).all()
    return standard_response({
        'items': [f.to_dict(include_reply=True) for f in fbs],
        'total': total,
        'page': page,
        'per_page': per_page,
    })


@bp.route('/admin/<fid>/reply', methods=['POST'])
@admin_required
def admin_reply(fid):
    """管理员回复反馈"""
    data = request.get_json() or {}
    reply = (data.get('reply') or '').strip()
    if not reply:
        return error_response(400, '请输入回复内容')

    from app.models.feedback import Feedback
    fb = Feedback.query.get(fid)
    if not fb:
        return error_response(404, '反馈不存在')

    fb.reply = reply
    if fb.status == 'pending':
        fb.status = 'replied'
    db.session.commit()
    return standard_response(fb.to_dict(include_reply=True))


@bp.route('/admin/<fid>/status', methods=['POST'])
@admin_required
def admin_status(fid):
    """管理员更新反馈状态"""
    data = request.get_json() or {}
    new_status = data.get('status', '')
    if new_status not in VALID_STATUSES:
        return error_response(400, f'无效状态: {new_status}')

    from app.models.feedback import Feedback
    fb = Feedback.query.get(fid)
    if not fb:
        return error_response(404, '反馈不存在')

    fb.status = new_status
    db.session.commit()
    return standard_response(fb.to_dict(include_reply=True))
