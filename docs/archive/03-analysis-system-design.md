# 分析系统设计

## 数据处理管道

```
原始数据 (data/raw/{category}/)
    │
    ├─→ [去重]   deduplicate.py   → 去重后数据
    │
    ├─→ [标准化] normalize.py     → 统一字段格式
    │
    ├─→ [聚合]   aggregate.py     → 全平台聚合
    │
    ├─→ [分析]   analyze.py        → 趋势/共振/心跳
    │
    └─→ [入库]   import_kb.py      → 知识库
```

## 1. 数据聚合 (aggregate/)

**脚本**: `analysis/aggregate/aggregator.py`

```python
class DataAggregator:
    PLATFORMS = ["weibo", "douyin", "zhihu", "36kr", "huanqiu",
                 "huxiu", "eastmoney", "paper", "wangyi"]

    def load_latest(self, platform: str) -> list[dict]:
        """加载指定平台最新数据文件"""
        pass

    def deduplicate(self, items: list[dict]) -> list[dict]:
        """基于 id + title 去重"""
        pass

    def normalize_timestamp(self, item: dict) -> dict:
        """统一时间戳为 ISO 格式"""
        pass

    def aggregate_all(self) -> dict:
        """聚合所有平台数据，按时间排序"""
        pass

    def save(self, data: dict, filepath: str):
        """保存聚合结果"""
        pass
```

**输出**: `data/processed/all-platforms-aggregated.json`

**触发**: 
- 每次热点采集完成后自动运行
- 心跳分析前预聚合

## 2. 趋势分析 (trends/)

**脚本**: `analysis/trends/trend_analyzer.py`

核心功能:
- **关键词提取**: 基于 TF-IDF-like 统计（过滤停用词，取长度 >= 2 的词/字）
- **话题分类**: 基于规则映射表（8 大类：国际政治/体育/娱乐/财经/科技/游戏/教育/社会）
- **热度评分**: 按时间衰减计算（越新鲜分数越高）

**话题分类规则 (classification_map)**:

```python
TOPIC_MAP = {
    "国际政治": ["伊朗", "特朗普", "美国", "巴基", "斯坦", "东京", "审判", 
                "朝鲜", "外交", "国台办", "赖清德", "窜访"],
    "体育赛事": ["国乒", "CBA", "篮球", "网球", "斯诺克", "辽篮", "广东", 
                "辽宁", "季后赛"],
    "娱乐圈": ["票房", "电影", "演唱会", "李荣浩", "粉丝", "票房"],
    "财经市场": ["财报", "业绩", "同比增长", "股价", "股市", "投资", "利润"],
    "科技数码": ["AI", "人工智能", "芯片", "手机", "建模", "特效"],
    "游戏动漫": ["火影", "手游", "王者", "第五人格"],
    "教育文化": ["教资", "试卷", "老师", "学校", "考生"],
    "社会民生": ["五一", "假期", "旅游", "景区", "交通", "天气"]
}
```

## 3. 跨平台共振分析 (resonance/)

**脚本**: `analysis/resonance/resonance_analyzer.py`

核心算法:
1. 提取所有数据中的关键词（字符级别，2+ 字）
2. 统计每个关键词在多少个不同平台出现
3. 计算共振分 = 关键词出现平台数 × 关键词总出现次数
4. 取共振分 Top-N 作为跨平台热点

```python
def calculate_resonance(data: list[dict]) -> list[dict]:
    keyword_platforms = defaultdict(set)
    keyword_counts = Counter()

    for item in data:
        keywords = extract_keywords(item["title"])
        for kw in keywords:
            keyword_platforms[kw].add(item["platform"])
            keyword_counts[kw] += 1

    resonance_scores = []
    for kw, platforms in keyword_platforms.items():
        score = len(platforms) * keyword_counts[kw]
        resonance_scores.append({
            "keyword": kw,
            "platform_count": len(platforms),
            "total_mentions": keyword_counts[kw],
            "resonance_score": score,
            "platforms": list(platforms)
        })

    return sorted(resonance_scores, key=lambda x: x["resonance_score"], reverse=True)
```

## 4. 心跳分析 (heartbeat/)

**脚本**: `analysis/heartbeat/heartbeat_analyzer.py`

每小时执行，综合评估系统状态：

- **新鲜度检查**: 各平台数据文件年龄
- **采集量统计**: 每小时新增条目数
- **共振热点**: Top-5 跨平台热点
- **健康评分**: 基于数据质量和采集频率 (0-100)
- **告警**: 连续 2 小时无更新 → 触发重采

## 5. 洞察报告生成 (reports/)

**脚本**: `analysis/reports/insight_generator.py`

每天 9:00 和 21:00 生成:

```markdown
# 📊 跨平台热点洞察报告

**生成时间**: 2026-05-07 21:00
**数据覆盖**: 过去 12 小时

## 🔥 Top-10 跨平台热点

| 排名 | 关键词 | 涉及平台 | 出现次数 | 洞察 |
|---|---|---|---|---|
| 1 | 伊朗 | 微博/知乎/36kr | 23 | 多平台持续关注... |

## 📈 各平台热度排行

...

## 🎯 投资信号

...
```

## 6. 投资分析心跳

从现有 cron job `"投资分析心跳"` 迁移为独立模块:

- **数据源**: policy-monitor + exchange-announcements + cninfo
- **分析框架**: 节前效应 > 催化剂；期货 ≠ 股票；涨价链条 > 地缘链条
- **输出**: `investment-analysis/reports/policy_investment_report_{date}.md`
- **推送**: 飞书 Webhook

## 知识库入库

**脚本**: `analysis/kb_importer.py`

趋势分析和洞察报告的结果，按主题自动入库:

```python
class KBImporter:
    def import_trend(self, topic: str, data: dict):
        """将趋势数据写入知识库"""
        pass

    def import_insight(self, insight: dict):
        """将洞察写入知识库 03-行业分析/"""
        pass

    def build_entity_graph(self, items: list[dict]):
        """从采集数据构建实体关系图"""
        # 实体: 公司/人/机构
        # 关系: 投资/合作/竞争/政策影响
        pass
```
