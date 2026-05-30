# PLAN-02: 分析引擎 - LLM 多轮分析与报告系统

> 本文档定义分析引擎的架构设计、各分析器的职责和 LLM 调用策略。

---

## 一、现有分析代码清单

| 文件 | 行数 | 功能 | 状态 |
|------|------|------|------|
| `analysis/engine.py` | 644 | LLM 引擎核心，支持 Anthropic/OpenAI/Ollama | ✅ 已实现 |
| `analysis/agents/__init__.py` | - | 3个 Agent (Heartbeat/Insight/Optimization) | ✅ 已实现 |
| `analysis/aggregate/aggregator.py` | 157 | 多平台数据聚合 | ✅ 已实现 |
| `analysis/heartbeat/heartbeat_analyzer.py` | 126 | 数据新鲜度 + 快速洞察 | ✅ 已实现 |
| `analysis/resonance/resonance_analyzer.py` | 120 | 跨平台热点共振检测 | ✅ 已实现 |
| `analysis/trends/trend_analyzer.py` | 160 | 话题分类 + 热度评分 | ✅ 已实现 |
| `analysis/reports/insight_generator.py` | 120 | 完整洞察报告生成 | ✅ 已实现 |

---

## 二、分析引擎架构

```
analysis/
├── engine.py                  # ✅ LLM 引擎核心
│                              #    - Anthropic SDK + GLM 端点
│                              #    - 多后端自动检测
│                              #    - tool_use 多轮对话
│
├── agents/                    # ✅ 分析 Agent（LLM 驱动）
│   ├── __init__.py           # Agent 工厂 + 3个 Agent 定义
│   ├── heartbeat_agent.py    # 心跳分析 Agent
│   ├── insight_agent.py      # 深度洞察 Agent
│   └── optimization_agent.py # 自优化 Agent
│
├── prompts/                   # ✅ 提示词模板
│   ├── heartbeat.md          # 心跳分析 prompt
│   ├── insight.md            # 深度洞察 prompt
│   └── optimization.md       # 自优化 prompt
│
├── aggregate/                # ✅ 数据聚合（规则驱动）
│   └── aggregator.py
│
├── heartbeat/                # ✅ 心跳分析（规则驱动）
│   └── heartbeat_analyzer.py
│
├── resonance/                # ✅ 共振分析（规则驱动）
│   └── resonance_analyzer.py
│
├── trends/                   # ✅ 趋势分析（规则驱动）
│   └── trend_analyzer.py
│
└── reports/                  # ✅ 报告生成（规则 + LLM 混合）
    └── insight_generator.py
```

---

## 三、两种分析模式

### 模式 A: 规则驱动分析（已实现，无需 LLM）

用于：数据新鲜度检查、话题分类、共振检测、聚合统计

**特点：** 确定性输出，执行快速，不消耗 API 配额

```
数据加载 → 规则计算 → 结果输出
   ↓
例: heartbeat_analyzer.py → reports/heartbeat.json
    resonance_analyzer.py  → reports/cross-platform-resonance.json
    trend_analyzer.py      → reports/trend-analysis.json
    aggregator.py          → data/processed/all-platforms-aggregated.json
```

### 模式 B: LLM 驱动分析（已实现，使用 Claude SDK）

用于：深度洞察、报告生成、趋势解读、投资建议

**特点：** 理解上下文，生成自然语言洞察，支持多轮对话

```
上下文准备 → LLM 多轮对话 (max_turns=5) → 洞察输出
   ↓
例: HeartbeatAgent → "今日市场情绪：偏谨慎，科技股关注度上升..."
    InsightAgent   → "深度报告：A股今日热点..."
```

---

## 四、LLM 引擎核心设计

### 4.1 支持的后端

