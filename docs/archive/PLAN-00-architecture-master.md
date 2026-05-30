# IntelHub 架构总览 - 系统设计蓝图

> 本文档定义 IntelHub 的整体架构、功能边界和模块职责。是所有子系统的设计基准。

---

## 一、项目定位

IntelHub 是一个**面向投资的智能情报平台**，将多源数据采集、自动化分析和报告生成整合为统一系统，支持 Web 界面管理所有定时任务和数据看板。

**核心价值链:**

```
多源爬虫采集 → 数据清洗聚合 → LLM 深度分析 → 投资洞察报告 → 知识库沉淀
```

---

## 二、三层架构

```
┌──────────────────────────────────────────────────────────┐
│                     展示层 (Presentation)                  │
│   Web UI (React) │ API Explorer │ 报告阅读器 │ 配置面板   │
├──────────────────────────────────────────────────────────┤
│                     平台层 (Platform)                      │
│   任务调度 │ REST API │ 权限管理 │ 通知系统 │ CLI 工具   │
├──────────────────────────────────────────────────────────┤
│                     智能层 (Intelligence)                 │
│   数据聚合 │ 趋势分析 │ 共振分析 │ LLM 洞察 │ 报告生成  │
├──────────────────────────────────────────────────────────┤
│                     数据层 (Data)                         │
│   爬虫采集 │ 知识库管理 │ 原始数据 │ 处理数据 │ 报告存储  │
└──────────────────────────────────────────────────────────┘
```

---

## 三、五大子系统

### 子系统 1: 数据采集 (Crawlers)

负责从各平台采集原始数据，是整个系统的数据源头。

| 模块 | 职责 | 入口脚本 |
|------|------|---------|
| `hot_topics` | 9平台热点数据 (微博/抖音/知乎/36kr/虎嗅/东方财富/澎湃/网易/环球网) | `run_hot_topics.sh` |
| `policy` | 10大监管机构政策 (央行/证监会/财政部等) | `run_policy.sh` |
| `exchange` | 沪深北港四所公告采集 | `run_exchange.sh` |
| `financial` | 500+A股巨潮资讯批量采集 | `run_financial.sh` |

**采集策略优先级:** API > Hermes Browser > Node.js 脚本 > Python requests

**数据输出:** 统一 JSON → `data/raw/{category}/{platform}-{timestamp}.json`

---

### 子系统 2: 知识库 (Knowledge Base)

负责数据的结构化存储、检索和管理。

| 模块 | 职责 |
|------|------|
| `company/` | 上市公司基本信息库 |
| `industry/` | 行业分类知识图谱 |
| `topics/` | 热门话题索引与标签体系 |
| `graph/` | 实体关系图谱 (公司-行业-话题) |

**知识库构建流程:** 原始数据 → 去重 → 标准化 → 实体抽取 → 关系建模 → 索引 → 检索

---

### 子系统 3: 分析引擎 (Analysis Engine)

负责数据的多维度分析，生成投资洞察。

| 分析类型 | 触发频率 | 核心逻辑 | 输出 |
|---------|---------|---------|------|
| 心跳分析 (Heartbeat) | 每小时 | 数据新鲜度 + 快速洞察 | `reports/heartbeat/` |
| 共振分析 (Resonance) | 每小时 | 跨平台热点共振检测 | `reports/cross-platform-resonance.json` |
| 趋势分析 (Trends) | 每小时 | 话题分类 + 热度评分 | `reports/trend-analysis.json` |
| 深度洞察 (Insight) | 每天2次 | LLM 多轮深度分析报告 | `reports/insight/` |
| 自优化 (Optimization) | 每小时 | 系统健康检查 + 建议 | 日志 |

**LLM 引擎:** Anthropic SDK + GLM 兼容端点 (`https://open.bigmodel.cn/api/anthropic`)

---

### 子系统 4: 报告系统 (Reports)

