"""ReportExecutor - 报告生成器（Claude Agent SDK Harness 模式）

Harness 模式说明:
  - 使用 claude_agent_sdk 进行多轮分析
  - 自定义 MCP 工具: aggregate_data, compare_history, health_check, write_report, search_trends
  - Agent 自主选择调用工具，逐步构建完整报告
  - 当 Agent 决定报告完成时自动结束
  - 回退: OpenAI 兼容 API 或模板渲染
"""

import json, os, logging
from datetime import datetime
from app.utils.helpers import bj_now
from typing import Optional

logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
REPORTS_DIR = os.path.join(BASE_DIR, "reports", "agent")

# 记录 agent 在执行过程中是否已通过 write_report 工具写入过报告
_agent_written_report = None
_current_user_id = None  # 当前 generate_report 调用的 user_id

# 检测 claude_agent_sdk 是否可用
try:
    import claude_agent_sdk
    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False
    logger.warning("claude_agent_sdk not available, report generation will use template fallback")

# 检测 anthropic SDK (OpenAI fallback)
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


def _get_rss_summary_by_ids(source_ids: list, max_items: int = 50, user_id: str = None) -> str:
    """根据 RSS 源 ID 列表读取对应的采集数据"""
    if not source_ids:
        return _get_data_summary("rss", max_items)

    try:
        from app.models.rss_source import RssSource
        sources = RssSource.query.filter(RssSource.id.in_(source_ids), RssSource.enabled == True).all()
    except Exception:
        return _get_data_summary("rss", max_items)

    if not sources:
        return "[rss] 未找到启用的数据源"

    rss_dir = os.path.join(BASE_DIR, "data", "raw", "rss")
    items = []
    found = 0

    for src in sources:
        slug = src.slug or str(src.id)
        src_dir = os.path.join(rss_dir, slug)
        if not os.path.isdir(src_dir):
            continue
        json_files = sorted(
            [f for f in os.listdir(src_dir) if f.endswith(".json")],
            key=lambda f: os.path.getmtime(os.path.join(src_dir, f)),
            reverse=True,
        )
        if not json_files:
            continue
        found += 1
        try:
            with open(os.path.join(src_dir, json_files[0]), "r", encoding="utf-8") as f:
                data = json.load(f)
            batch = data.get("items", []) if isinstance(data, dict) else data if isinstance(data, list) else []
            items.extend(batch[:max(1, max_items // max(len(sources), 1))])
        except Exception:
            pass

    if not items:
        return f"[rss] {len(sources)} 个源，暂无采集数据"

    # Include personal RSS data if user_id provided
    if user_id:
        try:
            from app.utils.user_dirs import user_rss_dir
            user_rss_base = os.path.join(BASE_DIR, "data", "users", user_id, "rss")
            if os.path.isdir(user_rss_base):
                for slug_dir in os.listdir(user_rss_base):
                    slug_path = os.path.join(user_rss_base, slug_dir)
                    if not os.path.isdir(slug_path):
                        continue
                    jsons = sorted(
                        [f for f in os.listdir(slug_path) if f.endswith(".json")],
                        key=lambda f: os.path.getmtime(os.path.join(slug_path, f)),
                        reverse=True,
                    )
                    if jsons:
                        try:
                            with open(os.path.join(slug_path, jsons[0]), "r", encoding="utf-8") as f:
                                data = json.load(f)
                            batch = data.get("items", []) if isinstance(data, dict) else data if isinstance(data, list) else []
                            items.extend(batch[:10])
                            found += 1
                        except Exception:
                            pass
        except Exception:
            pass

    keys = list(items[0].keys())[:8] if isinstance(items[0], dict) else []
    lines = [f"[rss] 共 {len(items)} 条最新数据 (来自 {found}/{len(sources)} 个源)，字段: {keys}"]
    for item in items[:10]:
        title = item.get("title") or item.get("keyword") or item.get("name", str(item)[:50])
        url = item.get("url", item.get("link", ""))
        if url:
            lines.append(f"  - [{title}]({url})")
        else:
            lines.append(f"  - {title}")
    return "\n".join(lines)


def _get_data_summary(source: str, max_items: int = 50, subdir: str = None) -> str:
    """获取指定数据源的摘要，支持子目录遍历和过滤"""
    data_dir = os.path.join(BASE_DIR, "data", "raw", source)
    if not os.path.isdir(data_dir):
        return f"[{source}] 数据目录不存在"

    items = []
    subdirs_found = []

    entries = sorted(os.listdir(data_dir))
    all_subdirs = [e for e in entries if os.path.isdir(os.path.join(data_dir, e))]

    # Filter by subdir if specified
    if subdir:
        matched = [sd for sd in all_subdirs if subdir.lower() in sd.lower()]
        if not matched:
            available = ", ".join(all_subdirs) if all_subdirs else "无"
            return f"[{source}] 未找到匹配 '{subdir}' 的子目录。可用: {available}"
        subdirs = matched
    else:
        subdirs = all_subdirs

    if subdirs:
        for sd in subdirs:
            sd_path = os.path.join(data_dir, sd)
            json_files = sorted(
                [f for f in os.listdir(sd_path) if f.endswith(".json")],
                key=lambda f: os.path.getmtime(os.path.join(sd_path, f)),
                reverse=True,
            )
            if not json_files:
                continue
            subdirs_found.append(sd)
            latest = os.path.join(sd_path, json_files[0])
            try:
                with open(latest, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    items.extend(data[:max_items // max(len(subdirs), 1)])
                elif isinstance(data, dict) and "items" in data:
                    items.extend(data["items"][:max_items // max(len(subdirs), 1)])
                elif isinstance(data, dict) and "data" in data:
                    d = data["data"]
                    if isinstance(d, list):
                        items.extend(d[:max_items // max(len(subdirs), 1)])
            except Exception:
                pass
    else:
        files = sorted(
            [f for f in entries if f.endswith(".json")],
            key=lambda f: os.path.getmtime(os.path.join(data_dir, f)),
            reverse=True,
        )[:5]
        for fname in files:
            try:
                with open(os.path.join(data_dir, fname), "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    items.extend(data[:max_items // 5])
                elif isinstance(data, dict) and "data" in data:
                    d = data["data"]
                    if isinstance(d, list):
                        items.extend(d[:max_items // 5])
            except Exception:
                pass

    if not items:
        return f"[{source}] 暂无数据"

    if isinstance(items[0], dict):
        keys = list(items[0].keys())[:8]
        summary_lines = [f"[{source}] 共 {len(items)} 条最新数据 (来自 {len(subdirs_found)} 个数据源)，字段: {keys}"]
        for item in items[:10]:
            title = item.get("title") or item.get("keyword") or item.get("name", str(item)[:50])
            url = item.get("url", item.get("link", ""))
            if url:
                summary_lines.append(f"  - [{title}]({url})")
            else:
                summary_lines.append(f"  - {title}")
        return "\n".join(summary_lines)
    return f"[{source}] {len(items)} 条数据"


def _load_latest_report(days: int = 7) -> str:
    """加载历史报告用于趋势对比"""
    report_file = os.path.join(BASE_DIR, "reports", "insight", "insight-report-latest.json")
    if not os.path.exists(report_file):
        return "[历史报告] 暂无历史数据"
    try:
        with open(report_file, "r", encoding="utf-8") as f:
            report = json.load(f)
        gen_time = report.get("generated_at", "未知时间")
        resonance = report.get("resonance", {})
        health = report.get("health", {})
        hotspots = resonance.get("all_hotspots", [])[:5]
        hotspot_str = "\n".join([
            f"  - {h.get('keyword','?')} (平台:{','.join(h.get('platforms',[]))}, 分数:{h.get('resonance_score',0)})"
            for h in hotspots
        ]) or "  无"
        return (
            f"[历史报告] 生成时间: {gen_time}\n"
            f"[共振 Top-5]\n{hotspot_str}\n"
            f"[健康] {health.get('status','unknown')}, "
            f"过期:{health.get('stale_count',0)}, 异常:{health.get('critical_count',0)}"
        )
    except Exception as e:
        return f"[历史报告] 读取失败: {e}"


def _system_health() -> str:
    """系统健康检查"""
    try:
        from analysis.heartbeat.heartbeat_analyzer import generate_heartbeat
        hb = generate_heartbeat()
        alerts = hb.get("alerts", [])
        alert_str = "\n".join([f"  WARN {a}" for a in alerts]) if alerts else "  无"
        return (
            f"[健康] 评分:{hb.get('health_score',0)}/100 "
            f"正常:{hb.get('fresh_count',0)} "
            f"过期:{hb.get('stale_count',0)} "
            f"异常:{hb.get('critical_count',0)}\n"
            f"[告警]\n{alert_str}"
        )
    except Exception as e:
        return f"[健康检查] 失败: {e}"


def _do_write_report(content: str, filename: str = "", title: str = "") -> str:
    global _agent_written_report
    # Use user-specific dir if generating for a user
    if _current_user_id:
        from app.utils.user_dirs import user_reports_dir
        out_dir = user_reports_dir(_current_user_id)
    else:
        out_dir = REPORTS_DIR
    os.makedirs(out_dir, exist_ok=True)
    if not filename:
        filename = f"agent-report-{bj_now().strftime('%Y%m%d-%H%M%S')}.md"
    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    _agent_written_report = {"path": path, "filename": filename, "title": title}
    # Write per-report JSON
    ts = bj_now().strftime('%Y-%m-%dT%H-%M-%S')
    report_json = {
        "generated_at": bj_now().isoformat(),
        "source": "agent-report",
        "filename": filename,
        "health": {"status": "healthy"},
        "trends": [],
        "resonance": {"total": 0, "all_hotspots": []},
        "total_items": len(content.split("\n")),
    }
    json_ts_path = os.path.join(out_dir, f"report-{ts}.json")
    with open(json_ts_path, "w", encoding="utf-8") as f:
        json.dump(report_json, f, ensure_ascii=False, indent=2)
    # Also update latest
    json_path = os.path.join(out_dir, "insight-report-latest.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_json, f, ensure_ascii=False, indent=2)
    return f"报告已写入: {path}"


def _search_trends(keyword: str, days: int = 7) -> str:
    results = []
    for src in ["hot_topics", "policy", "exchange", "financial", "rss"]:
        data_dir = os.path.join(BASE_DIR, "data", "raw", src)
        if not os.path.isdir(data_dir):
            continue
        for item in sorted(os.listdir(data_dir)):
            item_path = os.path.join(data_dir, item)
            if os.path.isdir(item_path):
                for fname in sorted(os.listdir(item_path), reverse=True)[:3]:
                    if not fname.endswith('.json'):
                        continue
                    try:
                        with open(os.path.join(item_path, fname), "r", encoding="utf-8") as f:
                            data = json.load(f)
                        items = data if isinstance(data, list) else data.get("data", data.get("items", []))
                        for it in items:
                            text = json.dumps(it, ensure_ascii=False)
                            if keyword in text:
                                title = it.get("title") or it.get("keyword") or ""
                                results.append(f"  [{src}/{item}] {title}")
                    except Exception:
                        pass
    if not results:
        return f"未找到包含 '{keyword}' 的数据"
    return f"找到 {len(results)} 条结果（近{days}天）：\n" + "\n".join(results[:20])


def _query_kb_fallback(query: str) -> str:
    """Knowledge base query fallback for Anthropic SDK harness"""
    try:
        from knowledge_base.kb_manager import KnowledgeBaseManager
        kb = KnowledgeBaseManager()
        results = kb.search(query, 10)
        return json.dumps(results, ensure_ascii=False, indent=2)
    except Exception as e:
        return f"知识库查询失败: {e}"


# ── Claude Agent SDK MCP 工具 ────────────────────────────────────────────────

def _create_report_mcp_server():
    """为报告生成创建 MCP 工具"""
    try:
        from claude_agent_sdk import tool, create_sdk_mcp_server

        @tool(
            "aggregate_data",
            "聚合指定数据源的原始数据。参数: sources(必填,数据源数组如['hot_topics','policy','rss']), max_items(可选,每个源最多条数,默认50), subdir(可选,筛选子目录如weibo/pbc/sse), rss_source_ids(可选,RSS 源 ID 列表,细化选择), user_source_ids(可选,用户数据源 ID 列表)。",
            {"sources": list, "max_items": int, "subdir": str, "rss_source_ids": list, "user_source_ids": list},
        )
        async def sdk_aggregate(args):
            rss_ids = args.get("rss_source_ids")
            subdir = args.get("subdir")
            parts = []
            for s in args.get("sources", []):
                if s == "rss" and rss_ids:
                    parts.append(_get_rss_summary_by_ids(rss_ids, args.get("max_items", 50), user_id=_current_user_id))
                else:
                    parts.append(_get_data_summary(s, args.get("max_items", 50), subdir=subdir))
            # Append user source data if requested
            user_src_ids = args.get("user_source_ids")
            if user_src_ids and _current_user_id:
                for sid in user_src_ids:
                    src_dir = os.path.join(BASE_DIR, "data", "users", _current_user_id, "sources", str(sid))
                    if os.path.isdir(src_dir):
                        json_files = sorted(
                            [f for f in os.listdir(src_dir) if f.endswith(".json")],
                            key=lambda f: os.path.getmtime(os.path.join(src_dir, f)),
                            reverse=True,
                        )
                        if json_files:
                            try:
                                with open(os.path.join(src_dir, json_files[0]), "r", encoding="utf-8") as f:
                                    data = json.load(f)
                                items = data.get("items", []) if isinstance(data, dict) else data if isinstance(data, list) else []
                                if items:
                                    parts.append(f"[user_source:{sid}] {len(items)} 条数据\n" + json.dumps(items[:20], ensure_ascii=False)[:3000])
                            except Exception:
                                pass
            return {"content": [{"type": "text", "text": "\n\n".join(parts)}]}

        @tool(
            "compare_history",
            "对比历史报告获取趋势参考。参数: days(可选,对比天数,默认7)。",
            {"days": int},
        )
        async def sdk_compare(args):
            result = _load_latest_report(args.get("days", 7))
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "health_check",
            "系统健康检查,返回各数据源状态和告警信息。无参数。",
            {},
        )
        async def sdk_health(args):
            result = _system_health()
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "write_report",
            "将最终报告写入文件(分析完成后调用)。参数: content(必填,Markdown报告内容), filename(可选,文件名)。",
            {"content": str, "filename": str},
        )
        async def sdk_write(args):
            result = _do_write_report(args.get("content", ""), args.get("filename", ""))
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "search_trends",
            "搜索关键词在采集数据中的出现趋势。参数: keyword(必填,关键词), days(可选,搜索天数,默认7)。",
            {"keyword": str, "days": int},
        )
        async def sdk_search(args):
            result = _search_trends(args.get("keyword", ""), args.get("days", 7))
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "query_knowledge_base",
            "查询知识库获取话题趋势、行业分析或实体关系。参数: query(必填,查询关键词)。",
            {"query": str},
        )
        async def sdk_query_kb(args):
            try:
                from knowledge_base.kb_manager import KnowledgeBaseManager
                kb = KnowledgeBaseManager()
                results = kb.search(args.get("query", ""), 10)
                return {"content": [{"type": "text", "text": json.dumps(results, ensure_ascii=False, indent=2)}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"知识库查询失败: {e}"}]}

        @tool(
            "get_task_runs",
            "查询任务执行记录。参数: task_id(可选,指定任务ID), status(可选,按状态筛选done/failed/timeout), limit(可选,返回条数默认10)。",
            {"task_id": str, "status": str, "limit": int},
        )
        async def sdk_task_runs(args):
            try:
                from app import create_app as _ca
                from app.models.task_run import TaskRun
                _app = _ca()
                with _app.app_context():
                    q = TaskRun.query
                    tid = args.get("task_id")
                    if tid:
                        q = q.filter_by(task_id=tid)
                    status = args.get("status")
                    if status:
                        q = q.filter_by(status=status)
                    if _current_user_id:
                        q = q.filter_by(user_id=_current_user_id)
                    runs = q.order_by(TaskRun.started_at.desc()).limit(args.get("limit", 10)).all()
                    items = [{
                        'id': r.id, 'task_id': r.task_id, 'status': r.status,
                        'started_at': r.started_at.isoformat() if r.started_at else None,
                        'finished_at': r.finished_at.isoformat() if r.finished_at else None,
                        'duration_ms': r.duration_ms, 'exit_code': r.exit_code,
                        'trigger_type': r.trigger_type,
                        'stderr': (r.stderr or '')[:200] if r.status == 'failed' else None,
                    } for r in runs]
                return {"content": [{"type": "text", "text": json.dumps(items, ensure_ascii=False, indent=2)}]}
            except Exception as e:
                return {"content": [{"type": "text", "text": f"查询执行记录失败: {e}"}]}

        return create_sdk_mcp_server("report-tools", tools=[
            sdk_aggregate,
            sdk_compare,
            sdk_health,
            sdk_write,
            sdk_search,
            sdk_query_kb,
            sdk_task_runs,
        ])
    except ImportError:
        return None
    except Exception as e:
        logger.error("Failed to create report MCP server: %s", e)
        return None


# ── Anthropic Harness 工具定义 (fallback) ────────────────────────────────────

TOOLS = [
    {
        "name": "aggregate_data",
        "description": "聚合指定数据源的原始数据",
        "input_schema": {
            "type": "object",
            "properties": {
                "sources": {"type": "array", "items": {"type": "string"},
                    "description": "数据源: hot_topics, policy, exchange, financial, rss"},
                "max_items": {"type": "integer", "description": "每个源最多条数", "default": 50},
                "rss_source_ids": {"type": "array", "items": {"type": "integer"},
                    "description": "RSS 源 ID 列表,细化选择特定 RSS 数据源"}
            },
            "required": ["sources"]
        }
    },
    {
        "name": "compare_history",
        "description": "对比历史报告（趋势参考）",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {"type": "integer", "description": "对比天数", "default": 7}
            }
        }
    },
    {
        "name": "health_check",
        "description": "系统健康检查",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "write_report",
        "description": "将最终报告写入文件（最后调用）",
        "input_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "完整报告 Markdown 内容"},
                "filename": {"type": "string", "description": "文件名（可选）"},
                "title": {"type": "string", "description": "报告标题：简洁有力、有吸引力的中文标题，15字以内，不要含日期、emoji、标点符号"}
            },
            "required": ["content"]
        }
    },
    {
        "name": "search_trends",
        "description": "搜索关键词趋势",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
                "days": {"type": "integer", "default": 7}
            },
            "required": ["keyword"]
        }
    },
    {
        "name": "query_knowledge_base",
        "description": "查询知识库获取话题趋势、行业分析或实体关系",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "查询关键词"}
            },
            "required": ["query"]
        }
    },
]

