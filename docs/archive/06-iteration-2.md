# IntelHub Iteration 2 - 任务详情 & 数据浏览器

## 概述

本轮迭代聚焦三个核心需求：
1. **任务详情页** -- 执行日志持久化、产物清单、数据预览
2. **任务历史记录** -- 每次执行的完整记录列表
3. **原生数据浏览器** -- 树形目录、按天聚合、文本预览

---

## Phase 1: 任务详情页 & 执行日志持久化

### 1.1 后端：新增 TaskRun 模型

文件：`app/models/task_run.py`

```
TaskRun 表：
  id            VARCHAR(36) PK
  task_id       VARCHAR(36) FK -> scheduled_tasks.id
  status        VARCHAR(16)  # running | done | failed | timeout
  started_at    DATETIME
  finished_at   DATETIME
  duration_ms   INTEGER
  exit_code     INTEGER
  stdout        TEXT          # 完整输出日志
  stderr        TEXT          # 错误输出
  artifacts     TEXT          # JSON: [{path, size, type, name}]
  trigger_type  VARCHAR(16)  # manual | scheduled
  created_at    DATETIME
```

文件：`app/models/task_run.py`
- TaskRun 模型，与 ScheduledTask 一对多关系
- `to_dict()` 序列化方法

### 1.2 后端：改造执行引擎

文件：`app/api/tasks.py`

- `_run_script_async()` 改造：
  - 启动时创建 TaskRun 记录（status=running）
  - 执行完成后更新 TaskRun（status=done/failed, stdout, stderr, duration）
  - 扫描 `data/raw/{module}/` 目录下新增文件作为 artifacts 记录
  - 同时更新 scheduled_tasks 的 last_log 字段

- 新增 API：
  - `GET /api/v1/tasks/<id>/runs` -- 该任务的所有执行记录
  - `GET /api/v1/tasks/<id>/runs/<run_id>` -- 单条执行记录详情
  - `GET /api/v1/tasks/<id>/status` -- 已有，保持不变

### 1.3 后端：数据预览 API

文件：`app/api/data.py` 新增路由

- `GET /api/v1/data/preview?path=xxx` -- 安全读取 data/ 下的文件内容
  - 路径安全校验：只允许 data/ 目录下，禁止 `..`
  - 大文件只返回前 2000 行
  - 返回 `{filename, size, lines, content, type}`

### 1.4 前端：任务详情页

新文件：`frontend/src/pages/TaskDetail.jsx`

布局：
```
┌─────────────────────────────────────────┐
│ ← 返回  热点平台数据采集               │
│ hot_topics | cron 0 */3 * * * | enabled │
├─────────────────────────────────────────┤
│ [概览] [执行日志] [产物] [历史]          │  ← Tab 切换
├─────────────────────────────────────────┤
│ 概览：                                   │
│   成功/失败/总数  最近运行时间  平均耗时  │
│                                         │
│ 执行日志（当前/最近一次）：              │
│   ┌─────────────────────────────────┐   │
│   │ [START] Hot Topics at ...       │   │
│   │ [36kr] Collected 10 items       │   │
│   │ ...                             │   │
│   │ [DONE] Hot Topics at ...        │   │
│   └─────────────────────────────────┘   │
│                                         │
│ 产物清单：                               │
│   📄 36kr-20260508_151102.json  5.5K   │
│   📄 huanqiu-20260508_151102.json 921B │
│   点击可预览内容                         │
│                                         │
│ 历史记录：                               │
│   时间      状态   耗时   产物数         │
│   15:15:43  done   2.1s   4             │
│   15:11:01  done   1.8s   4             │
└─────────────────────────────────────────┘
```

路由：`/tasks/:id` → TaskDetail 组件

### 1.5 前端：数据预览弹窗

新组件：`frontend/src/components/DataPreview.jsx`

- Modal 弹窗，调用 `/api/v1/data/preview?path=xxx`
- JSON 文件自动格式化高亮
- 纯文本文件直接显示
- 显示文件元信息（大小、行数、采集时间）

---

## Phase 2: 任务历史记录

### 2.1 后端

已在 Phase 1 的 TaskRun 模型中覆盖，API：
- `GET /api/v1/tasks/<id>/runs` 返回分页列表
  - query params: `?page=1&per_page=20`
  - 返回 `{items: [...], total, page, per_page}`

