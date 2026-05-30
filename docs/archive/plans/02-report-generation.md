# Plan 2: 报告生成功能

## 目标
在报告中心页面直接触发生成新报告，无需切换到任务管理页面。

## 现状问题
- 生成报告只能通过任务管理 → 手动运行对应任务
- 无法在报告中心快速触发一次采集+分析+生成
- 无生成进度反馈

## 实现步骤

### 2.1 报告生成按钮
- 在报告中心顶部添加"生成报告"按钮
- 下拉选择报告类型：
  - 洞察报告（insight）— 需要最新爬虫数据
  - 心跳检测（heartbeat）— 快速检查数据新鲜度
  - 数据聚合（aggregate）— 聚合所有平台数据
- 点击后调用 `/api/v1/tasks/<id>/run` 触发对应任务

### 2.2 任务与报告类型映射
- 后端新增 API: `GET /api/v1/reports/generators`
  - 返回可用的报告生成器列表（对应已配置的任务）
  ```json
  {
    "generators": [
      {"task_id": "xxx", "name": "洞察报告生成", "type": "report", "module": "analysis"},
      {"task_id": "yyy", "name": "系统心跳", "type": "system", "module": "system"}
    ]
  }
  ```

### 2.3 生成进度轮询
- 触发后显示进度条/状态指示
- 轮询 `GET /api/v1/tasks/<task_id>/status` 获取执行状态
- 完成后自动刷新报告列表
- 支持查看生成日志

### 2.4 一键生成（快捷按钮）
- "快速洞察" — 一键执行：爬虫采集 → 数据聚合 → 洞察报告生成
- 串行执行多个任务，每步完成后自动触发下一步
- 整体进度展示

## 后端 API 变更
- `app/api/reports.py` — 新增 `GET /generators` 和 `POST /generate`
- `app/services/report_generator.py` — 新建，编排多步生成流程

## 文件变更
- `app/api/reports.py` — 新增 2 个路由
- `app/services/report_generator.py` — 新建
- `frontend/src/pages/Reports.jsx` — 添加生成按钮和进度组件

## 验收标准
- [ ] 报告中心页面有"生成报告"按钮
- [ ] 可选择报告类型并触发生成
- [ ] 生成过程有进度反馈
- [ ] 完成后报告列表自动刷新
