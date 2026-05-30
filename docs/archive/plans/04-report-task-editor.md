# Plan 4: 报告任务编辑 — 提示词 + 数据筛选 + 趋势参考

## 目标
让用户在 Web 界面自定义报告生成逻辑：编辑分析提示词、选择数据源、设定趋势参考。
使用 Claude Agent SDK harness 模式执行分析任务。

## 现状问题
- 报告生成用的是硬编码脚本，用户无法自定义分析角度
- 无法选择用哪些平台的数据
- 无法设置关注的关键词/趋势
- 分析任务跑在 subprocess 里，无法利用 LLM Agent 能力

## 架构设计

### Claude Agent SDK Harness 模式
```
用户配置（提示词+数据筛选+趋势参考）
        ↓
   TaskExecutor
        ↓
   Claude Agent SDK (harness)
    ├─ 输入：筛选后的原始数据 + 用户提示词
    ├─ 工具：read_file(数据), search(趋势), web_search(补充)
    └─ 输出：结构化报告 JSON/MD
```

Agent SDK 负责编排分析流程，不需要每个步骤硬编码。

### 数据模型
```sql
-- report_templates 表（新增）
CREATE TABLE report_templates (
    id VARCHAR(16) PRIMARY KEY,
    name VARCHAR(200),          -- 模板名称
    description TEXT,            -- 模板描述
    prompt TEXT,                 -- 分析提示词（用户可编辑）
    data_sources JSON,           -- 数据源筛选 {"platforms": ["weibo","36kr"], "tags": ["科技"]}
    trend_keywords JSON,         -- 趋势参考关键词 ["芯片","新能源","AI"]
    output_format VARCHAR(20),   -- md / json
    schedule_config TEXT,        -- 调度配置
    task_id VARCHAR(16),         -- 关联的 ScheduledTask ID
    last_run_at DATETIME,
    created_at DATETIME,
    updated_at DATETIME
);
```

## 实现步骤

### 4.1 数据模型 + API
- 创建 `ReportTemplate` 模型（`app/models/report_template.py`）
- CRUD API（`app/api/report_templates.py` 已存在，需扩展）
  - `GET /api/v1/report-templates` — 列表
  - `POST /api/v1/report-templates` — 创建
  - `PUT /api/v1/report-templates/<id>` — 更新
  - `DELETE /api/v1/report-templates/<id>` — 删除

### 4.2 提示词编辑器
- Rich text / Markdown 编辑器组件
- 预设模板选择：
  - "市场热点分析" — 分析热点话题、跨平台共振
  - "政策影响评估" — 分析政策对各行业的影响
  - "投资风险扫描" — 识别潜在风险信号
- 变量插值支持：`{{date}}` `{{platforms}}` `{{keywords}}`

### 4.3 数据筛选面板
- 平台多选：勾选要包含的数据源（weibo/36kr/huxiu 等）
- 时间范围：最近 N 小时 / 自定义日期范围
- 关键词过滤：包含/排除关键词
- 数据量限制：最多分析 N 条
- 实时预览：显示筛选后的数据量和样例

### 4.4 趋势参考设置
- 手动输入关注关键词
- 从历史数据自动推荐热门关键词
- 关键词权重设置（高/中/低）
- 自动发现模式：根据历史数据发现新兴趋势

### 4.5 Claude Agent SDK 集成
- 安装 `anthropic` SDK
- 创建 `app/services/agent_harness.py`：
  ```python
  class AgentHarness:
      def __init__(self, template, data):
          self.template = template
          self.data = data
      
      async def run(self):
          # 1. 构建系统提示词（用户自定义 + 数据上下文）
          # 2. 构建 tools（read_file, search, web_search）
          # 3. 调用 Claude API with tools
          # 4. 收集 Agent 输出
          # 5. 保存报告文件
          pass
  ```
- TaskExecutor 检测 task_type=report 时调用 AgentHarness

### 4.6 报告模板管理页面
- 新增页面：`/templates`（或在报告中心内嵌）
- 模板列表：卡片展示，显示名称、描述、数据源标签
- 模板详情：
  - 左栏：提示词编辑器 + 趋势关键词
  - 右栏：数据筛选面板 + 预览
- 底部：保存 + 立即运行 + 调度设置

## 文件变更
- `app/models/report_template.py` — 新建
- `app/services/agent_harness.py` — 新建（Claude Agent SDK 集成）
- `app/api/report_templates.py` — 扩展 CRUD
- `app/scheduler/executor.py` — 支持 report 类型调用 AgentHarness
- `frontend/src/pages/ReportTemplates.jsx` — 新建
- `frontend/src/components/PromptEditor.jsx` — 新建
- `frontend/src/components/DataSourceFilter.jsx` — 新建
- `frontend/src/components/TrendKeywords.jsx` — 新建

## 技术要点
- Claude Agent SDK 使用 streaming 模式，实时反馈分析进度
- 提示词模板支持变量插值，运行时自动填充
- 数据筛选在内存中完成，避免大量临时文件
- Agent 生成报告保存到 `data/reports/` 目录，与现有报告系统无缝集成

## 验收标准
- [ ] 可创建/编辑报告模板，自定义分析提示词
- [ ] 数据筛选面板支持平台选择、时间范围、关键词过滤
- [ ] 趋势参考支持手动输入和历史推荐
- [ ] 点击"运行"后通过 Claude Agent SDK 生成报告
- [ ] 生成的报告在报告中心正常展示
- [ ] 模板可关联定时任务，按计划自动执行
