# Plan 1: 报告详情面板增强

## 目标
提升报告详情的展示质量，让 MD 报告有格式化渲染，JSON 报告有更丰富的可视化。

## 现状问题
- MD 报告内容用 `<pre>` 标签直接展示纯文本，没有 Markdown 渲染
- Insight JSON 报告只有 3 个数字指标卡片，内容展示不够
- 无报告之间的时间线对比视图

## 实现步骤

### 1.1 Markdown 渲染
- 安装 `react-markdown` + `remark-gfm` 依赖
- 替换 `<pre>` 为 `<ReactMarkdown>` 组件
- 自定义暗色主题渲染器（标题、代码块、表格、列表）
- 支持图片链接预览

### 1.2 Insight 报告详情增强
- 解析 JSON 中的 `health`、`resonance`、`trends` 完整结构
- 健康状态：进度条 + 状态标签（healthy/warning/critical）
- 共振分析：跨平台热点列表，显示平台来源和共振强度
- 趋势洞察：卡片列表，含方向标签（bullish/bearish/neutral）
- 数据源标签：显示 `source`（agent-harness/manual）

### 1.3 Heartbeat 报告增强
- 平台状态网格：每个平台一个卡片，颜色编码
  - fresh=绿, stale=黄, critical=红, missing=灰
- 健康评分仪表盘（0-100 分的环形图）
- 告警列表分级显示（CRITICAL 红色 / WARNING 黄色）

### 1.4 Aggregate 报告增强
- 各平台数据量柱状图
- 数据完整性检查列表

## 文件变更
- `frontend/src/pages/Reports.jsx` — ReportDetail 组件重写
- `frontend/package.json` — 添加 react-markdown 依赖
- `frontend/src/components/ReportDetailInsight.jsx` — 新建
- `frontend/src/components/ReportDetailHeartbeat.jsx` — 新建

## 验收标准
- [ ] MD 报告有完整的 Markdown 渲染（标题、列表、表格、代码块）
- [ ] Insight 报告展示健康状态、共振数据、趋势卡片
- [ ] Heartbeat 报告展示平台网格和告警分级
- [ ] 暗色主题统一，无样式冲突
