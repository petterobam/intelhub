"""Claude Analysis Engine - 多轮分析引擎

支持多种 LLM 后端:
- Claude Agent SDK (首选, 使用 claude_agent_sdk)
- OpenAI 兼容 API (ZAI/GLM 等, 通过 OPENAI_API_KEY + OPENAI_BASE_URL)
- 本地 Ollama (无需 API key)

Agent 通过 claude_agent_sdk 实现多轮分析, 可读取采集数据、计算趋势、生成报告。
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# IntelHub 项目根目录 (analysis/engine.py -> analysis/ -> intel-hub/)
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, 'data', 'raw')
REPORTS_DIR = os.path.join(PROJECT_DIR, 'reports')


def _load_env():
    """加载项目 .env 文件到环境变量"""
    candidates = [
        os.path.join(PROJECT_DIR, '.env'),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env'),
    ]
    for env_path in candidates:
        env_path = os.path.normpath(env_path)
        if os.path.exists(env_path):
            logger.info("Loading env from %s", env_path)
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, _, val = line.partition('=')
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key and key not in os.environ:
                            os.environ[key] = val
            return


# 启动时加载 .env
_load_env()


def _get_llm_config_from_db(key: str, default: str = '') -> str:
    """从 DB 读 LLM 配置 (需要 app context, 无 context 则 fallback 到 env)"""
    try:
        from app.models.llm_config import LlmConfig
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


def _get_llm_backend():
    """获取 LLM 后端类型 - 自动检测

    返回: (backend_name, client_or_none)
      - ('claude_sdk', None)   — claude_agent_sdk 可用
      - ('openai', client)     — OpenAI SDK
      - ('ollama', client)     — 本地 Ollama
      - (None, None)           — 无可用后端
    """
    preferred = os.environ.get('LLM_BACKEND', '').lower()

    # 如果明确指定了非 anthropic 后端, 跳过 claude_sdk
    if preferred in ('openai',):
        r = _try_openai()
        if r:
            return r

    if preferred in ('ollama',):
        r = _try_ollama()
        if r:
            return r

    # 默认优先级: claude_sdk -> openai -> ollama
    if preferred in ('', 'anthropic', 'claude_sdk'):
        if _try_claude_sdk():
            return 'claude_sdk', None

    for fn in [_try_openai, _try_ollama]:
        r = fn()
        if r:
            return r

    return None, None


def _try_claude_sdk():
    """检查 claude_agent_sdk 是否可用

    优先从 DB 读配置，fallback 到环境变量。
    """
    try:
        import claude_agent_sdk

        # 先尝试从 DB 读取
        db_key = _get_llm_config_from_db('api_key')
        if db_key:
            return True

        # Fallback: 检查环境变量
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if api_key:
            return True

        # 检查 LLM_BACKEND=anthropic + LLM_API_KEY 的情况
        backend = os.environ.get('LLM_BACKEND', '').lower()
        llm_key = os.environ.get('LLM_API_KEY', '')
        if backend == 'anthropic' and llm_key:
            os.environ['ANTHROPIC_API_KEY'] = llm_key
            base_url = os.environ.get('LLM_BASE_URL', '')
            if base_url and not os.environ.get('ANTHROPIC_BASE_URL'):
                os.environ['ANTHROPIC_BASE_URL'] = base_url
            return True

        logger.debug("claude_agent_sdk imported but no API key configured")
    except ImportError:
        logger.debug("claude_agent_sdk not installed")
    return False


def _try_openai():
    """OpenAI 兼容 (ZAI / GLM / OpenRouter / DeepSeek 等)"""
    api_key = (
        os.environ.get('LLM_API_KEY', '') or
        os.environ.get('OPENAI_API_KEY', '') or
        os.environ.get('ZAI_API_KEY', '') or
        os.environ.get('GLM_API_KEY', '')
    )
    if not api_key:
        return None
    try:
        import openai
        base_url = (
            os.environ.get('LLM_BASE_URL', '') or
            os.environ.get('OPENAI_BASE_URL', '') or
            os.environ.get('ZAI_BASE_URL', '')
        )
        kwargs = {'api_key': api_key}
        if base_url:
            kwargs['base_url'] = base_url
        client = openai.OpenAI(**kwargs)
        logger.info("Using OpenAI backend (base_url=%s)", base_url or 'default')
        return 'openai', client
    except ImportError:
        logger.warning("openai package not installed")
        return None


def _try_ollama():
    """本地 Ollama"""
    try:
        import openai
        client = openai.OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')
        return 'ollama', client
    except Exception:
        return None


def _get_model_name(backend: str) -> str:
    """获取模型名 (优先从 DB 读，支持任意模型名如 glm-5.1)"""
    # 先尝试 DB 配置
    db_model = _get_llm_config_from_db('model')
    if db_model:
        return db_model

    if backend == 'claude_sdk':
        model = os.environ.get('ANTHROPIC_MODEL', '')
        if model:
            return model
        return 'claude-sonnet-4-6'
    elif backend == 'openai':
        return os.environ.get('LLM_MODEL', '') or os.environ.get('OPENAI_MODEL', 'glm-4.7')
    elif backend == 'ollama':
        return os.environ.get('OLLAMA_MODEL', 'qwen2.5:14b')
    return 'unknown'


# ==================== 工具实现 ====================

def _tool_read_latest(params: Dict) -> str:
    """读取最新数据"""
    module = params.get('module', '')
    subdir = params.get('subdir', '')
    count = params.get('count', 50)

    base = os.path.join(DATA_DIR, module)
    if subdir:
        base = os.path.join(base, subdir)

    if not os.path.exists(base):
        return json.dumps({"error": f"Directory not found: {base}"}, ensure_ascii=False)

    # 查找最新 JSON 文件
    json_files = sorted(
        [f for f in os.listdir(base) if f.endswith('.json')],
        key=lambda f: os.path.getmtime(os.path.join(base, f)),
        reverse=True,
    )
    if not json_files:
        return json.dumps({"error": "No JSON files found"}, ensure_ascii=False)

    latest = os.path.join(base, json_files[0])
    try:
        with open(latest, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict) and 'items' in data:
            data['items'] = data['items'][:count]
        return json.dumps({
            "file": json_files[0],
            "data": data,
        }, ensure_ascii=False)[:8000]
    except Exception as e:
        return json.dumps({"error": str(e)})


def _tool_list_data(params: Dict) -> str:
    """列出可用数据"""
    module = params.get('module', '')
    base = os.path.join(DATA_DIR, module)
    if not os.path.exists(base):
        return json.dumps({"error": f"Module not found: {module}"})

    result = {}
    for item in sorted(os.listdir(base)):
        path = os.path.join(base, item)
        if os.path.isdir(path):
            files = [f for f in os.listdir(path) if f.endswith('.json')]
            result[item] = {
                "total_files": len(files),
                "latest": sorted(files, reverse=True)[0] if files else None,
            }
    return json.dumps(result, ensure_ascii=False)


def _tool_read_timeseries(params: Dict) -> str:
    """读取时间序列数据"""
    module = params.get('module', '')
    subdir = params.get('subdir', '')
    hours = params.get('hours', 24)

    base = os.path.join(DATA_DIR, module, subdir)
    if not os.path.exists(base):
        return json.dumps({"error": "Path not found"}, ensure_ascii=False)

    import time
    cutoff = time.time() - hours * 3600
    series = []
    for f in sorted(os.listdir(base)):
        if f.endswith('.json'):
            fpath = os.path.join(base, f)
            if os.path.getmtime(fpath) >= cutoff:
                try:
                    with open(fpath, 'r', encoding='utf-8') as fp:
                        data = json.load(fp)
                    series.append({
                        "file": f,
                        "item_count": len(data.get('items', [])) if isinstance(data, dict) else len(data) if isinstance(data, list) else 0,
                        "collected_at": data.get('collected_at', ''),
                    })
                except Exception:
                    pass
    return json.dumps({"count": len(series), "series": series[:20]}, ensure_ascii=False)


def _tool_write_report(params: Dict) -> str:
    """写入报告"""
    report_type = params.get('report_type', 'general')
    title = params.get('title', 'Report')
    content = params.get('content', '')
    summary = params.get('summary', '')
    data = params.get('data', {})

    # 按报告类型分目录
    type_dir = os.path.join(REPORTS_DIR, report_type if report_type in ('heartbeat', 'insight', 'agent') else 'agent')
    os.makedirs(type_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')

    # 写 Markdown 报告
    md_path = os.path.join(type_dir, f'{report_type}-{ts}.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f'# {title}\n\n')
        f.write(f'**生成时间**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n\n')
        if summary:
            f.write(f'**摘要**: {summary}\n\n')
        f.write('---\n\n')
        f.write(content)

    # 写 JSON 数据
    if data:
        json_path = os.path.join(type_dir, f'{report_type}-{ts}.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'type': report_type,
                'title': title,
                'summary': summary,
                'data': data,
                'generated_at': datetime.now().isoformat(),
            }, f, ensure_ascii=False, indent=2)

    return json.dumps({"status": "ok", "path": md_path}, ensure_ascii=False)


def _tool_search_keywords(params: Dict) -> str:
    """搜索关键词"""
    keywords = params.get('keywords', [])
    module = params.get('module', '')

    results = []
    search_dirs = []
    if module:
        search_dirs = [os.path.join(DATA_DIR, module)]
    else:
        for d in ['hot_topics', 'policy', 'exchange', 'financial']:
            search_dirs.append(os.path.join(DATA_DIR, d))

    for base in search_dirs:
        if not os.path.exists(base):
            continue
        for item in os.listdir(base):
            path = os.path.join(base, item)
            if os.path.isdir(path):
                json_files = sorted(
                    [f for f in os.listdir(path) if f.endswith('.json')],
                    reverse=True,
                )[:3]
                for jf in json_files:
                    try:
                        with open(os.path.join(path, jf), 'r', encoding='utf-8') as f:
                            text = f.read()
                        for kw in keywords:
                            if kw in text:
                                results.append({
                                    "keyword": kw,
                                    "file": os.path.join(item, jf),
                                })
                                break
                    except Exception:
                        pass

    return json.dumps({"matches": len(results), "results": results[:30]}, ensure_ascii=False)


# ==================== OpenAI 工具定义 (fallback) ====================

TOOLS = [
    {
        "name": "read_latest_data",
        "description": "读取指定模块的最新采集数据。返回JSON格式的采集结果。",
        "input_schema": {
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "数据模块: hot_topics/policy/exchange/financial",
                    "enum": ["hot_topics", "policy", "exchange", "financial"],
                },
                "subdir": {
                    "type": "string",
                    "description": "子目录/平台名(如 weibo, 36kr, pbc, sse)",
                },
                "count": {
                    "type": "integer",
                    "description": "返回的最大条目数",
                    "default": 50,
                },
            },
            "required": ["module"],
        },
    },
    {
        "name": "list_available_data",
        "description": "列出指定模块下所有可用的数据子目录和最新文件",
        "input_schema": {
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "数据模块",
                },
            },
            "required": ["module"],
        },
    },
    {
        "name": "read_time_series",
        "description": "读取指定数据的时间序列 (多个历史文件)",
        "input_schema": {
            "type": "object",
            "properties": {
                "module": {"type": "string"},
                "subdir": {"type": "string"},
                "hours": {
                    "type": "integer",
                    "description": "回溯小时数",
                    "default": 24,
                },
            },
            "required": ["module", "subdir"],
        },
    },
    {
        "name": "write_report",
        "description": "将分析结果写入报告文件",
        "input_schema": {
            "type": "object",
            "properties": {
                "report_type": {
                    "type": "string",
                    "description": "报告类型: heartbeat/insight/optimization",
                },
                "title": {"type": "string", "description": "报告标题"},
                "content": {"type": "string", "description": "报告内容(Markdown)"},
                "summary": {"type": "string", "description": "一句话摘要"},
                "data": {
                    "type": "object",
                    "description": "结构化分析数据(JSON)",
                },
            },
            "required": ["report_type", "title", "content"],
        },
    },
    {
        "name": "search_keywords",
        "description": "在采集数据中搜索关键词,返回匹配结果",
        "input_schema": {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "搜索关键词列表",
                },
                "module": {"type": "string", "description": "限定模块"},
            },
            "required": ["keywords"],
        },
    },
]


def execute_tool(name: str, params: Dict) -> str:
    """执行 Agent 工具调用 (OpenAI fallback 路径)"""
    handlers = {
        'read_latest_data': _tool_read_latest,
        'list_available_data': _tool_list_data,
        'read_time_series': _tool_read_timeseries,
        'write_report': _tool_write_report,
        'search_keywords': _tool_search_keywords,
    }
    handler = handlers.get(name)
    if handler:
        return handler(params)
    return json.dumps({"error": f"Unknown tool: {name}"})


# ==================== Claude Agent SDK 工具 ====================

def _create_sdk_mcp_server():
    """创建 Claude Agent SDK 的自定义 MCP 工具服务"""
    try:
        from claude_agent_sdk import tool, create_sdk_mcp_server

        @tool(
            "read_latest_data",
            "读取指定模块的最新采集数据。参数: module(必填,数据模块名如hot_topics/policy/exchange/financial), subdir(可选,子目录/平台名), count(可选,返回条目数,默认50)。返回JSON数据。",
            {"module": str, "subdir": str, "count": int},
        )
        async def sdk_read_latest(args):
            result = _tool_read_latest(args)
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "list_available_data",
            "列出指定模块下所有可用的数据子目录和最新文件。参数: module(必填,数据模块名)。",
            {"module": str},
        )
        async def sdk_list_data(args):
            result = _tool_list_data(args)
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "read_time_series",
            "读取指定数据的时间序列(多个历史文件)。参数: module(必填), subdir(必填), hours(可选,回溯小时数,默认24)。",
            {"module": str, "subdir": str, "hours": int},
        )
        async def sdk_read_timeseries(args):
            result = _tool_read_timeseries(args)
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "write_report",
            "将分析结果写入报告文件。参数: report_type(必填,如heartbeat/insight/agent), title(必填), content(必填,Markdown内容), summary(可选,一句话摘要), data(可选,结构化JSON数据)。",
            {"report_type": str, "title": str, "content": str, "summary": str, "data": dict},
        )
        async def sdk_write_report(args):
            result = _tool_write_report(args)
            return {"content": [{"type": "text", "text": result}]}

        @tool(
            "search_keywords",
            "在采集数据中搜索关键词。参数: keywords(必填,关键词数组), module(可选,限定模块)。",
            {"keywords": list, "module": str},
        )
        async def sdk_search_keywords(args):
            result = _tool_search_keywords(args)
            return {"content": [{"type": "text", "text": result}]}

        return create_sdk_mcp_server("intel-hub-tools", tools=[
            sdk_read_latest,
            sdk_list_data,
            sdk_read_timeseries,
            sdk_write_report,
            sdk_search_keywords,
        ])
    except ImportError:
        logger.warning("claude_agent_sdk not available for MCP tool creation")
        return None
    except Exception as e:
        logger.error("Failed to create SDK MCP server: %s", e)
        return None


# ==================== 分析引擎 ====================

class AnalysisEngine:
    """多轮分析引擎"""

    def __init__(self):
        self.backend, self.client = _get_llm_backend()
        self.model = _get_model_name(self.backend) if self.backend else ''
        self.reports_dir = REPORTS_DIR
        os.makedirs(self.reports_dir, exist_ok=True)

    def is_available(self) -> bool:
        return self.backend is not None

    def analyze(self, task_type: str, system_prompt: str, initial_context: str,
                max_turns: int = 5) -> Dict[str, Any]:
        """
        执行多轮分析

        Args:
            task_type: heartbeat/insight/optimization
            system_prompt: 系统提示词
            initial_context: 初始上下文(数据描述)
            max_turns: 最大轮数

        Returns:
            分析结果
        """
        if not self.is_available():
            return self._offline_analysis(task_type, initial_context)

        logger.info("Starting %s analysis with %s/%s (max %d turns)",
                     task_type, self.backend, self.model, max_turns)

        if self.backend == 'claude_sdk':
            return self._analyze_claude_sdk(task_type, system_prompt, initial_context, max_turns)
        elif self.backend in ('openai', 'ollama'):
            return self._analyze_openai(task_type, system_prompt, initial_context, max_turns)
        else:
            return self._offline_analysis(task_type, initial_context)

    # ------------------------------------------------------------------
    # claude_agent_sdk: Claude Agent SDK
    # ------------------------------------------------------------------
    def _analyze_claude_sdk(self, task_type: str, system_prompt: str,
                            initial_context: str, max_turns: int) -> Dict:
        """使用 Claude Agent SDK 进行多轮分析"""
        try:
            import anyio
            from claude_agent_sdk import query, ClaudeAgentOptions, ResultMessage

            # 创建自定义 MCP 工具
            mcp_server = _create_sdk_mcp_server()
            mcp_servers = {}
            if mcp_server is not None:
                mcp_servers["intel-hub"] = mcp_server

            # 构建 env — 从 DB 读配置，fallback 到 env var
            api_key = _get_llm_config_from_db('api_key') or os.environ.get('ANTHROPIC_API_KEY', '')
            base_url = _get_llm_config_from_db('base_url') or os.environ.get('ANTHROPIC_BASE_URL', '')
            env = {}
            if api_key:
                env['ANTHROPIC_API_KEY'] = api_key
            if base_url:
                env['ANTHROPIC_BASE_URL'] = base_url.rstrip("/")

            result_text = []

            async def _run():
                async for message in query(
                    prompt=initial_context,
                    options=ClaudeAgentOptions(
                        cwd=PROJECT_DIR,
                        allowed_tools=["Read", "Glob", "Grep"],
                        system_prompt=system_prompt,
                        max_turns=max_turns,
                        permission_mode="bypassPermissions",
                        mcp_servers=mcp_servers if mcp_servers else None,
                        model=self.model or None,
                        env=env if env else None,
                    )
                ):
                    if isinstance(message, ResultMessage):
                        if message.result:
                            result_text.append(message.result)

            anyio.run(_run)

            return {
                'task_type': task_type,
                'status': 'success',
                'backend': 'claude_sdk',
                'model': self.model or 'claude-sonnet-4-6',
                'response': '\n'.join(result_text),
                'generated_at': datetime.now().isoformat(),
            }
        except ImportError as e:
            logger.warning("claude_agent_sdk not available: %s, falling back to offline", e)
            return self._offline_analysis(task_type, initial_context)
        except Exception as e:
            logger.error("Claude SDK analysis failed: %s", e)
            return {
                'task_type': task_type,
                'status': 'error',
                'backend': 'claude_sdk',
                'error': str(e),
                'response': '',
                'generated_at': datetime.now().isoformat(),
            }

    # ------------------------------------------------------------------
    # openai / ollama: OpenAI 兼容 API
    # ------------------------------------------------------------------
    def _analyze_openai(self, task_type: str, system_prompt: str,
                        initial_context: str, max_turns: int) -> Dict:
        """OpenAI 兼容 API 多轮分析 (含 tool calling)"""
        openai_tools = []
        for t in TOOLS:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                }
            })

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": initial_context},
        ]
        final_response = ''

        for turn in range(max_turns):
            logger.info("  Turn %d/%d", turn + 1, max_turns)
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=openai_tools,
                    max_tokens=4096,
                )
            except Exception as e:
                logger.error("LLM API error: %s", e)
                break

            if not response.choices:
                logger.error("LLM returned no choices, response: %s", response)
                break
            choice = response.choices[0]
            msg = choice.message
            messages.append(msg.model_dump())

            if msg.content:
                final_response = msg.content

            if choice.finish_reason == 'stop':
                break

            if choice.finish_reason == 'tool_calls' and msg.tool_calls:
                tool_results = []
                for tc in msg.tool_calls:
                    logger.info("  Tool call: %s(%s)", tc.function.name,
                                tc.function.arguments[:100])
                    params = json.loads(tc.function.arguments)
                    result = execute_tool(tc.function.name, params)
                    tool_results.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result,
                    })
                messages.extend(tool_results)

        return {
            'task_type': task_type,
            'status': 'success',
            'backend': self.backend,
            'model': self.model,
            'turns': turn + 1 if 'turn' in dir() else 0,
            'response': final_response,
            'generated_at': datetime.now().isoformat(),
        }

    # ------------------------------------------------------------------
    # 离线模式
    # ------------------------------------------------------------------
    def _offline_analysis(self, task_type: str, context: str) -> Dict:
        """离线分析 - 无LLM后端时的降级方案"""
        summary = f"[离线模式] {task_type} 分析 (无LLM后端)\n\n"
        summary += "数据概览:\n"

        for module in ['hot_topics', 'policy', 'exchange', 'financial']:
            base = os.path.join(DATA_DIR, module)
            if os.path.exists(base):
                subdirs = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
                summary += f"  {module}: {len(subdirs)} 数据源\n"
                for sd in subdirs[:5]:
                    files = [f for f in os.listdir(os.path.join(base, sd)) if f.endswith('.json')]
                    summary += f"    - {sd}: {len(files)} 文件\n"

        os.makedirs(REPORTS_DIR, exist_ok=True)
        ts = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
        report_path = os.path.join(REPORTS_DIR, 'agent', f'{task_type}-offline-{ts}.md')
        os.makedirs(os.path.dirname(report_path), exist_ok=True)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f'# {task_type} 分析报告 (离线模式)\n\n')
            f.write(summary)

        return {
            'task_type': task_type,
            'status': 'offline',
            'backend': 'none',
            'response': summary,
            'report_path': report_path,
            'generated_at': datetime.now().isoformat(),
        }
