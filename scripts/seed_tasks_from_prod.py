"""Seed crawler and report tasks from production, remapping RSS source IDs."""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.task import ScheduledTask
from app.models.rss_source import RssSource

# Category mapping: prod category → open-source category
CATEGORY_MAP = {
    '公众号': '公众号',
    '新闻': '新闻',
    '财经': '财经',
    '科技/AI': '科技',
    '科技': '科技',
    'Technology': 'Technology',
    '编程': '编程',
    'Programming': 'Programming',
    '外国媒体': '外国媒体',
    'News': 'News',
    '知识': '知识',
    '生活': '生活',
    '娱乐': '娱乐',
    '技术博客': '科技',
    '软件工具': '科技',
    '综合资讯': '新闻',
    '独立开发者/创业': '科技',
    '其他': 'Other',
    'Telegram 频道': 'News',
    '社区/论坛': '科技',
    '游戏': '娱乐',
    '新闻媒体': '新闻',
    '视频/B站': '娱乐',
    '人文社科': '知识',
    '财经商业': '财经',
    'Other': 'Other',
}

# Tasks to import: id, schedule_override (optional)
CRAWLER_TASKS = [
    {'name': 'RSS-国内新闻', 'category': '新闻', 'prod_category': ['新闻', 'News'],
     'schedule': '{"type": "interval", "interval_minutes": 60}',
     'desc': '采集国内新闻数据源：澎湃、新京报、南方周末、人民网、新华网、联合早报等',
     'tags': 'RSS,国内,新闻,资讯'},
    {'name': 'RSS-国际新闻', 'category': '外国媒体', 'prod_category': ['外国媒体', 'News'],
     'schedule': '{"type": "interval", "interval_minutes": 90}',
     'desc': '采集国际新闻数据源：BBC、Economist、WIRED、NYT、WSJ、Al Jazeera、端传媒等',
     'tags': 'RSS,国际,新闻,外媒'},
    {'name': 'RSS-公众号', 'category': '公众号', 'prod_category': ['公众号'],
     'schedule': '{"type": "cron", "cron": "0 9,15,21 * * *"}',
     'desc': '采集微信公众号数据源：机器之心、果壳、丁香医生、虎嗅、36氪、刘润、经济观察报等',
     'tags': 'RSS,公众号,微信'},
    {'name': 'RSS-科技技术', 'category': '科技', 'prod_category': ['科技', '科技/AI', 'Technology'],
     'schedule': '{"type": "interval", "interval_minutes": 90}',
     'desc': '采集科技技术类数据源：36氪、虎嗅、少数派、爱范儿、InfoQ、Hacker News、OpenAI、arXiv等',
     'tags': 'RSS,科技,AI,编程,技术'},
    {'name': 'RSS-经济金融', 'category': '财经', 'prod_category': ['财经'],
     'schedule': '{"type": "cron", "cron": "30 8,12,16 * * 1-5"}',
     'desc': '采集财经类数据源：雪球、财富中文网、经济日报、经济观察网、界面财经等',
     'tags': 'RSS,财经,金融,经济'},
    {'name': 'RSS-生活百科', 'category': '生活', 'prod_category': ['生活', '知识'],
     'schedule': '{"type": "interval", "interval_minutes": 120}',
     'desc': '采集生活百科类数据源：煎蛋、微博热搜、知乎日报/热榜、简书、每日一文等',
     'tags': 'RSS,生活,百科,知识'},
    {'name': 'RSS-影视娱乐', 'category': '娱乐', 'prod_category': ['娱乐'],
     'schedule': '{"type": "interval", "interval_minutes": 120}',
     'desc': '采集影视娱乐类数据源：豆瓣影评/书评、机核、游戏研究社、触乐、B站动态等',
     'tags': 'RSS,影视,娱乐,游戏'},
    {'name': 'RSS-技术博客', 'category': '编程', 'prod_category': ['编程', 'Programming'],
     'schedule': '{"type": "cron", "cron": "0 9,18 * * *"}',
     'desc': '采集技术博客类数据源：CoolShell、美团技术、V2EX、掘金、Dan Abramov、各类工程博客等',
     'tags': 'RSS,博客,技术,开发者'},
]

