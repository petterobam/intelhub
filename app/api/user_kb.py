"""User Knowledge Base API — 用户私有知识库

路由:
  GET  /api/v1/user-kb/stats         — KB 概览
  GET  /api/v1/user-kb/search?q=     — 搜索
  GET  /api/v1/user-kb/topics         — 话题索引
  GET  /api/v1/user-kb/timeline/<entity> — 实体时间线
  POST /api/v1/user-kb/build          — 手动触发 KB 重建
  GET  /api/v1/user-kb/export         — 导出 Markdown zip
"""

import io
import json
import logging
import os
import zipfile
from datetime import datetime

from flask import Blueprint, request, g, send_file

from app.utils.auth import login_required, tier_required
from app.utils.user_dirs import user_kb_dir
from app.utils.helpers import standard_response, error_response

logger = logging.getLogger(__name__)

bp = Blueprint('user_kb', __name__, url_prefix='/api/v1/user-kb')


def _kb_dir():
    return user_kb_dir(g.current_user.id)


@bp.route('/stats', methods=['GET'])
@login_required
@tier_required('v4')
def kb_stats():
    kb_dir = _kb_dir()
    index_path = os.path.join(kb_dir, 'index.json')
    if not os.path.exists(index_path):
        return standard_response({
            'built': False,
            'entity_count': 0,
            'report_count': 0,
            'topic_count': 0,
        })
    with open(index_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data['built'] = True
    return standard_response(data)


@bp.route('/search', methods=['GET'])
@login_required
@tier_required('v4')
def kb_search():
    query = (request.args.get('q') or '').strip().lower()
    if not query:
        return error_response(400, '搜索关键词不能为空')

    kb_dir = _kb_dir()
    results = []

    # Search in entities
    entities_path = os.path.join(kb_dir, 'entities.json')
    if os.path.exists(entities_path):
        with open(entities_path, 'r', encoding='utf-8') as f:
            entities = json.load(f)
        for e in entities:
            if query in e.get('name', '').lower():
                results.append({'type': 'entity', 'name': e['name'], 'count': e.get('item_count', 0)})

    # Search in timeline files
    timeline_dir = os.path.join(kb_dir, 'timeline')
    if os.path.isdir(timeline_dir):
        for f in os.listdir(timeline_dir):
            if not f.endswith('.json'):
                continue
            try:
                with open(os.path.join(timeline_dir, f), 'r', encoding='utf-8') as fp:
                    items = json.load(fp)
                for item in items[:50]:
                    text = (item.get('title', '') + ' ' + item.get('content', '')).lower()
                    if query in text:
                        results.append({
                            'type': 'item',
                            'title': item.get('title', '')[:100],
                            'date': item.get('timestamp', '')[:10],
                            'source': item.get('source', ''),
                        })
            except Exception:
                continue

    return standard_response(results[:30])


@bp.route('/topics', methods=['GET'])
@login_required
@tier_required('v4')
def kb_topics():
    kb_dir = _kb_dir()
    path = os.path.join(kb_dir, 'topics', 'topic_index.json')
    if not os.path.exists(path):
        return standard_response({})
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return standard_response(data)


@bp.route('/timeline/<entity>', methods=['GET'])
@login_required
@tier_required('v4')
def kb_timeline(entity):
    kb_dir = _kb_dir()
    safe = entity.replace('/', '_').replace('\\', '_')
    path = os.path.join(kb_dir, 'timeline', f'{safe}.json')
    if not os.path.exists(path):
        return standard_response({'entity': entity, 'items': []})
    with open(path, 'r', encoding='utf-8') as f:
        items = json.load(f)
    return standard_response({'entity': entity, 'items': items[:30]})


@bp.route('/build', methods=['POST'])
@login_required
@tier_required('v4')
def kb_build():
    try:
        from knowledge_base.user_kb_builder import UserKBBuilder
        import threading

        user_id = g.current_user.id

        def _build():
            from app import create_app
            app = create_app()
            with app.app_context():
                UserKBBuilder().build(user_id)

        threading.Thread(target=_build, daemon=True).start()
        return standard_response({'message': 'KB 构建已启动'})
    except Exception as e:
        return error_response(500, f'构建失败: {str(e)[:200]}')


@bp.route('/export', methods=['GET'])
@login_required
@tier_required('v4')
def kb_export():
    kb_dir = _kb_dir()
    if not os.path.isdir(kb_dir):
        return error_response(404, '知识库尚未构建')

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Export timeline as markdown
        timeline_dir = os.path.join(kb_dir, 'timeline')
        if os.path.isdir(timeline_dir):
            for f in os.listdir(timeline_dir):
                if not f.endswith('.json'):
                    continue
                entity_name = f.replace('.json', '')
                try:
                    with open(os.path.join(timeline_dir, f), 'r', encoding='utf-8') as fp:
                        items = json.load(fp)
                    md_lines = [f'# {entity_name} 时间线\n']
                    for item in items:
                        date = item.get('timestamp', '')[:10]
                        title = item.get('title', '')
                        content = item.get('content', '')
                        md_lines.append(f'## {date} — {title}\n')
                        if content:
                            md_lines.append(f'{content}\n')
                    zf.writestr(f'{entity_name}.md', '\n'.join(md_lines))
                except Exception:
                    continue

        # Export index
        index_path = os.path.join(kb_dir, 'index.json')
        if os.path.exists(index_path):
            zf.write(index_path, 'index.json')

    buf.seek(0)
    return send_file(buf, mimetype='application/zip',
                     as_attachment=True, download_name=f'kb-{g.current_user.id}-{bj_now().strftime("%Y%m%d")}.zip')
