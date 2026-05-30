"""User Tasks API — 个人任务管理

路由:
  GET    /api/v1/user-tasks           — 列出当前用户的任务
  POST   /api/v1/user-tasks           — 创建个人任务 (v2+)
  GET    /api/v1/user-tasks/<id>      — 获取详情
  PUT    /api/v1/user-tasks/<id>      — 更新任务
  DELETE /api/v1/user-tasks/<id>      — 删除任务
  POST   /api/v1/user-tasks/<id>/run  — 手动执行
  GET    /api/v1/user-tasks/<id>/runs — 运行历史
"""

import uuid
import json
import os
import datetime
import threading
import logging

from flask import Blueprint, request, g

from app import db
from app.models.task import ScheduledTask
from app.models.task_run import TaskRun
from app.utils.auth import login_required, tier_required
from app.utils.helpers import standard_response, error_response, bj_now


logger = logging.getLogger(__name__)

bp = Blueprint('user_tasks', __name__, url_prefix='/api/v1/user-tasks')

ALLOWED_TASK_TYPES = ('crawler', 'report')

TIER_TASK_LIMITS = {
    'free': 0, 'v1': 0,
    'v2': 2, 'v3': 5, 'v4': 15, 'v5': 50,
}

MANUAL_RUN_DAILY_LIMIT = 10


def _check_ownership(task):
    if not task or task.user_id != g.current_user.id:
        return False
    return True


@bp.route('', methods=['GET'])
@login_required
def list_tasks():
    tasks = ScheduledTask.query.filter_by(user_id=g.current_user.id)\
        .filter(ScheduledTask.is_auto == False)\
        .order_by(ScheduledTask.created_at.desc()).all()
    result = []
    for t in tasks:
        d = t.to_dict()
        d['schedule_description'] = _human_schedule(t.schedule_type, t.schedule_config)
        result.append(d)
    return standard_response(result)


@bp.route('/platform', methods=['GET'])
@login_required
def list_platform_tasks():
    """用户可查看的平台任务（仅采集和报告）"""
    tasks = ScheduledTask.query.filter(
        ScheduledTask.user_id.is_(None),
        ScheduledTask.task_type.in_(['crawler', 'report']),
    ).order_by(ScheduledTask.created_at.desc()).all()
    result = []
    for t in tasks:
        d = t.to_dict()
        d['schedule_description'] = _human_schedule(t.schedule_type, t.schedule_config)
        result.append(d)
    return standard_response(result)
@login_required
@tier_required('v2')
def create_task():
    data = request.get_json(silent=True) or {}
    task_type = data.get('task_type', 'crawler')
    if task_type not in ALLOWED_TASK_TYPES:
        return error_response(400, f'个人任务仅支持: {", ".join(ALLOWED_TASK_TYPES)}')

    user_tier = g.current_user.effective_tier
    limit = TIER_TASK_LIMITS.get(user_tier, 0)
    current = ScheduledTask.query.filter_by(user_id=g.current_user.id).count()
    if current >= limit:
        return error_response(403, f'已达到 {user_tier} 等级的任务数量上限 ({limit} 个)')

    name = (data.get('name') or '').strip()
    if not name:
        return error_response(400, 'name 必填')

    module = data.get('module', 'rss' if task_type == 'crawler' else 'report')
    script = data.get('script', '{}')
    if isinstance(script, dict):
        script = json.dumps(script, ensure_ascii=False)

    schedule_config = data.get('schedule_config', {})
    if isinstance(schedule_config, str):
        try:
            schedule_config = json.loads(schedule_config)
        except Exception:
            schedule_config = {}

    # 个人用户：不允许 interval 模式
    stype = data.get('schedule_type', schedule_config.get('type', ''))
    if stype == 'interval' or schedule_config.get('type') == 'interval':
        return error_response(400, '个人用户仅支持小时级或天/周级定时任务')

    if isinstance(schedule_config, dict):
        schedule_config = json.dumps(schedule_config, ensure_ascii=False)

    tags_val = data.get('tags', '')
    if isinstance(tags_val, list):
        tags_val = ','.join(tags_val)

    task = ScheduledTask(
        id=str(uuid.uuid4())[:8],
        user_id=g.current_user.id,
        name=name,
        task_type=task_type,
        module=module,
        script=script,
        description=data.get('description', ''),
        tags=tags_val,
        schedule_type=data.get('schedule_type', 'cron'),
        schedule_config=schedule_config,
        enabled=data.get('enabled', True),
    )
    db.session.add(task)
    db.session.commit()

    # Register to scheduler
    _register_to_worker(task)

    return standard_response(task.to_dict()), 201


