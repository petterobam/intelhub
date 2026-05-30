# PLAN-01: 数据管道 - 爬虫架构与知识库构建

> 本文档定义数据采集（爬虫）系统和知识库管理系统的完整架构。

---

## 一、爬虫子系统

### 1.1 目录结构

```
crawlers/
├── scripts/                      # 迁移的 JS 爬虫脚本（Hermes 来源）
│   ├── hot_topics/              # 热点平台 (9个)
│   │   ├── weibo-crawler.js
│   │   ├── douyin-hot-crawler.js
│   │   ├── zhihu-crawler.js
│   │   ├── 36kr-crawler.js
│   │   ├── huxiu-crawler.js
│   │   ├── eastmoney-crawler.js
│   │   ├── paper-crawler.js
│   │   ├── wangyi-browser-crawler.js
│   │   └── huanqiu-crawler.js
│   ├── policy/                  # 政策监控 (10个机构)
│   │   ├── policy_pbc.js        # 中国人民银行
│   │   ├── policy_csrc.js       # 证监会
│   │   ├── policy_mof.js        # 财政部
│   │   ├── policy_boc.js        # 中国银行
│   │   ├── policy_gov.js        # 国务院
│   │   ├── policy_safe.js       # 外管局
│   │   ├── policy_ndrc.js       # 发改委
│   │   ├── policy_miit.js       # 工信部
│   │   ├── policy_stats.js      # 统计局
│   │   └── policy_sasac.js      # 国资委
│   ├── exchange/                # 交易所 (4个)
│   │   ├── exchange-sse.js      # 上交所
│   │   ├── exchange-szse.js      # 深交所
│   │   ├── exchange-bse.js       # 北交所
│   │   └── exchange-hkex.js      # 港交所
│   ├── financial/               # 巨潮资讯
│   │   ├── cninfo-hermes-crawler.js
│   │   └── cninfo-stocks-expanded.config
│   └── utils/                    # 共享工具
│       ├── deduplicate-data.py
│       └── normalize-fields.py
│
├── hot_topics/                   # 热点采集 Runner (Python)
│   └── runner.py                 # 调用 JS 脚本 + JS优先+requests降级
├── policy/                        # 政策采集 Runner
│   └── runner.py                 # 浏览器注入 + requests 降级
├── exchange/                      # 交易所采集 Runner
│   └── runner.py                 # API + HTML 混合
├── financial/                    # 财务数据 Runner
│   └── runner.py                 # 500+股票批量采集
├── hot-topics/                   # ⚠️ 重复目录，待清理（已迁移到 hot_topics/）
└── base/                          # 爬虫基类和共享工具
    ├── __init__.py
    ├── base_runner.py            # Runner 基类
    ├── data_standardizer.py      # 数据标准化
    └── freshness_tracker.py      # 新鲜度追踪
```

### 1.2 Runner 基类设计

所有 Runner 继承 `BaseRunner`，统一接口：

```python
# crawlers/base/base_runner.py
class BaseRunner:
    """爬虫 Runner 基类 - 统一接口"""

    PLATFORMS = {}  # 平台配置字典

    def run_all(self) -> List[dict]:
        """执行所有平台采集，返回结果列表"""
        raise NotImplementedError

    def run_single(self, platform: str) -> dict:
        """执行单个平台采集"""
        raise NotImplementedError

    def _call_node_script(self, script: str, cwd: str = None) -> dict:
        """调用 Node.js 脚本，返回 parsed JSON"""
        ...

    def _call_requests(self, url: str, method: str = 'GET', **kwargs) -> dict:
        """requests 降级方案"""
        ...

    def _deduplicate(self, items: list, key: str = 'id') -> list:
        """基于 key 去重"""
        ...

    def _save_output(self, items: list, filename: str, subdir: str = '') -> str:
        """保存 JSON 到 data/raw/{subdir}/"""
        ...

    def get_freshness(self) -> dict:
        """返回各平台数据新鲜度"""
        ...
```

### 1.3 采集策略（降级链路）

```
┌─────────────────────────────────────────────┐
│             采集执行流程                      │
├─────────────────────────────────────────────┤
│  1. 尝试 Node.js 脚本                         │
│     ↓ 失败                                   │
│  2. 尝试 Hermes Browser (browser_navigate)   │
│     ↓ 失败                                   │
│  3. 尝试 Python requests (HTML解析)           │
│     ↓ 失败                                   │
│  4. 静默失败，记录日志，不阻塞其他平台           │
└─────────────────────────────────────────────┘
```

### 1.4 统一数据格式

所有爬虫输出统一 JSON 格式：

```json
{
  "items": [
    {
      "id": "平台唯一ID",
      "title": "标题",
      "summary": "摘要（可选）",
      "url": "原文链接",
      "source": "平台名称",
      "author": "作者（可选）",
      "timestamp": "2026-05-09T10:30:00+08:00",
      "hotness": 85,
      "tags": ["科技", "投资"],
      "raw_fields": {}
    }
  ],
  "meta": {
    "platform": "微博热搜",
    "collected_at": "2026-05-09T10:30:00+08:00",
    "item_count": 50,
    "collector": "weibo-crawler.js"
  }
}
```

### 1.5 新鲜度追踪

每次采集后更新 `data/freshness/{module}-freshness.json`：

```json
{
  "hot_topics": {
    "weibo": {"file": "weibo-latest.json", "age_minutes": 5, "status": "fresh"},
    "douyin": {"file": "douyin-latest.json", "age_minutes": 8, "status": "fresh"},
    "36kr": {"file": "36kr-latest.json", "age_minutes": 12, "status": "fresh"}
  },
  "policy": {...},
  "exchange": {...},
  "financial": {...}
}
```

