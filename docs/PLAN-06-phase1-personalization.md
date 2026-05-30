# PLAN-06 Phase 1：个性化基础

> 对应 PLAN-05 → Phase 1  
> 涉及 REQ：REQ-01（用户分层）/ REQ-02（兴趣标签）/ REQ-03（个性化报告）/ REQ-04（H5页面）/ REQ-10（邮件升级）  
> 预计周期：3-4 周  
> 前置条件：无（可直接开始）

---

## 目标

让 V2 用户可以设置兴趣标签，每天收到只包含自己关注内容的日报邮件，点开是一个精美的 H5 页面。

---

## 任务清单（按顺序执行）

### T1 · 用户分层体系

**改哪里**：`app/models/user.py`

在 `User` 模型追加两个字段：

```app/models/user.py#L1-5
tier = Column(String(16), nullable=False, default='free')
# 取值：free | v1 | v2 | v3 | v4 | v5
tier_expires_at = Column(DateTime, nullable=True)
# NULL 表示永久有效；有值时需检查是否过期
```

**改哪里**：`app/utils/auth.py`  
新增权限装饰器，供后续所有 tier-gated API 使用：

```app/utils/auth.py#L1-10
TIER_ORDER = ['free', 'v1', 'v2', 'v3', 'v4', 'v5']

def tier_required(min_tier: str):
    """用法：@tier_required('v2')"""
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            user = g.current_user
            # 检查 tier 等级
            if TIER_ORDER.index(user.tier or 'free') < TIER_ORDER.index(min_tier):
                return error_response(403, f'此功能需要 {min_tier} 及以上权限')
            # 检查是否过期
            if user.tier_expires_at and user.tier_expires_at < datetime.utcnow():
                return error_response(403, '订阅已过期，请续费')
            return f(*args, **kwargs)
        return wrapped
    return decorator
```

**改哪里**：`app/api/auth.py` → `to_dict()` 和 `/me` 接口返回 `tier` 字段  
**改哪里**：`scripts/seed_db.py` → admin 用户默认 `tier='v5'`

**数据库迁移**：
```/dev/null/sql.sql#L1-3
ALTER TABLE users ADD COLUMN tier VARCHAR(16) NOT NULL DEFAULT 'free';
ALTER TABLE users ADD COLUMN tier_expires_at DATETIME;
UPDATE users SET tier = 'v5' WHERE role = 'admin';
```

**前端改动**：`frontend/src/App.jsx`  
- `api.getUser()` 返回值增加 `tier` 字段
- 侧边栏菜单根据 tier 显示/隐藏（`v2` 以下不显示「我的偏好」）

**Admin 管理**：`frontend/src/pages/Users.jsx`  
- 用户列表增加 `tier` 列（展示）
- 点击用户 → 弹窗可修改 tier + 设置到期时间

---

### T2 · 用户兴趣配置（UserProfile）

**新建文件**：`app/models/user_profile.py`

```app/models/user_profile.py#L1-20
class UserProfile(db.Model):
    __tablename__ = 'user_profiles'

    user_id      = Column(String(16), ForeignKey('users.id'), primary_key=True)
    interest_tags= Column(JSON, default=list)
    # 格式：[{"type": "company", "value": "华为"}, {"type": "topic", "value": "新能源"}]
    # type 枚举：company | person | topic | sector
    platforms    = Column(JSON, default=list)
    # 格式：["weibo", "zhihu", "36kr"]  — 从平台支持列表中勾选
    report_time  = Column(String(8), default='08:00')
    # 格式："HH:MM"，24小时制，Asia/Shanghai
    push_mode    = Column(String(16), default='summary')
    # summary（只推highlights）| full（全文）
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

**新建文件**：`app/api/profile.py`  
路由前缀：`/api/v1/profile`

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/interests` | 获取当前用户兴趣配置 | login |
| PUT | `/interests` | 保存兴趣标签 + 平台偏好 | v2+ |
| GET | `/push-settings` | 获取推送设置 | login |
| PUT | `/push-settings` | 保存推送时间和模式 | v1+ |

`PUT /interests` 请求体：
```/dev/null/json.json#L1-8
{
  "interest_tags": [
    {"type": "company", "value": "华为"},
    {"type": "topic", "value": "新能源"}
  ],
  "platforms": ["weibo", "zhihu", "36kr"]
}
```

**新建文件**：`data/tag_library.json`（平台维护的标签词库）
```/dev/null/json.json#L1-20
{
  "company": ["华为", "苹果", "特斯拉", "比亚迪", "字节跳动", "腾讯", "阿里", "百度", "OpenAI", "英伟达"],
  "person": ["马斯克", "黄仁勋", "任正非", "雷军", "Sam Altman"],
  "topic": ["新能源", "AI大模型", "半导体", "房地产", "消费复苏", "出海"],
  "sector": ["科技", "金融", "医疗", "消费", "能源", "制造"]
}
```

