"""Chat API - AI 对话 (SSE 流式输出, claude_agent_sdk)

路由:
  GET  /api/v1/chat/config         - 获取 LLM 配置状态
  POST /api/v1/chat/config         - 保存 LLM 配置 (写入 DB)
  GET  /api/v1/chat/models         - 动态拉取可用模型列表
  POST /api/v1/chat/stream         - SSE 流式对话
  GET  /api/v1/chat/sessions       - 列出历史对话
  DELETE /api/v1/chat/sessions/<id> - 删除对话
"""

import json
import os
import logging
import uuid
import threading
import urllib.request

from flask import Blueprint, request, Response

from app import db
from app.utils.helpers import standard_response, error_response, bj_now
from app.utils.auth import login_required
from flask import g

logger = logging.getLogger(__name__)

bp = Blueprint('chat', __name__, url_prefix='/api/v1/chat')

# Project root: app/api/chat.py -> app/api/ -> app/ -> intel-hub/
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# LlmConfig helpers
# ============================================================

def _get_config(key: str, default: str = '') -> str:
    """Read a config value from DB, fallback to os.environ.

    兼容新旧 key: 先读 llm_* 前缀 (统一配置中心), 再读旧 key, 最后 fallback env。
    """
    try:
        from app.models.llm_config import LlmConfig
        # Try unified key first
        unified = {'api_key': 'llm_api_key', 'base_url': 'llm_base_url', 'model': 'llm_model'}
        if key in unified:
            val = LlmConfig.get(unified[key])
            if val:
                return val
        val = LlmConfig.get(key)
        if val:
            return val
    except Exception:
        pass
    # Fallback to env var
    env_map = {
        'api_key': 'ANTHROPIC_API_KEY',
        'base_url': 'ANTHROPIC_BASE_URL',
        'model': 'ANTHROPIC_MODEL',
    }
    return os.environ.get(env_map.get(key, key), default)


def get_llm_env(model_override: str = None, user=None, force_global=False):
    """获取 LLM 配置。Open-source version: always uses global config.

    Returns: (env_dict, model_name, configured_source)
    """
    api_key = _get_config('api_key')
    base_url = _get_config('base_url')
    model = model_override or _get_config('model') or None
    env = {"ANTHROPIC_API_KEY": api_key}
    if base_url:
        env["ANTHROPIC_BASE_URL"] = base_url.rstrip("/")
    return env, model, 'global'


# ============================================================
# Config endpoints
# ============================================================

@bp.route('/config', methods=['GET'])
@login_required
def get_config():
    """获取 LLM 配置状态（open-source version: global config only）"""
    api_key = _get_config('api_key')
    base_url = _get_config('base_url')
    model = _get_config('model')
    sdk_available = False
    try:
        import claude_agent_sdk
        sdk_available = True
    except ImportError:
        pass
    return standard_response({
        'configured': bool(api_key),
        'has_key': bool(api_key),
        'base_url': base_url,
        'model': model,
        'sdk_available': sdk_available,
        'source': 'global',
    })


@bp.route('/config', methods=['POST'])
@login_required
def save_config():
    """保存 LLM 配置（open-source version: global config only）"""
    data = request.get_json(silent=True) or {}

    api_key = (data.get('api_key') or '').strip()
    base_url = (data.get('base_url') or '').strip()
    from app.models.llm_config import LlmConfig
    if api_key and api_key != '••••••••':
        LlmConfig.set('api_key', api_key)
        os.environ['ANTHROPIC_API_KEY'] = api_key
    if base_url is not None:
        LlmConfig.set('base_url', base_url)
        if base_url:
            os.environ['ANTHROPIC_BASE_URL'] = base_url

    return standard_response({'message': 'Configuration saved'})


