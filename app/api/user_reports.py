"""User Reports API — 按任务维度展示个人报告、订阅报告和偏好日报

路由:
  GET  /api/v1/user-reports           — 列出报告 (scope + task 分组)
  GET  /api/v1/user-reports/<id>      — 报告详情

订阅报告直接复用报告橱窗数据源（Report + task_id），不走 TaskRun 间接查询。
"""

import os
import logging

from flask import Blueprint, request, g

from app import db
from app.models.report import Report
from app.models.subscription import Subscription
from app.models.task import ScheduledTask
from app.models.user_profile import UserProfile
from app.utils.auth import login_required
from app.utils.helpers import standard_response, error_response

logger = logging.getLogger(__name__)

bp = Blueprint('user_reports', __name__, url_prefix='/api/v1/user-reports')


@bp.route('', methods=['GET'])
@login_required
def list_reports():
    """列出用户的报告，按 scope (personal/subscription) 分，每组内按任务分组

    Query params:
      scope   — 'personal' | 'subscription' | 'all' (默认 all)
      task_id — 过滤指定任务（可选）
    """
    user = g.current_user
    scope = request.args.get('scope', 'all')
    filter_task_id = request.args.get('task_id')

    personal_reports = []
    personal_task_map = {}
    subscription_reports = []
    subscription_task_map = {}
    seen_ids = set()

    # ── 个人报告 ─────────────────────────────────────────────────────
    if scope in ('all', 'personal'):
        q = Report.query.filter_by(user_id=user.id, scope='personal')
        if filter_task_id:
            q = q.filter_by(task_id=filter_task_id)
        rows = q.order_by(Report.generated_at.desc()).limit(100).all()

        for r in rows:
            if r.id in seen_ids:
                continue
            seen_ids.add(r.id)
            task = db.session.get(ScheduledTask, r.task_id) if r.task_id else None
            d = r.to_dict()
            d['source'] = 'personal'
            d['task_id'] = r.task_id
            d['task_name'] = task.name if task else ''
            personal_reports.append(d)
            if r.task_id and r.task_id not in personal_task_map:
                personal_task_map[r.task_id] = task.name if task else ''

    # ── 订阅报告（复用报告橱窗数据源：直接查 Report + task_id） ────────
    subs = Subscription.query.filter_by(email=user.email, enabled=True).all()
    sub_task_ids = [s.task_id for s in subs if s.task_id]

    if scope in ('all', 'subscription') and sub_task_ids:
        q = Report.query.filter(
            Report.scope == 'platform',
            Report.task_id.in_(sub_task_ids),
        )
        if filter_task_id:
            q = q.filter_by(task_id=filter_task_id)
        rows = q.order_by(Report.generated_at.desc()).limit(200).all()

        # 批量查任务名
        task_cache = {}
        for r in rows:
            if r.id in seen_ids:
                continue
            seen_ids.add(r.id)
            tid = r.task_id
            if tid not in task_cache:
                t = db.session.get(ScheduledTask, tid) if tid else None
                task_cache[tid] = t.name if t else ''
            d = r.to_dict()
            d['source'] = 'subscription'
            d['task_name'] = task_cache.get(tid, '')
            subscription_reports.append(d)
            if tid and tid not in subscription_task_map:
                subscription_task_map[tid] = task_cache[tid]

        # 加上用户订阅了但还没产生报告的任务
        for s in subs:
            if s.task_id and s.task_id not in subscription_task_map:
                task = db.session.get(ScheduledTask, s.task_id)
                if task:
                    subscription_task_map[s.task_id] = task.name

    # ── 偏好日报 ─────────────────────────────────────────────────────
    daily_reports = []
    profile = db.session.get(UserProfile, user.id)
    has_daily_enabled = bool(profile and profile.report_time)

    if scope in ('all', 'daily'):
        # Find by user_id + type, or by the user's auto task_id
        auto_task = ScheduledTask.query.filter_by(user_id=user.id, is_auto=True, task_type='report').first()
        daily_query = Report.query.filter_by(report_type='personal_daily')
        if auto_task:
            from sqlalchemy import or_
            daily_query = daily_query.filter(
                or_(Report.user_id == user.id, Report.task_id == auto_task.id)
            )
        else:
            daily_query = daily_query.filter_by(user_id=user.id)
        rows = daily_query.order_by(Report.generated_at.desc()).limit(100).all()
        for r in rows:
            d = r.to_dict()
            d['source'] = 'daily'
            daily_reports.append(d)

    return standard_response({
        'personal': {
            'reports': personal_reports,
            'tasks': [{'task_id': tid, 'task_name': name} for tid, name in personal_task_map.items()],
        },
        'subscription': {
            'reports': subscription_reports,
            'tasks': [{'task_id': tid, 'task_name': name} for tid, name in subscription_task_map.items()],
        },
        'daily': {
            'reports': daily_reports,
        },
        'has_daily_enabled': has_daily_enabled,
    })


@bp.route('/<report_id>', methods=['GET'])
@login_required
def get_report(report_id):
    report = db.session.get(Report, report_id)
    if not report:
        return error_response(404, '报告不存在')

    user = g.current_user

    if report.scope == 'personal' and report.user_id == user.id:
        d = report.to_dict()
        d['source'] = 'personal'
        if report.task_id:
            task = db.session.get(ScheduledTask, report.task_id)
            d['task_name'] = task.name if task else ''
        return standard_response(d)

    if report.scope == 'platform':
        subs = Subscription.query.filter_by(email=user.email, enabled=True).all()
        sub_task_ids = {s.task_id for s in subs if s.task_id}
        if report.task_id and report.task_id in sub_task_ids:
            d = report.to_dict()
            d['source'] = 'subscription'
            task = db.session.get(ScheduledTask, report.task_id)
            d['task_name'] = task.name if task else ''
            return standard_response(d)

    return error_response(403, '无权查看此报告')
