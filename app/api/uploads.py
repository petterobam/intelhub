"""Uploads API — 文件上传与摄入

路由:
  GET  /api/v1/uploads         — 列出已上传文件
  POST /api/v1/uploads         — 上传文件
  POST /api/v1/uploads/url     — 提交网页 URL 抓取
  DELETE /api/v1/uploads/<id>  — 删除文件
  GET  /api/v1/uploads/quota   — 查看存储配额
"""

import logging
import os
import re
import threading
import uuid

from flask import Blueprint, request, g

from app import db
from app.models.user_upload import UserUpload
from app.utils.auth import login_required, tier_required
from app.utils.user_dirs import user_uploads_dir, assert_within_user_dir
from app.utils.helpers import standard_response, error_response

logger = logging.getLogger(__name__)

bp = Blueprint('uploads', __name__, url_prefix='/api/v1/uploads')

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'md', 'markdown', 'docx'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_STORAGE = 500 * 1024 * 1024   # 500MB

BLOCKED_URL_PATTERNS = [
    r'^https?://(localhost|127\.|192\.168\.|10\.|172\.(1[6-9]|2[0-9]|3[01])\.)',
]


def _is_safe_url(url: str) -> bool:
    return not any(re.match(p, url) for p in BLOCKED_URL_PATTERNS)


def _get_used_storage(user_id: str) -> int:
    uploads_dir = user_uploads_dir(user_id)
    if not os.path.exists(uploads_dir):
        return 0
    return sum(
        os.path.getsize(os.path.join(uploads_dir, f))
        for f in os.listdir(uploads_dir)
        if os.path.isfile(os.path.join(uploads_dir, f))
    )


@bp.route('', methods=['GET'])
@login_required
@tier_required('v5')
def list_uploads():
    uploads = UserUpload.query.filter_by(user_id=g.current_user.id).order_by(UserUpload.created_at.desc()).all()
    return standard_response([u.to_dict() for u in uploads])


@bp.route('', methods=['POST'])
@login_required
@tier_required('v5')
def upload_file():
    if 'file' not in request.files:
        return error_response(400, '请选择文件')

    f = request.files['file']
    user_id = g.current_user.id

    # Validate extension
    ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
    if ext not in ALLOWED_EXTENSIONS:
        return error_response(400, f'不支持的文件类型: .{ext}，可选: {", ".join(sorted(ALLOWED_EXTENSIONS))}')

    # Validate size
    f.seek(0, 2)
    size = f.tell()
    f.seek(0)
    if size > MAX_FILE_SIZE:
        return error_response(400, '文件不能超过 10MB')

    # Check storage quota
    used = _get_used_storage(user_id)
    if used + size > MAX_STORAGE:
        return error_response(400, f'存储空间不足，已用 {used // (1024*1024)}MB / 500MB')

    # Save file
    upload_id = uuid.uuid4().hex[:8]
    save_path = os.path.join(user_uploads_dir(user_id), f'{upload_id}.{ext}')
    assert_within_user_dir(user_id, save_path)
    f.save(save_path)

    # DB record
    record = UserUpload(
        id=upload_id, user_id=user_id, filename=f.filename,
        ext=ext, size=size, path=save_path,
    )
    db.session.add(record)
    db.session.commit()

    # Async ingest
    def _ingest():
        from app import create_app
        app = create_app()
        with app.app_context():
            from knowledge_base.parsers.ingestor import ingest_upload
            ingest_upload(upload_id)

    threading.Thread(target=_ingest, daemon=True).start()

    return standard_response({'id': upload_id, 'filename': f.filename, 'status': 'parsing'}), 201


@bp.route('/url', methods=['POST'])
@login_required
@tier_required('v5')
def fetch_url():
    data = request.get_json(silent=True) or {}
    url = (data.get('url') or '').strip()

    if not url.startswith(('http://', 'https://')):
        return error_response(400, '请输入有效的 HTTP/HTTPS URL')
    if not _is_safe_url(url):
        return error_response(400, '不允许访问内网地址')

    user_id = g.current_user.id
    upload_id = uuid.uuid4().hex[:8]

    record = UserUpload(
        id=upload_id, user_id=user_id, filename=url[:200],
        ext='url', size=0, source_url=url,
    )
    db.session.add(record)
    db.session.commit()

    def _ingest():
        from app import create_app
        app = create_app()
        with app.app_context():
            from knowledge_base.parsers.ingestor import ingest_upload
            ingest_upload(upload_id)

    threading.Thread(target=_ingest, daemon=True).start()

    return standard_response({'id': upload_id, 'url': url, 'status': 'fetching'}), 201


@bp.route('/<upload_id>', methods=['DELETE'])
@login_required
@tier_required('v5')
def delete_upload(upload_id):
    upload = db.session.get(UserUpload, upload_id)
    if not upload or upload.user_id != g.current_user.id:
        return error_response(404, '文件不存在')

    # Delete file
    if upload.path and os.path.exists(upload.path):
        os.remove(upload.path)

    db.session.delete(upload)
    db.session.commit()
    return standard_response({'deleted': True})


@bp.route('/quota', methods=['GET'])
@login_required
@tier_required('v5')
def get_quota():
    user_id = g.current_user.id
    used = _get_used_storage(user_id)
    count = UserUpload.query.filter_by(user_id=user_id).count()
    return standard_response({
        'storage_used': used,
        'storage_limit': MAX_STORAGE,
        'storage_used_mb': round(used / (1024 * 1024), 1),
        'storage_limit_mb': MAX_STORAGE // (1024 * 1024),
        'file_count': count,
    })