```python
# analysis/engine.py 中的后端检测优先级
LLM_BACKEND = os.environ.get('LLM_BACKEND', 'anthropic')

if LLM_BACKEND == 'anthropic':
    # Anthropic SDK + GLM 兼容端点
    # base_url: https://open.bigmodel.cn/api/anthropic/
    # 兼容: Claude 3.5/3.7, Sonnet, Opus
    client = anthropic.Anthropic(
        base_url=os.environ.get('LLM_BASE_URL'),
        api_key=os.environ.get('LLM_API_KEY'),
    )
    model = os.environ.get('LLM_MODEL', 'glm-4.7')  # GLM 模型名

elif LLM_BACKEND == 'openai':
    # OpenAI SDK（兼容 ZAI/GLM/DeepSeek 等）
    client = OpenAI(
        base_url=os.environ.get('OPENAI_BASE_URL'),
        api_key=os.environ.get('OPENAI_API_KEY'),
    )
    model = 'gpt-4o'

elif LLM_BACKEND == 'ollama':
    # 本地 Ollama（无需 API key）
    client = OpenAI(base_url='http://localhost:11434/v1', api_key='ollama')
    model = 'llama3'
```

### 4.2 Agent 工具定义

LLM Agent 通过 tool_use 访问系统数据：

```python
ANALYSIS_TOOLS = [
    {
        "name": "read_latest_data",
        "description": "读取最新采集的多平台热点数据",
        "input_schema": {
            "type": "object",
            "properties": {
                "module": {"type": "string", "enum": ["hot_topics", "policy", "exchange", "financial"]},
                "hours": {"type": "integer", "description": "最近几小时的数据"}
            }
        }
    },
    {
        "name": "read_aggregated_data",
        "description": "读取已聚合的全平台数据",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "read_trend_report",
        "description": "读取趋势分析报告",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "read_heartbeat",
        "description": "读取心跳报告（数据新鲜度）",
        "input_schema": {"type": "object", "properties": {}}
    },
    {
        "name": "read_knowledge_base",
        "description": "查询知识库",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "entity_type": {"type": "string", "enum": ["company", "industry", "topic"]}
            }
        }
    },
    {
        "name": "write_report",
        "description": "将分析报告保存到文件",
        "input_schema": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
                "content": {"type": "string"},
                "report_type": {"type": "string"}
            }
        }
    }
]
```

### 4.3 多轮分析流程

```python
class AnalysisEngine:
    """LLM 多轮分析引擎"""

    def analyze(self, task_type: str, context: dict, max_turns: int = 5) -> dict:
        """
        执行多轮分析
        
        Args:
            task_type: heartbeat | insight | optimization
            context: 预加载的上下文数据
            max_turns: 最大对话轮数（防止无限循环）
        """
        agent = self._get_agent(task_type)
        
        # 构建系统提示词
        system_prompt = self._load_prompt(task_type)
        
        # 构建初始消息（含上下文）
        messages = [{"role": "user", "content": self._prepare_context(context)}]
        
        # 多轮对话
        for turn in range(max_turns):
            response = self._call_llm(agent, messages)
            messages.append(response)
            
            # 检查是否需要调用工具
            if response.stop_reason == "tool_use":
                tool_results = self._execute_tools(response.content)
                messages.append(tool_results)
            elif response.stop_reason == "end_turn":
                break
        
        return self._parse_output(messages[-1], task_type)
```

---

## 五、各分析器详细设计

### 5.1 心跳分析器 (Heartbeat)

**触发:** 每小时 + 9/13/16/22 点
**输入:** 各平台最新 JSON
**输出:** `reports/heartbeat/YYYYMMDD_HH.json`

```python
class HeartbeatAnalyzer:
    """心跳分析 - 系统健康 + 快速洞察"""
    
    def analyze(self) -> dict:
        # 1. 检查各平台数据新鲜度
        freshness = self._check_freshness()
        
        # 2. 统计今日数据量
        volume = self._count_items()
        
        # 3. 检测异常（某平台数据突然中断）
        anomalies = self._detect_anomalies()
        
        # 4. 快速洞察（TOP 5 热点）
        quick_insights = self._extract_top5()
        
        # 5. LLM 辅助解读（可选）
        if self.llm_available:
            llm_insight = self._llm_quick_analysis(quick_insights)
        
        return {
            "freshness": freshness,
            "volume": volume,
            "anomalies": anomalies,
            "top5": quick_insights,
            "timestamp": datetime.now().isoformat()
        }
```

### 5.2 共振分析器 (Resonance)

**触发:** 每小时
**输入:** `data/processed/all-platforms-aggregated.json`
**输出:** `reports/cross-platform-resonance.json`