**新建 API**：`GET /api/v1/profile/tag-library` → 返回上面词库  
**前端**：新建页面 `frontend/src/pages/Preferences.jsx`
- 从 `/tag-library` 拉取词库
- 按分类展示可选标签（多选 chip 组件）
- 平台勾选（checkbox grid，显示平台图标）
- 推送时间选择器
- 保存按钮调用 `PUT /interests` + `PUT /push-settings`
- 在 sidebar 增加「我的偏好」入口（`v2+` 显示）

**Admin 词库管理**：  
- `GET /api/v1/admin/tag-library` — 获取
- `PUT /api/v1/admin/tag-library` — 更新（写入 JSON 文件）
- Admin Settings 页面增加「标签词库」Tab

---

### T3 · 个性化报告生成

**新建目录**：`analysis/personalized/`

**新建文件**：`analysis/personalized/filter.py`  
职责：从平台聚合数据中按用户标签筛选相关条目

```analysis/personalized/filter.py#L1-20
def filter_items_by_tags(items: list, interest_tags: list, platforms: list) -> list:
    """
    items: 来自 data/processed/all-platforms-aggregated.json 的条目列表
    interest_tags: [{"type": "company", "value": "华为"}, ...]
    platforms: ["weibo", "zhihu"] 或 [] 表示不限
    
    返回：相关条目列表，每条带 match_tags 字段标注匹配原因
    """
    keywords = [tag['value'] for tag in interest_tags]
    result = []
    for item in items:
        # 平台过滤
        if platforms and item.get('_platform') not in platforms:
            continue
        # 关键词匹配（title + content）
        text = (item.get('title', '') + ' ' + item.get('content', '')).lower()
        matched = [kw for kw in keywords if kw.lower() in text]
        if matched:
            item['match_tags'] = matched
            result.append(item)
    return result
```

**新建文件**：`analysis/personalized/generator.py`  
职责：组装 Prompt，调用 AI 引擎生成个人日报

关键逻辑：
1. 调用 `filter_items_by_tags()` 筛选相关条目（最多取 top 50）
2. 构建 system_prompt，注入用户兴趣标签作为报告焦点
3. 调用 `AnalysisEngine.analyze(task_type='personal_daily', ...)`
4. 将 Markdown 报告写入 `reports/users/{user_id}/daily/{date}.md`
5. 调用 H5 生成器（T4）生成静态页
6. 返回 `{report_path, h5_path, highlights}`

**新建文件**：`analysis/personalized/scheduler.py`  
职责：扫描所有 v2+ 用户，按各自的 `report_time` 触发生成

```analysis/personalized/scheduler.py#L1-15
def schedule_personalized_reports(scheduler):
    """在 APScheduler 中注册，每小时检查一次需要生成报告的用户"""
    def _run():
        now_hhmm = datetime.now(tz=ZoneInfo('Asia/Shanghai')).strftime('%H:%M')
        profiles = UserProfile.query.join(User).filter(
            User.tier.in_(['v2', 'v3', 'v4', 'v5']),
            UserProfile.report_time == now_hhmm,
        ).all()
        for profile in profiles:
            generate_personal_report(profile.user_id)
    
    scheduler.add_job(_run, 'cron', minute=0, id='personalized_reports')
```

**注意**：`generate_personal_report` 要捕获单个用户的异常，不能因一个用户失败影响其他用户。

---

### T4 · 静态 H5 报告页

**新建目录**：`app/templates/reports/`

**新建文件**：`app/templates/reports/daily.html`  
要求：纯 inline CSS，无外部 JS 依赖，移动端优先（max-width: 680px），支持深色背景（与 IntelHub 品牌色一致）

页面结构（Jinja2 模板）：
```/dev/null/html.html#L1-30
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ title }} — IntelHub</title>
  <!-- inline CSS only -->
</head>
<body>
  <header>IntelHub 日报 · {{ date }}</header>
  
  <!-- Highlights 摘要（3-5条） -->
  <section class="highlights">
    {% for h in highlights %}
    <div class="highlight-item">
      <span class="platform-badge">{{ h.platform }}</span>
      <p>{{ h.text }}</p>
      <a href="{{ h.url }}">原文 →</a>
    </div>
    {% endfor %}
  </section>

  <!-- 完整报告内容（Markdown 转 HTML） -->
  <section class="full-report">{{ content | safe }}</section>

  <!-- Footer 引流 -->
  <footer>
    <a href="https://intelhub.ai">订阅 IntelHub，每日智能情报</a>
  </footer>
</body>
</html>
```

**新建文件**：`app/utils/report_renderer.py`  
职责：接收 Markdown 报告 + highlights，渲染 HTML，写入 `static/reports/`

```app/utils/report_renderer.py#L1-15
def render_report_page(
    report_md: str,
    highlights: list,
    output_path: str,
    title: str = '智能日报',
    access_token: str = None,   # 个人报告传 token，公共报告传 None
) -> str:
    """渲染并写入 HTML 文件，返回相对 URL 路径"""
    ...
```

**新建路由**：`app/api/` 增加 report viewer

```app/api/__init__.py#L1-5
# 在 Flask app 注册：
@app.route('/r/<report_id>')
def view_report(report_id):
    # 1. 查 reports 表获取 html_path + scope + access_token
    # 2. 个人报告验证 ?token=xxx 参数
    # 3. 返回静态 HTML 文件内容
```

