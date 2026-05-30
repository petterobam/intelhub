# PLAN-03: 平台层 - 调度系统、API 与 Web UI

> 本文档定义任务调度系统、REST API 设计和 Web UI 架构。

---

## 一、现有架构

```
Flask (:5003) + APScheduler + SQLite
  ├── app/api/tasks.py       ← 任务管理 API (已实现)
  ├── app/scheduler/         ← 调度器 (已实现)
  └── app/models/            ← 数据模型 (已实现)

React + Vite (:3000)
  └── frontend/src/
      ├── pages/Tasks.jsx    ← 任务管理页 (已实现)
      └── App.jsx            ← 路由 (已实现)
```

---

## 二、任务调度系统

### 2.1 任务类型系统（扩展）

当前只有 `script` 和 `analysis` 两种，需要扩展为 5 种：

```python
# app/models/task.py 扩展
TASK_TYPES = {
    "script":    "Shell 脚本任务（调用 cron_wrapper 脚本）",
    "analysis":  "LLM 分析任务（调用 analysis engine）",
    "crawler":    "爬虫任务（调用 Runner 的 run_all）",
    "knowledge": "知识库任务（调用 KB builder）",
    "report":     "报告任务（调用报告生成器）",
}
```

### 2.2 统一执行器架构

```python
# app/scheduler/executor.py 扩展

class TaskExecutor:
    """统一执行器 - 支持 5 种任务类型"""

    HANDLERS = {
        "script":    self._execute_script,
        "analysis": self._execute_analysis,
        "crawler":   self._execute_crawler,
        "knowledge": self._execute_knowledge,
        "report":    self._execute_report,
    }

    def execute(self, task) -> dict:
        handler = self.HANDLERS.get(task.task_type, self._execute_script)
        return handler(task)

    def _execute_crawler(self, task) -> dict:
        """执行爬虫任务 - 调用 Runner"""
        from crawlers.hot_topics.runner import HotTopicsRunner
        runner = self._get_runner(task.script)  # 根据 script 字段确定 Runner
        results = runner.run_all()
        return {
            "status": "success",
            "results": results,
            "artifacts": self._scan_artifacts(task),
        }

    def _execute_knowledge(self, task) -> dict:
        """执行知识库任务"""
        from knowledge_base.kb_manager import KnowledgeBaseManager
        kb = KnowledgeBaseManager()
        module = task.config.get("module", "all")
        return kb.ingest(module)

    def _execute_report(self, task) -> dict:
        """执行报告任务"""
        from analysis.reports.insight_generator import generate_insight_report
        result = generate_insight_report()
        return {"status": "success", "report": result}
```

### 2.3 调度器配置

```python
# app/scheduler/scheduler.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

def setup_scheduler(app, db_path: str):
    """根据数据库中的任务配置设置调度"""
    scheduler = BackgroundScheduler()
    
    tasks = load_tasks_from_db(db_path)
    for task in tasks:
        if not task.enabled:
            continue
        
        trigger = _parse_trigger(task.schedule_config)
        scheduler.add_job(
            func=trigger_task,
            trigger=trigger,
            args=[task.id, db_path],
            id=task.id,
            name=task.name,
        )
    
    scheduler.start()
    return scheduler

def _parse_trigger(config: dict) -> Trigger:
    """解析 DB 中的 schedule_config JSON"""
    if config["type"] == "interval":
        return IntervalTrigger(minutes=config["interval_minutes"])
    elif config["type"] == "cron":
        return CronTrigger.from_crontab(config["cron"])
```

### 2.4 任务执行流程

```
定时触发 / API触发
    │
    ▼
TaskExecutor.execute(task)
    │
    ├─→ [script]    Bash script (cron_wrapper)
    ├─→ [analysis]  LLM Analysis Engine
    ├─→ [crawler]   Crawler Runner
    ├─→ [knowledge] KB Manager
    └─→ [report]    Report Generator
    │
    ▼
结果写入 task_runs 表
    │
    ▼
扫描产出物 (artifacts)
    │
    ▼
前端轮询 / WebSocket 推送
```

---

## 三、REST API 设计

### 3.1 现有 API (已实现)

```
GET    /api/v1/tasks                    # 列表
GET    /api/v1/tasks/:id                # 详情
POST   /api/v1/tasks                    # 创建
PUT    /api/v1/tasks/:id                # 更新
DELETE /api/v1/tasks/:id                # 删除
POST   /api/v1/tasks/:id/run            # 手动触发
GET    /api/v1/tasks/:id/status         # 执行状态
GET    /api/v1/tasks/:id/logs           # 执行日志
GET    /api/v1/health                   # 健康检查
```

### 3.2 待扩展 API

```
# 知识库 API
GET    /api/v1/knowledge/search?q=...   # 知识检索
GET    /api/v1/knowledge/entity/:type/:id  # 实体详情
POST   /api/v1/knowledge/ingest        # 手动触发构建
GET    /api/v1/knowledge/stats         # 知识库统计

# 报告 API
GET    /api/v1/reports                  # 报告列表
GET    /api/v1/reports/:type/:date      # 报告详情
GET    /api/v1/reports/:id/download     # 下载报告

# 数据 API
GET    /api/v1/data/:module/:platform   # 原始数据
GET    /api/v1/data/aggregated          # 聚合数据
GET    /api/v1/data/freshness           # 数据新鲜度

# 分析 API
POST   /api/v1/analysis/run             # 触发分析
GET    /api/v1/analysis/status          # 分析状态
GET    /api/v1/analysis/result          # 分析结果

# 看板 API
GET    /api/v1/dashboard/summary        # 仪表盘摘要
GET    /api/v1/dashboard/trends         # 趋势数据
```

