# PLAN-08 Phase 3：用户私有知识库

> 对应 PLAN-05 → Phase 3  
> 涉及 REQ：REQ-07（用户私有知识库）/ REQ-09（数据质量与隔离边界）  
> 预计周期：4-5 周  
> 前置条件：Phase 1 完成（用户目录结构 `data/users/{user_id}/` 已存在，日报已写入其中）

---

## 目标

用户积累的历史日报自动沉淀为可搜索的个人知识库。AI 对话时能引用「过去一周华为有什么动态」这类历史问题，且每个用户的 KB 完全隔离。

---

## 任务清单

### T1 · 用户目录规范化

在 Phase 1 中已创建 `data/users/{user_id}/reports/daily/`，这里正式确认完整的目录规范，并在应用启动时自动创建骨架。

**修改文件**：`app/utils/user_dirs.py`（新建）

```app/utils/user_dirs.py#L1-20
"""用户目录管理 — 统一的路径计算与初始化"""
import os

BASE_DATA_DIR = os.environ.get('DATA_DIR', os.path.join(os.path.dirname(__file__), '../../data'))

def user_dir(user_id: str) -> str:
    return os.path.join(BASE_DATA_DIR, 'users', user_id)

def user_reports_dir(user_id: str) -> str:
    return os.path.join(user_dir(user_id), 'reports', 'daily')

def user_sources_dir(user_id: str) -> str:
    return os.path.join(user_dir(user_id), 'sources')

def user_kb_dir(user_id: str) -> str:
    return os.path.join(user_dir(user_id), 'kb')

def user_uploads_dir(user_id: str) -> str:
    return os.path.join(user_dir(user_id), 'uploads')

def ensure_user_dirs(user_id: str):
    """创建用户完整目录骨架"""
    for d in [user_reports_dir(user_id), user_sources_dir(user_id),
              user_kb_dir(user_id), user_uploads_dir(user_id)]:
        os.makedirs(d, exist_ok=True)

def assert_within_user_dir(user_id: str, path: str):
    """安全校验：确保 path 在用户目录内（防路径遍历）"""
    base = os.path.abspath(user_dir(user_id))
    target = os.path.abspath(path)
    if not target.startswith(base + os.sep):
        raise PermissionError(f'Path escape detected: {path}')
```

所有涉及用户文件操作的地方统一 import 这个模块，禁止直接拼接字符串路径。

---

### T2 · KnowledgeBaseManager 支持用户模式

**修改文件**：`knowledge_base/kb_manager.py`

现有构造函数：
```knowledge_base/kb_manager.py#L1-5
def __init__(self, kb_root=None, raw_root=None):
    self.kb_root = kb_root or KB_ROOT
    self.raw_root = raw_root or RAW_ROOT
```

修改为支持 `user_id` 参数，自动切换到用户目录：
```knowledge_base/kb_manager.py#L1-10
def __init__(self, kb_root=None, raw_root=None, user_id=None):
    if user_id:
        from app.utils.user_dirs import user_kb_dir, user_dir
        self.kb_root = user_kb_dir(user_id)
        self.raw_root = user_dir(user_id)   # 用户目录下的 reports/ + sources/ 作为原始数据
        self.user_id = user_id
        self.mode = 'user'
    else:
        self.kb_root = kb_root or KB_ROOT
        self.raw_root = raw_root or RAW_ROOT
        self.user_id = None
        self.mode = 'platform'
```

**关键约束**：`mode='user'` 时，`ingest()`、`search()` 等方法只操作用户目录，不读写平台公共数据。

---

### T3 · 个人 KB 构建器

**新建文件**：`knowledge_base/user_kb_builder.py`  
专门处理用户数据（日报 Markdown + 用户源 JSON），区别于平台的 `builder.py`

构建逻辑：

