"""Settings API — 配置中心 (LLM + SMTP + Site)

路由:
  GET  /api/v1/settings          — 获取所有配置 (分组, 敏感字段打码)
  PUT  /api/v1/settings          — 批量更新配置
  POST /api/v1/settings/smtp/test — 发送测试邮件
  GET  /api/v1/settings/models   — 拉取可用模型列表
"""

import os
import json
import logging
import urllib.request

from flask import Blueprint, request

from app.utils.helpers import standard_response, error_response
from app.utils.auth import admin_required

logger = logging.getLogger(__name__)

bp = Blueprint('settings', __name__, url_prefix='/api/v1/settings')

# ── Key 映射 ────────────────────────────────────────────────────────────

LLM_KEYS = {
    'api_key': 'llm_api_key',
    'base_url': 'llm_base_url',
    'model': 'llm_model',
}

SMTP_KEY_MAP = {
    'host': 'smtp_host',
    'port': 'smtp_port',
    'user': 'smtp_user',
    'password': 'smtp_password',
    'from_name': 'smtp_from_name',
    'use_tls': 'smtp_use_tls',
}

SITE_KEY_MAP = {
    'site_url': 'site_url',
}

SENSITIVE_KEYS = {'llm_api_key', 'smtp_password'}
MASK = '••••••••'


def _cfg():
    from app.models.llm_config import LlmConfig
    return LlmConfig


def _get(key, default=''):
    return _cfg().get(key, default)


def _get_llm_env():
    api_key = _get('llm_api_key') or _get('api_key') or os.environ.get('ANTHROPIC_API_KEY', '')
    base_url = _get('llm_base_url') or _get('base_url') or os.environ.get('ANTHROPIC_BASE_URL', '')
    model = _get('llm_model') or _get('model') or os.environ.get('ANTHROPIC_MODEL', '')
    env = {"ANTHROPIC_API_KEY": api_key}
    if base_url:
        env["ANTHROPIC_BASE_URL"] = base_url.rstrip("/")
    return env, model, api_key


def _mask(val):
    if not val:
        return ''
    return val[:4] + '••••' + val[-4:] if len(val) > 12 else MASK


# ── GET /api/v1/settings ──────────────────────────────────────────────

@bp.route('', methods=['GET'])
@admin_required
def get_settings():
    all_cfg = _cfg().get_all()

    llm_api_key = all_cfg.get('llm_api_key') or all_cfg.get('api_key') or ''
    llm_base_url = all_cfg.get('llm_base_url') or all_cfg.get('base_url') or ''
    llm_model = all_cfg.get('llm_model') or all_cfg.get('model') or ''

    sdk_available = False
    try:
        import claude_agent_sdk
        sdk_available = True
    except ImportError:
        pass

    llm = {
        'api_key': _mask(llm_api_key),
        'base_url': llm_base_url,
        'model': llm_model,
        'configured': bool(llm_api_key),
        'sdk_available': sdk_available,
    }

    smtp = {
        'host': all_cfg.get('smtp_host', ''),
        'port': int(all_cfg.get('smtp_port', '465') or '465'),
        'user': all_cfg.get('smtp_user', ''),
        'password': _mask(all_cfg.get('smtp_password', '')),
        'from_name': all_cfg.get('smtp_from_name', 'IntelHub'),
        'use_tls': all_cfg.get('smtp_use_tls', 'true').lower() == 'true',
        'configured': bool(all_cfg.get('smtp_host') and all_cfg.get('smtp_user')),
    }

    site = {
        'site_url': all_cfg.get('site_url', ''),
    }

    return standard_response({'llm': llm, 'smtp': smtp, 'site': site})


# ── PUT /api/v1/settings ──────────────────────────────────────────────

