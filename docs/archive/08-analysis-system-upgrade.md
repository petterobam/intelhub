# 迭代3: 分析系统升级 - Claude Agent SDK 多轮分析

**目标**: 使用 Anthropic Claude SDK 实现多轮分析系统，替代 Hermes cron 中的分析任务（投资心跳、洞察报告、自优化分析）。

---

## 一、Hermes 分析任务梳理

| 任务 | 频率 | 逻辑 | 输出 |
|------|------|------|------|
| 投资分析心跳 | 9/13/16/22点 | 读取最新采集数据 → 多维度分析 → 生成洞察 | 飞书报告 |
| 洞察报告发布 | 9/21点 | 读取采集日志+聚合数据 → 深度分析 → 结构化报告 | 飞书报告 |
| 自优化分析 | 每小时 | 分析采集质量 → 优化建议 → 系统健康 | 日志 |

---

## 二、技术方案: Anthropic Claude SDK

### 依赖
```bash
pip install anthropic  # Anthropic Python SDK
```

### 架构设计

```
analysis/
├── __init__.py
├── engine.py                    # 核心引擎: ClaudeAgent 分析引擎
├── agents/                      # 分析 Agent 定义
│   ├── __init__.py
│   ├── heartbeat_agent.py       # 投资心跳分析
│   ├── insight_agent.py         # 洞察报告生成
│   ├── optimization_agent.py    # 自优化分析
│   └── base_agent.py           # Agent 基类
├── prompts/                     # 提示词模板
│   ├── heartbeat.md            # 心跳分析提示词
│   ├── insight.md              # 洞察报告提示词
│   └── optimization.md         # 自优化提示词
├── tools/                       # Agent 可用工具
│   ├── __init__.py
│   ├── data_reader.py          # 读取采集数据
│   ├── trend_calculator.py     # 趋势计算
│   └── report_writer.py        # 报告生成
├── aggregate/
│   └── aggregator.py           # 数据聚合
├── heartbeat/
│   └── heartbeat_analyzer.py   # 心跳分析器
├── resonance/
│   └── resonance_analyzer.py   # 共振分析
├── trends/
│   └── trend_analyzer.py       # 趋势分析
└── reports/
    └── insight_generator.py    # 洞察生成
```

### 核心引擎: ClaudeAgent

```python
import anthropic
import json
import os

class ClaudeAnalysisEngine:
    """使用 Anthropic Claude SDK 实现多轮分析"""
    
    def __init__(self):
        self.client = anthropic.Anthropic()
        self.model = "claude-sonnet-4-20250514"
    
    def analyze(self, task_type: str, context: dict, max_turns: int = 5) -> dict:
        """
        执行多轮分析
        
        Args:
            task_type: 分析类型 (heartbeat/insight/optimization)
            context: 上下文数据 (采集结果、历史数据等)
            max_turns: 最大分析轮数
            
        Returns:
            分析结果 + 生成的报告
        """
        system_prompt = self._load_prompt(task_type)
        
        # 第一轮: 提供数据 + 分析指令
        messages = [{
            "role": "user",
            "content": self._format_context(context)
        }]
        
        for turn in range(max_turns):
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages,
                tools=self._get_tools(task_type)
            )
            
            # 处理响应 - 可能包含工具调用
            messages.append({"role": "assistant", "content": response.content})
            
            if response.stop_reason == "end_turn":
                break
            
            # 执行工具调用并追加结果
            tool_results = self._execute_tool_calls(response.content)
            messages.append({"role": "user", "content": tool_results})
        
        return self._parse_result(response, task_type)
```

### 分析任务定义

#### 1. 投资心跳分析 (HeartbeatAgent)

```python
class HeartbeatAgent(BaseAgent):
    """
    模拟 Hermes 投资分析心跳任务
    输入: 最新采集数据 (热点/政策/交易所/巨潮)
    处理: 
      - Round 1: 读取各平台最新数据，识别关键变化
      - Round 2: 跨平台共振分析 (同一主题在多平台出现)
      - Round 3: 时间序列异常检测
      - Round 4: 生成投资洞察 + 风险提示
    输出: 结构化心跳报告 (JSON + Markdown)
    """
    
    TOOLS = [
        "read_latest_data",      # 读取最新采集数据
        "calculate_trends",      # 计算趋势变化
        "cross_platform_analysis",  # 跨平台共振分析
        "write_report"           # 写入报告
    ]
```

#### 2. 洞察报告生成 (InsightAgent)

```python
class InsightAgent(BaseAgent):
    """
    模拟 Hermes 洞察报告发布任务
    输入: 采集日志 + 聚合数据 + 历史报告
    处理:
      - Round 1: 数据质量评估
      - Round 2: 主题提取 + 情感分析
      - Round 3: 深度关联分析
      - Round 4: 生成结构化洞察报告
    输出: Markdown 洞察报告
    """
```

#### 3. 自优化分析 (OptimizationAgent)

```python
class OptimizationAgent(BaseAgent):
    """
    模拟 Hermes 自优化分析器
    输入: 系统运行日志 + 采集统计
    处理:
      - Round 1: 采集成功率分析
      - Round 2: 数据新鲜度检查
      - Round 3: 优化建议生成
    输出: 优化建议 + 健康报告
    """
```

---

## 三、Claude Agent 工具定义

Agent 在分析过程中可调用以下工具 (通过 Claude tool_use):

### data_reader
```python
{
    "name": "read_latest_data",
    "description": "读取指定模块的最新采集数据",
    "input_schema": {
        "type": "object",
        "properties": {
            "module": {"type": "string", "enum": ["hot_topics", "policy", "exchange", "financial"]},
            "platform": {"type": "string", "description": "具体平台名"},
            "count": {"type": "integer", "default": 50}
        }
    }
}
```

### trend_calculator
```python
{
    "name": "calculate_trends",
    "description": "计算指定关键词/主题的趋势变化",
    "input_schema": {
        "type": "object",
        "properties": {
            "keywords": {"type": "array", "items": {"type": "string"}},
            "time_range": {"type": "string", "enum": ["1h", "6h", "24h", "7d"]}
        }
    }
}
```

### report_writer
```python
{
    "name": "write_report",
    "description": "将分析结果写入报告文件",
    "input_schema": {
        "type": "object",
        "properties": {
            "report_type": {"type": "string"},
            "content": {"type": "string"},
            "format": {"type": "string", "enum": ["markdown", "json"]}
        }
    }
}
```

---

## 四、执行步骤

### Step 1: 安装 anthropic SDK
```bash
pip install anthropic
```

### Step 2: 创建分析引擎核心
- `analysis/engine.py` - ClaudeAnalysisEngine
- `analysis/agents/base_agent.py` - BaseAgent

### Step 3: 实现 Agent 工具
- `analysis/tools/data_reader.py` - 数据读取工具
- `analysis/tools/trend_calculator.py` - 趋势计算
- `analysis/tools/report_writer.py` - 报告写入

### Step 4: 实现三个分析 Agent
- HeartbeatAgent - 投资心跳
- InsightAgent - 洞察报告
- OptimizationAgent - 自优化

### Step 5: 编写提示词模板
- `analysis/prompts/heartbeat.md`
- `analysis/prompts/insight.md`
- `analysis/prompts/optimization.md`

### Step 6: 集成到任务执行器
- 在 `app/scheduler/executor.py` 中支持 `analysis` 类型任务
- 分析任务执行时调用对应 Agent

### Step 7: 更新 DB 任务定义
- 新增 analysis 类型任务
- 配置 API key (从环境变量读取)

### Step 8: 端到端测试
- 手动触发每个分析任务
- 验证报告生成
