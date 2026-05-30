# PLAN-04: 部署与 CLI 工具

> 本文档定义 IntelHub 的部署方案、Docker 配置和 CLI 工具设计。

---

## 一、现有启动方式

```bash
# 后端
cd ~/workspace/intel-hub && python3 run.py --port 5003

# 前端
cd ~/workspace/intel-hub/frontend && npx vite --port 3000

# 一键启动
./dev.sh start
```

---

## 二、部署方案

### 2.1 本地开发（当前）

```bash
# 目录结构
intel-hub/
├── run.py              # 后端入口
├── run.sh              # CLI 入口
├── dev.sh             # 开发环境一键脚本
├── app/               # Flask 应用
├── frontend/          # React 前端
├── data/              # 数据目录（SQLite + JSON）
├── crawlers/          # 爬虫模块
├── analysis/          # 分析模块
├── knowledge_base/     # 知识库模块
└── reports/           # 报告输出
```

### 2.2 Docker 部署（规划）

```bash
# docker/docker-compose.yml
services:
  backend:
    build: ./docker/backend
    ports: ["5003:5003"]
    volumes:
      - ./data:/app/data
      - ./reports:/app/reports
    environment:
      - FLASK_ENV=production
      - LLM_BACKEND=${LLM_BACKEND}
      - LLM_API_KEY=${LLM_API_KEY}
      - LLM_BASE_URL=${LLM_BASE_URL}
    depends_on: []

  frontend:
    build: ./docker/frontend
    ports: ["3000:80"]
    depends_on:
      - backend

  # 可选: Redis 用于缓存和消息队列
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

---

## 三、CLI 工具设计

### 3.1 统一 CLI 入口

```bash
python3 run.py --help

用法: run.py [命令] [选项]

命令:
  server     启动 Web 服务 (backend + frontend)
  crawl      执行爬虫任务
  analyze    执行分析任务
  report     生成报告
  kb         知识库管理
  task       任务管理
  status     查看系统状态

示例:
  python3 run.py server --port 5003 --dev
  python3 run.py crawl hot_topics
  python3 run.py analyze heartbeat
  python3 run.py status
```

### 3.2 CLI 模块设计

```
run.py                    # CLI 入口
│
commands/
├── __init__.py
├── server.py             # server 命令
├── crawl.py              # crawl 命令
├── analyze.py            # analyze 命令
├── report.py             # report 命令
├── kb.py                 # knowledge base 命令
├── task.py               # task 命令
└── status.py             # status 命令
```

### 3.3 各命令详细设计

```python
# commands/crawl.py
"""
用法: python3 run.py crawl [module] [--platform PLATFORM]

示例:
  python3 run.py crawl hot_topics          # 执行热点采集
  python3 run.py crawl policy              # 执行政策采集
  python3 run.py crawl hot_topics --platform weibo   # 只采集微博
  python3 run.py crawl all                 # 执行所有爬虫
"""

# commands/analyze.py
"""
用法: python3 run.py analyze [type] [--context CONTEXT]

示例:
  python3 run.py analyze heartbeat         # 心跳分析
  python3 run.py analyze insight            # 深度洞察
  python3 run.py analyze trends            # 趋势分析
  python3 run.py analyze resonance         # 共振分析
  python3 run.py analyze all               # 执行所有分析
"""

# commands/report.py
"""
用法: python3 run.py report [type] [--time AM|PM]

示例:
  python3 run.py report insight --time am   # 生成早间洞察
  python3 run.py report insight --time pm   # 生成晚间洞察
  python3 run.py report heartbeat           # 心跳报告
  python3 run.py report daily               # 每日报告
"""

# commands/kb.py
"""
用法: python3 run.py kb [action]

示例:
  python3 run.py kb build                   # 构建全量知识库
  python3 run.py kb build --module company   # 只构建公司库
  python3 run.py kb search "华为"           # 搜索
  python3 run.py kb stats                   # 查看统计
  python3 run.py kb rebuild                 # 全量重建
"""

# commands/task.py
"""
用法: python3 run.py task [action]

示例:
  python3 run.py task list                  # 列出所有任务
  python3 run.py task run <task_id>         # 手动触发任务
  python3 run.py task pause <task_id>       # 暂停任务
  python3 run.py task resume <task_id>      # 恢复任务
  python3 run.py task logs <task_id>        # 查看日志
  python3 run.py task create --name xxx --cron "0 9 * * *"  # 创建任务
"""

