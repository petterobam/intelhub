"""脚本 & Agent 提示词文件管理 API（list / read / update）"""
import os
import shutil
from datetime import datetime

from flask import Blueprint, request

from app.utils.helpers import standard_response, error_response

bp = Blueprint('scripts', __name__, url_prefix='/api/v1/scripts')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts', 'cron_wrappers')
PROMPTS_DIR = os.path.join(BASE_DIR, 'analysis', 'agents', 'prompts')

MAX_SIZE = 100 * 1024  # 100 KB


def _safe_path(filename, base_dir):
    """Return safe absolute path or None if traversal detected."""
    if not filename or '/' in filename or '\\' in filename or '..' in filename:
        return None
    full = os.path.normpath(os.path.join(base_dir, filename))
    if not full.startswith(os.path.normpath(base_dir)):
        return None
    return full


def _dir_for_category(category):
    if category == 'prompt':
        return PROMPTS_DIR
    return SCRIPTS_DIR


# ── List ──────────────────────────────────────────────────────────────────────

@bp.route('', methods=['GET'])
def list_scripts():
    """列出 shell 脚本 + agent 提示词文件元信息"""
    def _scan(directory, category):
        items = []
        if not os.path.isdir(directory):
            return items
        for fname in sorted(os.listdir(directory)):
            full = os.path.join(directory, fname)
            if not os.path.isfile(full):
                continue
            st = os.stat(full)
            items.append({
                'filename': fname,
                'category': category,
                'size': st.st_size,
                'modified': datetime.fromtimestamp(st.st_mtime).isoformat(),
            })
        return items

    return standard_response({
        'shell_scripts': _scan(SCRIPTS_DIR, 'shell'),
        'agent_prompts': _scan(PROMPTS_DIR, 'prompt'),
    })


# ── Read ──────────────────────────────────────────────────────────────────────

@bp.route('/<path:filename>', methods=['GET'])
def read_script(filename):
    """读取单个文件内容"""
    category = request.args.get('category', 'shell')
    base_dir = _dir_for_category(category)
    full = _safe_path(filename, base_dir)
    if full is None:
        return error_response(400, 'Invalid filename'), 400
    if not os.path.isfile(full):
        return error_response(404, 'File not found'), 404

    size = os.path.getsize(full)
    if size > MAX_SIZE:
        return error_response(413, 'File too large (max 100KB)'), 413

    try:
        with open(full, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
    except Exception as e:
        return error_response(500, str(e)), 500

    return standard_response({
        'filename': filename,
        'category': category,
        'size': size,
        'modified': datetime.fromtimestamp(os.path.getmtime(full)).isoformat(),
        'content': content,
    })


# ── Update ────────────────────────────────────────────────────────────────────

@bp.route('/<path:filename>', methods=['PUT'])
def update_script(filename):
    """更新文件内容（自动备份 .bak）"""
    data = request.get_json()
    if not data or 'content' not in data:
        return error_response(400, 'content is required'), 400

    category = data.get('category', 'shell')
    base_dir = _dir_for_category(category)
    full = _safe_path(filename, base_dir)
    if full is None:
        return error_response(400, 'Invalid filename'), 400
    if not os.path.isfile(full):
        return error_response(404, 'File not found'), 404

    content = data['content']
    if len(content.encode('utf-8')) > MAX_SIZE:
        return error_response(413, 'Content too large (max 100KB)'), 413

    try:
        # backup
        shutil.copy2(full, full + '.bak')
        with open(full, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        return error_response(500, str(e)), 500

    st = os.stat(full)
    return standard_response({
        'filename': filename,
        'category': category,
        'size': st.st_size,
        'modified': datetime.fromtimestamp(st.st_mtime).isoformat(),
        'message': 'Updated successfully',
    })