@bp.route('', methods=['PUT'])
@admin_required
def save_settings():
    data = request.get_json(silent=True) or {}
    Cfg = _cfg()

    llm = data.get('llm', {})
    if llm:
        for short_key, unified_key in LLM_KEYS.items():
            val = llm.get(short_key)
            if val is not None and val != MASK and val != '••••••••':
                Cfg.set(unified_key, val)
                Cfg.set(short_key, val)
                if short_key == 'api_key':
                    os.environ['ANTHROPIC_API_KEY'] = val
                elif short_key == 'base_url' and val:
                    os.environ['ANTHROPIC_BASE_URL'] = val
                elif short_key == 'model' and val:
                    os.environ['ANTHROPIC_MODEL'] = val

    smtp = data.get('smtp', {})
    if smtp:
        for field, db_key in SMTP_KEY_MAP.items():
            val = smtp.get(field)
            if val is not None:
                if field == 'password' and (val == MASK or val == '••••••••'):
                    continue
                Cfg.set(db_key, str(val))

    site = data.get('site', {})
    if site:
        for field, db_key in SITE_KEY_MAP.items():
            val = site.get(field)
            if val is not None:
                Cfg.set(db_key, str(val).rstrip('/'))

    return standard_response({'message': 'Settings saved'})


# ── GET /api/v1/settings/models ───────────────────────────────────────

@bp.route('/models', methods=['GET'])
@admin_required
def fetch_models():
    api_key = _get('llm_api_key') or _get('api_key') or os.environ.get('ANTHROPIC_API_KEY', '')
    base_url = _get('llm_base_url') or _get('base_url') or os.environ.get('ANTHROPIC_BASE_URL', '')
    if not api_key:
        return error_response(400, '请先配置 API Key')
    if not base_url:
        return error_response(400, '请先配置 Base URL')

    url = f"{base_url.rstrip('/')}/v1/models"
    req = urllib.request.Request(url, headers={
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
    })
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        rdata = json.loads(resp.read())
        models = [{"id": m.get("id", ""), "display_name": m.get("display_name", m.get("id", ""))}
                  for m in rdata.get("data", [])]
        models.sort(key=lambda m: m["id"])
        return standard_response(models)
    except urllib.error.HTTPError as e:
        return error_response(502, f'拉取模型列表失败: HTTP {e.code}')
    except Exception as e:
        return error_response(502, f'拉取模型列表失败: {str(e)[:200]}')


# ── POST /api/v1/settings/smtp/test ────────────────────────────────────

@bp.route('/smtp/test', methods=['POST'])
@admin_required
def test_smtp():
    data = request.get_json(silent=True) or {}
    to = data.get('to', '').strip()
    if not to:
        return error_response(400, 'to is required')

    try:
        from app.services.email_sender import EmailSender
        sender = EmailSender()
        if not sender.is_configured():
            return error_response(400, 'SMTP 未配置，请先保存 SMTP 设置')
        ok = sender.send(to, '[IntelHub] 测试邮件', '<h2>邮件服务测试</h2><p>如果你收到了这封邮件，说明 SMTP 配置正确。</p>')
        if ok:
            return standard_response({'message': f'测试邮件已发送至 {to}'})
        return error_response(500, '发送失败，请检查 SMTP 配置')
    except Exception as e:
        logger.error("SMTP test failed: %s", e)
        return error_response(500, str(e))


# ── POST /api/v1/settings/upload ─────────────────────────────────────

@bp.route('/upload', methods=['POST'])
@admin_required
def upload_file():
    import uuid
    from werkzeug.utils import secure_filename

    f = request.files.get('file')
    if not f:
        return error_response(400, '请选择文件')

    allowed_ext = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
    filename = f.filename or 'file'
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    if ext not in allowed_ext:
        return error_response(400, f'不支持的文件类型: .{ext}')

    safe_name = f"{uuid.uuid4().hex[:8]}_{secure_filename(filename)}"
    upload_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)

    save_path = os.path.join(upload_dir, safe_name)
    f.save(save_path)

    url = f"/data/uploads/{safe_name}"
    return standard_response({'url': url, 'filename': safe_name})
