"""OAuth API — GitHub / Google / Microsoft / Discord / 微信 / 飞书 社交登录

流程:
  GET /api/v1/oauth/providers          → 返回已配置的 provider 列表
  GET /api/v1/oauth/<provider>         → 302 跳转到 OAuth 授权页
  GET /api/v1/oauth/<provider>/callback → 处理回调，自动注册/登录，302 回前端
"""

import logging
import secrets
import string
from urllib.parse import urlencode

import requests as http_requests
from flask import Blueprint, redirect, request
from sqlalchemy.exc import IntegrityError

from app import db
from app.models.user import User
from app.models.subscription import Subscription
from app.models.task import ScheduledTask
from app.utils.auth import generate_token
from app.utils.helpers import standard_response, get_proxies

logger = logging.getLogger(__name__)

bp = Blueprint('oauth', __name__, url_prefix='/api/v1/oauth')

# ── Provider 配置 ────────────────────────────────────────────────────

PROVIDERS = {
    'github': {
        'name': 'GitHub',
        'authorize_url': 'https://github.com/login/oauth/authorize',
        'token_url': 'https://github.com/login/oauth/access_token',
        'userinfo_url': 'https://api.github.com/user',
        'email_url': 'https://api.github.com/user/emails',
        'scope': 'user:email',
        'client_id_key': 'oauth_github_client_id',
        'client_secret_key': 'oauth_github_client_secret',
    },
    'google': {
        'name': 'Google',
        'authorize_url': 'https://accounts.google.com/o/oauth2/v2/auth',
        'token_url': 'https://oauth2.googleapis.com/token',
        'userinfo_url': 'https://www.googleapis.com/oauth2/v2/userinfo',
        'scope': 'openid email profile',
        'client_id_key': 'oauth_google_client_id',
        'client_secret_key': 'oauth_google_client_secret',
    },
    'microsoft': {
        'name': 'Microsoft',
        'authorize_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/authorize',
        'token_url': 'https://login.microsoftonline.com/common/oauth2/v2.0/token',
        'userinfo_url': 'https://graph.microsoft.com/v1.0/me',
        'scope': 'openid email User.Read',
        'client_id_key': 'oauth_microsoft_client_id',
        'client_secret_key': 'oauth_microsoft_client_secret',
    },
    'discord': {
        'name': 'Discord',
        'authorize_url': 'https://discord.com/api/oauth2/authorize',
        'token_url': 'https://discord.com/api/oauth2/token',
        'userinfo_url': 'https://discord.com/api/v10/users/@me',
        'scope': 'identify email',
        'client_id_key': 'oauth_discord_client_id',
        'client_secret_key': 'oauth_discord_client_secret',
    },
    'wechat': {
        'name': '微信',
        'authorize_url': 'https://open.weixin.qq.com/connect/qrconnect',
        'token_url': 'https://api.weixin.qq.com/sns/oauth2/access_token',
        'userinfo_url': 'https://api.weixin.qq.com/sns/userinfo',
        'scope': 'snsapi_login',
        'client_id_key': 'oauth_wechat_app_id',
        'client_secret_key': 'oauth_wechat_app_secret',
    },
    'feishu': {
        'name': '飞书',
        'authorize_url': 'https://open.feishu.cn/open-apis/authen/v1/authorize',
        'token_url': 'https://open.feishu.cn/open-apis/authen/v1/oidc/access_token',
        'app_token_url': 'https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal/',
        'userinfo_url': 'https://open.feishu.cn/open-apis/authen/v1/user_info',
        'scope': 'contact:user.base:readonly',
        'client_id_key': 'oauth_feishu_app_id',
        'client_secret_key': 'oauth_feishu_app_secret',
    },
}


def _cfg():
    from app.models.llm_config import LlmConfig
    return LlmConfig


def _get_frontend_url():
    site_url = _cfg().get('site_url', '')
    return site_url.rstrip('/') if site_url else 'http://localhost:18432'


def _get_backend_url():
    site_url = _cfg().get('site_url', '')
    return site_url.rstrip('/') if site_url else 'http://localhost:18923'


def _is_configured(cfg):
    client_id = _cfg().get(cfg['client_id_key'], '')
    client_secret = _cfg().get(cfg['client_secret_key'], '')
    return bool(client_id and client_secret)


def _redirect_error(msg):
    return redirect(f'{_get_frontend_url()}/login?oauth_error={msg}', code=302)


# ── 路由 ──────────────────────────────────────────────────────────────

@bp.route('/providers', methods=['GET'])
def get_providers():
    if _cfg().get('oauth_enabled', 'true').lower() == 'false':
        return standard_response({})
    configured = {}
    for name, cfg in PROVIDERS.items():
        if _is_configured(cfg):
            configured[name] = cfg['name']
    return standard_response(configured)


