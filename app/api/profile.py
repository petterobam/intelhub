"""Profile API — 用户兴趣偏好管理

路由:
  GET  /api/v1/profile/tag-library    — 获取标签词库
  GET  /api/v1/profile/interests      — 获取当前用户兴趣
  PUT  /api/v1/profile/interests      — 保存兴趣标签 (v2+)
  GET  /api/v1/profile/push-settings  — 获取推送设置
  PUT  /api/v1/profile/push-settings  — 保存推送设置 (v1+)
"""

import json
import os
import logging
import uuid

from flask import Blueprint, g

from app import db
from app.models.user_profile import UserProfile
from app.models.task import ScheduledTask
from app.utils.auth import login_required, tier_required
from app.utils.helpers import standard_response, error_response, bj_now


logger = logging.getLogger(__name__)

bp = Blueprint('profile', __name__, url_prefix='/api/v1/profile')

TAG_LIBRARY_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'tag_library.json')

PERSONAL_DAILY_PROMPT = """你是 IntelHub 智能分析助手。请根据以下数据，结合用户兴趣偏好，生成一份个性化的每日简报。

## 当前时间
{date}

## 系统健康状态
{health}

## 历史趋势对比
{previous_report}

## 跨平台热点（共振分析）
{resonance}

## 话题趋势
{trends}

## 各平台数据详情
### 热点话题
{hot_topics}

### 政策动态
{policy_data}

### 交易所公告
{exchange_data}

### 财经资讯
{financial_data}

### RSS 订阅
{rss_data}

---

{user_preferences}

请生成一份个性化日报，要求：

1. **角色适配** — 根据用户关注的领域（如公司、行业、话题），以对应领域的专业视角进行分析，不局限于投资视角
2. **偏好聚焦** — 优先筛选与用户关注标签直接相关的内容，放在最前面
3. **信息分层** — 按重要程度排列：与用户偏好高度相关的深入分析 → 一般性热点速览 → 风险/机会提示
4. **数据溯源** — 每条信息标注来源平台，方便用户追溯
5. **风险提示** — 如发现与用户关注领域相关的风险信号，请特别标注

报告语言：中文
格式：Markdown"""


def _get_or_create_profile(user_id):
    profile = UserProfile.query.get(user_id)
    if not profile:
        profile = UserProfile(user_id=user_id)
        db.session.add(profile)
        db.session.commit()
    return profile


