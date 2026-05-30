"""Auth API — 登录 / 注册 / 用户管理

路由:
  POST /api/v1/auth/login           — 登录
  POST /api/v1/auth/register        — 邮箱注册（发送免登录链接）
  GET  /api/v1/auth/me              — 当前用户信息
  POST /api/v1/auth/change-password — 修改密码
  GET  /api/v1/users                — 用户列表 (admin)
  POST /api/v1/users                — 创建用户 (admin)
  PUT  /api/v1/users/<id>           — 编辑用户 (admin)
  DELETE /api/v1/users/<id>         — 删除用户 (admin)
"""

import logging
import secrets
import string

from flask import Blueprint, request, g

from app import db
from app.models.user import User
from app.models.subscription import Subscription
from app.models.task import ScheduledTask
from app.utils.auth import generate_token, login_required, admin_required, TIER_ORDER
from app.utils.helpers import standard_response, error_response

logger = logging.getLogger(__name__)

bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')


# ── 注册 ──────────────────────────────────────────────────────────────

DEFAULT_REPORT_TASK_NAME = '生活娱乐日报'


def _get_or_create_default_task():
    """获取或创建默认订阅的报告任务"""
    task = ScheduledTask.query.filter_by(
        name=DEFAULT_REPORT_TASK_NAME, task_type='report'
    ).first()
    if task:
        return task

    task = ScheduledTask(
        name=DEFAULT_REPORT_TASK_NAME,
        task_type='report',
        module='daily_brief',
        script='# 自动创建的默认订阅报告任务\npass',
        description='系统默认订阅报告',
        schedule_type='cron',
        schedule_config='{"hour": 8, "minute": 0}',
        enabled=True,
        status='idle',
    )
    db.session.add(task)
    db.session.commit()
    return task


@bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()

    if not email or '@' not in email:
        return error_response(400, '请输入有效的邮箱地址')

    user = User.query.filter_by(email=email).first()

    if not user:
        # 新用户：创建账号
        alphabet = string.ascii_letters + string.digits
        raw_password = ''.join(secrets.choice(alphabet) for _ in range(16))
        display_name = email.split('@')[0]

        user = User(email=email, display_name=display_name, role='user')
        user.set_password(raw_password)
        db.session.add(user)
        db.session.flush()

        # 订阅默认报告
        task = _get_or_create_default_task()
        existing_sub = Subscription.query.filter_by(
            email=email, task_id=task.id
        ).first()
        if not existing_sub:
            sub = Subscription(email=email, name=display_name, task_id=task.id)
            db.session.add(sub)

        db.session.commit()
        logger.info("New user registered: %s", email)

    # 生成 token 登录链接
    token = generate_token(user.id, user.role)

    # 读取站点 URL
    try:
        from app.models.llm_config import LlmConfig
        site_url = (LlmConfig.get('site_url') or '').rstrip('/')
    except Exception:
        site_url = ''

    login_url = f'{site_url}/login?token={token}'

    # 发送邮件
    email_sent = False
    try:
        from app.services.email_sender import EmailSender
        sender = EmailSender()
        if sender.is_configured():
            display_name = user.display_name or email.split('@')[0]
            html = (
                '<div style="max-width:560px;margin:0 auto;font-family:-apple-system,sans-serif;padding:24px">'
                f'<h2 style="color:#1a365d">欢迎使用 IntelHub 智能情报平台</h2>'
                f'<p style="color:#2d3748">你好 <strong>{display_name}</strong>，</p>'
                '<p style="color:#2d3748">点击下方按钮即可登录平台：</p>'
                '<div style="margin:24px 0;text-align:center">'
                f'<a href="{login_url}" style="display:inline-block;background:#0ea5e9;color:#fff;padding:12px 32px;'
                'border-radius:8px;text-decoration:none;font-size:14px;font-weight:600">立即登录</a></div>'
                '<p style="color:#718096;font-size:13px">或复制以下链接到浏览器打开：</p>'
                f'<p style="color:#3182ce;font-size:13px;word-break:break-all">{login_url}</p>'
                '<p style="color:#a0aec0;font-size:12px;margin-top:24px">此链接 24 小时内有效。</p>'
                '<hr style="margin:24px 0 10px;border-color:#e2e8f0">'
                '<p style="color:#a0aec0;font-size:12px">此邮件由 IntelHub 智能平台自动发送</p></div>'
            )
            email_sent = sender.send(email, '[IntelHub] 登录链接', html)
    except Exception as e:
        logger.warning("Register email failed for %s: %s", email, e)

    if not email_sent:
        # 邮件发送失败时仍然返回 token，方便调试
        return standard_response({
            'message': f'注册成功，但邮件发送失败。请联系管理员。',
            'email': email,
        })

    return standard_response({
        'message': f'登录链接已发送至 {email}，请查收邮件。',
        'email': email,
    })