def _aggregate_handler(args):
    rss_ids = args.get("rss_source_ids")
    parts = []
    for s in args.get("sources", []):
        if s == "rss" and rss_ids:
            parts.append(_get_rss_summary_by_ids(rss_ids, args.get("max_items", 50)))
        else:
            parts.append(_get_data_summary(s, args.get("max_items", 50)))
    return "\n\n".join(parts)

TOOL_MAP = {
    "aggregate_data": _aggregate_handler,
    "compare_history": lambda a: _load_latest_report(a.get("days", 7)),
    "health_check": lambda a: _system_health(),
    "write_report": lambda a: _do_write_report(a.get("content", ""), a.get("filename", ""), a.get("title", "")),
    "search_trends": lambda a: _search_trends(a.get("keyword", ""), a.get("days", 7)),
    "query_knowledge_base": lambda a: _query_kb_fallback(a.get("query", "")),
}


def _run_harness_sdk(prompt: str, max_turns: int = 15, model: str = None) -> str:
    """使用 Claude Agent SDK 运行报告生成"""
    if not CLAUDE_SDK_AVAILABLE:
        return "[ERROR] claude_agent_sdk not available"

    # 从 DB 读配置，fallback 到 env var
    from analysis.engine import _get_llm_config_from_db
    api_key = _get_llm_config_from_db('api_key') or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("LLM_API_KEY")
    if not api_key:
        return "[ERROR] No ANTHROPIC_API_KEY or LLM_API_KEY"

    from analysis.engine import _load_env
    _load_env()

    try:
        import anyio
        from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

        mcp_server = _create_report_mcp_server()
        mcp_servers = {}
        if mcp_server is not None:
            mcp_servers["report-tools"] = mcp_server

        system_msg = (
            "你是专业的投资研究报告生成助手。通过调用工具获取数据，逐步构建完整报告，"
            "最后必须调用 write_report 工具写入。\n\n"
            "重要：当你认为报告已完整时，务必调用 write_report 工具结束。\n\n"
            "报告规范：\n"
            "- 每个观点和数据点必须标注来源（平台/数据源名称）\n"
            "- 如果数据包含 url 字段，在报告中以 [来源](url) 格式提供可点击的引用链接\n"
            "- 对于热点新闻和重要数据，优先提供原始链接以便读者追溯\n\n"
            "标题规范：\n"
            "- 调用 write_report 时必须提供 title 参数\n"
            "- 标题要简洁有力、有吸引力，能概括报告核心观点\n"
            "- 15字以内，纯中文，不要含日期、emoji、标点符号\n"
            "- 示例：「科技巨头AI军备赛升级」「楼市回暖信号频现」「消费新趋势洞察」"
        )

        # 构建 env — 从 DB 读配置，fallback 到 env var
        base_url = _get_llm_config_from_db('base_url') or os.environ.get("ANTHROPIC_BASE_URL", "") or os.environ.get("LLM_BASE_URL", "")
        env = {"ANTHROPIC_API_KEY": api_key}
        if base_url:
            env["ANTHROPIC_BASE_URL"] = base_url.rstrip("/")

        # 从 DB 读 model（通过代理支持非 claude-* 模型名）
        effective_model = model or _get_llm_config_from_db('model') or os.environ.get("ANTHROPIC_MODEL", "") or None

        result_text = []
        tool_log = []  # Capture tool call trace for stdout

        async def _run():
            from claude_agent_sdk.types import AssistantMessage, ToolUseBlock, ToolResultBlock
            async for message in query(
                prompt=prompt,
                options=ClaudeAgentOptions(
                    cwd=BASE_DIR,
                    allowed_tools=["Read", "Glob", "Grep"],
                    system_prompt=system_msg,
                    max_turns=max_turns,
                    permission_mode="bypassPermissions",
                    mcp_servers=mcp_servers if mcp_servers else None,
                    model=effective_model,
                    env=env,
                    **({'user': 'intelhub'} if os.getuid() == 0 else {}),
                )
            ):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, ToolUseBlock):
                            args_str = json.dumps(block.input, ensure_ascii=False)[:200]
                            tool_log.append(f"[Tool] {block.name}({args_str})")
                        elif isinstance(block, ToolResultBlock):
                            content_str = (block.content if isinstance(block.content, str)
                                           else json.dumps(block.content, ensure_ascii=False))
                            tool_log.append(f"[Result] {content_str[:150]}")
                elif isinstance(message, ResultMessage):
                    if message.result:
                        result_text.append(message.result)

        anyio.run(_run)
        # Store tool log separately, return only result text
        global _last_agent_log
        if tool_log:
            log_parts = [f"=== Agent 执行过程 ({len(tool_log)} 步) ==="]
            log_parts.extend(tool_log)
            _last_agent_log = '\n'.join(log_parts)
        if result_text:
            return '\n'.join(result_text)
        # If no result_text but tool_log exists (agent wrote report via tool), return success marker
        if tool_log:
            return "[Agent completed via write_report tool]"
        return "[ERROR] Agent returned empty result"

    except ImportError as e:
        return f"[ERROR] SDK import failed: {e}"
    except Exception as e:
        logger.error("SDK harness failed: %s", e)
        return f"[ERROR] SDK harness failed: {e}"


