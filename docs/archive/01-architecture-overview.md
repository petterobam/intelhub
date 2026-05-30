# IntelHub - 智能情报与投资分析平台

## 项目概述

IntelHub 是一个面向投资的智能情报平台，整合多源数据采集、自动化分析和报告生成，支持通过 Web 界面管理所有定时任务和数据看板。

## 现有系统分析

### 当前 7 个定时任务

| 任务名称 | 调度 | 核心功能 | 数据来源 |
|---|---|---|---|
| auto-browser-crawler-hourly | 每 90 分钟 | 热点平台浏览器采集 | 36kr/虎嗅/微博/知乎/东方财富等 |
| self-optimization-analyzer-hourly | 每 60 分钟 | 健康检查 + 优化建议 | crawler-notes/data/* |
| insight-report-publisher | 每天 9:00/21:00 | 跨平台洞察报告生成 | logs/latest.md + crawler-data-recent.json |
| 投资分析心跳 | 每天 9:00/13:00/16:00/22:00 | 市场情绪量化分析 | 巨潮资讯 + 政策数据 |
| 巨潮资讯采集（500+） | 工作日 8:00/12:00/16:00 | 财报公告批量采集 | 巨潮资讯网 |
| 交易所公告采集 | 工作日 9:00/13:00/15:00 | 沪深北港四所公告 | 各交易所官网 |
| 政策监控（10大机构） | 每 3 小时 | 央行/银保监/国务院等 | 10大监管机构官网 |

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         Web UI (Frontend)                       │
│    Dashboard │ 任务管理 │ 知识库浏览 │ 报告查看 │ 配置中心      │
└──────────────┬──────────────────────────────────────────────────┘
               │ HTTP/REST API
┌──────────────▼──────────────────────────────────────────────────┐
│                     Flask API Server                            │
│  /api/tasks    /api/crawlers   /api/reports   /api/kb          │
└──────┬─────────┬───────────────┬─────────────┬─────────────────┘
       │         │               │             │
┌──────▼──┐ ┌────▼────┐ ┌────────▼────┐ ┌─────▼──────┐
│ Scheduler│ │ Crawlers│ │  Analysis   │ │ Knowledge  │
│ 调度引擎 │ │ 爬虫模块 │ │  分析模块   │ │  知识库    │
└────┬───┘ └────┬────┘ └──────┬─────┘ └─────┬──────┘
     │          │             │             │
┌────▼──────────▼─────────────▼─────────────▼─────────┐
│              Data Layer (数据层)                    │
│  原始数据 │ 去重数据 │ 聚合数据 │ 报告 │ 知识条目   │
└─────────────────────────────────────────────────────┘
```

## 模块划分

### 1. 爬虫模块 (crawlers/)

四大采集类别，共享统一的数据写入接口：

- **hot-topics/** — 热点平台采集
  - 36kr、虎嗅、微博、知乎、东方财富、澎湃、网易、环球、胡锡进观察
  - 技术栈: Hermes Browser (browser_navigate/snapshot)
  - 输出: `data/raw/{platform}-latest.json`

- **policy/** — 政策监控采集
  - 央行(PBC)、银保监(BOC)、国务院、发改委、财政部、证监会等 10+ 机构
  - 技术栈: Node.js 脚本 + Hermes Browser
  - 输出: `data/raw/policy/{org}/{date}/`

- **exchange/** — 交易所公告
  - 上交所、深交所、北交所、港交所
  - 技术栈: Python requests + Hermes Browser 兜底
  - 输出: `data/raw/exchange/{exchange}/{date}/`

- **financial/** — 金融数据
  - 巨潮资讯（500+ 核心股票财报）
  - 技术栈: Hermes Browser 批量采集
  - 输出: `data/raw/cninfo/{date}/`

### 2. 分析模块 (analysis/)

数据管道：Raw → Deduplicate → Normalize → Aggregate → Analyze

- **aggregate/** — 数据聚合
  - 合并多平台数据，统一时间戳和字段格式
  - 输出: `data/processed/all-platforms-aggregated.json`

- **trends/** — 趋势分析
  - 关键词提取、话题分类、热度计算
  - 输出: `reports/trend-*.json`

- **resonance/** — 跨平台共振分析
  - 识别多平台同时出现的热点（关键词跨平台出现频次）
  - 输出: `reports/cross-platform-insights.json`

- **heartbeat/** — 心跳分析
  - 定期数据新鲜度检查 + 快速洞察生成
  - 每小时运行，健康分告警

### 3. 知识库 (knowledge-base/)

对原始数据进行结构化存储和主题组织：

- **topics/** — 按主题分类（国际/体育/娱乐/财经/科技/游戏/教育）
- **industry/** — 行业分析知识
- **company/** — 公司研究知识
- **graph/** — 实体关系图谱

### 4. 报告系统 (reports/)

- **daily/** — 每日简报（政策 + 市场）
- **insight/** — 深度洞察报告（每天 9:00、21:00）
- **heartbeat/** — 心跳分析快照

### 5. 调度引擎 (scheduler/)

通过 Web API 与 Hermes Cron 集成：

- 创建 / 更新 / 暂停 / 删除定时任务
- 手动触发立即执行
- 查看任务历史和状态
- 支持技能绑定（skill_manage 管理的技能）

## 数据流向

```
[浏览器/Hermes]
    │ browser_navigate → 采集原始 HTML
    ▼
[爬虫节点 crawlers/]
    │ extract → 结构化 JSON
    ▼
[data/raw/]
    │ dedupe + normalize
    ▼
[data/processed/]
    │ aggregate
    ▼
[analysis/] ──────→ [knowledge-base/]
    │                      │
    │ trends + resonance   │ 结构化入库
    ▼                      ▼
[reports/]           [知识条目]
    │
    │ publish
    ▼
[Feishu Webhook]
```

## 技术栈

- **后端**: Flask + SQLAlchemy + APScheduler
- **前端**: React + TailwindCSS
- **数据存储**: JSON 文件 + SQLite（任务配置）
- **调度**: APScheduler（进程内） + Hermes Cron（Agent 级）
- **浏览器自动化**: Hermes Browser 工具
- **部署**: Docker Compose

## 项目目录结构

```
intel-hub/
├── app/                    # Flask 应用
│   ├── api/                # REST API 端点
│   ├── scheduler/          # 调度引擎
│   ├── tasks/              # 任务执行逻辑
│   ├── models/             # 数据模型
│   └── utils/              # 工具函数
├── crawlers/               # 爬虫模块
│   ├── hot-topics/         # 热点平台
│   ├── policy/             # 政策监控
│   ├── exchange/           # 交易所公告
│   └── financial/          # 金融数据
├── analysis/               # 分析模块
│   ├── aggregate/          # 数据聚合
│   ├── trends/             # 趋势分析
│   ├── resonance/          # 跨平台共振
│   └── heartbeat/           # 健康心跳
├── knowledge-base/          # 知识库
├── reports/                # 报告输出
├── data/                    # 数据存储
│   ├── raw/                 # 原始数据
│   ├── processed/           # 处理后数据
│   └── freshness/          # 新鲜度状态
├── scripts/                 # 工具脚本
│   ├── cron_wrappers/       # 定时任务包装器
│   └── utilities/           # 通用工具
├── frontend/                # React 前端
├── docker/                  # Docker 配置
└── docs/                    # 设计文档
    ├── 01-architecture-overview.md   ← 本文档
    ├── 02-crawler-system-design.md
    ├── 03-analysis-system-design.md
    ├── 04-api-design.md
    └── 05-task-scheduler-design.md
```

## 下一步

- [ ] 确认技术栈选择（Flask vs FastAPI）
- [ ] 设计 API 规范
- [ ] 定义数据模型
- [ ] 实现调度引擎与 Hermes 的集成