@bp.route('/<task_id>', methods=['GET'])
@login_required
def get_task(task_id):
    task = db.session.get(ScheduledTask, task_id)
    if not task:
        return error_response(404, '任务不存在')

    is_owner = task.user_id == g.current_user.id
    is_platform = task.user_id is None and task.task_type in ('crawler', 'report')
    if not is_owner and not is_platform:
        return error_response(404, '任务不存在')

    d = task.to_dict()
    d['schedule_description'] = _human_schedule(task.schedule_type, task.schedule_config)
    d['_read_only'] = not is_owner

    last_run = TaskRun.query.filter_by(task_id=task_id).order_by(TaskRun.started_at.desc()).first()
    if last_run:
        d['last_run_detail'] = last_run.to_dict()

    return standard_response(d)


@bp.route('/<task_id>', methods=['PUT'])
@login_required
def update_task(task_id):
    task = db.session.get(ScheduledTask, task_id)
    if not _check_ownership(task):
        return error_response(404, '任务不存在')

    data = request.get_json(silent=True) or {}

    if 'task_type' in data and data['task_type'] not in ALLOWED_TASK_TYPES:
        return error_response(400, f'个人任务仅支持: {", ".join(ALLOWED_TASK_TYPES)}')

    # 个人用户：不允许 interval 模式
    schedule_cfg = data.get('schedule_config', {})
    if isinstance(schedule_cfg, str):
        try:
            schedule_cfg = json.loads(schedule_cfg)
        except Exception:
            schedule_cfg = {}
    stype = data.get('schedule_type', schedule_cfg.get('type', ''))
    if stype == 'interval' or schedule_cfg.get('type') == 'interval':
        return error_response(400, '个人用户仅支持小时级或天/周级定时任务')

    for key in ['name', 'module', 'script', 'schedule_type', 'enabled', 'description', 'task_type']:
        if key in data:
            setattr(task, key, data[key])

    if 'schedule_config' in data:
        cfg = data['schedule_config']
        if isinstance(cfg, dict):
            cfg = json.dumps(cfg, ensure_ascii=False)
        task.schedule_config = cfg

    if 'tags' in data:
        tags_val = data['tags']
        if isinstance(tags_val, list):
            tags_val = ','.join(tags_val)
        task.tags = tags_val

    db.session.commit()
    _register_to_worker(task)
    return standard_response(task.to_dict())