```knowledge_base/user_kb_builder.py#L1-40
class UserKBBuilder:
    """从用户日报和订阅源数据构建个人知识库"""
    
    def build(self, user_id: str) -> dict:
        kb_dir = user_kb_dir(user_id)
        os.makedirs(kb_dir, exist_ok=True)
        
        # 1. 加载历史日报
        reports = self._load_reports(user_id)
        
        # 2. 加载用户源数据
        source_items = self._load_source_items(user_id)
        
        # 3. 实体提取（基于用户的 interest_tags）
        tags = self._get_user_tags(user_id)
        entities = self._extract_entities(reports + source_items, tags)
        
        # 4. 构建时间线（每个实体跨日期的动态）
        timeline = self._build_timeline(entities)
        
        # 5. 构建话题索引
        topics = self._build_topics(reports + source_items)
        
        # 6. 写入 KB 文件
        self._write_kb(kb_dir, timeline, topics, entities)
        
        return {'status': 'success', 'entity_count': len(entities), 'report_count': len(reports)}
    
    def _extract_entities(self, items: list, tags: list) -> dict:
        """
        基于 interest_tags 中的关键词，提取相关条目
        返回：{entity_name: [相关条目列表]}
        """
        result = {}
        for tag in tags:
            kw = tag['value']
            matched = [i for i in items if kw.lower() in (i.get('title','') + i.get('content','')).lower()]
            if matched:
                result[kw] = matched
        return result
    
    def _build_timeline(self, entities: dict) -> dict:
        """
        返回：{entity_name: [{date, title, url, source}]}
        按日期排序
        """
        timeline = {}
        for entity, items in entities.items():
            sorted_items = sorted(items, key=lambda x: x.get('timestamp', ''), reverse=True)
            timeline[entity] = sorted_items
        return timeline
```

KB 输出文件结构：
```/dev/null/tree.txt#L1-8
data/users/{user_id}/kb/
├── index.json              # KB 元数据（最后更新时间、实体数、报告数）
├── topics/
│   └── topic_index.json   # 话题索引（与平台同格式）
├── timeline/
│   ├── 华为.json          # 该实体的历史条目
│   └── 新能源.json
└── entities.json           # 实体关系（简化版，无需图谱）
```

---

### T4 · 日报生成后自动触发 KB 构建

**修改文件**：`analysis/personalized/generator.py`

在 `generate_personal_report()` 函数末尾追加：
```analysis/personalized/generator.py#L1-10
# 报告写入后，异步触发 KB 增量更新
import threading
from knowledge_base.user_kb_builder import UserKBBuilder

def _async_kb_build(user_id):
    try:
        UserKBBuilder().build(user_id)
    except Exception as e:
        logger.warning("User KB build failed for %s: %s", user_id, e)

threading.Thread(target=_async_kb_build, args=(user_id,), daemon=True).start()
```

---

### T5 · AI 对话注入个人 KB 工具

**修改文件**：`app/api/chat.py`

在 `_create_chat_mcp_server()` 函数中，根据用户 tier 条件注入个人 KB 工具：

```app/api/chat.py#L1-25
# 在 _create_chat_mcp_server(user) 中追加（v4+ 用户）：

if user and TIER_ORDER.index(user.tier or 'free') >= TIER_ORDER.index('v4'):
    
    @mcp_server.tool(name='chat_search_user_kb')
    async def chat_search_user_kb(query: str) -> str:
        """搜索用户个人知识库"""
        kb = KnowledgeBaseManager(user_id=user.id)
        results = kb.search(query, top_k=5)
        return json.dumps(results, ensure_ascii=False)
    
    @mcp_server.tool(name='chat_user_timeline')
    async def chat_user_timeline(entity: str) -> str:
        """查询某个实体（公司/人物）在用户KB中的历史动态"""
        timeline_path = os.path.join(user_kb_dir(user.id), 'timeline', f'{entity}.json')
        if not os.path.exists(timeline_path):
            return json.dumps({'entity': entity, 'items': [], 'message': '暂无该实体的历史记录'})
        with open(timeline_path, 'r') as f:
            data = json.load(f)
        return json.dumps({'entity': entity, 'items': data[:20]}, ensure_ascii=False)
```

---

### T6 · 用户 KB API