def _run_harness_anthropic(prompt: str, model: Optional[str] = None,
                           api_key: Optional[str] = None, max_turns: int = 15) -> str:
    """使用原始 Anthropic SDK 运行 (fallback)"""
    if not ANTHROPIC_AVAILABLE:
        return "[ERROR] anthropic SDK not available"

    # 从 DB 读配置，fallback 到 env var
    from analysis.engine import _get_llm_config_from_db
    key = api_key or _get_llm_config_from_db('api_key') or os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("LLM_API_KEY")
    if not key:
        return "[ERROR] No ANTHROPIC_API_KEY or LLM_API_KEY"

    from analysis.engine import _load_env
    _load_env()

    base_url = (
        _get_llm_config_from_db('base_url') or
        os.environ.get("ANTHROPIC_BASE_URL", "") or
        os.environ.get("LLM_BASE_URL", "")
    )
    effective_model = model or _get_llm_config_from_db('model') or os.environ.get("LLM_MODEL", "") or os.environ.get("ANTHROPIC_MODEL", "")

    kwargs = {"api_key": key}
    if base_url:
        kwargs["base_url"] = base_url
    client = anthropic.Anthropic(**kwargs)
    system_msg = (
        "你是专业的投资研究报告生成助手。通过调用工具获取数据，逐步构建完整报告，"
        "最后必须调用 write_report 工具写入。\n\n"
        "重要：当你认为报告已完整时，务必调用 write_report 工具结束。\n\n"
        "报告规范：\n"
        "- 每个观点和数据点必须标注来源（平台/数据源名称）\n"
        "- 如果数据包含 url 字段，在报告中以 [来源](url) 格式提供可点击的引用链接\n"
        "- 对于热点新闻和重要数据，优先提供原始链接以便读者追溯\n\n"
        "标题规范：\n"
        "- 调用 write_report 时必须提供 title 参数\n"
        "- 标题要简洁有力、有吸引力，能概括报告核心观点\n"
        "- 15字以内，纯中文，不要含日期、emoji、标点符号\n"
        "- 示例：「科技巨头AI军备赛升级」「楼市回暖信号频现」「消费新趋势洞察」"
    )

    messages = [{"role": "user", "content": prompt}]

    for turn in range(1, max_turns + 1):
        logger.info(f"[ReportHarness] Turn {turn}/{max_turns}")
        resp = client.messages.create(
            model=effective_model, max_tokens=4096,
            system=system_msg, tools=TOOLS, messages=messages,
        )

        text_parts = []
        tool_results = []

        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                handler = TOOL_MAP.get(block.name, lambda a: f"[Unknown tool: {block.name}]")
                result = handler(block.input)
                logger.info(f"[ReportHarness] Tool {block.name} -> {result[:80]}")
                tool_results.append({"type": "tool_result", "tool_use_id": block.id, "content": result})

        if text_parts:
            messages.append({"role": "assistant", "content": "\n".join(text_parts)})

        if not tool_results:
            final = "\n".join(text_parts) if text_parts else ""
            if "<done>" in final:
                final = final[:final.index("<done>")]
            return final

        messages.append({"role": "user", "content": tool_results})

        for tr in tool_results:
            if "报告已写入" in str(tr.get("content", "")):
                return tr["content"]

    return "[ERROR] max turns exceeded"