REPORT_TASKS = [
    {
        'id': '72966fe8',
        'name': '市场洞察报告',
        'module': 'analysis',
        'script_file': 'report_market_insight.json',
        'schedule': '{"type": "cron", "cron": "0 9,21 * * *"}',
        'desc': 'LLM深度分析: 全景扫描 → 关联分析 → 结构化洞察 (每天2次)',
        'tags': '分析,LLM,报告,洞察',
    },
    {
        'id': '45bef843',
        'name': '每日综合简报',
        'module': 'reports',
        'script_file': 'report_daily_comprehensive.json',
        'schedule': '{"type": "cron", "cron": "0 7 * * *"}',
        'desc': '生成每日洞察报告，包含趋势、共振、心跳分析',
        'tags': '报告,洞察',
    },
    {
        'id': 'finance_daily',
        'name': '通用金融简报',
        'module': 'analysis',
        'script_file': 'report_finance.json',
        'schedule': '{"type": "cron", "cron": "30 8 * * *"}',
        'desc': '通用金融市场洞察，每天09:30生成，周一自动切周报格式',
        'tags': '金融,市场,财经,日报',
    },
]


def seed_crawlers(app):
    """Seed RSS crawler tasks based on local RSS source categories."""
    with app.app_context():
        existing = {t.name for t in ScheduledTask.query.filter_by(task_type='crawler').all()}
        added = 0

        for task_def in CRAWLER_TASKS:
            name = task_def['name']
            if name in existing:
                print(f'  SKIP {name} — already exists')
                continue

            # Find matching RSS sources by category
            source_ids = [
                s.id for s in RssSource.query.filter(
                    RssSource.category.in_(task_def['category'] if isinstance(task_def['category'], list) else [task_def['category']])
                ).all()
            ]

            script = json.dumps({'type': 'rss', 'source_ids': source_ids})

            task = ScheduledTask(
                id=task_def.get('id', os.urandom(4).hex()),
                name=name,
                task_type='crawler',
                module='rss',
                script=script,
                description=task_def['desc'],
                tags=task_def['tags'],
                schedule_type='cron',
                schedule_config=task_def['schedule'],
                enabled=True,
            )
            db.session.add(task)
            added += 1
            print(f'  ADD {name} — {len(source_ids)} RSS sources')

        db.session.commit()
        print(f'Seeded {added} crawler tasks')


def seed_reports(app):
    """Seed report tasks with simplified prompts (no hardcoded RSS source IDs)."""
    with app.app_context():
        existing = {t.id for t in ScheduledTask.query.filter_by(task_type='report').all()}
        added = 0

        # Report scripts with generic source config (all RSS by category)
        all_finance_ids = [
            s.id for s in RssSource.query.filter(RssSource.category == '财经').all()
        ]
        all_news_ids = [
            s.id for s in RssSource.query.filter(RssSource.category.in_(['新闻', 'News'])).all()
        ]
        all_tech_ids = [
            s.id for s in RssSource.query.filter(RssSource.category.in_(['科技', 'Technology', '编程', 'Programming'])).all()
        ]
        all_life_ids = [
            s.id for s in RssSource.query.filter(RssSource.category.in_(['生活', '娱乐', '知识'])).all()
        ]
        all_wechat_ids = [
            s.id for s in RssSource.query.filter(RssSource.category == '公众号').all()
        ]
        all_foreign_ids = [
            s.id for s in RssSource.query.filter(RssSource.category == '外国媒体').all()
        ]

        for task_def in REPORT_TASKS:
            tid = task_def['id']
            if tid in existing:
                print(f'  SKIP {tid} ({task_def["name"]}) — already exists')
                continue

            # Build script config based on report type
            if tid == '72966fe8':  # 市场洞察
                rss_ids = all_finance_ids + all_foreign_ids + all_news_ids
                sources = ["hot_topics", "policy", "exchange", "financial", "rss"]
                prompt = MARKET_INSIGHT_PROMPT
            elif tid == '45bef843':  # 每日综合
                rss_ids = all_news_ids + all_foreign_ids + all_finance_ids + all_tech_ids + all_wechat_ids + all_life_ids
                sources = ["hot_topics", "policy", "exchange", "financial", "rss"]
                prompt = DAILY_COMPREHENSIVE_PROMPT
            elif tid == 'finance_daily':  # 金融简报
                rss_ids = all_finance_ids + all_news_ids + all_foreign_ids
                sources = ["hot_topics", "policy", "exchange", "financial", "rss"]
                prompt = FINANCE_DAILY_PROMPT
            else:
                continue

            script = json.dumps({
                "template_id": "template:daily",
                "prompt": prompt,
                "sources": sources,
                "rss_source_ids": rss_ids,
                "trend_reference": True,
                "use_harness": True,
            })

            task = ScheduledTask(
                id=tid,
                name=task_def['name'],
                task_type='report',
                module=task_def['module'],
                script=script,
                description=task_def['desc'],
                tags=task_def['tags'],
                schedule_type='cron',
                schedule_config=task_def['schedule'],
                enabled=True,
            )
            db.session.add(task)
            added += 1
            print(f'  ADD {task_def["name"]} — {len(rss_ids)} RSS sources')

        db.session.commit()
        print(f'Seeded {added} report tasks')