@bp.route('/<task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    task = db.session.get(ScheduledTask, task_id)
    if not _check_ownership(task):
        return error_response(404, '任务不存在')

    db.session.delete(task)
    db.session.commit()
    _unregister_from_worker(task_id)
    return standard_response({'deleted': task_id})


@bp.route('/<task_id>/run', methods=['POST'])
@login_required
def run_task(task_id):
    task = db.session.get(ScheduledTask, task_id)
    if not _check_ownership(task):
        return error_response(404, '任务不存在')

    # 每日手动运行限制（非管理员）
    if g.current_user.role != 'admin':
        today_start = bj_now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_runs = TaskRun.query.filter(
            TaskRun.user_id == g.current_user.id,
            TaskRun.trigger_type == 'manual',
            TaskRun.started_at >= today_start,
        ).count()
        if today_runs >= MANUAL_RUN_DAILY_LIMIT:
            return error_response(429, f'今日手动运行已达上限 ({MANUAL_RUN_DAILY_LIMIT} 次/天)')

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script_val = task.script or ''

    # Create TaskRun record
    run_id = str(uuid.uuid4())[:8]
    start_dt = bj_now()

    run = TaskRun(
        id=run_id,
        task_id=task_id,
        user_id=g.current_user.id,
        status='running',
        started_at=start_dt,
        trigger_type='manual',
    )
    db.session.add(run)
    db.session.commit()

    # Route to executor based on task type
    if task.task_type == 'report' and script_val.strip().startswith('{'):
        t = threading.Thread(
            target=_run_user_report,
            args=(task_id, run_id, script_val, base_dir, g.current_user.id)
        )
        t.daemon = True
        t.start()
    elif task.task_type == 'crawler' and script_val.strip().startswith('{'):
        t = threading.Thread(
            target=_run_user_crawler,
            args=(task_id, run_id, task, base_dir, g.current_user.id)
        )
        t.daemon = True
        t.start()
    else:
        return error_response(400, '不支持的任务配置')

    return standard_response({
        'task_id': task_id,
        'run_id': run_id,
        'status': 'started',
    })


@bp.route('/<task_id>/runs', methods=['GET'])
@login_required
def task_runs(task_id):
    task = db.session.get(ScheduledTask, task_id)
    is_owner = task and task.user_id == g.current_user.id
    is_platform = task and task.user_id is None and task.task_type in ('crawler', 'report')
    if not is_owner and not is_platform:
        return error_response(404, '任务不存在')

    if is_owner:
        runs = TaskRun.query.filter_by(task_id=task_id, user_id=g.current_user.id)\
            .order_by(TaskRun.started_at.desc()).limit(20).all()
    else:
        runs = TaskRun.query.filter_by(task_id=task_id)\
            .order_by(TaskRun.started_at.desc()).limit(20).all()
    return standard_response([r.to_dict() for r in runs])


@bp.route('/<task_id>/status', methods=['GET'])
@login_required
def task_status(task_id):
    task = db.session.get(ScheduledTask, task_id)
    if not _check_ownership(task):
        return error_response(404, '任务不存在')

    latest = TaskRun.query.filter_by(task_id=task_id, user_id=g.current_user.id)\
        .order_by(TaskRun.started_at.desc()).first()
    if not latest:
        return standard_response({'status': 'none'})

    if latest.status == 'running' and latest.started_at:
        elapsed = (bj_now() - latest.started_at).total_seconds()
        if elapsed > 600:
            latest.status = 'timeout'
            db.session.commit()

    return standard_response({'status': latest.status})


@bp.route('/<task_id>/outputs', methods=['GET'])
@login_required
def task_outputs(task_id):
    task = db.session.get(ScheduledTask, task_id)
    if not _check_ownership(task):
        return error_response(404, '任务不存在')

    user_id = g.current_user.id
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    outputs = []

    # Scan user data files
    user_data_dir = os.path.join(base_dir, 'data', 'users', user_id)
    if os.path.isdir(user_data_dir):
        for root, dirs, files in os.walk(user_data_dir):
            for f in files:
                if f.endswith('.json'):
                    fpath = os.path.join(root, f)
                    rel = os.path.relpath(fpath, base_dir)
                    outputs.append({
                        'name': f,
                        'path': rel,
                        'size': os.path.getsize(fpath),
                        'mtime': datetime.datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat(),
                    })

    # Scan user reports
    user_report_dir = os.path.join(base_dir, 'reports', 'users', user_id)
    if os.path.isdir(user_report_dir):
        for root, dirs, files in os.walk(user_report_dir):
            for f in files:
                if f.endswith('.md') or f.endswith('.json'):
                    fpath = os.path.join(root, f)
                    rel = os.path.relpath(fpath, base_dir)
                    outputs.append({
                        'name': f,
                        'path': rel,
                        'size': os.path.getsize(fpath),
                        'mtime': datetime.datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat(),
                    })

    outputs.sort(key=lambda x: x.get('mtime', ''), reverse=True)
    return standard_response(outputs[:50])


@bp.route('/<task_id>/pause', methods=['POST'])
@login_required
def pause_task(task_id):
    task = db.session.get(ScheduledTask, task_id)
    if not _check_ownership(task):
        return error_response(404, '任务不存在')
    task.enabled = False
    db.session.commit()
    _unregister_from_worker(task_id)
    return standard_response(task.to_dict())


@bp.route('/<task_id>/resume', methods=['POST'])
@login_required
def resume_task(task_id):
    task = db.session.get(ScheduledTask, task_id)
    if not _check_ownership(task):
        return error_response(404, '任务不存在')
    task.enabled = True
    db.session.commit()
    _register_to_worker(task)
    return standard_response(task.to_dict())


# ── Background runners ──────────────────────────────────────────

def _run_user_report(task_id, run_id, script_val, base_dir, user_id):
    from app import create_app as _create_app
    _app = _create_app()
    start_ts = bj_now().timestamp()

    try:
        report_cfg = json.loads(script_val)
    except Exception:
        report_cfg = {}

    with _app.app_context():
        try:
            from app.scheduler.report_executor import generate_report
            result = generate_report(
                template_id=report_cfg.get('template_id'),
                prompt_template=report_cfg.get('prompt'),
                data_sources=report_cfg.get('sources'),
                trend_reference=report_cfg.get('trend_reference', True),
                use_harness=report_cfg.get('use_harness', True),
                rss_source_ids=report_cfg.get('rss_source_ids'),
                user_id=user_id,
                task_id=task_id,
                use_preferences=report_cfg.get('use_preferences', False),
            )

            end_dt = bj_now()
            duration_ms = int((end_dt - bj_now()).total_seconds() * 1000) * -1

            run = db.session.get(TaskRun, run_id)
            if run:
                success = result.get('success', False)
                run.finished_at = end_dt
                run.duration_ms = duration_ms
                run.status = 'done' if success else 'failed'
                if success:
                    elapsed_s = end_dt.timestamp() - start_ts
                    lines = [
                        '报告生成完成',
                        f'文件: {result.get("filename", "")}',
                        f'路径: {result.get("path", "")}',
                        f'模型: {result.get("model_used", "unknown")}',
                        f'耗时: {elapsed_s:.1f}s',
                    ]
                    if report_cfg.get('sources'):
                        lines.append(f'数据源: {", ".join(report_cfg["sources"])}')
                    if report_cfg.get('use_preferences'):
                        lines.append('偏好注入: 已启用')
                    if report_cfg.get('push_channel_ids'):
                        lines.append(f'推送渠道: {len(report_cfg["push_channel_ids"])} 个')
                    run.stdout = '\n'.join(lines)[:5000]
                else:
                    run.stdout = (result.get('error', ''))[:5000]
                    run.stderr = result.get('error', '')[:2000]

                # Link to the Report record created by generate_report
                report_title = None
                if success and result.get('path'):
                    from app.models.report import Report
                    # Find the report already created by _save_report_record
                    report = Report.query.filter_by(
                        file_path=result.get('path', ''),
                        user_id=user_id,
                    ).order_by(Report.generated_at.desc()).first()
                    if report:
                        run.report_id = report.id
                        report_title = report.title

                db.session.commit()

            # Update task counters
            task = db.session.get(ScheduledTask, task_id)
            if task:
                task.last_run = end_dt
                task.run_count = (task.run_count or 0) + 1
                if result.get('success'):
                    task.success_count = (task.success_count or 0) + 1
                else:
                    task.fail_count = (task.fail_count or 0) + 1
                    task.last_error = result.get('error', '')[:500]
                db.session.commit()

            logger.info('[%s] User report job finished, success=%s', task_id, result.get('success'))

            # Push to user's selected channels
            if result.get('success') and report_cfg.get('push_channel_ids'):
                try:
                    # 构建含任务名的推送标题
                    task_obj = db.session.get(ScheduledTask, task_id)
                    task_name = task_obj.name if task_obj else None
                    if task_name:
                        if report_title:
                            push_title = f'{task_name} · {report_title}'
                        else:
                            push_title = f'{task_name} · {bj_now().strftime("%Y-%m-%d")}'
                    else:
                        push_title = report_title

                    _push_user_report(
                        report_path=result.get('path', ''),
                        user_id=user_id,
                        channel_ids=report_cfg.get('push_channel_ids', []),
                        title=push_title,
                    )
                except Exception as push_err:
                    import traceback
                    err_text = f'{type(push_err).__name__}: {push_err}\n{traceback.format_exc()}'
                    logger.error('[%s] Push failed: %s', task_id, err_text)
                    run = db.session.get(TaskRun, run_id)
                    if run:
                        run.stderr = (run.stderr or '') + '\n[推送失败] ' + err_text[:2000]
                        db.session.commit()

        except Exception as e:
            end_dt = bj_now()
            run = db.session.get(TaskRun, run_id)
            if run:
                run.status = 'error'
                run.finished_at = end_dt
                run.stderr = str(e)[:2000]
                db.session.commit()
            logger.error('[%s] User report job error: %s', task_id, e)


def _run_user_crawler(task_id, run_id, task, base_dir, user_id):
    from app import create_app as _create_app
    _app = _create_app()

    with _app.app_context():
        try:
            from app.scheduler.executor import TaskExecutor
            executor = TaskExecutor(base_dir)
            result = executor.execute(task)

            end_dt = bj_now()
            exit_code = result.get('exit_code', 1)

            run = db.session.get(TaskRun, run_id)
            if run:
                run.status = 'done' if exit_code == 0 else 'failed'
                run.finished_at = end_dt
                run.exit_code = exit_code
                run.stdout = (result.get('stdout', '') or '')[:5000]
                run.stderr = (result.get('stderr', '') or '')[:2000]
                arts = result.get('artifacts', [])
                if arts:
                    run.artifacts = json.dumps(arts)
                db.session.commit()

            task_obj = db.session.get(ScheduledTask, task_id)
            if task_obj:
                task_obj.last_run = end_dt
                task_obj.run_count = (task_obj.run_count or 0) + 1
                if exit_code == 0:
                    task_obj.success_count = (task_obj.success_count or 0) + 1
                else:
                    task_obj.fail_count = (task_obj.fail_count or 0) + 1
                    task_obj.last_error = (result.get('stderr', '') or '')[:500]
                db.session.commit()

            logger.info('[%s] User crawler job finished, exit_code=%d', task_id, exit_code)

        except Exception as e:
            end_dt = bj_now()
            run = db.session.get(TaskRun, run_id)
            if run:
                run.status = 'error'
                run.finished_at = end_dt
                run.stderr = str(e)[:2000]
                db.session.commit()
            logger.error('[%s] User crawler job error: %s', task_id, e)


# ── Helpers ──────────────────────────────────────────────────

def _register_to_worker(task):
    try:
        from flask import current_app
        worker = getattr(current_app, 'scheduler', None)
        if worker:
            worker.register_task(task)
    except Exception as e:
        logger.warning(f'Worker register failed for {task.id}: {e}')


def _unregister_from_worker(task_id):
    try:
        from flask import current_app
        worker = getattr(current_app, 'scheduler', None)
        if worker:
            worker.unregister_task(task_id)
    except Exception as e:
        logger.warning(f'Worker unregister failed for {task_id}: {e}')


def _human_schedule(schedule_type, schedule_config):
    """简化的调度描述"""
    cfg = schedule_config
    if isinstance(cfg, str):
        try:
            cfg = json.loads(cfg)
        except Exception:
            cfg = {}
    if not isinstance(cfg, dict):
        return str(schedule_config)

    if schedule_type == 'cron':
        cron_expr = cfg.get('cron', '')
        if cron_expr:
            return cron_expr
        hour = cfg.get('hour', '*')
        minute = cfg.get('minute', '0')
        return f'{hour}:{minute}'
    elif schedule_type == 'interval':
        mins = cfg.get('interval_minutes') or cfg.get('minutes') or 60
        return f'每{mins}分钟'
    return str(schedule_config)


def _push_user_report(report_path, user_id, channel_ids, title=None):
    """Push generated report to user's selected channels."""
    if not report_path or not os.path.isfile(report_path):
        return
    content = ''
    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return
    if not content:
        return

    # Get user email
    from app.models.user import User
    user = User.query.get(user_id)
    user_email = user.email if user else ''

    # Generate summary
    from app.services.report_notifier import _generate_email_summary, _md_to_simple_html, _get_site_url, _save_report_html
    summary_md = _generate_email_summary(content, 'personal')
    summary_html = _md_to_simple_html(summary_md) if summary_md else ''

    # Save HTML for online viewing
    html_filename = _save_report_html(report_path, content)
    view_link = ''
    site_url = _get_site_url()
    if site_url and html_filename:
        view_link = f'{site_url}/api/v1/reports/html/{html_filename}'

    from app.services.push_channels import PushDispatcher
    dispatcher = PushDispatcher()
    result = dispatcher.dispatch_to_channels(
        channel_ids=channel_ids,
        user_email=user_email,
        summary_html=summary_html,
        view_link=view_link,
        report_type='personal',
        raw_md=content,
        title=title or f'偏好日报 · {bj_now().strftime("%Y-%m-%d")}',
        summary_md=summary_md,
        report_path=report_path,
    )
    logger.info('Push user report: user=%s sent=%d failed=%d', user_id, result['sent'], result['failed'])