# Module-level holder for the latest agent execution log
_last_agent_log = ""


def _run_harness(prompt: str, model: Optional[str] = None,
                 api_key: Optional[str] = None, max_turns: int = 15) -> str:
    """运行报告生成 - 优先 Claude Agent SDK, 回退 Anthropic SDK

    Returns: report content string. Agent execution log stored in _last_agent_log.
    """
    global _last_agent_log
    _last_agent_log = ""

    # 优先使用 claude_agent_sdk
    if CLAUDE_SDK_AVAILABLE:
        result = _run_harness_sdk(prompt, max_turns)
        if not result.startswith("[ERROR]"):
            return result
        logger.warning("Claude SDK harness failed, trying anthropic fallback: %s", result[:100])

    # 回退到原始 anthropic SDK
    if ANTHROPIC_AVAILABLE:
        result = _run_harness_anthropic(prompt, model, api_key, max_turns)
        if not result.startswith("[ERROR]"):
            return result
        logger.warning("Anthropic harness failed: %s", result[:100])

    return "[ERROR] No LLM backend available"


# ── 主入口 ─────────────────────────────────────────────────────────────────────

def _extract_title(content: str, fallback: str = "") -> str:
    """从 Markdown 内容提取报告标题。

    优先取 ## 二级标题（通常是报告核心主题），
    清洗 emoji、日期后缀、装饰符号等，生成简洁标题。
    """
    import re

    # 收集所有标题
    h1_candidates = []
    h2_candidates = []
    for line in content.split('\n'):
        stripped = line.strip()
        if stripped.startswith('## '):
            title = stripped[3:].strip()
            h2_candidates.append(title)
        elif stripped.startswith('# '):
            title = stripped[2:].strip()
            h1_candidates.append(title)

    # 清洗函数
    def _clean(t):
        # 去 emoji
        t = re.sub(r'[\U0001F300-\U0001F9FF☀-➿]', '', t)
        # 去装饰符号 📅📡🏷️📐📏📎 等
        t = re.sub(r'[\U0001F4C0-\U0001F4FF\U0001F680-\U0001F6FF]', '', t)
        # 去《》书名号
        t = t.replace('《', '').replace('》', '')
        # 去多余空白
        t = re.sub(r'\s+', ' ', t).strip()
        # 去 · | — 等分隔符后面的日期部分（如 "xxx · 2026-05-17 21:00"）
        t = re.sub(r'\s*[·|—–]\s*\d{4}[-.]\d{2}[-.]\d{2}.*$', '', t)
        t = re.sub(r'\s*[·|—–]\s*每日.*$', '', t)
        t = re.sub(r'\s*[·|—–]\s*每日潮流雷达.*$', '', t)
        # 去 _2026-05-17 09:00 之类的时间后缀
        t = re.sub(r'[_\s]+\d{4}[-.]\d{2}[-.]\d{2}.*$', '', t)
        # 去首尾的 · 和 - 和 _
        t = t.strip('·-—–_ ')
        return t

    # 优先从 h1 取（通常是报告名）
    for raw in h1_candidates:
        cleaned = _clean(raw)
        if 4 < len(cleaned) <= 80:
            return cleaned

    # 从 h2 取核心主题（跳过"数据健康"等元信息）
    skip_keywords = ['数据健康', '数据源异常', '系统健康', '说明', '声明']
    for raw in h2_candidates:
        cleaned = _clean(raw)
        if any(k in cleaned for k in skip_keywords):
            continue
        if 4 < len(cleaned) <= 80:
            return cleaned

    # 回退：取第一个 h1（即使较长也截断）
    for raw in h1_candidates:
        cleaned = _clean(raw)
        if len(cleaned) > 4:
            return cleaned[:120]

    return fallback