负责结构化报告的生成与分发。

| 报告类型 | 触发 | 内容 |
|---------|------|------|
| 每日早报 | 9:00 | 前夜+早晨热点 + 政策要点 + 今日提示 |
| 盘中心跳 | 13:00/16:00 | 实时热点 + 资金动向 |
| 晚间洞察 | 21:00 | 全天数据深度分析 + LLM 洞察 |
| 投资预警 | 触发式 | 政策突变 + 重大事件 |

---

### 子系统 5: 平台调度 (Platform Scheduler)

负责任务的配置、执行和监控。

- **调度器:** APScheduler (in-process) + Hermes Cron (跨进程)
- **任务类型:** `script`(脚本) / `analysis`(分析) / `crawler`(爬虫) / `report`(报告)
- **执行器:** 异步线程池，支持超时控制 (10分钟) 和并发限制
- **监控:** 执行日志、产物清单、数据预览、执行历史

---

## 四、现有定时任务清单

| 任务名 | ID | 类型 | 频率 | 核心产出 |
|--------|-----|------|------|---------|
| 热点平台采集 | `e7b02b44` | script | 每90分钟 | 9平台热点 JSON |
| 政策监控采集 | `21a3ebc7` | script | 每3小时 | 10机构政策 JSON |
| 交易所公告采集 | `3f1699ab` | script | 工作日9/13/15点 | 四所公告 JSON |
| 巨潮资讯批量采集 | `968d8ad2` | script | 工作日8/12/16点 | 500+股票公告 |
| 数据聚合 | `b559c102` | script | 每60分钟 | 全平台聚合 JSON |
| 投资分析心跳 | `bd96be79` | analysis | 9/13/16/22点 | LLM 洞察分析 |
| 洞察报告生成 | `38d9f6f3` | analysis | 9/21点 | 深度洞察报告 |
| 系统自优化 | `338b8a2e` | analysis | 每60分钟 | 优化建议 |
| 系统心跳 | `2dc36015` | script | 每30分钟 | 健康检查 |

---

## 五、数据流向图

```
data/raw/
├── hot_topics/          ← 热点数据 (9平台 JSON)
│   ├── {platform}/
│   │   └── {platform}-{timestamp}.json
│   └── {platform}-latest.json
├── policy/              ← 政策数据 (10机构 JSON)
├── exchange/             ← 交易所公告 (4所 JSON)
└── financial/           ← 巨潮资讯 (500+股票)

data/processed/
└── all-platforms-aggregated.json   ← 全平台聚合

data/freshness/
└── {module}-freshness.json         ← 数据新鲜度追踪

knowledge_base/
├── company/             ← 上市公司库
├── industry/            ← 行业知识图谱
├── topics/               ← 话题索引
└── graph/               ← 实体关系图谱

reports/
├── heartbeat/           ← 心跳报告
├── insight/             ← 深度洞察报告
├── daily/               ← 每日报告
└── trend-analysis.json  ← 趋势分析结果
```

---

## 六、技术栈

| 层级 | 技术选型 |
|------|---------|
| 前端 | React + Vite + TailwindCSS |
| 后端 | Flask + SQLAlchemy + APScheduler |
| 数据库 | SQLite (`data/intel_hub.db`) |
| 爬虫 | Node.js (迁移脚本) + Hermes Browser + Python requests |
| LLM | Anthropic SDK + GLM 兼容端点 |
| 部署 | Docker (可选) / 直接部署 |

---

## 七、后续计划

| 计划编号 | 文档 | 内容 |
|---------|------|------|
| PLAN-01 | 数据管道 | 爬虫架构 + 知识库构建方案 |
| PLAN-02 | 分析引擎 | LLM 多轮分析 + 各分析器设计 |
| PLAN-03 | 平台层 | 调度系统 + API + WebUI |
| PLAN-04 | 部署与CLI | Docker + 一键部署 + CLI工具 |
