"""Knowledge Base API — 知识库查询与管理

路由:
  GET  /api/v1/kb/stats            — 概览统计
  GET  /api/v1/kb/topics           — 话题索引 (top20)
  GET  /api/v1/kb/industry         — 行业分类
  GET  /api/v1/kb/industry/<name>  — 单个行业详情
  GET  /api/v1/kb/graph            — 实体关系图谱
  GET  /api/v1/kb/search?q=xxx     — 全文搜索
  POST /api/v1/kb/build            — 触发构建
"""

import logging

from flask import Blueprint, request

from app.utils.helpers import standard_response, error_response

logger = logging.getLogger(__name__)

bp = Blueprint('knowledge', __name__, url_prefix='/api/v1/kb')


def _get_kb():
    from knowledge_base.kb_manager import KnowledgeBaseManager
    return KnowledgeBaseManager()


@bp.route('/stats', methods=['GET'])
def kb_stats():
    """概览统计 — 各模块状态、实体数、最后更新时间"""
    try:
        kb = _get_kb()
        return standard_response(kb.stats())
    except Exception as e:
        logger.error("KB stats error: %s", e)
        return error_response(500, str(e))


@bp.route('/topics', methods=['GET'])
def kb_topics():
    """话题索引 — top20 热点 + 实体"""
    try:
        kb = _get_kb()
        return standard_response(kb.get_topic())
    except Exception as e:
        logger.error("KB topics error: %s", e)
        return error_response(500, str(e))


@bp.route('/industry', methods=['GET'])
def kb_industry():
    """行业分类 — 各行业及其条目"""
    try:
        kb = _get_kb()
        return standard_response(kb.get_industry())
    except Exception as e:
        logger.error("KB industry error: %s", e)
        return error_response(500, str(e))


@bp.route('/industry/<name>', methods=['GET'])
def kb_industry_detail(name):
    """单个行业详情"""
    try:
        kb = _get_kb()
        return standard_response(kb.get_industry(name))
    except Exception as e:
        logger.error("KB industry detail error: %s", e)
        return error_response(500, str(e))


@bp.route('/graph', methods=['GET'])
def kb_graph():
    """实体关系图谱 — nodes + edges"""
    try:
        kb = _get_kb()
        return standard_response(kb.get_graph())
    except Exception as e:
        logger.error("KB graph error: %s", e)
        return error_response(500, str(e))


@bp.route('/search', methods=['GET'])
def kb_search():
    """全文搜索 — 跨话题 + 行业"""
    q = request.args.get('q', '').strip()
    top_k = request.args.get('top_k', 10, type=int)
    if not q:
        return error_response(400, 'q parameter is required')
    try:
        kb = _get_kb()
        return standard_response(kb.search(q, top_k))
    except Exception as e:
        logger.error("KB search error: %s", e)
        return error_response(500, str(e))


@bp.route('/build', methods=['POST'])
def kb_build():
    """触发知识库构建"""
    data = request.get_json(silent=True) or {}
    module = data.get('module', 'all')
    try:
        import threading
        from knowledge_base.kb_manager import KnowledgeBaseManager

        def _run_build():
            kb = KnowledgeBaseManager()
            result = kb.ingest(module)
            logger.info("KB build completed: %s", result.get('status'))

        t = threading.Thread(target=_run_build, daemon=True)
        t.start()

        return standard_response({
            'message': f'KB build triggered for module: {module}',
            'module': module,
        })
    except Exception as e:
        logger.error("KB build error: %s", e)
        return error_response(500, str(e))