### 2.2 前端

TaskDetail 页的「历史」Tab：
- 表格列出所有执行记录
- 列：时间、状态(badge)、耗时、exit_code、产物数
- 点击行展开显示 stdout/stderr
- 支持分页

---

## Phase 3: 原生数据浏览器

### 3.1 后端：目录树 API

文件：`app/api/data.py` 新增路由

- `GET /api/v1/data/tree` -- 返回 data/ 目录的树形结构
  - 按天聚合：同一目录下同一天的文件归入 `{date}` 子节点
  - 返回格式：
    ```json
    {
      "name": "data",
      "type": "dir",
      "children": [
        {
          "name": "raw",
          "type": "dir",
          "children": [
            {
              "name": "hot_topics",
              "type": "dir",
              "children": [
                {
                  "name": "2026-05-08",
                  "type": "dir",
                  "children": [
                    {"name": "36kr-20260508_151102.json", "type": "file", "size": 5635, "path": "data/raw/hot_topics/36kr-20260508_151102.json"},
                    ...
                  ]
                }
              ]
            }
          ]
        }
      ]
    }
    ```

- `GET /api/v1/data/preview?path=data/raw/hot_topics/36kr-20260508_151102.json`
  - 已在 Phase 1 实现

### 3.2 前端：数据浏览器页面

新文件：`frontend/src/pages/DataExplorer.jsx`

布局：
```
┌──────────────────┬──────────────────────────┐
│  📁 data/        │  36kr-20260508_151102.json│
│    📁 raw/       │  大小: 5.5K | 10 条      │
│      📁 hot_topics│                          │
│        📁 05-08  │  [{                      │
│          📄 36kr │    "platform": "36kr",   │
│          📄 huanqiu│   "name": "36氪",       │
│          📄 weibo │    "items": [            │
│          📄 zhihu │      {                   │
│      📁 policy   │        "title": "...",   │
│        📁 05-08  │        "url": "...",     │
│      📁 exchange │        ...               │
│      📁 financial│      }                   │
│    📁 processed  │    ]                      │
│    📁 reports    │  }                        │
│                  │                           │
│                  │  ← JSON 语法高亮显示       │
└──────────────────┴──────────────────────────┘
```

特性：
- 左侧树形导航，可展开/折叠
- 按天聚合目录自动展开（`YYYY-MM-DD` 格式）
- 点击文件右侧显示预览
- JSON 自动格式化 + 折叠
- 纯文本直接显示
- 显示文件大小、修改时间

### 3.3 路由更新

`App.jsx` 新增：
- `/tasks/:id` → TaskDetail
- `/data` → DataExplorer
- 侧栏新增「数据浏览」菜单项

---

## 数据库变更

新增 `task_runs` 表，无需迁移脚本：
- SQLAlchemy `db.create_all()` 会自动创建
- 需在 `app/models/__init__.py` 中 import TaskRun

---

## 文件清单

### 新增文件
```
app/models/task_run.py                  # TaskRun 模型
frontend/src/pages/TaskDetail.jsx       # 任务详情页
frontend/src/pages/DataExplorer.jsx     # 数据浏览器页
frontend/src/components/DataPreview.jsx # 数据预览组件
```

### 修改文件
```
app/models/__init__.py                  # import TaskRun
app/api/tasks.py                        # 执行日志写入 TaskRun + 新增 runs API
app/api/data.py                         # tree + preview API
app/__init__.py                         # 无变更（db.create_all 自动处理）
frontend/src/App.jsx                    # 新路由 + 侧栏菜单
```

---

## 执行顺序

1. Phase 1.1 - TaskRun 模型（后端）
2. Phase 1.2 - 执行引擎改造（后端）
3. Phase 1.3 - 数据预览 API（后端）
4. Phase 2.1 - 历史记录 API（后端，与 1.2 同步完成）
5. Phase 3.1 - 目录树 API（后端）
6. Phase 1.4 - 任务详情页（前端）
7. Phase 1.5 - 数据预览弹窗（前端组件）
8. Phase 2.2 - 历史记录 Tab（前端）
9. Phase 3.2 - 数据浏览器页（前端）
10. Phase 3.3 - 路由更新（前端）