新鲜度阈值：
- **新鲜 (fresh):** < 120 分钟
- **正常 (normal):** 120-360 分钟
- **陈旧 (stale):** > 360 分钟

---

## 二、知识库子系统

### 2.1 目录结构

```
knowledge_base/
├── kb_manager.py          # 知识库管理器（核心入口）
├── builder.py             # 知识库构建器
│
├── company/               # 上市公司知识库
│   ├── company_index.json       # 公司索引 (id → 基本信息)
│   ├── financial_reports/       # 财报数据
│   │   └── {stock_code}_{year}Q{quarter}.json
│   └── announcements/          # 公告摘要
│       └── {stock_code}_latest.json
│
├── industry/              # 行业知识图谱
│   ├── industry_index.json      # 行业分类索引
│   ├── sector_map.json          # 板块映射 (概念股分类)
│   └── industry_chain.json      # 产业链关系
│
├── topics/               # 话题知识库
│   ├── topic_index.json         # 话题索引
│   ├── hot_topics/              # 热点话题聚合
│   │   └── {date}_hot_topics.json
│   └── topic_timeline/           # 话题时间线
│       └── {topic_id}_timeline.json
│
└── graph/                # 实体关系图谱
    ├── entities.json           # 实体库
    ├── relations.json          # 关系库
    └── triplets.json          # 知识三元组
```

### 2.2 知识库构建流程

```
原始数据 (data/raw/)
    │
    ├─→ [去重]   deduplicate()     → 去除重复 items
    │
    ├─→ [标准化] standardize()      → 统一字段格式 + 类型归一化
    │
    ├─→ [实体抽取] extract_entities()
    │     - 从 title/summary 中抽取公司名、行业、人物、地区
    │     - 使用正则 + 词典匹配
    │
    ├─→ [关系建模] build_relations()
    │     - 公司-行业 (所属关系)
    │     - 公司-公司 (母子/竞品关系)
    │     - 话题-公司 (影响关系)
    │
    ├─→ [索引更新] update_index()
    │     - 更新各模块索引文件
    │     - 维护话题-时间线
    │
    └─→ [知识三元组] build_triplets()
          - (主体, 关系, 客体) 三元组格式
          - 供 LLM 分析使用
```

### 2.3 知识库管理器接口

```python
# knowledge_base/kb_manager.py
class KnowledgeBaseManager:
    """知识库统一管理器"""

    def __init__(self, kb_root: str):
        self.kb_root = kb_root

    # === 查询接口 ===
    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """全文检索，返回相关实体"""
        ...

    def get_company(self, code_or_name: str) -> dict:
        """获取公司信息"""
        ...

    def get_topic(self, topic: str) -> dict:
        """获取话题详情（含时间线）"""
        ...

    def get_industry(self, industry: str) -> dict:
        """获取行业信息"""
        ...

    def get_related_companies(self, topic: str) -> list[dict]:
        """获取与话题相关的公司列表"""
        ...

    # === 写入接口 ===
    def ingest(self, source_module: str, items: list[dict]) -> dict:
        """摄入新的原始数据，触发完整构建流程"""
        ...

    def update_index(self, module: str) -> bool:
        """增量更新索引"""
        ...

    def rebuild(self, module: str = None) -> dict:
        """全量重建指定模块"""
        ...
```

### 2.4 实体抽取规则

```python
# knowledge_base/entity_extractor.py
ENTITY_PATTERNS = {
    "company": [
        r'[\u4e00-\u9fa5]{2,6}(股份|集团|公司|有限|控股)',
        r'[\u4e00-\u9fa5]{2,6}A?股',
    ],
    "industry": [
        r'新能源|半导体|医药|消费|金融|地产|科技|制造',
        r'汽车|家电|钢铁|煤炭|电力|银行|保险|证券',
    ],
    "person": [
        r'[\u4e00-\u9fa5]{2,4}(总|董|秘|长|总|经理)',
    ],
    "region": [
        r'[\u4e00-\u9fa5]{2,4}(省|市|区|县|国)',
    ]
}
```

---

## 三、定时任务 → 子系统映射

| Cron Job | 子系统 | 触发模块 |
|---------|--------|---------|
| 热点采集 (每90分钟) | 爬虫 | `crawlers/hot_topics/runner.py` |
| 政策采集 (每3小时) | 爬虫 | `crawlers/policy/runner.py` |
| 交易所采集 (工作日) | 爬虫 | `crawlers/exchange/runner.py` |
| 巨潮采集 (工作日) | 爬虫 | `crawlers/financial/runner.py` |
| 数据聚合 (每60分钟) | 知识库 | `knowledge_base/builder.py` |
| 知识库构建 (每2小时) | 知识库 | `knowledge_base/kb_manager.py` |

---

## 四、待实施清单

- [ ] 清理 `crawlers/hot-topics/` 重复目录
- [ ] 实现 `crawlers/base/base_runner.py` 基类，4个 Runner 统一继承
- [ ] 实现 `knowledge_base/builder.py` 知识库构建器
- [ ] 实现 `knowledge_base/kb_manager.py` 知识库管理器
- [ ] 实现 `knowledge_base/entity_extractor.py` 实体抽取
- [ ] 实现 `knowledge_base/graph_builder.py` 图谱构建
- [ ] 新增"知识库"定时任务
- [ ] 新增"知识库管理"API 端点
- [ ] 前端新增"知识库浏览"页面