### 3.3 API 响应格式

```json
// 成功
{
  "success": true,
  "data": { ... },
  "timestamp": "2026-05-09T10:30:00+08:00"
}

// 错误
{
  "success": false,
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "Task with id xxx not found"
  },
  "timestamp": "2026-05-09T10:30:00+08:00"
}
```

---

## 四、Web UI 架构

### 4.1 页面结构

```
frontend/src/
├── pages/
│   ├── Dashboard.jsx        # 首页仪表盘（新规划）
│   ├── Tasks.jsx           # ✅ 任务管理
│   ├── DataBrowser.jsx     # ✅ 原生数据浏览
│   ├── Reports.jsx         # 报告查看（规划）
│   ├── KnowledgeBase.jsx   # 知识库浏览（规划）
│   └── Settings.jsx        # 配置中心（规划）
├── components/
│   ├── TaskCard.jsx        # 任务卡片
│   ├── TaskDetail.jsx      # 任务详情（执行日志+产物+预览）
│   ├── RunHistory.jsx      # 执行历史
│   ├── DataPreview.jsx     # 数据预览
│   ├── TrendChart.jsx      # 趋势图表
│   ├── ReportCard.jsx      # 报告卡片
│   └── Navigation.jsx      # 导航栏
└── services/
    └── api.js              # API 客户端封装
```

### 4.2 仪表盘设计 (Dashboard)

```
┌─────────────────────────────────────────────────────────────┐
│ IntelHub · 智能情报平台              [任务] [数据] [报告] [知识库] [配置] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📊 数据新鲜度                                               │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐             │
│  │ 微博    │ │ 36kr   │ │ 政策   │ │ 交易所  │             │
│  │ 5分钟前  │ │ 12分钟前 │ │ 1小时前 │ │ 3小时前  │             │
│  │ ✅ 新鲜  │ │ ✅ 新鲜  │ │ ⚠️ 正常 │ │ ❌ 陈旧  │             │
│  └────────┘ └────────┘ └────────┘ └────────┘             │
│                                                             │
│  📈 今日热点 (TOP 5)                                         │
│  1. [科技] 华为发布新芯片 → 5平台共振                        │
│  2. [财经] A股三大指数集体上涨                               │
│  3. [国际] 中美贸易谈判最新进展                             │
│  4. [产业] 新能源汽车销量数据发布                            │
│  5. [政策] 证监会发布新规                                   │
│                                                             │
│  🔥 跨平台共振                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ "AI" 在 6个平台 同时出现                               │    │
│  │ "芯片" 在 4个平台 同时出现                             │    │
│  │ "华为" 在 5个平台 同时出现                             │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                             │
│  📅 任务状态                                                 │
│  ● 运行中: 热点采集 (3分钟前开始)                           │
│  ● 下次: 政策采集 (1小时23分后)                             │
│  ● 今日完成: 12次任务, 2次失败                               │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 任务详情页（已有，待增强）

当前状态：✅ 任务执行 ✅ 执行日志 ✅ 产物清单 ✅ 数据预览

待增强：
- [ ] 实时执行进度（WebSocket）
- [ ] 任务编辑（直接修改 cron 表达式）
- [ ] 任务对比（历史执行数据图表）
- [ ] 任务复制

---

## 五、数据模型

### 5.1 现有模型

```
scheduled_tasks          # 定时任务
task_runs               # 任务执行记录
```

### 5.2 待新增模型

```python
# app/models/knowledge_stats.py
class KnowledgeStats(db.Model):
    __tablename__ = "knowledge_stats"
    
    id = db.Column(db.String, primary_key=True)
    module = db.Column(db.String)  # company | industry | topics | graph
    entity_count = db.Column(db.Integer)
    last_updated = db.Column(db.DateTime)
    build_duration_seconds = db.Column(db.Float)

# app/models/report.py
class Report(db.Model):
    __tablename__ = "reports"
    
    id = db.Column(db.String, primary_key=True)
    report_type = db.Column(db.String)  # heartbeat | insight | daily
    title = db.Column(db.String)
    content_md = db.Column(db.Text)
    content_json = db.Column(db.Text)
    generated_at = db.Column(db.DateTime)
    trigger_task_id = db.Column(db.String, db.ForeignKey("scheduled_tasks.id"))
```

---

## 六、待实施清单

- [ ] 扩展任务类型：新增 `crawler` / `knowledge` / `report`
- [ ] 重构 `TaskExecutor` 为统一执行器（5种任务类型）
- [ ] 新增知识库 API (`/api/v1/knowledge/*`)
- [ ] 新增报告 API (`/api/v1/reports/*`)
- [ ] 新增数据 API (`/api/v1/data/*`)
- [ ] 新增看板 API (`/api/v1/dashboard/*`)
- [ ] 新增 Dashboard 页面
- [ ] 新增报告查看页面
- [ ] 新增知识库浏览页面
- [ ] 实现 WebSocket 实时推送（替代轮询）
- [ ] 新增报告分发配置（飞书/Webhook）
- [ ] 新增用户认证（API Key 模式）