@bp.route('/tag-library', methods=['GET'])
@login_required
def get_tag_library():
    try:
        with open(TAG_LIBRARY_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        data = {}
    return standard_response(data)


@bp.route('/interests', methods=['GET'])
@login_required
def get_interests():
    profile = UserProfile.query.get(g.current_user.id)
    if not profile:
        return standard_response({'interest_tags': [], 'platforms': [], 'rss_source_ids': [], 'user_source_ids': [], 'push_channel_ids': []})
    return standard_response({
        'interest_tags': profile.interest_tags or [],
        'platforms': profile.platforms or [],
        'rss_source_ids': profile.rss_source_ids or [],
        'user_source_ids': profile.user_source_ids or [],
        'push_channel_ids': profile.push_channel_ids or [],
    })


@bp.route('/interests', methods=['PUT'])
@login_required
@tier_required('v2')
def save_interests():
    from flask import request
    data = request.get_json(silent=True) or {}

    profile = _get_or_create_profile(g.current_user.id)

    if 'interest_tags' in data:
        if not isinstance(data['interest_tags'], list):
            return error_response(400, 'interest_tags 必须为数组')
        profile.interest_tags = data['interest_tags']

    if 'platforms' in data:
        if not isinstance(data['platforms'], list):
            return error_response(400, 'platforms 必须为数组')
        profile.platforms = data['platforms']

    if 'rss_source_ids' in data:
        if not isinstance(data['rss_source_ids'], list):
            return error_response(400, 'rss_source_ids 必须为数组')
        profile.rss_source_ids = data['rss_source_ids']

    if 'user_source_ids' in data:
        if not isinstance(data['user_source_ids'], list):
            return error_response(400, 'user_source_ids 必须为数组')
        profile.user_source_ids = data['user_source_ids']

    if 'push_channel_ids' in data:
        if not isinstance(data['push_channel_ids'], list):
            return error_response(400, 'push_channel_ids 必须为数组')
        profile.push_channel_ids = data['push_channel_ids']

    db.session.commit()

    # 同步更新自动任务的 script 配置
    _sync_auto_task(g.current_user.id, profile)

    return standard_response(profile.to_dict())


@bp.route('/push-settings', methods=['GET'])
@login_required
def get_push_settings():
    profile = UserProfile.query.get(g.current_user.id)
    if not profile:
        return standard_response({'report_time': '08:00', 'push_mode': 'summary'})
    return standard_response({
        'report_time': profile.report_time or '08:00',
        'push_mode': profile.push_mode or 'summary',
    })


@bp.route('/push-settings', methods=['PUT'])
@login_required
@tier_required('v1')
def save_push_settings():
    from flask import request
    data = request.get_json(silent=True) or {}

    profile = _get_or_create_profile(g.current_user.id)

    if 'report_time' in data:
        rt = data['report_time']
        if not isinstance(rt, str) or len(rt) != 5:
            return error_response(400, 'report_time 格式为 HH:MM')
        profile.report_time = rt

    if 'push_mode' in data:
        if data['push_mode'] not in ('summary', 'full'):
            return error_response(400, 'push_mode 必须是 summary 或 full')
        profile.push_mode = data['push_mode']

    db.session.commit()

    # 创建/更新/禁用自动任务
    _sync_auto_task(g.current_user.id, profile)

    return standard_response({
        'report_time': profile.report_time,
        'push_mode': profile.push_mode,
    })


@bp.route('/test-daily', methods=['POST'])
@login_required
@tier_required('v2')
def test_daily():
    """手动触发偏好日报生成（立即执行一次）"""
    user_id = g.current_user.id
    auto_task = ScheduledTask.query.filter_by(
        user_id=user_id, is_auto=True, task_type='report'
    ).first()
    if not auto_task or not auto_task.enabled:
        return error_response(404, '偏好日报未启用，请先设置推送时间')

    import threading
    import datetime

    from app.models.task_run import TaskRun

    run_id = str(uuid.uuid4())[:8]
    start_dt = bj_now()
    run = TaskRun(
        id=run_id,
        task_id=auto_task.id,
        user_id=user_id,
        status='running',
        started_at=start_dt,
        trigger_type='manual',
    )
    db.session.add(run)
    db.session.commit()

    from app.api.user_tasks import _run_user_report
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    t = threading.Thread(
        target=_run_user_report,
        args=(auto_task.id, run_id, auto_task.script or '{}', base_dir, user_id),
        daemon=True,
    )
    t.start()

    return standard_response({'task_id': auto_task.id, 'run_id': run_id, 'status': 'started'})


def _sync_auto_task(user_id, profile):
    """根据用户偏好创建/更新/禁用自动偏好日报任务"""
    try:
        # 查找已有的自动任务
        auto_task = ScheduledTask.query.filter_by(
            user_id=user_id, is_auto=True, task_type='report'
        ).first()

        has_report_time = bool(profile and profile.report_time)

        if not has_report_time:
            # 没有推送时间，禁用或删除任务
            if auto_task:
                if auto_task.enabled:
                    auto_task.enabled = False
                    db.session.commit()
                    _unregister_task(auto_task.id)
            return

        # 构建任务 script 配置
        script_cfg = {
            'prompt': PERSONAL_DAILY_PROMPT,
            'sources': profile.platforms or [],
            'rss_source_ids': profile.rss_source_ids or [],
            'user_source_ids': profile.user_source_ids or [],
            'push_channel_ids': profile.push_channel_ids or [],
            'use_preferences': True,
            'interest_tags': profile.interest_tags or [],
        }

        # 构建 cron 配置从 report_time
        parts = (profile.report_time or '08:00').split(':')
        hour = int(parts[0]) if len(parts) > 0 else 8
        minute = int(parts[1]) if len(parts) > 1 else 0
        schedule_cfg = json.dumps({'type': 'cron', 'cron': f'{minute} {hour} * * *'})

        if auto_task:
            # 更新已有任务
            auto_task.script = json.dumps(script_cfg, ensure_ascii=False)
            auto_task.schedule_config = schedule_cfg
            auto_task.schedule_type = 'cron'
            auto_task.enabled = True
        else:
            # 创建新任务
            auto_task = ScheduledTask(
                id=str(uuid.uuid4())[:8],
                user_id=user_id,
                name='偏好日报',
                task_type='report',
                module='personal_daily',
                script=json.dumps(script_cfg, ensure_ascii=False),
                description='系统根据用户偏好自动创建的日报任务',
                schedule_type='cron',
                schedule_config=schedule_cfg,
                enabled=True,
                is_auto=True,
            )
            db.session.add(auto_task)

        db.session.commit()
        _register_task(auto_task)

    except Exception as e:
        logger.error(f'Failed to sync auto task for user {user_id}: {e}')


def _register_task(task):
    try:
        from flask import current_app
        worker = getattr(current_app, 'scheduler', None)
        if worker:
            worker.register_task(task)
    except Exception:
        pass


def _unregister_task(task_id):
    try:
        from flask import current_app
        worker = getattr(current_app, 'scheduler', None)
        if worker:
            worker.unregister_task(task_id)
    except Exception:
        pass