**Report 模型变更**：`app/models/report.py` 新增字段：
```app/models/report.py#L1-8
user_id      = Column(String(16), ForeignKey('users.id'), nullable=True)
# NULL = 平台公共报告；有值 = 用户个人报告
scope        = Column(String(16), default='platform')
# platform | personal
html_path    = Column(String(512), nullable=True)
# 生成的 H5 文件相对路径
access_token = Column(String(64), nullable=True)
# 个人报告的访问 token（7天有效，用 JWT 生成）
```

---

### T5 · 邮件模板升级

**新建文件**：`app/templates/email/daily_report.html`

邮件结构（inline CSS，Outlook 兼容）：
- 顶部：IntelHub 品牌 header
- 主体：3-5 条 highlights，每条含来源平台名 + 摘要文字
- CTA 按钮：「查看完整报告」→ 链接到 H5 页面（带 token）
- 底部：退订链接 + 版权

**修改文件**：`app/services/email_sender.py`  
新增方法：
```app/services/email_sender.py#L1-10
def send_daily_report(
    to: str,
    display_name: str,
    report_date: str,
    highlights: list,      # [{"platform": "微博", "text": "...", "url": "..."}]
    h5_url: str,           # 完整 H5 页面 URL（含 token）
) -> bool:
    """渲染 daily_report.html 模板并发送"""
```

**修改文件**：`analysis/personalized/generator.py`  
报告生成完成后调用 `email_sender.send_daily_report()`

---

## 文件清单汇总

| 操作 | 文件路径 |
|------|---------|
| **修改** | `app/models/user.py` — 增加 tier / tier_expires_at |
| **修改** | `app/utils/auth.py` — 增加 tier_required 装饰器 |
| **修改** | `app/api/auth.py` — /me 返回 tier |
| **修改** | `app/models/report.py` — 增加 user_id / scope / html_path / access_token |
| **修改** | `app/services/email_sender.py` — 增加 send_daily_report |
| **修改** | `app/__init__.py` — 注册 /r/<report_id> 路由 |
| **修改** | `scripts/seed_db.py` — admin 默认 tier=v5 |
| **修改** | `frontend/src/App.jsx` — sidebar 按 tier 控制 |
| **修改** | `frontend/src/pages/Users.jsx` — tier 展示与编辑 |
| **新建** | `app/models/user_profile.py` |
| **新建** | `app/api/profile.py` |
| **新建** | `app/utils/report_renderer.py` |
| **新建** | `app/templates/reports/daily.html` |
| **新建** | `app/templates/email/daily_report.html` |
| **新建** | `analysis/personalized/__init__.py` |
| **新建** | `analysis/personalized/filter.py` |
| **新建** | `analysis/personalized/generator.py` |
| **新建** | `analysis/personalized/scheduler.py` |
| **新建** | `data/tag_library.json` |
| **新建** | `frontend/src/pages/Preferences.jsx` |
| **新建目录** | `reports/users/` |
| **新建目录** | `static/reports/` |

---

## 数据库迁移 SQL

```/dev/null/migration.sql#L1-10
-- users 表扩展
ALTER TABLE users ADD COLUMN tier VARCHAR(16) NOT NULL DEFAULT 'free';
ALTER TABLE users ADD COLUMN tier_expires_at DATETIME;
UPDATE users SET tier = 'v5' WHERE role = 'admin';

-- 新建 user_profiles 表
CREATE TABLE user_profiles (
  user_id VARCHAR(16) PRIMARY KEY REFERENCES users(id),
  interest_tags JSON DEFAULT '[]',
  platforms JSON DEFAULT '[]',
  report_time VARCHAR(8) DEFAULT '08:00',
  push_mode VARCHAR(16) DEFAULT 'summary',
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- reports 表扩展
ALTER TABLE reports ADD COLUMN user_id VARCHAR(16) REFERENCES users(id);
ALTER TABLE reports ADD COLUMN scope VARCHAR(16) DEFAULT 'platform';
ALTER TABLE reports ADD COLUMN html_path VARCHAR(512);
ALTER TABLE reports ADD COLUMN access_token VARCHAR(64);
```

---

## 验收标准

1. **T1**：Admin 在用户管理页将某用户 tier 设为 v2，该用户登录后侧边栏出现「我的偏好」
2. **T2**：V2 用户进入「我的偏好」，选择「华为」「新能源」标签并保存，刷新后配置保留
3. **T3**：手动触发 `generate_personal_report(user_id)`，`reports/users/{user_id}/daily/` 下出现 Markdown 文件，内容只涉及所选标签
4. **T4**：`static/reports/users/{user_id}/` 下出现对应 HTML 文件，浏览器打开显示正常
5. **T5**：用户收到邮件，包含 3-5 条 highlights，点击「查看完整报告」跳转到 H5 页面

---

## 依赖关系

```
T1（tier字段）→ T2（UserProfile）→ T3（个性化报告生成）
                                  → T4（H5页面）← T3 生成完调用
                                  → T5（邮件）  ← T3 生成完调用
```

T1 和 T4 的 HTML 模板可以并行开始，互不依赖。