@bp.route('/<provider>', methods=['GET'])
def oauth_authorize(provider):
    if _cfg().get('oauth_enabled', 'true').lower() == 'false':
        return _redirect_error('社交登录已关闭')
    cfg = PROVIDERS.get(provider)
    if not cfg or not _is_configured(cfg):
        return _redirect_error('不支持的登录方式')

    state = secrets.token_urlsafe(32)
    client_id = _cfg().get(cfg['client_id_key'], '')
    redirect_uri = f'{_get_backend_url()}/api/v1/oauth/{provider}/callback'

    params = {
        'redirect_uri': redirect_uri,
        'state': state,
        'response_type': 'code',
    }

    # Provider-specific 参数名
    if provider == 'wechat':
        params['appid'] = client_id
        params['scope'] = cfg['scope']
    elif provider == 'feishu':
        params['app_id'] = client_id
    else:
        params['client_id'] = client_id
        params['scope'] = cfg['scope']

    url = f'{cfg["authorize_url"]}?{urlencode(params)}'
    if provider == 'wechat':
        url += '#wechat_redirect'
    resp = redirect(url, code=302)
    resp.set_cookie(
        f'oauth_state_{provider}',
        state,
        httponly=True,
        samesite='Lax',
        max_age=600,
        path='/api/v1/oauth/',
    )
    return resp


@bp.route('/<provider>/callback', methods=['GET'])
def oauth_callback(provider):
    cfg = PROVIDERS.get(provider)
    if not cfg:
        return _redirect_error('不支持的登录方式')

    # 用户拒绝授权
    error = request.args.get('error')
    if error:
        return _redirect_error('登录已取消')

    code = request.args.get('code')
    state = request.args.get('state')
    if not code or not state:
        return _redirect_error('授权参数缺失')

    # 校验 state
    cookie_state = request.cookies.get(f'oauth_state_{provider}')
    if not cookie_state or cookie_state != state:
        return _redirect_error('安全验证失败，请重试')

    redirect_uri = f'{_get_backend_url()}/api/v1/oauth/{provider}/callback'

    try:
        # 换 access_token
        token_data = _exchange_code(provider, cfg, code, redirect_uri)
        access_token = token_data.get('access_token')
        if not access_token:
            return _redirect_error('OAuth 登录失败，请稍后重试')

        # 获取用户信息
        email, display_name = _fetch_userinfo(provider, cfg, token_data)
        if not email:
            return _redirect_error('OAuth 登录需要邮箱权限，请重试或使用邮箱登录')

        email = email.strip().lower()

        # 查找或创建用户
        user = _find_or_create_user(email, display_name)
        if not user:
            return _redirect_error('登录失败，请稍后重试')

        # 生成 JWT → 重定向回前端
        token = generate_token(user.id, user.role)
        resp = redirect(f'{_get_frontend_url()}/login?token={token}', code=302)
        resp.delete_cookie(f'oauth_state_{provider}', path='/api/v1/oauth/')
        return resp

    except Exception as e:
        logger.error('OAuth callback error (%s): %s', provider, e)
        return _redirect_error('OAuth 登录失败，请稍后重试')


# ── Token 交换 ────────────────────────────────────────────────────────

def _exchange_code(provider, cfg, code, redirect_uri):
    client_id = _cfg().get(cfg['client_id_key'], '')
    client_secret = _cfg().get(cfg['client_secret_key'], '')

    if provider == 'wechat':
        return _exchange_wechat(cfg, client_id, client_secret, code)

    if provider == 'feishu':
        return _exchange_feishu(cfg, client_id, client_secret, code, redirect_uri)

    # 标准 OAuth: POST with client_id/secret/code
    data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'code': code,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }
    headers = {'Accept': 'application/json'}

    resp = http_requests.post(cfg['token_url'], data=data, headers=headers, timeout=15, proxies=get_proxies())
    resp.raise_for_status()
    token_data = resp.json()
    return {'access_token': token_data.get('access_token')}


def _exchange_wechat(cfg, appid, secret, code):
    """微信: GET 参数换取，返回 access_token + openid"""
    resp = http_requests.get(cfg['token_url'], params={
        'appid': appid,
        'secret': secret,
        'code': code,
        'grant_type': 'authorization_code',
    }, timeout=15, proxies=get_proxies())
    resp.raise_for_status()
    data = resp.json()
    return {
        'access_token': data.get('access_token'),
        'openid': data.get('openid'),
    }


