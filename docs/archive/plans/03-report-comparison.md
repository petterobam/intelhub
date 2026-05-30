# Plan 3: 历史报告对比

## 目标
同类型多份报告的对比视图，发现趋势变化和数据差异。

## 现状问题
- 只能看单份报告，无法对比不同时间点的变化
- 不知道数据是变好了还是变差了
- 无历史趋势可视化

## 实现步骤

### 3.1 报告选择器（多选）
- 报告卡片支持多选模式（checkbox 或 shift+click）
- 选中 2-3 份同类型报告后出现"对比"按钮
- 底部展示对比面板

### 3.2 对比维度

#### Insight 报告对比
- 总条目数变化（柱状图：报告1 vs 报告2）
- 健康状态变化（healthy → warning → critical 转换）
- 趋势增减对比（新增/消失/持续的趋势标签）
- 共振强度对比

#### Heartbeat 报告对比
- 平台状态变化矩阵（每个平台的状态变迁）
- 健康评分趋势线（时间 → 分数）
- 告警增减（新出现/已解决/持续的告警）

#### Aggregate 报告对比
- 各平台数据量变化（堆叠柱状图）

### 3.3 时间线视图
- 同类型报告的横向时间线
- 标记关键事件（健康状态变化、数据突增/突降）
- 点击时间线节点切换查看

### 3.4 变化检测（后端）
- 新增 API: `GET /api/v1/reports/compare?type=insight&ids=id1,id2`
- 自动计算差异：
  - 数据量变化百分比
  - 新增/消失的关键词
  - 平台状态变化
- 返回结构化 diff 结果

## 文件变更
- `app/api/reports.py` — 新增 `GET /compare` 路由
- `app/services/report_comparator.py` — 新建，计算报告差异
- `frontend/src/components/ReportCompare.jsx` — 新建
- `frontend/src/components/ReportTimeline.jsx` — 新建
- `frontend/src/pages/Reports.jsx` — 集成多选和对比面板

## 验收标准
- [ ] 可多选同类型报告进行对比
- [ ] Insight 对比展示条目变化和趋势增减
- [ ] Heartbeat 对比展示平台状态变迁和评分趋势
- [ ] 时间线视图展示报告历史