```python
class ResonanceAnalyzer:
    """跨平台共振分析 - 找出多平台同时出现的热点"""
    
    def analyze(self) -> dict:
        # 1. 加载聚合数据
        items = load_aggregated_data()
        
        # 2. 对每条数据提取关键词
        for item in items:
            item["keywords"] = extract_keywords(item["title"])
        
        # 3. 关键词跨平台统计
        keyword_cross_platform = self._count_keywords_per_platform(keywords)
        
        # 4. 筛选共振关键词（出现在 ≥3 个平台）
        resonances = [
            kw for kw, platforms in keyword_cross_platform.items()
            if len(platforms) >= 3
        ]
        
        # 5. 生成共振事件列表
        events = self._build_resonance_events(resonances)
        
        return {"resonance_events": events, "total_events": len(events)}
```

### 5.3 趋势分析器 (Trends)

**触发:** 每小时
**输入:** 聚合数据
**输出:** `reports/trend-analysis.json`

```python
class TrendAnalyzer:
    """趋势分析 - 话题分类 + 热度评分"""
    
    TOPIC_MAP = {
        "国际政治": ["伊朗", "特朗普", "美国", "中美", "俄罗斯", "以色列"],
        "财经市场": ["财报", "股价", "A股", "港股", "牛市", "熊市", "基金"],
        "科技": ["AI", "芯片", "华为", "英伟达", "大模型"],
        "产业": ["新能源", "医药", "半导体", "汽车"],
        "政策": ["监管", "财政部", "央行", "证监会", "国务院"],
    }
    
    def analyze(self) -> dict:
        # 1. 话题分类（规则匹配）
        classified = self._classify_topics()
        
        # 2. 热度评分（基于 hotness + 平台权重）
        platform_weights = {
            "weibo": 1.2, "douyin": 1.1, "zhihu": 1.0,
            "36kr": 1.3, "eastmoney": 1.4, "huxiu": 1.1
        }
        scored = self._score_trends(classified, platform_weights)
        
        # 3. TOP 20 趋势
        top20 = sorted(scored, key=lambda x: x["score"], reverse=True)[:20]
        
        # 4. 趋势变化（新上榜 / 退榜）
        changes = self._detect_changes(top20)
        
        return {"trends": top20, "changes": changes}
```

### 5.4 洞察报告生成器 (Insight)

**触发:** 每天 9:00 / 21:00
**输入:** 所有分析结果 + 知识库
**输出:** `reports/insight/YYYYMMDD_{am|pm}.md`

```python
class InsightReportGenerator:
    """深度洞察报告 - LLM 多轮分析"""
    
    def generate(self, time_of_day: str) -> dict:
        # 1. 聚合所有输入
        context = {
            "aggregated": aggregate_all(),
            "trends": load_trend_report(),
            "resonance": load_resonance_report(),
            "heartbeat": load_heartbeat(),
            "knowledge": self.kb.search_recent(hours=24),
            "time_of_day": time_of_day,  # "am" | "pm"
        }
        
        # 2. LLM 多轮深度分析
        agent = HeartbeatAgent() if time_of_day == "am" else InsightAgent()
        result = self.engine.analyze("insight", context, max_turns=5)
        
        # 3. 格式化报告
        report_md = self._format_report(result, time_of_day)
        report_json = self._extract_structured_data(result)
        
        # 4. 保存
        self._save_report(report_md, report_json, time_of_day)
        
        return {"report_path": report_md, "json_path": report_json}
```

---

## 六、定时任务 → 分析器映射

| 任务 | ID | 分析器 | 模式 |
|------|-----|--------|------|
| 投资分析心跳 | `bd96be79` | HeartbeatAnalyzer + LLM | 规则+LLM |
| 洞察报告生成 | `38d9f6f3` | InsightReportGenerator | 规则+LLM |
| 系统自优化 | `338b8a2e` | OptimizationAgent | LLM |
| 数据聚合 | `b559c102` | DataAggregator | 规则 |

---

## 七、待实施清单

- [ ] 实现 Agent tools → 实际系统数据的绑定
- [ ] 实现 `read_knowledge_base` tool 绑定
- [ ] 实现 `write_report` tool 绑定
- [ ] 实现 Optimization Agent 的完整提示词和工具
- [ ] 优化 Insight 报告格式（结构化 Markdown + JSON 双输出）
- [ ] 新增报告分发功能（飞书/邮件/Webhook）
- [ ] 新增分析历史版本管理
