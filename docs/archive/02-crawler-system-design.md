# 爬虫系统设计

## 设计原则

1. **Hermes 优先** — 所有浏览器操作通过 Hermes Browser 工具（browser_navigate/snapshot）
2. **兜底策略** — API > Hermes Browser > requests > 静默失败
3. **数据标准化** — 所有平台输出统一字段格式
4. **幂等写入** — 同一时间戳的数据覆盖，不重复追加

## 统一数据格式

所有爬虫输出 JSON，字段标准如下：

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
      "timestamp": "2026-05-07T15:30:00+08:00",
      "hotness": 0,
      "tags": ["标签1", "标签2"],
      "raw_fields": {}
    }
  ],
  "meta": {
    "platform": "平台标识",
    "collected_at": "2026-05-07T15:30:00+08:00",
    "item_count": 20,
    "collection_method": "browser|api|requests"
  }
}
```

## 平台配置

配置文件: `crawlers/config/platforms.yaml`

```yaml
hot_topics:
  36kr:
    name: "36氪"
    url: "https://36kr.com/newsflashes"
    method: browser
    schedule: "90m"
    priority: high
    selectors:
      container: ".newsflash-item"
      title: ".item-title"
      link: "a[href]"
      time: ".item-time"

  huanqiu:
    name: "环球时报"
    url: "https://www.huanqiu.com/"
    method: browser
    schedule: "90m"
    priority: medium

  weibo:
    name: "微博热搜"
    url: "https://s.weibo.com/top/summary"
    method: browser
    schedule: "30m"
    priority: high
    auth_required: true

  zhihu:
    name: "知乎热榜"
    url: "https://www.zhihu.com/hot"
    method: browser
    schedule: "60m"
    priority: medium

policy:
  pbc:
    name: "中国人民银行"
    url: "http://www.pbc.gov.cn/..."
    method: browser
    schedule: "180m"
    priority: high
    org_type: bank

  boc:
    name: "银保监会"
    url: "http://www.cbirc.gov.cn/..."
    method: browser
    schedule: "180m"
    priority: high

  gov:
    name: "国务院"
    url: "http://www.gov.cn/..."
    method: browser
    schedule: "180m"
    priority: high

exchange:
  sse:
    name: "上交所"
    url: "http://www.sse.com.cn/..."
    method: api
    schedule: "0 9,13,15 * * 1-5"

  szse:
    name: "深交所"
    url: "http://www.szse.cn/..."
    method: api
    schedule: "0 9,13,15 * * 1-5"

financial:
  cninfo:
    name: "巨潮资讯"
    url: "http://www.cninfo.com.cn/..."
    method: browser
    schedule: "0 8,12,16 * * 1-5"
    stock_count: 500
```

## 爬虫基类

`crawlers/base/crawler_base.py`

```python
from abc import ABC, abstractmethod
from datetime import datetime
import json
import os

class CrawlerBase(ABC):
    """所有爬虫的基类，定义统一接口"""

    def __init__(self, platform: str, output_dir: str):
        self.platform = platform
        self.output_dir = output_dir
        self.items = []

    @abstractmethod
    async def collect(self) -> list[dict]:
        """执行采集，返回标准化数据"""
        pass

    def save(self, items: list[dict]):
        """保存到 JSON 文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(
            self.output_dir,
            f"{self.platform}-{timestamp}.json"
        )
        data = {
            "items": items,
            "meta": {
                "platform": self.platform,
                "collected_at": datetime.now().isoformat(),
                "item_count": len(items),
                "collection_method": "browser"
            }
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return filepath

    async def run(self):
        """标准运行流程"""
        items = await self.collect()
        return self.save(items)
```

## 采集流程

```
Hermes Agent (cron job prompt)
    │
    ├─→ 加载 crawler config
    │
    ├─→ 调用 Hermes Browser 工具
    │      browser_navigate(url)
    │      browser_snapshot() → 获取页面内容
    │      解析 HTML / JSON API 响应
    │
    ├─→ 提取标准化数据
    │
    ├─→ 保存到 data/raw/{category}/
    │
    └─→ 更新 freshness 状态
```

## 兜底策略 (Fallback Chain)

当主策略失败时，依次尝试：

```
1. API 抓取 (requests)
       ↓ 失败
2. Hermes Browser (browser_navigate + snapshot)
       ↓ 失败
3. RSS 源 (若有)
       ↓ 失败
4. 静默跳过，记录日志，不阻塞其他平台
```

## 任务包装器 (cron_wrappers/)

每个定时任务对应一个包装脚本：

| 包装脚本 | 触发任务 |
|---|---|
| `run_hot_topics.sh` | auto-browser-crawler-hourly |
| `run_policy_monitor.sh` | 政策监控（10大机构） |
| `run_exchange_announcements.sh` | 交易所公告采集 |
| `run_cninfo_financial.sh` | 巨潮资讯采集 |
| `run_aggregate.sh` | 数据聚合（作为其他任务的后置） |
| `run_heartbeat.sh` | 健康检查 + 快速洞察 |
| `run_insight_report.sh` | 洞察报告生成 |

## 数据新鲜度监控

`scripts/check_freshness.py`

- 扫描 `data/raw/` 下所有最新 JSON
- 计算文件年龄
- 超过阈值（如 2 小时）标记为 stale
- 生成 `data/freshness/status.json` 供 Dashboard 展示