# Simplified prompts (without hardcoded content, adapted for open-source)
MARKET_INSIGHT_PROMPT = """# 角色与任务
你是一位顶尖的首席市场策略师，擅长从海量碎片化数据中挖掘市场暗线与跨资产联动规律。

# 输入数据源
- 分析时间：{date}
- 历史轨迹：{previous_report}
- 多端共振信号：{resonance}
- 量化趋势指标：{trends}
- 核心原始数据：
  - 热点话题：{hot_topics}
  - 政策与行业数据：{policy_data}
  - 交易所公告：{exchange_data}
  - 财经数据：{financial_data}
  - RSS 资讯：{rss_data}

# 任务
请判断今天是周几，按规则生成日报或周报。

**周一 → 周报**
1. 本周核心热点 TOP 3
2. 关键转折信号
3. 持续性趋势
4. 本周策略复盘
5. 下周展望
标题：《市场洞察周报_{date}》

**周二至周日 → 日报**
标题：《市场洞察报告_{date}》
1. 核心洞见与市场定调 — 一句话概括 + 3 条关键信号
2. 宏观脉络 — 政策、资金、舆情
3. 核心热点深度推演（2-3个）— 驱动逻辑 + 映射标的 + 情景推演
4. 跨平台共振图谱
5. 风险预警 — 高危/灰犀牛/关键指标
6. 操作指南 — 短期战术 + 中期战略

# 约束
- 机构投研风格，多用金融术语
- Markdown 格式，核心数据加粗
- 如有数据缺失，基于已有数据合理推导

报告语言：中文
格式：Markdown"""

FINANCE_DAILY_PROMPT = """# 角色
你是一位资深的金融市场数据洞察分析师。

# 数据
时间：{date}
健康：{health}
历史：{previous_report}
共振：{resonance}
趋势：{trends}
热点：{hot_topics}
政策：{policy_data}
交易所：{exchange_data}
财经：{financial_data}
RSS：{rss_data}

# 任务
**周一 → 周报**：《市场金融周报 | {date}》
1. 本周核心热点 TOP 3
2. 关键转折信号
3. 持续性趋势
4. 本周策略复盘
5. 下周展望

**周二至周日 → 日报**：《市场金融洞察 | {date}》
1. 核心定调 — 一句话 + 3 条异动信号
2. 宏观与政策
3. 资金与流动性
4. 市场热点深度推演（2-3个）
5. 风险预警
6. 短期趋势研判

# 约束
- 如果没有差异化洞察，输出：无新洞察，静默结束
- 机构投研风格
- Markdown 格式
- 不要在末尾添加链接文字"""

DAILY_COMPREHENSIVE_PROMPT = """# 角色
你是一个专业的智能分析与资讯助手。

# 数据
时间：{date}
历史：{previous_report}
共振：{resonance}
趋势：{trends}
热点：{hot_topics}
政策：{policy_data}
交易所：{exchange_data}
财经：{financial_data}
RSS：{rss_data}

# 任务
**周一 → 周报**：《综合洞察周报_{date}》
1. 本周核心事件 TOP 5
2. 关键转折与意外
3. 持续性主题追踪
4. 跨领域联动分析
5. 下周前瞻

**周二至周日 → 日报**：《每日综合洞察日报_{date}》
1. 今日概览与宏观情绪
2. 关键主题及演变趋势（3-5个）
3. 跨平台共振与舆情焦点
4. 领域重点拆解 — 政经/科技/金融
5. 风险预警与前瞻建议

# 约束
- 如果没有差异化洞察，输出：无新洞察，静默结束
- Markdown 格式
- 不要在末尾添加链接文字"""


def main():
    app = create_app()
    seed_crawlers(app)
    seed_reports(app)


if __name__ == '__main__':
    main()