# commands/status.py
"""
用法: python3 run.py status [--verbose]

示例:
  python3 run.py status                     # 概览
  python3 run.py status --verbose           # 详细
  python3 run.py status --json             # JSON 输出（供脚本使用）
"""
```

---

## 四、脚本封装规范

### 4.1 cron_wrapper 脚本规范

所有定时任务通过 `scripts/cron_wrappers/` 下的 shell 脚本执行：

```bash
# 规范模板
#!/bin/bash
# {任务名称} - {简短描述}
# 调度: {频率}

set -e  # 任何命令失败立即退出
set -o pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/.logs"
mkdir -p "$LOG_DIR"

TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
LOG_FILE="$LOG_DIR/{task_name}_$TIMESTAMP.log"

exec > >(tee -a "$LOG_FILE")
exec 2>&1

echo "[START] {task_name} at $(date)"

# 执行逻辑
cd "$PROJECT_ROOT"
python3 -c "
import sys, os, logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
sys.path.insert(0, os.getcwd())
# ... 执行代码 ...
"

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "[DONE] {task_name} at $(date)"
else
    echo "[ERROR] {task_name} failed with exit code $EXIT_CODE"
fi

exit $EXIT_CODE
```

### 4.2 现有 cron_wrapper 清单

| 脚本 | 对应任务 | 状态 |
|------|---------|------|
| `run_hot_topics.sh` | 热点采集 | ✅ 已实现 |
| `run_policy.sh` | 政策采集 | ✅ 已实现 |
| `run_exchange.sh` | 交易所采集 | ✅ 已实现 |
| `run_financial.sh` | 巨潮采集 | ✅ 已实现 |
| `run_aggregate.sh` | 数据聚合 | ⬜ 待实现 |
| `run_heartbeat_analysis.sh` | 投资心跳 | ⬜ 待实现 |
| `run_insight_report.sh` | 洞察报告 | ⬜ 待实现 |
| `run_knowledge_base.sh` | 知识库构建 | ⬜ 待实现 |
| `run_system_heartbeat.sh` | 系统心跳 | ⬜ 待实现 |

---

## 五、环境配置

### 5.1 .env 配置项

```bash
# LLM 配置
LLM_BACKEND=anthropic              # anthropic | openai | ollama
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://open.bigmodel.cn/api/anthropic/
LLM_MODEL=glm-4.7

# 应用配置
FLASK_ENV=development
FLASK_DEBUG=1
DATABASE_URL=sqlite:///data/intel_hub.db

# 爬虫配置
CRAWLER_TIMEOUT=300
CRAWLER_MAX_RETRIES=2

# Hermes 配置（可选）
HERMES_API_KEY=your_hermes_key
HERMES_BASE_URL=http://localhost:8080

# 通知配置（可选）
FEISHU_WEBHOOK=your_feishu_webhook
EMAIL_SMTP=smtp.example.com
EMAIL_TO=notify@example.com
```

### 5.2 配置管理策略

- **开发环境:** `.env` 文件（已实现）
- **生产环境:** 环境变量覆盖 `.env`
- **敏感信息:** 存放在 `~/.hermes/auth.json`，通过 `hermes auth` 管理

---

## 六、监控与日志

### 6.1 日志结构

```
logs/
├── backend.log           # Flask 后端日志
├── frontend.log          # 前端构建日志
├── crawler/
│   ├── hot_topics_20260509.log
│   ├── policy_20260509.log
│   └── ...
└── analysis/
    ├── heartbeat_20260509.log
    ├── insight_20260509.log
    └── ...
```

### 6.2 健康检查端点

```
GET /api/v1/health
Response: {
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "services": {
    "database": "ok",
    "scheduler": "running",
    "llm": "ok"
  },
  "data_freshness": {
    "hot_topics": "5m ago",
    "policy": "1h ago",
    "exchange": "3h ago",
    "financial": "2h ago"
  }
}
```

---

## 七、待实施清单

- [ ] 实现 `run.py` 统一 CLI 入口（argparse）
- [ ] 实现 `commands/` 各子命令模块
- [ ] 实现 `run_aggregate.sh` cron_wrapper
- [ ] 实现 `run_knowledge_base.sh` cron_wrapper
- [ ] 实现 `run_system_heartbeat.sh` cron_wrapper
- [ ] 完善 `docker/docker-compose.yml`
- [ ] 添加 health check 端点增强（services 状态 + data_freshness）
- [ ] 添加日志轮转（logrotate 配置）
- [ ] 添加 Prometheus 指标端点（`/metrics`）
- [ ] 添加 Grafana 看板配置
