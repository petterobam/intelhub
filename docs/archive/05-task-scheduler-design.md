# 任务调度系统设计

## 双层调度架构

IntelHub 采用 Hermes Cron + APScheduler 双层调度：

```
┌─────────────────────────────────────────────────────┐
│              Hermes Agent (Layer 1)                 │
│  ┌─────────────────────────────────────────────┐   │
│  │  cron jobs: auto-browser-crawler           │   │
│  │          insight-report-publisher           │   │
│  │          投资分析心跳                         │   │
│  │          ...                               │   │
│  └──────────────────┬──────────────────────────┘   │
│                     │ cron job triggers            │
│                     ▼                              │
│  ┌─────────────────────────────────────────────┐   │
│  │        IntelHub API Server (Layer 2)        │   │
│  │         APScheduler (in-process)          │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐   │   │
│  │  │ Crawler  │ │ Analysis │ │ Report   │   │   │
│  │  │ Executor │ │ Executor │ │ Executor │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘   │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### Layer 1: Hermes Cron Jobs (现有)

- 管理复杂 AI 推理类任务（洞察分析、投资研判）
- 通过飞书推送结果
- 技能绑定执行
- 交付到 feishu channel

### Layer 2: APScheduler (新增)

- 管理结构化脚本执行（爬虫、数据聚合）
- 通过 Web UI 完全可控
- 支持 cron / interval / date 三种调度类型
- 任务状态持久化到 SQLite

## 任务分类

| 类型 | 执行层 | 典型任务 | 执行时间 |
|---|---|---|---|
| AI 分析类 | Hermes Cron | 投资心跳、洞察报告 | 9:00/13:00/16:00/22:00 |
| 爬虫采集类 | APScheduler | 热点采集、政策监控、交易所公告 | 每 90m/3h/工作日 |
| 数据处理类 | APScheduler | 数据聚合、去重、标准化 | 采集后自动触发 |
| 监控告警类 | APScheduler | 新鲜度检查、健康评分 | 每 60m |

## 任务配置模型

`app/models/task.py`

```python
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    module = Column(String, nullable=False)      # hot_topics / policy / exchange / ...
    script = Column(String, nullable=False)         # run_36kr.sh
    schedule_type = Column(String)                 # cron / interval / date
    schedule_config = Column(JSON)                 # {"minutes": 90} / {"hour": 9, "minute": 0}

    enabled = Column(Boolean, default=True)
    last_run = Column(DateTime)
    next_run = Column(DateTime)
    run_count = Column(Integer, default=0)
    success_count = Column(Integer, default=0)
    fail_count = Column(Integer, default=0)

    deliver_to = Column(String, default="local")    # local / feishu
    notify_on_failure = Column(Boolean, default=False)

    created_at = Column(DateTime)
    updated_at = Column(DateTime)
```

## 任务执行器

`app/scheduler/executor.py`

```python
import subprocess
import threading
from datetime import datetime

class TaskExecutor:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.active_tasks = {}

    def execute(self, task: ScheduledTask) -> dict:
        """执行单个任务，返回结果"""
        task_id = task.id
        start_time = datetime.now()

        self.active_tasks[task_id] = {
            "start_time": start_time,
            "status": "running"
        }

        script_path = os.path.join(
            self.base_dir,
            "scripts/cron_wrappers",
            task.script
        )

        result = subprocess.run(
            ["bash", script_path],
            capture_output=True,
            text=True,
            timeout=600,  # 10 分钟超时
            cwd=self.base_dir
        )

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        outcome = {
            "task_id": task_id,
            "status": "success" if result.returncode == 0 else "failed",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_seconds": duration,
            "stdout": result.stdout[-5000:],   # 限制日志长度
            "stderr": result.stderr[-2000:],
            "exit_code": result.returncode
        }

        self.active_tasks[task_id] = outcome
        return outcome
```

## 任务包装器 (cron_wrappers/)

每个包装器对应一个脚本，统一放在 `scripts/cron_wrappers/`：

### run_hot_topics.sh
```bash
#!/bin/bash
cd "$(dirname "$0")/../.."
python3 -c "
import asyncio
from crawlers.hot_topics.runner import HotTopicsRunner
runner = HotTopicsRunner()
asyncio.run(runner.run_all())
"
```

### run_policy_monitor.sh
```bash
#!/bin/bash
cd "$(dirname "$0")/../.."
bash crawlers/policy/scripts/collect_all.sh
```

### run_exchange.sh
```bash
#!/bin/bash
cd "$(dirname "$0")/../.."
python3 crawlers/exchange/collectors/sse_collector.py
python3 crawlers/exchange/collectors/szse_collector.py
```

### run_cninfo.sh
```bash
#!/bin/bash
cd "$(dirname "$0")/../.."
python3 crawlers/financial/cninfo_collector.py --batch 500
```

### run_aggregate.sh
```bash
#!/bin/bash
cd "$(dirname "$0")/../.."
python3 analysis/aggregate/aggregator.py
```

### run_heartbeat.sh
```bash
#!/bin/bash
cd "$(dirname "$0")/../.."
python3 analysis/heartbeat/heartbeat_analyzer.py
python3 scripts/check_freshness.py
```

### run_insight_report.sh
```bash
#!/bin/bash
cd "$(dirname "$0")/../.."
python3 analysis/reports/insight_generator.py --format markdown
python3 analysis/reports/insight_generator.py --format json
```

## 调度注册 (从现有 Hermes Cron 迁移)

现有 7 个 Hermes Cron Job，迁移策略：

1. **保留 Hermes Cron** → 用于 AI 分析类（投资心跳、洞察报告）
2. **迁移到 APScheduler** → 用于脚本执行类（爬虫采集、数据处理）

Web UI 提供一键迁移功能，生成对应的 `ScheduledTask` 记录。

## 监控与告警

- 任务执行日志 → `data/execution_logs/{task_id}/{timestamp}.log`
- 失败告警 → 飞书 Webhook
- 连续失败 3 次 → 自动暂停任务
- 新鲜度超时 → 自动触发重采
