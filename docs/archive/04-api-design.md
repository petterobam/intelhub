# API 设计

## 基础信息

- Base URL: `http://localhost:5000/api/v1`
- 认证: API Key (Header: `X-API-Key`)
- 响应格式: JSON
- 错误码: RFC 7807 Problem Details

## 模块分组

### Tasks (任务调度)

```
GET    /tasks                    列出所有任务
GET    /tasks/:id                任务详情
POST   /tasks                    创建任务
PUT    /tasks/:id                更新任务
DELETE /tasks/:id                删除任务
POST   /tasks/:id/run            手动触发执行
POST   /tasks/:id/pause          暂停任务
POST   /tasks/:id/resume         恢复任务
GET    /tasks/:id/logs           任务执行日志
```

**创建任务请求体:**

```json
{
  "name": "热点采集-36kr",
  "module": "hot_topics",
  "script": "run_36kr.sh",
  "schedule": {
    "type": "interval",
    "minutes": 90
  },
  "enabled": true,
  "notify_on_complete": true,
  "deliver_to": "local"
}
```

### Crawlers (爬虫)

```
GET    /crawlers                 爬虫节点列表
GET    /crawlers/:name           爬虫详情
POST   /crawlers/:name/run       立即运行指定爬虫
GET    /crawlers/:name/status    采集状态和新鲜度
```

### Data (数据)

```
GET    /data/latest              最新聚合数据
GET    /data/platform/:name      指定平台最新数据
GET    /data/freshness           所有平台新鲜度状态
GET    /data/history/:platform   平台历史数据文件
```

**freshness 响应示例:**

```json
{
  "timestamp": "2026-05-07T15:30:00+08:00",
  "platforms": [
    {
      "name": "36kr",
      "latest_file": "36kr-20260507_1530.json",
      "age_minutes": 15,
      "status": "fresh"
    },
    {
      "name": "weibo",
      "latest_file": "weibo-20260507_1530.json",
      "age_minutes": 180,
      "status": "stale"
    }
  ]
}
```

### Reports (报告)

```
GET    /reports                  报告列表
GET    /reports/:id              报告详情
GET    /reports/latest           最新报告
GET    /reports/insights         洞察报告
GET    /reports/daily            每日简报
GET    /reports/heartbeat        心跳快照
```

### Knowledge Base (知识库)

```
GET    /kb/topics                主题列表
GET    /kb/topics/:id            主题详情
GET    /kb/search?q=关键词        知识库搜索
GET    /kb/entities              实体列表
GET    /kb/graph                  知识图谱
```

### Analysis (分析)

```
POST   /analysis/aggregate       触发数据聚合
POST   /analysis/trends          触发趋势分析
POST   /analysis/resonance        触发共振分析
GET    /analysis/status           分析任务状态
```

### Health (健康检查)

```
GET    /health                   系统健康状态
GET    /health/crawlers          爬虫健康状态
GET    /health/analysis           分析系统状态
GET    /health/storage           存储使用情况
```

## 统一响应格式

成功:
```json
{
  "success": true,
  "data": { ... },
  "timestamp": "2026-05-07T15:30:00+08:00"
}
```

错误:
```json
{
  "success": false,
  "error": {
    "code": "TASK_NOT_FOUND",
    "message": "Task with id 'abc' not found",
    "details": "..."
  },
  "timestamp": "2026-05-07T15:30:00+08:00"
}
```

## WebSocket (实时推送)

```
ws://localhost:5000/ws/logs          实时任务日志
ws://localhost:5000/ws/freshness      新鲜度变化推送
ws://localhost:5000/ws/analysis       分析进度推送
```