def _extract_summary(content: str, max_len: int = 200) -> str:
    """从 Markdown 内容提取摘要（取第一个非空、非标题的段落）。"""
    import re
    for line in content.split('\n'):
        stripped = line.strip()
        if not stripped or stripped.startswith('#') or stripped.startswith('```') or stripped.startswith('---'):
            continue
        # 跳过纯 emoji 或过短的行
        if len(re.sub(r'[\U0001F300-\U0001F9FF\s*·|—–:：📅📡🏷️]', '', stripped)) < 10:
            continue
        # 清洗 markdown 格式
        cleaned = re.sub(r'\*{1,2}([^*]+)\*{1,2}', r'\1', stripped)
        cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)
        if len(cleaned) > max_len:
            cleaned = cleaned[:max_len] + '...'
        return cleaned
    return ''


def _save_report_record(path: str, content: str, task_id: str = None, user_id: str = None, agent_title: str = None, report_type: str = None):
    """创建 Report 数据库记录，关联 task_id。"""
    try:
        from app import db
        from app.models.report import Report
        from app.models.task import ScheduledTask
        filename = os.path.basename(path)
        # 优先用 agent 生成的标题，否则从内容提取
        title = agent_title if agent_title and len(agent_title) > 2 else _extract_title(content, fallback=filename.replace('.md', ''))
        summary = _extract_summary(content)

        # Auto-detect report_type from task module
        effective_type = report_type or 'agent'
        if not report_type and task_id:
            task = db.session.get(ScheduledTask, task_id)
            if task and task.module == 'personal_daily':
                effective_type = 'personal_daily'

        report = Report(
            title=title,
            report_type=effective_type,
            file_path=path,
            summary=summary,
            user_id=user_id,
            task_id=task_id,
            scope='personal' if user_id else 'platform',
        )
        db.session.add(report)
        db.session.commit()
        return report
    except Exception as e:
        logger.warning(f"Failed to save report record: {e}")
        return None