@bp.route('/models', methods=['GET'])
@login_required
def fetch_models():
    """用已配置的 key+url 动态拉取可用模型列表"""
    env, _, source = get_llm_env()
    api_key = env.get('ANTHROPIC_API_KEY', '')
    base_url = env.get('ANTHROPIC_BASE_URL', '')
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
        data = json.loads(resp.read())
        models = [
            {
                "id": m.get("id", ""),
                "display_name": m.get("display_name", m.get("id", "")),
            }
            for m in data.get("data", [])
        ]
        # Sort by id for consistent display
        models.sort(key=lambda m: m["id"])
        return standard_response(models)
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode('utf-8', errors='replace')[:500]
        except Exception:
            pass
        logger.error("Failed to fetch models: HTTP %s: %s", e.code, body)
        return error_response(502, f'拉取模型列表失败: HTTP {e.code}')
    except Exception as e:
        logger.error("Failed to fetch models: %s", e)
        return error_response(502, f'拉取模型列表失败: {str(e)[:200]}')


# ============================================================
# Sessions endpoints (DB-backed)
# ============================================================

@bp.route('/sessions', methods=['GET'])
@login_required
def list_sessions():
    """列出历史对话（open-source version: all sessions）"""
    from app.models.chat import ChatSession
    sessions = ChatSession.query.order_by(ChatSession.updated_at.desc()).all()
    return standard_response([s.to_dict() for s in sessions])


@bp.route('/sessions/<session_id>', methods=['GET'])
@login_required
def get_session(session_id):
    """获取对话详情（含消息历史）"""
    from app.models.chat import ChatSession
    sess = db.session.get(ChatSession, session_id)
    if not sess:
        return error_response(404, 'Session not found')
    return standard_response(sess.to_dict(include_messages=True))


@bp.route('/sessions/<session_id>', methods=['DELETE'])
@login_required
def delete_session(session_id):
    """删除对话"""
    from app.models.chat import ChatSession
    sess = db.session.get(ChatSession, session_id)
    if sess:
        db.session.delete(sess)
        db.session.commit()
    return standard_response({'deleted': True})


# ============================================================
# SSE streaming chat
# ============================================================

@bp.route('/stream', methods=['POST'])
@login_required
def stream_chat():
    """SSE 流式对话端点

    Body: {"message": "...", "session_id?": "...", "model?": "...", "max_turns?": 10}
    """
    data = request.get_json(silent=True) or {}
    user_message = data.get('message', '').strip()
    session_id = data.get('session_id')
    model = data.get('model', '').strip() or None
    max_turns = min(data.get('max_turns', 10), 30)

    if not user_message:
        return error_response(400, 'message is required')

    env, _, source = get_llm_env(model)
    if not env.get('ANTHROPIC_API_KEY'):
        return error_response(400, '请先配置 API Key')

    # Create new session if needed
    from app.models.chat import ChatSession, ChatMessage
    if not session_id:
        session_id = str(uuid.uuid4())

    sess = db.session.get(ChatSession, session_id)
    if not sess:
        sess = ChatSession(id=session_id, title=user_message[:50], user_id='admin')
        db.session.add(sess)
    sess.updated_at = bj_now()
    db.session.add(ChatMessage(session_id=session_id, role='user', content=user_message))
    db.session.commit()

    return Response(
        _run_sse_stream(user_message, session_id, max_turns, model, env),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
        },
    )


