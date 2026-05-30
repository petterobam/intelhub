# PLAN-07 Phase 2：数据源扩展

> 对应 PLAN-05 → Phase 2  
> 涉及 REQ：REQ-06（爬虫扩展）/ REQ-05（用户内容订阅源）  
> 预计周期：3-4 周  
> 前置条件：Phase 1 完成（UserProfile、tier 体系存在）

---

## 目标

两件事并行：**提升平台公共数据质量**（扩充爬虫）+ **让 V3 用户能添加自己的内容源**（RSS/B站/YouTube）。

---

## Part A · 平台爬虫扩展（REQ-06）

### A1 · 新增科技类爬虫

**新建目录**：`crawlers/scripts/tech/`

| 文件 | 目标站点 | 采集内容 | 实现方式 |
|------|---------|---------|---------|
| `sspai-crawler.js` | 少数派 | 首页最新文章 | Cheerio 解析 HTML |
| `ithome-crawler.js` | IT之家 | 新闻列表 | Cheerio 解析 HTML |
| `github-trending-crawler.js` | GitHub Trending | 日榜仓库 | 解析 `github.com/trending` |

输出格式（所有爬虫统一）：
```/dev/null/json.json#L1-10
{
  "platform": "sspai",
  "name": "少数派",
  "collected_at": "2026-05-07T10:00:00",
  "items": [
    {"title": "...", "url": "...", "timestamp": "...", "category": "tech"}
  ]
}
```

**修改文件**：`crawlers/hot_topics/runner.py`  
在 `PLATFORMS` 字典追加：
```crawlers/hot_topics/runner.py#L1-10
'sspai': {
    'script': 'sspai-crawler.js',
    'name': '少数派',
    'subdir': 'sspai',
    'scripts_dir': 'tech',   # 新增字段，指向 scripts/tech/
},
'ithome': {
    'script': 'ithome-crawler.js',
    'name': 'IT之家',
    'subdir': 'ithome',
    'scripts_dir': 'tech',
},
'github': {
    'script': 'github-trending-crawler.js',
    'name': 'GitHub Trending',
    'subdir': 'github',
    'scripts_dir': 'tech',
},
```

同时修改 `_run_js_crawler` 方法，让 `SCRIPTS_DIR` 支持 `scripts_dir` 子目录：
```crawlers/hot_topics/runner.py#L1-5
scripts_dir = pcfg.get('scripts_dir', 'hot_topics')
script_path = os.path.join(BASE_DIR, 'scripts', scripts_dir, pcfg['script'])
```

### A2 · 新增财经类爬虫

**新建目录**：`crawlers/scripts/finance/`

| 文件 | 目标站点 | 采集内容 | 实现方式 |
|------|---------|---------|---------|
| `wallstreet-crawler.js` | 华尔街见闻 | 快讯列表 | API 接口 |
| `yicai-crawler.js` | 第一财经 | 新闻列表 | Cheerio 解析 HTML |

**新建 Runner**：`crawlers/finance/runner.py`  
参照 `hot_topics/runner.py` 模式，独立运行，数据存入 `data/raw/finance/`

**修改 Aggregator**：`analysis/aggregate/aggregator.py`  
在 `PLATFORMS` 列表追加 `'finance'`，合并进聚合数据

### A3 · 更新知识库行业分类

**修改文件**：`knowledge_base/builder.py`  
在行业分类逻辑中追加科技/财经关键词映射：
```knowledge_base/builder.py#L1-8
INDUSTRY_KEYWORDS = {
    ...现有分类...,
    '科技创新': ['AI', '大模型', '半导体', 'GitHub', '开源', '算力'],
    '数字媒体': ['少数派', 'IT之家', '科技', 'App'],
    '资本市场': ['华尔街', '第一财经', '股市', '基金', '债券'],
}
```

---

## Part B · 用户内容订阅源（REQ-05）

### B1 · UserSource 数据模型