**新建文件**：`app/api/user_kb.py`  
路由前缀：`/api/v1/user-kb`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/stats` | KB 概览（实体数、报告数、最后更新）| v4+ |
| GET | `/search?q=` | 全文搜索 | v4+ |
| GET | `/topics` | 话题索引 | v4+ |
| GET | `/timeline/<entity>` | 实体历史时间线 | v4+ |
| POST | `/build` | 手动触发 KB 重建 | v4+ |
| GET | `/export` | 下载 Markdown 压缩包 | v4+ |

**`GET /export` 实现**：将 `data/users/{user_id}/kb/timeline/` 下所有 JSON 转成 Markdown 文件，打包成 zip 返回（Content-Disposition: attachment）

---

### T7 · 前端「个人知识库」页面

**新建文件**：`frontend/src/pages/UserKnowledge.jsx`

页面结构：
- **概览 Tab**：统计卡片（关注实体数、历史报告数、最后构建时间）+ 「重新构建」按钮
- **话题 Tab**：话题列表，点击展开相关条目
- **时间线 Tab**：左侧实体列表（来自 interest_tags），右侧显示选中实体的历史条目（时间轴样式）
- **搜索 Tab**：输入关键词，展示跨话题搜索结果

侧边栏：`v4+` 用户显示「个人知识库」入口（和现有的平台「知识库」区分，标注「我的」）

### T8 · 数据隔离中间件（REQ-09 落地）

**修改文件**：`app/utils/auth.py`  
新增用于文件操作的安全校验 helper：

```app/utils/auth.py#L1-10
def require_own_user_data(user_id: str):
    """在涉及用户数据文件的 API 中调用，确保操作的是当前登录用户的数据"""
    current = g.current_user
    if current.role != 'admin' and current.id != user_id:
        from app.utils.helpers import error_response
        raise PermissionError('无权访问其他用户数据')
```

**规范**：凡是读写 `data/users/{user_id}/` 的 API，都必须调用 `assert_within_user_dir()` + `require_own_user_data()`，两道验证缺一不可。

---

## 文件清单汇总

| 操作 | 文件路径 |
|------|---------|
| **新建** | `app/utils/user_dirs.py` |
| **新建** | `knowledge_base/user_kb_builder.py` |
| **新建** | `app/api/user_kb.py` |
| **新建** | `frontend/src/pages/UserKnowledge.jsx` |
| **修改** | `knowledge_base/kb_manager.py` — 支持 user_id 参数 |
| **修改** | `analysis/personalized/generator.py` — 生成后触发 KB 构建 |
| **修改** | `app/api/chat.py` — v4+ 用户注入个人 KB 工具 |
| **修改** | `app/utils/auth.py` — 增加 require_own_user_data |
| **修改** | `frontend/src/App.jsx` — 追加「个人知识库」路由 |

---

## 数据库迁移 SQL

本阶段无新数据表，改动都在文件系统层面。

---

## 验收标准

1. **T1**：`ensure_user_dirs('abc123')` 在 `data/users/abc123/` 下创建完整目录骨架
2. **T2**：`KnowledgeBaseManager(user_id='abc')` 的 `kb_root` 指向用户目录，不指向平台 KB
3. **T3**：`UserKBBuilder().build('abc')` 执行后，`data/users/abc/kb/timeline/` 下出现以 interest_tag 命名的 JSON 文件
4. **T4**：V4 用户个人报告生成完成后 1-2 秒内，KB 自动触发构建（日志可见）
5. **T5**：V4 用户在 AI 对话中发送「华为最近一周有什么动态？」，AI 调用 `chat_user_timeline` 工具并返回基于个人 KB 的答案
6. **T8**：用户 A 尝试访问 `/api/v1/user-kb/stats` 时，server 返回 A 自己的 KB，不返回 B 的

---

## 隔离原则备忘

```
写数据时：os.path.abspath(path).startswith(user_dir(user_id))  ← 必须校验
读数据时：user_id 从 g.current_user.id 取，不接受客户端传入
API 入参：URL 中出现 user_id 时，要么校验等于当前用户，要么限 admin
```