def generate_report(
    template_id: str = None,
    prompt_template: str = None,
    data_sources: list = None,
    trend_reference: bool = True,
    max_items: int = 50,
    use_harness: bool = True,
    rss_source_ids: list = None,
    user_id: str = None,
    task_id: str = None,
    use_preferences: bool = False,
) -> dict:
    global _agent_written_report, _current_user_id
    _agent_written_report = None
    _current_user_id = user_id

    # 个人报告输出到用户目录
    if user_id:
        from app.utils.user_dirs import user_reports_dir
        out_dir = user_reports_dir(user_id)
    else:
        out_dir = REPORTS_DIR
    os.makedirs(out_dir, exist_ok=True)

    # 加载模板 — 自定义提示词优先于 template_id
    from app.models.report_template import ReportTemplate
    if prompt_template:
        from app.models.report_template import ReportTemplate
        tmpl = ReportTemplate(
            name="adhoc", prompt_template=prompt_template,
            data_sources=data_sources or [], trend_reference=trend_reference,
            max_items_per_source=max_items,
        )
    elif template_id:
        from app import db as _db
        tmpl = _db.session.get(ReportTemplate, template_id)
        if not tmpl:
            logger.warning("Template %s not found in DB, falling back to default", template_id)
            tmpl = ReportTemplate.get_default_template()
    else:
        from app.models.report_template import ReportTemplate
        tmpl = ReportTemplate.get_default_template()

    sources = tmpl.data_sources or data_sources or ["hot_topics"]

    context = {
        "date": bj_now().strftime("%Y-%m-%d %H:%M"),
        "health": _system_health(),
        "hot_topics": _get_data_summary("hot_topics", max_items),
        "policy_data": _get_data_summary("policy", max_items),
        "exchange_data": _get_data_summary("exchange", max_items),
        "financial_data": _get_data_summary("financial", max_items),
        "rss_data": _get_rss_summary_by_ids(rss_source_ids, max_items, user_id) if rss_source_ids else _get_data_summary("rss", max_items),
        "trends": "[使用 search_trends 工具获取]",
        "resonance": "[使用 analyze_resonance 工具获取]",
        "previous_report": _load_latest_report(7) if trend_reference else "[趋势参考已禁用]",
        "user_preferences": "",
    }

    # 用户偏好注入 (disabled in open-source version)
    if use_preferences and user_id:
        pass

    if use_harness and (CLAUDE_SDK_AVAILABLE or ANTHROPIC_AVAILABLE):
        rendered = tmpl.render_prompt(context)
        result = _run_harness(rendered)
        if result.startswith("[ERROR]"):
            logger.warning(f"Harness failed: {result}, falling back to template")
            result = tmpl.render_prompt(context)
    else:
        result = tmpl.render_prompt(context)

    # 如果 agent 在执行过程中已通过 write_report 工具写入过完整报告，直接返回
    if _agent_written_report:
        logger.info(f"[ReportExecutor] Agent already wrote report: {_agent_written_report['path']}")
        report_json = {
            "generated_at": bj_now().isoformat(),
            "source": "agent-harness",
            "filename": _agent_written_report["filename"],
            "template_id": template_id,
            "health": {"status": "healthy"},
            "trends": [], "resonance": {"total": 0},
            "total_items": len(result.split("\n")),
        }
        # 写入 per-report JSON
        ts = bj_now().strftime('%Y-%m-%dT%H-%M-%S')
        json_ts_path = os.path.join(out_dir, f"report-{ts}.json")
        with open(json_ts_path, "w", encoding="utf-8") as f:
            json.dump(report_json, f, ensure_ascii=False, indent=2)
        # 更新 latest
        json_path = os.path.join(out_dir, "insight-report-latest.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_json, f, ensure_ascii=False, indent=2)
        # 保存报告记录
        try:
            report_content = open(_agent_written_report["path"], "r", encoding="utf-8").read()
        except Exception:
            report_content = result
        _save_report_record(_agent_written_report["path"], report_content,
                           task_id=task_id, user_id=user_id,
                           agent_title=_agent_written_report.get("title"))
        return {"success": True, "path": _agent_written_report["path"],
                "filename": _agent_written_report["filename"],
                "model_used": "claude-sdk" if CLAUDE_SDK_AVAILABLE else "harness",
                "agent_log": _last_agent_log}

    # agent 未通过工具写入报告时，将 harness 输出作为报告写入
    filename = f"agent-report-{bj_now().strftime('%Y%m%d-%H%M%S')}.md"
    path = os.path.join(out_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(result)

    report_json = {
        "generated_at": bj_now().isoformat(),
        "source": "agent-harness" if use_harness else "template",
        "filename": filename, "template_id": template_id,
        "health": {"status": "healthy"},
        "trends": [], "resonance": {"total": 0},
        "total_items": len(result.split("\n")),
    }
    # 写入 per-report JSON
    ts = bj_now().strftime('%Y-%m-%dT%H-%M-%S')
    json_ts_path = os.path.join(out_dir, f"report-{ts}.json")
    with open(json_ts_path, "w", encoding="utf-8") as f:
        json.dump(report_json, f, ensure_ascii=False, indent=2)
    # 更新 latest
    json_path = os.path.join(out_dir, "insight-report-latest.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report_json, f, ensure_ascii=False, indent=2)

    logger.info(f"[ReportExecutor] Saved: {path}")
    # 保存报告记录
    _save_report_record(path, result, task_id=task_id, user_id=user_id)
    return {"success": True, "path": path, "filename": filename,
            "model_used": "claude-sdk" if CLAUDE_SDK_AVAILABLE else ("harness" if ANTHROPIC_AVAILABLE else "template"),
            "agent_log": _last_agent_log}