# ── 登录 ──────────────────────────────────────────────────────────────

@bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''

    if not email or not password:
        return error_response(400, '邮箱和密码不能为空')

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return error_response(401, '邮箱或密码错误')
    if not user.enabled:
        return error_response(403, '账号已被禁用')

    token = generate_token(user.id, user.role)
    return standard_response({
        'token': token,
        'user': user.to_dict(),
    })


@bp.route('/me', methods=['GET'])
@login_required
def me():
    return standard_response(g.current_user.to_dict())


@bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    data = request.get_json(silent=True) or {}
    old_pwd = data.get('old_password') or ''
    new_pwd = data.get('new_password') or ''

    if not old_pwd or not new_pwd:
        return error_response(400, '旧密码和新密码不能为空')
    if len(new_pwd) < 6:
        return error_response(400, '新密码至少 6 个字符')

    user = g.current_user
    if not user.check_password(old_pwd):
        return error_response(400, '旧密码错误')

    user.set_password(new_pwd)
    db.session.commit()
    return standard_response({'message': '密码已修改'})


# ── 用户管理 (admin) ──────────────────────────────────────────────────

user_bp = Blueprint('users', __name__, url_prefix='/api/v1/users')


@user_bp.route('', methods=['GET'])
@admin_required
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return standard_response([u.to_dict() for u in users])


@user_bp.route('/by-email', methods=['GET'])
@admin_required
def get_user_by_email():
    email = request.args.get('email', '').strip().lower()
    if not email:
        return standard_response({'error': 'email required'}), 400
    user = User.query.filter_by(email=email).first()
    if not user:
        return standard_response({'data': None})
    return standard_response(user.to_dict())


@user_bp.route('', methods=['POST'])
@admin_required
def create_user():
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    password = data.get('password') or ''
    role = data.get('role', 'user')

    if not email or not password:
        return error_response(400, '邮箱和密码不能为空')
    if len(password) < 6:
        return error_response(400, '密码至少 6 个字符')
    if role not in ('admin', 'user'):
        return error_response(400, '角色只能是 admin 或 user')

    tier = data.get('tier', 'free')
    if tier not in TIER_ORDER:
        return error_response(400, f'tier 必须是: {", ".join(TIER_ORDER)}')

    if User.query.filter_by(email=email).first():
        return error_response(409, f'邮箱 {email} 已注册')

    user = User(
        email=email,
        display_name=data.get('display_name', ''),
        role=role,
        tier=tier,
        enabled=data.get('enabled', True),
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return standard_response(user.to_dict()), 201


@user_bp.route('/<user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return error_response(404, '用户不存在')

    data = request.get_json(silent=True) or {}
    if 'display_name' in data:
        user.display_name = data['display_name']
    if 'role' in data:
        if data['role'] not in ('admin', 'user'):
            return error_response(400, '角色只能是 admin 或 user')
        user.role = data['role']
    if 'enabled' in data:
        user.enabled = bool(data['enabled'])
    if 'is_member' in data:
        user.is_member = bool(data['is_member'])
    if 'tier' in data:
        if data['tier'] not in TIER_ORDER:
            return error_response(400, f'tier 必须是: {", ".join(TIER_ORDER)}')
        user.tier = data['tier']
    if 'tier_expires_at' in data:
        from datetime import datetime
        v = data['tier_expires_at']
        user.tier_expires_at = datetime.fromisoformat(v) if v else None
    if 'password' in data and data['password']:
        if len(data['password']) < 6:
            return error_response(400, '密码至少 6 个字符')
        user.set_password(data['password'])

    db.session.commit()
    return standard_response(user.to_dict())


@user_bp.route('/<user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return error_response(404, '用户不存在')
    if user.email == 'admin@intelhub.local':
        return error_response(400, '不能删除默认管理员')

    db.session.delete(user)
    db.session.commit()
    return standard_response({'deleted': True})