def _exchange_feishu(cfg, app_id, app_secret, code, redirect_uri):
    """飞书: 两步 — 先获取 app_access_token，再换 user_access_token"""
    # Step 1: 获取 app_access_token
    resp = http_requests.post(cfg['app_token_url'], json={
        'app_id': app_id,
        'app_secret': app_secret,
    }, timeout=15, proxies=get_proxies())
    resp.raise_for_status()
    app_token = resp.json().get('app_access_token')
    if not app_token:
        return {}

    # Step 2: 用 app_access_token 换 user_access_token
    resp = http_requests.post(
        cfg['token_url'],
        headers={'Authorization': f'Bearer {app_token}', 'Content-Type': 'application/json'},
        json={'grant_type': 'authorization_code', 'code': code, 'redirect_uri': redirect_uri},
        timeout=15,
        proxies=get_proxies(),
    )
    resp.raise_for_status()
    data = resp.json()
    return {
        'access_token': data.get('access_token'),
        'openid': data.get('open_id'),
    }


# ── 用户信息获取 ──────────────────────────────────────────────────────

def _fetch_userinfo(provider, cfg, token_data):
    access_token = token_data.get('access_token', '')
    openid = token_data.get('openid', '')
    headers = {'Authorization': f'Bearer {access_token}'}

    if provider == 'github':
        return _fetch_github_user(cfg, access_token, headers)

    if provider == 'wechat':
        return _fetch_wechat_user(cfg, access_token, openid)

    if provider == 'feishu':
        return _fetch_feishu_user(cfg, access_token)

    # 通用: Bearer token GET userinfo
    resp = http_requests.get(cfg['userinfo_url'], headers=headers, timeout=15, proxies=get_proxies())
    resp.raise_for_status()
    info = resp.json()

    if provider == 'google':
        return info.get('email'), info.get('name', '')
    elif provider == 'microsoft':
        email = info.get('mail') or info.get('userPrincipalName', '')
        return email, info.get('displayName', '')
    elif provider == 'discord':
        return info.get('email'), info.get('username', '')

    return None, None


def _fetch_wechat_user(cfg, access_token, openid):
    """微信: 不返回邮箱，用虚拟邮箱 wx_{openid}@wechat.internal"""
    resp = http_requests.get(cfg['userinfo_url'], params={
        'access_token': access_token,
        'openid': openid,
    }, timeout=15, proxies=get_proxies())
    resp.raise_for_status()
    info = resp.json()
    nickname = info.get('nickname', '')
    email = f'wx_{openid}@wechat.internal'
    return email, nickname


def _fetch_feishu_user(cfg, access_token):
    """飞书: 返回 email + name"""
    resp = http_requests.get(cfg['userinfo_url'], headers={
        'Authorization': f'Bearer {access_token}',
    }, timeout=15, proxies=get_proxies())
    resp.raise_for_status()
    data = resp.json()
    info = data.get('data', data)
    email = info.get('email', '')
    name = info.get('name', '')
    return email, name


def _fetch_github_user(cfg, access_token, headers):
    # GitHub 基本信息
    resp = http_requests.get(cfg['userinfo_url'], headers=headers, timeout=15, proxies=get_proxies())
    resp.raise_for_status()
    info = resp.json()
    display_name = info.get('name') or info.get('login', '')

    # GitHub 用户邮箱需要单独获取
    resp = http_requests.get(cfg['email_url'], headers=headers, timeout=15, proxies=get_proxies())
    resp.raise_for_status()
    emails = resp.json()

    # 取 primary + verified 的邮箱
    for e in emails:
        if e.get('primary') and e.get('verified'):
            return e.get('email'), display_name

    # 退而求其次取任意 verified 邮箱
    for e in emails:
        if e.get('verified'):
            return e.get('email'), display_name

    # 最后取第一个
    if emails:
        return emails[0].get('email'), display_name

    return None, None


# ── 查找或创建用户 ────────────────────────────────────────────────────

def _find_or_create_user(email, display_name=''):
    user = User.query.filter_by(email=email).first()
    if user:
        return user

    # 自动注册
    alphabet = string.ascii_letters + string.digits
    raw_password = ''.join(secrets.choice(alphabet) for _ in range(32))
    user = User(
        email=email,
        display_name=display_name or email.split('@')[0],
        role='user',
    )
    user.set_password(raw_password)

    try:
        db.session.add(user)
        db.session.flush()

        # 订阅默认报告（复用 auth.py 的逻辑）
        task = _get_or_create_default_task()
        existing_sub = Subscription.query.filter_by(
            email=email, task_id=task.id
        ).first()
        if not existing_sub:
            sub = Subscription(
                email=email,
                name=user.display_name,
                task_id=task.id,
            )
            db.session.add(sub)

        db.session.commit()
        logger.info('OAuth auto-registered user: %s', email)
        return user
    except IntegrityError:
        db.session.rollback()
        # 并发场景：另一个请求已经创建了该用户
        user = User.query.filter_by(email=email).first()
        return user


def _get_or_create_default_task():
    """获取或创建默认订阅的报告任务"""
    task = ScheduledTask.query.filter_by(
        name='生活娱乐日报', task_type='report'
    ).first()
    if task:
        return task

    task = ScheduledTask(
        name='生活娱乐日报',
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
