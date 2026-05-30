"""Seed database with system tasks for open-source version.

Seeds core system tasks (no user_id). RSS crawler tasks
with source_ids are seeded separately after RSS sources are loaded.
"""
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.task import ScheduledTask


def seed_tasks():
    app = create_app()
    with app.app_context():
        existing = {t.id for t in ScheduledTask.query.all()}
        tasks = []

        # ===== Script tasks =====
        script_tasks = [
            ('cfd0c200', '热点平台采集', 'hot_topics', 'run_hot_topics.sh',
             'interval', 90, '9大热点平台: 微博/抖音/知乎/36kr/虎嗅/东方财富/澎湃/网易/环球网', '热点,爬虫,实时'),
            ('360beb46', '政策监控采集', 'policy', 'run_policy_monitor.sh',
             'interval', 180, '10大监管机构: 央行/证监会/财政部/中行/国务院/外管局/发改委/工信部/统计局/国资委', '政策,监管,爬虫'),
            ('e663e1a6', '交易所公告采集', 'exchange', 'run_exchange.sh',
             'cron', '0 9,13,15 * * 1-5', '四大交易所: 上交所/深交所/北交所/港交所', '交易所,公告,爬虫'),
            ('2f012b13', '巨潮资讯批量采集', 'financial', 'run_cninfo.sh',
             'cron', '0 8,12,16 * * 1-5', '500+只A股核心股票: 沪深300+中证500+行业龙头', '巨潮,财务,股票,爬虫'),
            ('648badce', '数据聚合', 'aggregate', 'run_aggregate.sh',
             'interval', 60, '汇总各模块采集数据统计，生成聚合报告', '聚合,统计'),
            ('18905919', '系统自优化', 'analysis', 'run_insight_report.sh',
             'interval', 60, 'LLM分析系统健康: 数据新鲜度 → 采集质量 → 优化建议', '分析,LLM,运维'),
            ('8717eaa1', '系统心跳', 'system', 'run_system_heartbeat.sh',
             'interval', 30, '检查系统运行状态和数据新鲜度', '心跳,监控'),
        ]

        for tid, name, module, script, sched_type, sched_val, desc, tags in script_tasks:
            if tid in existing:
                print(f'  SKIP {tid} ({name}) — already exists')
                continue
            cfg = ({'type': 'interval', 'interval_minutes': sched_val} if sched_type == 'interval'
                   else {'type': 'cron', 'cron': sched_val})
            tasks.append(ScheduledTask(
                id=tid, name=name, task_type='script', module=module,
                script=script, description=desc, tags=tags,
                schedule_type=sched_type,
                schedule_config=json.dumps(cfg),
                enabled=True,
            ))

        # ===== Analysis task =====
        if 'ed61224c' not in existing:
            tasks.append(ScheduledTask(
                id='ed61224c', name='投资分析心跳', task_type='analysis', module='analysis',
                script='run_heartbeat.sh',
                description='LLM多轮分析: 跨平台共振 → 趋势识别 → 投资洞察 (每天3次)',
                tags='分析,LLM,投资,心跳',
                schedule_type='cron',
                schedule_config=json.dumps({'type': 'cron', 'cron': '0 9,13,16 * * *'}),
                enabled=True,
            ))

        # ===== Knowledge task =====
        if '48428d76' not in existing:
            tasks.append(ScheduledTask(
                id='48428d76', name='知识库构建', task_type='knowledge', module='knowledge',
                script='run_knowledge_base.sh',
                description='实体抽取+关系建模+索引更新，构建结构化知识库',
                tags='知识库,实体,图谱',
                schedule_type='interval',
                schedule_config=json.dumps({'type': 'interval', 'interval_minutes': 120}),
                enabled=True,
            ))

        for task in tasks:
            db.session.add(task)

        db.session.commit()
        print(f'Seeded {len(tasks)} new tasks ({len(existing)} already existed):')
        for t in tasks:
            cfg = json.loads(t.schedule_config)
            schedule = cfg.get('cron', f"every {cfg.get('interval_minutes', '?')}min")
            print(f'  [{t.module:12s}] {t.name:20s} type={t.task_type:8s} schedule={schedule}')


if __name__ == '__main__':
    seed_tasks()