**新建文件**：`app/models/user_source.py`

```app/models/user_source.py#L1-30
class UserSource(db.Model):
    __tablename__ = 'user_sources'

    id           = Column(String(16), primary_key=True, default=lambda: uuid.uuid4().hex[:8])
    user_id      = Column(String(16), ForeignKey('users.id'), nullable=False, index=True)
    type         = Column(String(16), nullable=False)
    # rss | bilibili | youtube | wechat
    source_id    = Column(String(512), nullable=False)
    # RSS: URL 全路径；Bilibili: UP主UID；YouTube: 频道ID
    display_name = Column(String(128), default='')
    # 用户自定义别名
    enabled      = Column(Boolean, default=True)
    last_fetched = Column(DateTime, nullable=True)
    item_count   = Column(Integer, default=0)
    status       = Column(String(16), default='active')
    # active | error | rate_limited | paused
    last_error   = Column(Text, nullable=True)
    created_at   = Column(DateTime, default=datetime.utcnow)
```

**数据库迁移**：
```/dev/null/sql.sql#L1-15
CREATE TABLE user_sources (
  id           VARCHAR(16) PRIMARY KEY,
  user_id      VARCHAR(16) NOT NULL REFERENCES users(id),
  type         VARCHAR(16) NOT NULL,
  source_id    VARCHAR(512) NOT NULL,
  display_name VARCHAR(128) DEFAULT '',
  enabled      BOOLEAN DEFAULT 1,
  last_fetched DATETIME,
  item_count   INTEGER DEFAULT 0,
  status       VARCHAR(16) DEFAULT 'active',
  last_error   TEXT,
  created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, type, source_id)
);
```

### B2 · 用户源 API

**新建文件**：`app/api/user_sources.py`  
路由前缀：`/api/v1/user-sources`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/` | 列出当前用户所有源 | v3+ |
| POST | `/` | 新增订阅源 | v3+ |
| PUT | `/<id>` | 修改（改名/启停）| v3+，限本人 |
| DELETE | `/<id>` | 删除 | v3+，限本人 |
| POST | `/<id>/fetch` | 立即手动采集 | v3+，限本人 |
| GET | `/quota` | 查看配额（已用/上限）| v3+ |

`POST /` 请求体示例：
```/dev/null/json.json#L1-8
// RSS
{"type": "rss", "source_id": "https://sspai.com/feed", "display_name": "少数派"}

// Bilibili
{"type": "bilibili", "source_id": "12345678", "display_name": "某UP主"}

// YouTube
{"type": "youtube", "source_id": "UCxxxxxx", "display_name": "某频道"}
```

**源数量配额**（在 API 创建时校验）：
```app/api/user_sources.py#L1-5
TIER_SOURCE_LIMITS = {
    'v3': 10,
    'v4': 30,
    'v5': 100,
}
```

### B3 · 用户源适配器

**新建目录**：`crawlers/user_sources/`

**新建文件**：`crawlers/user_sources/base.py` — 基类：
```crawlers/user_sources/base.py#L1-15
class UserSourceAdapter:
    """所有用户源适配器的基类"""
    
    def validate(self, source_id: str) -> dict:
        """验证 source_id 是否有效，返回 {valid: bool, display_name: str, error: str}"""
        raise NotImplementedError
    
    def fetch(self, source_id: str, since: datetime = None) -> list:
        """
        采集最新内容
        返回：[{title, url, content, timestamp, platform, source_display_name}]
        """
        raise NotImplementedError
```

**新建文件**：`crawlers/user_sources/rss.py` — RSS/Atom 适配器（P0，最高优先级）：
```crawlers/user_sources/rss.py#L1-20
import feedparser