def _sse(data: dict) -> str:
    """Format an SSE event."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _run_sse_stream(user_message: str, session_id: str, max_turns: int, model: str = None, env: dict = None):
    """Run claude_agent_sdk in a background thread, yield SSE events via queue."""
    import queue
    from queue import Empty

    q = queue.Queue()

    def _worker():
        try:
            import anyio
            anyio.run(_sdk_loop, q, user_message, session_id, max_turns, model, env)
        except Exception as e:
            logger.error(f"Chat worker error: {e}", exc_info=True)
            q.put(('error', str(e)))
            q.put(('done', None))

    t = threading.Thread(target=_worker, daemon=True)
    t.start()

    while True:
        try:
            event_type, payload = q.get(timeout=300)
        except Empty:
            yield _sse({"type": "error", "content": "Timeout waiting for response"})
            yield _sse({"type": "done"})
            return

        if event_type == 'content':
            yield _sse({"type": "content", "content": payload})
        elif event_type == 'thinking':
            yield _sse({"type": "thinking", "content": payload})
        elif event_type == 'tool_call':
            yield _sse({"type": "tool_call", "tool_name": payload.get("name", ""), "tool_args": payload.get("input", {})})
        elif event_type == 'tool_result':
            yield _sse({"type": "tool_result", "tool_name": payload.get("name", ""), "result": payload.get("result", "")[:3000]})
        elif event_type == 'session':
            yield _sse({"type": "session", "session_id": payload})
        elif event_type == 'assistant_text':
            # Final assistant text — save to DB (runs in worker thread, needs app context)
            try:
                from app import create_app as _create_app, db as _db
                from app.models.chat import ChatMessage, ChatSession
                _app = _create_app()
                with _app.app_context():
                    _db.session.add(ChatMessage(session_id=session_id, role='assistant', content=payload))
                    sess = _db.session.get(ChatSession, session_id)
                    if sess:
                        sess.updated_at = bj_now()
                    _db.session.commit()
            except Exception as e:
                logger.error("Failed to save assistant message: %s", e)
        elif event_type == 'error':
            yield _sse({"type": "error", "content": payload})
        elif event_type == 'done':
            yield _sse({"type": "done"})
            return


async def _sdk_loop(q, user_message: str, session_id: str, max_turns: int, model_override: str = None, env: dict = None):
    """Async SDK loop — runs inside anyio.run from worker thread."""
    try:
        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
        from claude_agent_sdk.types import (
            AssistantMessage,
            ResultMessage,
            StreamEvent,
            ToolUseBlock,
            ToolResultBlock,
        )
    except ImportError as e:
        logger.error(f"claude_agent_sdk import error: {e}")
        q.put(('error', f'claude_agent_sdk 未安装，请运行: pip install claude-agent-sdk'))
        q.put(('done', None))
        return

    # Use passed env, fallback to global
    if not env or not env.get('ANTHROPIC_API_KEY'):
        env, model_override = get_llm_env(model_override)

    # Create MCP tools for intel-hub domain (platform tools only)
    mcp_server = _create_chat_mcp_server()
    mcp_servers = {}
    if mcp_server is not None:
        mcp_servers["intel-hub"] = mcp_server

    # Build system prompt
    system_prompt = (
        "你是 IntelHub 智能投资情报分析平台的 AI 助手。\n"
        "你可以通过工具访问平台的采集数据（微博热搜、36氪、央行政策、交易所等）、"
        "查看系统健康状态、搜索关键词、获取趋势数据，以及生成报告。\n\n"
        "请用中文回答用户问题，善用工具获取实时数据。\n\n"
        "重要：当引用数据或新闻时，如果数据包含 url 字段，请以 [标题](url) 格式提供来源链接，"
        "方便用户跳转查看原文。"
    )

    # Build message with conversation history
    history_text = _build_history_prompt(session_id)
    full_message = history_text + user_message if history_text else user_message

    from claude_agent_sdk.types import PermissionResultAllow, PermissionResultDeny

    _allowed_dirs = [os.path.join(PROJECT_DIR, 'data'), os.path.join(PROJECT_DIR, 'reports')]

    async def _check_tool(name, params, ctx):
        if name in ('Read', 'Glob', 'Grep'):
            path = params.get('file_path') or params.get('path') or params.get('pattern') or ''
            resolved = os.path.abspath(os.path.join(PROJECT_DIR, path))
            if any(resolved.startswith(d) for d in _allowed_dirs):
                return PermissionResultAllow()
            return PermissionResultDeny(message=f"禁止访问项目源码目录，只能读取 data/ 和 reports/ 目录")
        return PermissionResultDeny(message=f"工具 {name} 不被允许")

    options = ClaudeAgentOptions(
        cwd=PROJECT_DIR,
        allowed_tools=["Read", "Glob", "Grep"],
        system_prompt=system_prompt,
        max_turns=max_turns,
        permission_mode="dontAsk",
        can_use_tool=_check_tool,
        mcp_servers=mcp_servers if mcp_servers else None,
        model=model_override or None,
        include_partial_messages=True,
        env=env,
        **({'user': 'intelhub'} if os.getuid() == 0 else {}),
    )

    full_text_parts = []

    try:
        async with ClaudeSDKClient(options=options) as client:
            await client.query(full_message)

            async for msg in client.receive_response():
                if isinstance(msg, AssistantMessage):
                    for block in msg.content:
                        if isinstance(block, ToolUseBlock):
                            q.put(('tool_call', {"name": block.name, "input": block.input}))
                        elif isinstance(block, ToolResultBlock):
                            content_str = (
                                block.content if isinstance(block.content, str)
                                else json.dumps(block.content, ensure_ascii=False)
                            )
                            q.put(('tool_result', {"name": getattr(block, 'name', ''), "result": content_str}))

                    # Collect text from assistant message blocks
                    for block in msg.content:
                        if hasattr(block, 'text') and isinstance(getattr(block, 'text', None), str):
                            full_text_parts.append(block.text)

                    if msg.session_id:
                        q.put(('session', msg.session_id))

                elif isinstance(msg, StreamEvent):
                    event = msg.event or {}
                    event_type = event.get("type", "")
                    if event_type == "content_block_delta":
                        delta = event.get("delta", {})
                        delta_type = delta.get("type", "")
                        if delta_type == "text_delta":
                            text = delta.get("text", "")
                            if text:
                                q.put(('content', text))
                        elif delta_type == "thinking_delta":
                            thinking = delta.get("thinking", "")
                            if thinking:
                                q.put(('thinking', thinking))

                elif isinstance(msg, ResultMessage):
                    if msg.is_error and msg.errors:
                        q.put(('error', "; ".join(msg.errors)))
                    # Save accumulated text — use msg.result as fallback
                    final_text = "".join(full_text_parts) if full_text_parts else (msg.result or "")
                    if final_text:
                        q.put(('assistant_text', final_text))
                    q.put(('done', None))
                    return

            # If loop ends without ResultMessage
            if full_text_parts:
                q.put(('assistant_text', "".join(full_text_parts)))
            q.put(('done', None))

    except ImportError as e:
        logger.error(f"claude_agent_sdk import error: {e}")
        q.put(('error', f'claude_agent_sdk 未安装: {e}'))
        q.put(('done', None))
    except FileNotFoundError as e:
        logger.error(f"Claude CLI not found: {e}")
        q.put(('error', 'Claude CLI 未找到，请确认 claude-agent-sdk 安装正确'))
        q.put(('done', None))
    except Exception as e:
        logger.error(f"SDK error: {type(e).__name__}: {e}", exc_info=True)
        q.put(('error', f'执行失败: {type(e).__name__}: {str(e)[:500]}'))
        q.put(('done', None))


def _build_history_prompt(session_id: str) -> str:
    """Build conversation history as a prefix for the user message (from DB)."""
    try:
        from app.models.chat import ChatMessage
        from app import db as _db
        msgs = ChatMessage.query.filter_by(session_id=session_id)\
            .order_by(ChatMessage.id.asc()).all()
    except Exception:
        return ""

    if len(msgs) <= 1:
        return ""

    # Include previous messages as context (skip the last one — that's the current)
    lines = []
    for m in msgs[:-1]:
        if m.role == 'user':
            lines.append(f"用户: {m.content}")
        elif m.role == 'assistant':
            lines.append(f"助手: {m.content[:2000]}")
    if lines:
        return "以下是之前的对话历史:\n" + "\n".join(lines) + "\n\n请基于以上上下文继续对话。\n\n用户最新消息: "
    return ""


# ============================================================
# MCP Tools (intel-hub domain tools for chat)
# ============================================================

_TOOL_REGISTRY = {}  # populated by _create_chat_mcp_server()


def _register_tool(fn, scope):
    """Register a single tool into _TOOL_REGISTRY with scope metadata."""
    schema = getattr(fn, 'input_schema', {}) or {}
    params = {k: v.__name__ if isinstance(v, type) else str(v)
              for k, v in schema.items()} if isinstance(schema, dict) else {}
    _TOOL_REGISTRY[getattr(fn, 'name', '')] = {
        'name': getattr(fn, 'name', ''),
        'description': getattr(fn, 'description', ''),
        'params': params,
        'scope': scope,
    }


@bp.route('/mcp-tools', methods=['GET'])
@login_required
def list_mcp_tools():
    """返回当前所有已注册 MCP 工具的元数据"""
    if not _TOOL_REGISTRY:
        _create_chat_mcp_server()
    return standard_response(list(_TOOL_REGISTRY.values()))

def _create_chat_mcp_server():
    """Create MCP tool server for chat — reuses engine/report_executor helpers.

    Open-source version: platform tools only, no per-user personal tools.
    """
    try:
        from claude_agent_sdk import tool, create_sdk_mcp_server
        from analysis.engine import (
            _tool_read_latest, _tool_list_data,
            _tool_read_timeseries, _tool_search_keywords,
        )
        from app.scheduler.report_executor import _system_health, _get_data_summary

        # ── Platform tools (14) ──────────────────────────────────────────

        @tool(
            "get_latest_data",
            "获取指定模块的最新采集数据。参数: module(必填,如hot_topics/policy/exchange/financial), subdir(可选,平台名), count(可选,返回条数默认50)。",
            {"module": str, "subdir": str, "count": int},
        )
        async def chat_get_latest(args):
            result = _tool_read_latest(args)
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "list_data_sources",
            "列出指定模块下所有可用的数据子目录和最新文件。参数: module(必填,数据模块名)。",
            {"module": str},
        )
        async def chat_list_data(args):
            result = _tool_list_data(args)
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "search_keywords",
            "在采集数据中搜索关键词。参数: keywords(必填,关键词数组), module(可选,限定模块)。",
            {"keywords": list, "module": str},
        )
        async def chat_search_keywords(args):
            result = _tool_search_keywords(args)
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "get_health_status",
            "系统健康状态检查，返回各数据源状态和告警信息。无参数。",
            {},
        )
        async def chat_health(args):
            result = _system_health()
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "get_report_summary",
            "获取最新报告摘要。无参数。",
            {},
        )
        async def chat_report_summary(args):
            reports_dir = os.path.join(PROJECT_DIR, 'reports')
            summaries = []
            for subdir in ['agent', 'insight', 'heartbeat']:
                d = os.path.join(reports_dir, subdir)
                if not os.path.isdir(d):
                    continue
                files = sorted(
                    [f for f in os.listdir(d) if f.endswith('.md')],
                    key=lambda f: os.path.getmtime(os.path.join(d, f)),
                    reverse=True,
                )[:1]
                for fname in files:
                    fpath = os.path.join(d, fname)
                    try:
                        with open(fpath, 'r', encoding='utf-8') as f:
                            content = f.read(2000)
                        summaries.append(f"[{subdir}/{fname}]\n{content}")
                    except Exception:
                        pass
            result = "\n\n".join(summaries) if summaries else "暂无报告"
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "get_trend_data",
            "获取指定数据的时间序列趋势。参数: module(必填), subdir(必填,平台名), hours(可选,回溯小时数默认24)。",
            {"module": str, "subdir": str, "hours": int},
        )
        async def chat_trend_data(args):
            result = _tool_read_timeseries(args)
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "search_knowledge",
            "搜索知识库，返回话题、行业、实体等结构化信息。参数: query(必填,搜索关键词), top_k(可选,返回条数默认10)。",
            {"query": str, "top_k": int},
        )
        async def chat_search_kb(args):
            try:
                from knowledge_base.kb_manager import KnowledgeBaseManager
                kb = KnowledgeBaseManager()
                results = kb.search(args.get("query", ""), args.get("top_k", 10))
                return {"content": [{"type": "text", "text": json.dumps(results, ensure_ascii=False, indent=2)}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"知识库搜索失败: {e}"}]}

        @tool(
            "get_industry_info",
            "获取行业分类信息，包含各行业的条目和数据。参数: industry(可选,指定行业名，不传则返回全部行业)。",
            {"industry": str},
        )
        async def chat_industry(args):
            try:
                from knowledge_base.kb_manager import KnowledgeBaseManager
                kb = KnowledgeBaseManager()
                industry = args.get("industry")
                result = kb.get_industry(industry)
                return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"获取行业信息失败: {e}"}]}

        @tool(
            "get_entity_graph",
            "获取实体关系图谱或查询特定实体的关联关系。参数: entity(可选,查关联实体，不传则返回完整图谱)。",
            {"entity": str},
        )
        async def chat_entity(args):
            try:
                from knowledge_base.kb_manager import KnowledgeBaseManager
                kb = KnowledgeBaseManager()
                entity = args.get("entity")
                if entity:
                    result = kb.get_related(entity)
                else:
                    result = kb.get_graph()
                return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"获取实体图谱失败: {e}"}]}

        @tool(
            "get_hot_topics",
            "获取热点话题数据摘要。参数: subdir(可选,筛选平台如weibo/zhihu/bilibili), max_items(可选,返回条数默认20)。",
            {"subdir": str, "max_items": int},
        )
        async def chat_hot_topics(args):
            result = _get_data_summary("hot_topics", args.get("max_items", 20), subdir=args.get("subdir"))
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "get_policy_updates",
            "获取政策法规动态摘要。参数: subdir(可选,筛选部门如pbc/csrc/ndrc/gov/safe), max_items(可选,返回条数默认20)。",
            {"subdir": str, "max_items": int},
        )
        async def chat_policy_updates(args):
            result = _get_data_summary("policy", args.get("max_items", 20), subdir=args.get("subdir"))
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "get_exchange_data",
            "获取交易所公告数据摘要。参数: subdir(可选,筛选交易所如sse/szse/hkex/bse), max_items(可选,返回条数默认20)。",
            {"subdir": str, "max_items": int},
        )
        async def chat_exchange_data(args):
            result = _get_data_summary("exchange", args.get("max_items", 20), subdir=args.get("subdir"))
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "get_financial_news",
            "获取财经资讯数据摘要。参数: subdir(可选,筛选来源如36kr/eastmoney/sina), max_items(可选,返回条数默认20)。",
            {"subdir": str, "max_items": int},
        )
        async def chat_financial_news(args):
            result = _get_data_summary("financial", args.get("max_items", 20), subdir=args.get("subdir"))
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "get_rss_feed",
            "获取 RSS 订阅内容摘要。参数: source_ids(可选,指定RSS源ID列表), subdir(可选,筛选RSS源slug), max_items(可选,返回条数默认20)。",
            {"source_ids": list, "subdir": str, "max_items": int},
        )
        async def chat_rss_feed(args):
            source_ids = args.get("source_ids")
            if source_ids:
                from app.scheduler.report_executor import _get_rss_summary_by_ids
                result = _get_rss_summary_by_ids(source_ids, args.get("max_items", 20), user_id=None)
            else:
                result = _get_data_summary("rss", args.get("max_items", 20), subdir=args.get("subdir"))
            return {"content": [{"type": "text", "text": result}]}

        # ── Tool registry & MCP server ───────────────────────────────────

        _platform_tools = [
            chat_get_latest, chat_list_data, chat_search_keywords,
            chat_health, chat_report_summary, chat_trend_data,
            chat_search_kb, chat_industry, chat_entity,
            chat_hot_topics, chat_policy_updates, chat_exchange_data,
            chat_financial_news, chat_rss_feed,
        ]

        # Populate registry (once, for /mcp-tools API)
        if not _TOOL_REGISTRY:
            for fn in _platform_tools:
                _register_tool(fn, 'platform')

        return create_sdk_mcp_server("intel-hub-chat-tools", tools=list(_platform_tools))
    except ImportError:
        logger.warning("claude_agent_sdk not available for chat MCP tools")
        return None
    except Exception as e:
        logger.error(f"Failed to create chat MCP server: {e}")
        return None