class RssAdapter(UserSourceAdapter):
    
    def validate(self, source_id: str) -> dict:
        """尝试 fetch 并解析，确认是有效 RSS"""
        feed = feedparser.parse(source_id)
        if feed.bozo:  # 解析错误
            return {'valid': False, 'error': 'Invalid RSS feed'}
        return {
            'valid': True,
            'display_name': feed.feed.get('title', source_id),
        }
    
    def fetch(self, source_id: str, since: datetime = None) -> list:
        feed = feedparser.parse(source_id)
        items = []
        for entry in feed.entries[:20]:
            pub = entry.get('published_parsed') or entry.get('updated_parsed')
            items.append({
                'title': entry.get('title', ''),
                'url': entry.get('link', ''),
                'content': entry.get('summary', ''),
                'timestamp': datetime(*pub[:6]).isoformat() if pub else '',
                'platform': 'rss',
            })
        return items
```

**新建文件**：`crawlers/user_sources/bilibili.py` — B站 UP主适配器（P1）：
- 调用 `https://api.bilibili.com/x/space/arc/search?mid={uid}&ps=10`
- 返回最新投稿列表

**新建文件**：`crawlers/user_sources/youtube.py` — YouTube 适配器（P2）：
- 调用 YouTube Data API v3：`/youtube/v3/search?channelId={id}&order=date`
- 需要用户在系统设置中配置 YouTube API Key（或管理员统一配置）

**新建文件**：`crawlers/user_sources/dispatcher.py` — 根据 type 分发到对应适配器：
```crawlers/user_sources/dispatcher.py#L1-10
ADAPTERS = {
    'rss': RssAdapter,
    'bilibili': BilibiliAdapter,
    'youtube': YoutubeAdapter,
}

def get_adapter(source_type: str) -> UserSourceAdapter:
    cls = ADAPTERS.get(source_type)
    if not cls:
        raise ValueError(f'Unsupported source type: {source_type}')
    return cls()
```

### B4 · 用户源独立调度器

> 核心原则：与 APScheduler 主队列完全隔离，用户源失败不影响平台健康

**新建文件**：`app/scheduler/user_source_scheduler.py`

```app/scheduler/user_source_scheduler.py#L1-30
import threading
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix='user-src')

def fetch_user_source(source: UserSource):
    """采集单个用户源，结果写入 data/users/{user_id}/sources/{source.id}/"""
    adapter = get_adapter(source.type)
    try:
        items = adapter.fetch(source.source_id, since=source.last_fetched)
        # 保存到用户目录
        out_dir = os.path.join(DATA_DIR, 'users', source.user_id, 'sources', source.id)
        os.makedirs(out_dir, exist_ok=True)
        ts = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
        with open(os.path.join(out_dir, f'{ts}.json'), 'w') as f:
            json.dump({'items': items, 'fetched_at': ts}, f, ensure_ascii=False)
        # 更新 DB 状态
        source.last_fetched = datetime.utcnow()
        source.item_count = len(items)
        source.status = 'active'
        source.last_error = None
    except Exception as e:
        source.status = 'error'
        source.last_error = str(e)[:500]
    db.session.commit()

def schedule_all_user_sources(scheduler):
    """每6小时扫描一次所有激活的用户源"""
    def _run():
        sources = UserSource.query.filter_by(enabled=True, status='active').all()
        for src in sources:
            _executor.submit(fetch_user_source, src)
    
    scheduler.add_job(_run, 'cron', hour='*/6', id='user_sources_fetch')
```

### B5 · 个性化报告合并用户源

**修改文件**：`analysis/personalized/generator.py`  
在报告生成时，额外读取用户源数据并合并到上下文中：

```analysis/personalized/generator.py#L1-15
def _load_user_source_items(user_id: str) -> list:
    """加载用户所有订阅源的最新数据"""
    sources_dir = os.path.join(DATA_DIR, 'users', user_id, 'sources')
    if not os.path.exists(sources_dir):
        return []
    items = []
    for source_id in os.listdir(sources_dir):
        source_dir = os.path.join(sources_dir, source_id)
        files = sorted(glob.glob(os.path.join(source_dir, '*.json')), reverse=True)
        if files:
            data = json.load(open(files[0]))
            for item in data.get('items', []):
                item['_source'] = 'user_subscription'   # 标注来源
                item['_source_id'] = source_id
            items.extend(data.get('items', []))
    return items
```

在报告 Prompt 中追加用户源内容段落，并在报告中明确标注「以下来自你的个人订阅」。

### B6 · 前端「我的数据源」页面

**新建文件**：`frontend/src/pages/MyDataSources.jsx`

页面功能：
- 列出已添加的所有源（显示类型图标、名称、最后采集时间、条目数、状态）
- 「添加数据源」按钮 → 弹窗：选择类型、输入 source_id（URL/UID/频道ID）→ 调用 validate API 预览名称 → 确认添加
- 每行操作：启停、立即采集、删除
- 页面底部显示配额：`已使用 3/10 个数据源`

侧边栏：`v3+` 用户显示「我的数据源」入口

---

## 文件清单汇总

| 操作 | 文件路径 |
|------|---------|
| **新建** | `crawlers/scripts/tech/sspai-crawler.js` |
| **新建** | `crawlers/scripts/tech/ithome-crawler.js` |
| **新建** | `crawlers/scripts/tech/github-trending-crawler.js` |
| **新建** | `crawlers/scripts/finance/wallstreet-crawler.js` |
| **新建** | `crawlers/scripts/finance/yicai-crawler.js` |
| **新建** | `crawlers/finance/runner.py` |
| **新建** | `crawlers/user_sources/base.py` |
| **新建** | `crawlers/user_sources/rss.py` |
| **新建** | `crawlers/user_sources/bilibili.py` |
| **新建** | `crawlers/user_sources/youtube.py` |
| **新建** | `crawlers/user_sources/dispatcher.py` |
| **新建** | `app/models/user_source.py` |
| **新建** | `app/api/user_sources.py` |
| **新建** | `app/scheduler/user_source_scheduler.py` |
| **新建** | `frontend/src/pages/MyDataSources.jsx` |
| **修改** | `crawlers/hot_topics/runner.py` — 支持 scripts_dir 子目录 + 新增平台 |
| **修改** | `analysis/aggregate/aggregator.py` — 追加 finance 来源 |
| **修改** | `analysis/personalized/generator.py` — 合并用户源数据 |
| **修改** | `knowledge_base/builder.py` — 行业分类追加关键词 |
| **修改** | `app/scheduler/__init__.py` — 注册 user_source_scheduler |
| **修改** | `frontend/src/App.jsx` — 追加「我的数据源」路由 |

---

## 验收标准

1. **A**（平台爬虫）：`python3 -c "from crawlers.hot_topics.runner import HotTopicsRunner; HotTopicsRunner().run_platform('sspai')"` 输出 success，`data/raw/hot_topics/sspai/` 下出现 JSON 文件
2. **B1-B2**（用户源API）：V3 用户调用 `POST /api/v1/user-sources` 添加一个 RSS URL，`user_sources` 表中出现记录
3. **B3**（RSS适配器）：`RssAdapter().fetch('https://sspai.com/feed')` 返回条目列表
4. **B4**（调度器）：手动调用 `fetch_user_source(source)`，`data/users/{user_id}/sources/{source_id}/` 下出现 JSON 文件
5. **B5**（报告合并）：V3 用户添加 RSS 源后触发个人报告，报告中含有「个人订阅」来源标注

---

## 注意事项

- **RSS 优先**：B站/YouTube 适配器可以推迟，先把 RSS 做完上线，覆盖 90% 的场景
- **feedparser 依赖**：需在 `requirements.txt` 追加 `feedparser>=6.0`
- **YouTube API 限额**：YouTube Data API 免费额度每天 10,000 单位，需要 Admin 配置 API Key，不能每个用户单独配
