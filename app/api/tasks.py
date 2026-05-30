"""任务管理 API"""
from flask import Blueprint, request
from app import db
from app.models.task import ScheduledTask
from app.models.task_run import TaskRun
from app.utils.helpers import standard_response, error_response, bj_now

from app.utils.auth import admin_required
import uuid, subprocess, os, datetime, threading, logging, json, glob

bp = Blueprint('tasks', __name__, url_prefix='/api/v1/tasks')
logger = logging.getLogger(__name__)

# 异步执行中的任务（内存状态）
_async_jobs = {}


# ── Worker 同步 helper ──────────────────────────────────────────────
def _get_worker():
    """获取当前 app 的 Worker 实例"""
    from flask import current_app
    return getattr(current_app, 'scheduler', None)


def _worker_register(task):
    """注册/重新注册任务到 Worker"""
    worker = _get_worker()
    if worker:
        try:
            worker.register_task(task)
            logger.info(f'Worker: registered task {task.id} ({task.name})')
        except Exception as e:
            logger.warning(f'Worker register failed for {task.id}: {e}')


def _worker_unregister(task_id):
    """从 Worker 移除任务"""
    worker = _get_worker()
    if worker:
        try:
            worker.unregister_task(task_id)
            logger.info(f'Worker: removed task {task_id}')
        except Exception as e:
            logger.warning(f'Worker unregister failed for {task_id}: {e}')


def _scan_artifacts(base_dir, module, since_time):
    """扫描模块目录下在 since_time 之后新增的文件（含子目录）"""
    artifacts = []
    module_dir = os.path.join(base_dir, 'data', 'raw', module)
    if not os.path.isdir(module_dir):
        return artifacts
    for f in sorted(glob.glob(os.path.join(module_dir, '**', '*.json'), recursive=True)):
        try:
            if os.path.islink(f) and not os.path.exists(f):
                continue
            mtime = os.path.getmtime(f)
            if mtime >= since_time:
                artifacts.append({
                    'name': os.path.basename(f),
                    'path': os.path.relpath(f, base_dir),
                    'size': os.path.getsize(f),
                })
        except Exception:
            pass
    # 也扫描 reports 目录
    reports_dir = os.path.join(base_dir, 'reports')
    if os.path.isdir(reports_dir):
        for f in sorted(glob.glob(os.path.join(reports_dir, '**', '*.json'), recursive=True)):
            try:
                if os.path.islink(f) and not os.path.exists(f):
                    continue
                mtime = os.path.getmtime(f)
                if mtime >= since_time:
                    artifacts.append({
                        'name': os.path.basename(f),
                        'path': os.path.relpath(f, base_dir),
                        'size': os.path.getsize(f),
                    })
            except Exception:
                pass
    return artifacts


def _run_report_async(task_id, report_cfg, base_dir, trigger_type, module):
    """后台线程执行报告/分析任务 (通过 report_executor)"""
    import sqlite3
    db_path = os.path.join(base_dir, 'data', 'intel_hub.db')
    start_ts = bj_now().timestamp()
    start_dt = bj_now()

    # 查询 task 的 user_id、name 和 script 中的 push_channel_ids
    user_id = None
    task_name = None
    push_channel_ids = None
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT user_id, name, script FROM scheduled_tasks WHERE id=?", (task_id,)).fetchone()
        if row:
            user_id = row[0]
            task_name = row[1]
            if row[2] and row[2].strip().startswith('{'):
                try:
                    push_channel_ids = json.loads(row[2]).get('push_channel_ids')
                except Exception:
                    pass

    run_id = str(uuid.uuid4())[:8]
    _async_jobs[task_id]['run_id'] = run_id
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO task_runs (id, task_id, status, started_at, trigger_type, user_id, created_at) VALUES (?,?,?,?,?,?,?)",
            (run_id, task_id, 'running', start_dt.isoformat(), trigger_type, user_id, start_dt.isoformat())
        )
        conn.commit()

    try:
        from app import create_app as _create_app
        _app = _create_app()
        with _app.app_context():
            from app.scheduler.report_executor import generate_report
            result = generate_report(
                template_id=report_cfg.get('template_id'),
                prompt_template=report_cfg.get('prompt'),
                data_sources=report_cfg.get('sources'),
                trend_reference=report_cfg.get('trend_reference', True),
                use_harness=report_cfg.get('use_harness', True),
                rss_source_ids=report_cfg.get('rss_source_ids'),
                task_id=task_id,
                user_id=user_id,
                use_preferences=report_cfg.get('use_preferences', False),
            )

        end_dt = bj_now()
        duration_ms = int((end_dt - start_dt).total_seconds() * 1000)

        success = result.get('success', False)
        if success:
            lines = [
                f'报告生成完成',
                f'文件: {result.get("filename", "")}',
                f'路径: {result.get("path", "")}',
                f'模型: {result.get("model_used", "unknown")}',
                f'耗时: {(end_dt - start_dt).total_seconds():.1f}s',
            ]
            if report_cfg.get('sources'):
                lines.append(f'数据源: {", ".join(report_cfg["sources"])}')
            if user_id:
                lines.append(f'用户: {user_id}')
            if push_channel_ids:
                lines.append(f'推送渠道: {len(push_channel_ids)} 个')
            stdout_text = '\n'.join(lines)
        else:
            stdout_text = result.get('error', 'Unknown error')
        artifacts = _scan_artifacts(base_dir, module, start_ts)
        arts_json = json.dumps(artifacts, ensure_ascii=False)

        success = result.get('success', False)
        with sqlite3.connect(db_path) as conn:
            if success:
                conn.execute(
                    "UPDATE task_runs SET status='done', finished_at=?, duration_ms=?, exit_code=0, stdout=?, artifacts=? WHERE id=?",
                    (end_dt.isoformat(), duration_ms, stdout_text[:5000], arts_json, run_id)
                )
                conn.execute(
                    "UPDATE scheduled_tasks SET last_run=?, run_count=run_count+1, success_count=success_count+1, last_error=NULL, last_log=? WHERE id=?",
                    (end_dt.isoformat(), stdout_text[:2000], task_id)
                )
            else:
                err_msg = result.get('error', 'Unknown error')
                conn.execute(
                    "UPDATE task_runs SET status='failed', finished_at=?, duration_ms=?, exit_code=1, stdout=?, stderr=?, artifacts=? WHERE id=?",
                    (end_dt.isoformat(), duration_ms, stdout_text[:5000], err_msg[:2000], arts_json, run_id)
                )
                conn.execute(
                    "UPDATE scheduled_tasks SET last_run=?, run_count=run_count+1, fail_count=fail_count+1, last_error=?, last_log=? WHERE id=?",
                    (end_dt.isoformat(), err_msg[:500], stdout_text[:2000], task_id)
                )
            conn.commit()

        _async_jobs[task_id]['status'] = 'done'
        _async_jobs[task_id]['run_id'] = run_id
        logger.info("[%s] Report job finished, success=%s", task_id, success)

        # Link to the Report record created by generate_report's _save_report_record
        if success and result.get('path'):
            try:
                with _app.app_context():
                    from app.models.report import Report
                    q = Report.query.filter_by(file_path=result['path'])
                    report = q.order_by(Report.generated_at.desc()).first()
                    if report:
                        report_id = report.id
                        with sqlite3.connect(db_path) as conn:
                            conn.execute("UPDATE task_runs SET report_id=? WHERE id=?", (report_id, run_id))
                            conn.commit()
                        logger.info("[%s] Linked Report %s to run %s", task_id, report_id, run_id)
                    else:
                        # Fallback: create record if _save_report_record didn't run
                        report_title = f'Platform Report {end_dt.strftime("%Y-%m-%d %H:%M")}'
                        try:
                            report_path = result['path']
                            if os.path.isfile(report_path):
                                with open(report_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                from app.scheduler.report_executor import _extract_title
                                filename = os.path.splitext(os.path.basename(report_path))[0]
                                extracted = _extract_title(content, fallback=filename)
                                if extracted and len(extracted) > 2:
                                    report_title = extracted
                        except Exception:
                            pass
                        with sqlite3.connect(db_path) as conn:
                            report_id = str(uuid.uuid4())
                            conn.execute(
                                "INSERT INTO reports (id, title, report_type, file_path, generated_at, scope, task_id) VALUES (?,?,?,?,?,?,?)",
                                (report_id, report_title, module or 'insight', result['path'], end_dt.isoformat(), 'platform', task_id)
                            )
                            conn.execute("UPDATE task_runs SET report_id=? WHERE id=?", (report_id, run_id))
                            conn.commit()
                            logger.info("[%s] Created fallback Report %s", task_id, report_id)
            except Exception as re:
                logger.warning("[%s] Failed to link Report: %s", task_id, re)

        # 报告生成成功后触发推送
        if success and result.get('path'):
            try:
                with _app.app_context():
                    from app.utils.helpers import bj_now as _bj_now
                    date_str = _bj_now().strftime('%Y-%m-%d')
                    push_title = f'{task_name} · {date_str}' if task_name else date_str

                    if user_id and push_channel_ids:
                        # open-source: skip user-specific push, use notify_report instead
                        logger.info("[%s] Skipping per-user push (open-source mode), using notify_report", task_id)

                    report_type = module or 'insight'
                    from app.services.report_notifier import notify_report
                    notify_report(result['path'], report_type, title=push_title, app=_app)
                    logger.info("[%s] Report notification triggered for %s", task_id, result['path'])
            except Exception as ne:
                import traceback
                push_err = f'{type(ne).__name__}: {ne}\n{traceback.format_exc()}'
                logger.warning("[%s] Push failed: %s", task_id, push_err)
                with sqlite3.connect(db_path) as conn:
                    conn.execute("UPDATE task_runs SET stderr=? WHERE id=?", (push_err[:2000], run_id))
                    conn.commit()

    except Exception as e:
        end_dt = bj_now()
        duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE task_runs SET status='error', finished_at=?, duration_ms=?, stderr=? WHERE id=?",
                (end_dt.isoformat(), duration_ms, str(e)[:2000], run_id)
            )
            conn.commit()
        _async_jobs[task_id]['status'] = 'error'
        _async_jobs[task_id]['error'] = str(e)
        _async_jobs[task_id]['run_id'] = run_id
        logger.error("[%s] Report job error: %s", task_id, e)


def _run_rss_async(task_id, task, base_dir, trigger_type):
    """后台线程执行 RSS 爬虫任务"""
    import sqlite3
    from app.scheduler.executor import TaskExecutor
    db_path = os.path.join(base_dir, 'data', 'intel_hub.db')
    start_dt = bj_now()

    run_id = str(uuid.uuid4())[:8]
    _async_jobs[task_id]['run_id'] = run_id
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO task_runs (id, task_id, status, started_at, trigger_type, created_at) VALUES (?,?,?,?,?,?)",
            (run_id, task_id, 'running', start_dt.isoformat(), trigger_type, start_dt.isoformat())
        )
        conn.commit()

    try:
        from app import create_app as _create_app
        _app = _create_app()
        with _app.app_context():
            executor = TaskExecutor(base_dir)
            result = executor.execute(task)
        end_dt = bj_now()
        duration_ms = int((end_dt - start_dt).total_seconds() * 1000)

        arts_json = json.dumps(result.get('artifacts', []), ensure_ascii=False)
        exit_code = result.get('exit_code', 1)
        status = 'done' if exit_code == 0 else 'failed'

        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE task_runs SET status=?, finished_at=?, duration_ms=?, exit_code=?, stdout=?, stderr=?, artifacts=? WHERE id=?",
                (status, end_dt.isoformat(), duration_ms, exit_code,
                 (result.get('stdout', '') or '')[:5000], (result.get('stderr', '') or '')[:2000], arts_json, run_id)
            )
            if exit_code == 0:
                conn.execute(
                    "UPDATE scheduled_tasks SET last_run=?, run_count=run_count+1, success_count=success_count+1, last_error=NULL, last_log=? WHERE id=?",
                    (end_dt.isoformat(), (result.get('stdout', '') or '')[:2000], task_id)
                )
            else:
                conn.execute(
                    "UPDATE scheduled_tasks SET last_run=?, run_count=run_count+1, fail_count=fail_count+1, last_error=?, last_log=? WHERE id=?",
                    (end_dt.isoformat(), (result.get('stderr', '') or '')[:500], (result.get('stdout', '') or '')[:2000], task_id)
                )
            conn.commit()

        _async_jobs[task_id]['status'] = status
        _async_jobs[task_id]['exit_code'] = exit_code
        _async_jobs[task_id]['run_id'] = run_id
        logger.info("[%s] RSS async job finished, exit_code=%d", task_id, exit_code)

    except Exception as e:
        end_dt = bj_now()
        duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE task_runs SET status='error', finished_at=?, duration_ms=?, stderr=? WHERE id=?",
                (end_dt.isoformat(), duration_ms, str(e)[:2000], run_id)
            )
            conn.commit()
        _async_jobs[task_id]['status'] = 'error'
        _async_jobs[task_id]['error'] = str(e)
        _async_jobs[task_id]['run_id'] = run_id
        logger.error("[%s] RSS async job error: %s", task_id, e)


def _run_script_async(task_id, script_path, base_dir, trigger_type, module):
    """后台线程执行脚本任务"""
    import sqlite3
    db_path = os.path.join(base_dir, 'data', 'intel_hub.db')
    start_ts = bj_now().timestamp()
    start_dt = bj_now()

    # 创建 TaskRun 记录
    run_id = str(uuid.uuid4())[:8]
    _async_jobs[task_id]['run_id'] = run_id
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO task_runs (id, task_id, status, started_at, trigger_type, created_at) VALUES (?,?,?,?,?,?)",
            (run_id, task_id, 'running', start_dt.isoformat(), trigger_type, start_dt.isoformat())
        )
        conn.commit()

    try:
        result = subprocess.run(
            ['bash', script_path],
            capture_output=True, text=True, timeout=600,
            cwd=base_dir
        )
        end_dt = bj_now()
        duration_ms = int((end_dt - start_dt).total_seconds() * 1000)

        # 扫描产物
        artifacts = _scan_artifacts(base_dir, module, start_ts)
        arts_json = json.dumps(artifacts, ensure_ascii=False)

        with sqlite3.connect(db_path) as conn:
            if result.returncode == 0:
                conn.execute(
                    "UPDATE task_runs SET status='done', finished_at=?, duration_ms=?, exit_code=?, stdout=?, stderr=?, artifacts=? WHERE id=?",
                    (end_dt.isoformat(), duration_ms, result.returncode,
                     result.stdout[-5000:], result.stderr[-2000:], arts_json, run_id)
                )
                conn.execute(
                    "UPDATE scheduled_tasks SET last_run=?, run_count=run_count+1, success_count=success_count+1, last_error=NULL, last_log=? WHERE id=?",
                    (end_dt.isoformat(), result.stdout[-2000:], task_id)
                )
            else:
                conn.execute(
                    "UPDATE task_runs SET status='failed', finished_at=?, duration_ms=?, exit_code=?, stdout=?, stderr=?, artifacts=? WHERE id=?",
                    (end_dt.isoformat(), duration_ms, result.returncode,
                     result.stdout[-5000:], result.stderr[-2000:], arts_json, run_id)
                )
                conn.execute(
                    "UPDATE scheduled_tasks SET last_run=?, run_count=run_count+1, fail_count=fail_count+1, last_error=?, last_log=? WHERE id=?",
                    (end_dt.isoformat(), result.stderr[:500], result.stdout[-2000:], task_id)
                )
            conn.commit()

        _async_jobs[task_id]['status'] = 'done'
        _async_jobs[task_id]['exit_code'] = result.returncode
        _async_jobs[task_id]['run_id'] = run_id
        logger.info("[%s] Async job finished, exit_code=%d, artifacts=%d", task_id, result.returncode, len(artifacts))

    except subprocess.TimeoutExpired:
        end_dt = bj_now()
        duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE task_runs SET status='timeout', finished_at=?, duration_ms=? WHERE id=?",
                (end_dt.isoformat(), duration_ms, run_id)
            )
            conn.execute(
                "UPDATE scheduled_tasks SET last_run=?, run_count=run_count+1, fail_count=fail_count+1, last_error='Timeout' WHERE id=?",
                (end_dt.isoformat(), task_id)
            )
            conn.commit()
        _async_jobs[task_id]['status'] = 'timeout'
        _async_jobs[task_id]['run_id'] = run_id

    except Exception as e:
        end_dt = bj_now()
        duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                "UPDATE task_runs SET status='error', finished_at=?, duration_ms=?, stderr=? WHERE id=?",
                (end_dt.isoformat(), duration_ms, str(e)[:2000], run_id)
            )
            conn.commit()
        _async_jobs[task_id]['status'] = 'error'
        _async_jobs[task_id]['error'] = str(e)
        _async_jobs[task_id]['run_id'] = run_id
        logger.error("[%s] Async job error: %s", task_id, e)


def _detect_real_type(schedule_type, cfg):
    """自动检测真实的调度类型（DB 中可能 type 和 config 不匹配）"""
    if isinstance(cfg, str):
        try:
            cfg = json.loads(cfg)
        except Exception:
            return schedule_type, cfg
    if not isinstance(cfg, dict):
        return schedule_type, cfg
    # 如果 type 说是 cron 但 config 只有 interval_minutes，修正为 interval
    if schedule_type == 'cron' and not cfg.get('cron') and not cfg.get('hour') and cfg.get('interval_minutes'):
        return 'interval', cfg
    # 如果 type 说是 interval 但 config 里有 cron 表达式，修正为 cron
    if schedule_type == 'interval' and cfg.get('cron'):
        return 'cron', cfg
    return schedule_type, cfg


def _human_schedule(schedule_type, schedule_config):
    """返回人类可读的调度描述

    支持两种 config 格式:
      1. 结构化: {"type":"cron","hour":9,"minute":0,"day_of_week":"1-5"}
      2. 原始 cron: {"type":"cron","cron":"0 9,13,15 * * 1-5"}
      3. interval: {"type":"interval","interval_minutes":90} 或 {"type":"interval","minutes":60}
    """
    cfg = schedule_config
    if isinstance(cfg, str):
        try:
            cfg = json.loads(cfg)
        except Exception:
            cfg = {}
    if not isinstance(cfg, dict):
        return str(schedule_config)
    # 自动修正 type/config 不匹配
    schedule_type, cfg = _detect_real_type(schedule_type, cfg)

    # ── cron 类型 ──
    if schedule_type == 'cron':
        # 优先使用原始 cron 表达式
        cron_expr = cfg.get('cron', '')
        if cron_expr:
            return _parse_cron_expr(cron_expr)

        # 否则用结构化字段
        hour = cfg.get('hour', '*')
        minute = cfg.get('minute', '0')
        day = cfg.get('day_of_week', '*')
        day_map = {'0': '周日', '1': '周一', '2': '周二', '3': '周三',
                   '4': '周四', '5': '周五', '6': '周六', '1-5': '工作日'}
        if str(day) == '1-5':
            day_str = '工作日'
        elif str(day) == '*':
            day_str = '每天'
        else:
            day_str = day_map.get(str(day), f'周{day}')

        def fmt_time(h, m):
            try:
                return f'{int(h):02d}:{int(m):02d}'
            except (ValueError, TypeError):
                return f'{h}:{m}'

        if isinstance(hour, list):
            times = [fmt_time(h, minute) for h in hour]
            return f'{day_str} {", ".join(times)}'
        return f'{day_str} {fmt_time(hour, minute)}'

    # ── interval 类型 ──
    elif schedule_type == 'interval':
        # 兼容 interval_minutes 和 minutes 两种 key
        mins = cfg.get('interval_minutes') or cfg.get('minutes') or 60
        try:
            mins = int(mins)
        except (ValueError, TypeError):
            return f"每{mins}分钟"
        if mins >= 60:
            hrs = mins // 60
            rem = mins % 60
            if rem == 0:
                return f'每{hrs}小时' if hrs > 1 else '每小时'
            return f'每{hrs}小时{rem}分钟'
        return f'每{mins}分钟'

    return str(schedule_config)


def _parse_cron_expr(expr):
    """解析标准 5 段 cron 表达式为中文描述"""
    parts = expr.strip().split()
    if len(parts) != 5:
        return expr

    minute, hour, day_of_month, month, day_of_week = parts

    # 星期描述
    dow_map = {'0': '周日', '1': '周一', '2': '周二', '3': '周三',
               '4': '周四', '5': '周五', '6': '周六', '1-5': '工作日',
               '1-6': '周一至周六', '0-6': '每天', '*': '每天'}
    if day_of_week == '*':
        day_str = '每天'
    elif day_of_week in dow_map:
        day_str = dow_map[day_of_week]
    else:
        day_str = f'周{day_of_week}'

    # 时间描述
    if hour == '*':
        time_str = '每小时'
        if minute != '0':
            time_str += f':{minute}'
        return f'{day_str} {time_str}'

    hours = [h.strip() for h in str(hour).split(',')]
    try:
        times = [f'{int(h):02d}:{int(minute):02d}' for h in hours]
    except (ValueError, TypeError):
        times = [f'{h}:{minute}' for h in hours]

    return f'{day_str} {", ".join(times)}'


def _calc_next_run(schedule_type, schedule_config):
    """根据 schedule 配置计算下次执行时间"""
    cfg = schedule_config
    if isinstance(cfg, str):
        try:
            cfg = json.loads(cfg)
        except Exception:
            return None
    if not isinstance(cfg, dict):
        return None
    # 自动修正 type/config 不匹配
    schedule_type, cfg = _detect_real_type(schedule_type, cfg)

    now = bj_now()

    try:
        if schedule_type == 'cron':
            cron_expr = cfg.get('cron', '')
            if cron_expr:
                # 用 croniter 计算下次执行时间
                try:
                    from croniter import croniter
                    cron = croniter(cron_expr, now)
                    return cron.get_next(datetime.datetime).isoformat()
                except ImportError:
                    pass
                # 无 croniter，简单估算
                parts = cron_expr.strip().split()
                if len(parts) == 5:
                    hour_part = parts[1]
                    minute_part = parts[0]
                    if hour_part != '*':
                        hours = [int(h) for h in hour_part.split(',')]
                        target_h = min((h for h in hours if h >= now.hour), default=hours[0])
                        target_m = int(minute_part) if minute_part != '*' else 0
                        if target_h == now.hour and target_m <= now.minute:
                            # 今天这个时间已过，取下一个
                            hours_sorted = sorted(hours)
                            idx = hours_sorted.index(target_h)
                            if idx < len(hours_sorted) - 1:
                                target_h = hours_sorted[idx + 1]
                            else:
                                target_h = hours_sorted[0]  # 明天
                        next_dt = now.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
                        if next_dt <= now:
                            next_dt += datetime.timedelta(days=1)
                        return next_dt.isoformat()

            # 结构化 cron
            hour = cfg.get('hour', 9)
            minute = cfg.get('minute', 0)
            try:
                target = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
            except (ValueError, TypeError):
                return None
            if target <= now:
                target += datetime.timedelta(days=1)
            return target.isoformat()

        elif schedule_type == 'interval':
            mins = cfg.get('interval_minutes') or cfg.get('minutes') or 60
            try:
                mins = int(mins)
            except (ValueError, TypeError):
                return None
            return (now + datetime.timedelta(minutes=mins)).isoformat()

    except Exception:
        return None
    return None


@bp.route('', methods=['GET'])
def list_tasks():
    tasks = ScheduledTask.query.all()
    # 从 app 获取 worker 实例
    from flask import current_app
    worker = getattr(current_app, 'scheduler', None)

    # 批量查询用户信息，避免 N+1
    from app.models.user import User
    user_ids = {t.user_id for t in tasks if t.user_id}
    users = {u.id: u for u in User.query.filter(User.id.in_(user_ids)).all()} if user_ids else {}

    result = []
    for t in tasks:
        d = t.to_dict()
        d['schedule_description'] = _human_schedule(t.schedule_type, t.schedule_config)
        if t.user_id and t.user_id in users:
            u = users[t.user_id]
            d['user_display_name'] = u.display_name or ''
            d['user_email'] = u.email or ''
        if t.id in _async_jobs:
            d['_async_status'] = _async_jobs[t.id]['status']
        # 从 Worker 获取真实的下次执行时间
        if worker:
            nrt = worker.get_next_run_time(t.id)
            if nrt:
                d['next_run_time'] = nrt
            is_paused = worker.is_task_paused(t.id)
            if is_paused:
                d['worker_paused'] = True
        result.append(d)
    return standard_response(result)


@bp.route('/<task_id>/run', methods=['POST'])
def run_task(task_id):
    task = db.session.get(ScheduledTask, task_id)
    if not task:
        return error_response(404, 'Task {} not found'.format(task_id))

    if task_id in _async_jobs and _async_jobs[task_id]['status'] == 'running':
        return error_response(409, 'Task {} is already running'.format(task_id))

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script_val = task.script or ''

    trigger_type = 'manual'
    try:
        payload = request.get_json(silent=True)
        if payload:
            trigger_type = payload.get('trigger_type', 'manual')
    except Exception:
        pass

    _async_jobs[task_id] = {
        'status': 'running',
        'started_at': bj_now().isoformat(),
    }

    # 报告/分析任务: script 字段是 JSON 配置，路由到 report_executor
    if task.task_type in ('report', 'analysis') and script_val.strip().startswith('{'):
        try:
            report_cfg = json.loads(script_val)
        except Exception:
            report_cfg = {}
        t = threading.Thread(
            target=_run_report_async,
            args=(task_id, report_cfg, base_dir, trigger_type, task.module)
        )
        t.daemon = True
        t.start()
        return standard_response({
            'task_id': task_id,
            'status': 'started',
            'message': 'Report task started in background',
            'started_at': _async_jobs[task_id]['started_at'],
        })

    # RSS 爬虫任务: script 字段 JSON 含 type=rss，路由到 executor
    if task.task_type == 'crawler' and script_val.strip().startswith('{'):
        try:
            rss_cfg = json.loads(script_val)
            if rss_cfg.get('type') == 'rss':
                t = threading.Thread(
                    target=_run_rss_async,
                    args=(task_id, task, base_dir, trigger_type)
                )
                t.daemon = True
                t.start()
                return standard_response({
                    'task_id': task_id,
                    'status': 'started',
                    'message': 'RSS crawler task started in background',
                    'started_at': _async_jobs[task_id]['started_at'],
                })
        except Exception:
            pass  # fall through to script path

    # 脚本任务: 查找并执行 bash 脚本
    if os.path.isabs(script_val):
        script_path = script_val
    else:
        script_path = os.path.join(base_dir, script_val)
        # 搜索 scripts/cron_wrappers/ 目录
        if not os.path.exists(script_path):
            alt = os.path.join(base_dir, 'scripts', 'cron_wrappers', script_val)
            if os.path.exists(alt):
                script_path = alt

    if not os.path.exists(script_path):
        # 清理 async_jobs 状态
        _async_jobs.pop(task_id, None)
        return error_response(404, 'Script not found: {}'.format(script_path))

    t = threading.Thread(
        target=_run_script_async,
        args=(task_id, script_path, base_dir, trigger_type, task.module)
    )
    t.daemon = True
    t.start()

    return standard_response({
        'task_id': task_id,
        'status': 'started',
        'message': 'Task started in background',
        'started_at': _async_jobs[task_id]['started_at'],
    })


@bp.route('/<task_id>/status', methods=['GET'])
def task_status(task_id):
    """查询异步任务实时状态"""
    if task_id not in _async_jobs:
        return error_response(404, 'No async job found')
    return standard_response(_async_jobs[task_id])


@bp.route('/<task_id>/runs', methods=['GET'])
def task_runs(task_id):
    """获取任务的所有执行记录"""
    task = db.session.get(ScheduledTask, task_id)
    if not task:
        return error_response(404, 'Task {} not found'.format(task_id)), 404

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    per_page = min(per_page, 100)

    pagination = TaskRun.query.filter_by(task_id=task_id)\
        .order_by(TaskRun.started_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    items = []
    for r in pagination.items:
        d = r.to_dict()
        _enrich_run_artifacts(d, task, base_dir)
        items.append(d)

    return standard_response({
        'items': items,
        'total': pagination.total,
        'page': page,
        'per_page': per_page,
    })


def _task_output_dirs(task):
    """根据任务的 module 和 task_type 返回产物扫描目录列表"""
    from flask import current_app
    base_dir = current_app.config.get('BASE_DIR', '')
    if not base_dir:
        return []

    module = getattr(task, 'module', '')
    task_type = getattr(task, 'task_type', '')
    dirs = []

    if task_type == 'report':
        dirs.append(os.path.join(base_dir, 'reports', 'agent'))
        dirs.append(os.path.join(base_dir, 'reports', 'insight'))
    elif task_type == 'analysis':
        dirs.append(os.path.join(base_dir, 'reports', 'heartbeat'))
        dirs.append(os.path.join(base_dir, 'reports', 'insight'))
    elif task_type == 'knowledge':
        dirs.append(os.path.join(base_dir, 'data', 'knowledge'))
        dirs.append(os.path.join(base_dir, 'reports', 'insight'))
    elif module == 'aggregate':
        dirs.append(os.path.join(base_dir, 'data', 'processed'))
    elif module == 'system':
        dirs.append(os.path.join(base_dir, 'reports', 'heartbeat'))
        dirs.append(os.path.join(base_dir, 'data', 'freshness'))
    elif module:
        dirs.append(os.path.join(base_dir, 'data', 'raw', module))

    return [d for d in dirs if os.path.isdir(d)]


def _enrich_run_artifacts(run_dict, task, base_dir):
    """用实时扫描替代 DB 中的旧 artifacts"""
    from flask import current_app
    if not base_dir:
        base_dir = current_app.config.get('BASE_DIR', '')
    if not base_dir or not task:
        return
    scan_dirs = _task_output_dirs(task)
    since_time = 0
    started = run_dict.get('started_at')
    if started:
        from datetime import datetime as _dt
        try:
            since_time = _dt.fromisoformat(started).timestamp()
        except Exception:
            pass
    artifacts = []
    for scan_dir in scan_dirs:
        for f in sorted(glob.glob(os.path.join(scan_dir, '**', '*.*'), recursive=True)):
            try:
                if os.path.islink(f) and not os.path.exists(f):
                    continue
                if not f.endswith(('.json', '.md')):
                    continue
                if since_time and os.path.getmtime(f) < since_time:
                    continue
                artifacts.append({
                    'name': os.path.basename(f),
                    'path': os.path.relpath(f, base_dir),
                    'size': os.path.getsize(f),
                })
            except Exception:
                pass
    run_dict['artifacts'] = artifacts[-30:]


@bp.route('/<task_id>/runs/<run_id>', methods=['GET'])
def task_run_detail(task_id, run_id):
    """获取单条执行记录，实时扫描产物"""
    run = db.session.get(TaskRun, run_id)
    if not run or run.task_id != task_id:
        return error_response(404, 'Run {} not found'.format(run_id)), 404

    result = run.to_dict()
    task = db.session.get(ScheduledTask, task_id)
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _enrich_run_artifacts(result, task, base_dir)

    return standard_response(result)


# --- CRUD ---

@bp.route('', methods=['POST'])
@admin_required
def create_task():
    data = request.get_json()

    # 管理员：interval 最小 60 分钟
    schedule_cfg = data.get('schedule_config', {})
    if isinstance(schedule_cfg, str):
        try:
            schedule_cfg = json.loads(schedule_cfg)
        except Exception:
            schedule_cfg = {}
    stype = data.get('schedule_type', schedule_cfg.get('type', ''))
    if (stype == 'interval' or schedule_cfg.get('type') == 'interval'):
        mins = schedule_cfg.get('interval_minutes') or schedule_cfg.get('minutes') or 0
        if int(mins) < 60:
            return error_response(400, '定时任务间隔不能小于 60 分钟')

    # tags 可以是数组或字符串
    tags_val = data.get('tags', '')
    if isinstance(tags_val, list):
        tags_val = ','.join(tags_val)
    task = ScheduledTask(
        id=str(uuid.uuid4())[:8],
        name=data['name'],
        module=data.get('module', 'hot_topics'),
        script=data.get('script', ''),
        schedule_type=data.get('schedule_type', 'interval'),
        schedule_config=json.dumps(data.get('schedule_config', {})) if isinstance(data.get('schedule_config'), dict) else data.get('schedule_config', '{}'),
        enabled=data.get('enabled', True),
        deliver_to=data.get('deliver_to', 'local'),
        notify_on_failure=data.get('notify_on_failure', False),
        description=data.get('description', ''),
        tags=tags_val,
        task_type=data.get('task_type', 'crawler'),
    )
    db.session.add(task)
    db.session.commit()
    # 同步到 Worker
    if task.enabled:
        _worker_register(task)
    return standard_response(task.to_dict()), 201


@bp.route('/<task_id>', methods=['GET'])
def get_task(task_id):
    task = db.session.get(ScheduledTask, task_id)
    if not task:
        return error_response(404, 'Task {} not found'.format(task_id)), 404
    d = task.to_dict()
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # 追加最近一次运行信息
    last_run = TaskRun.query.filter_by(task_id=task_id).order_by(TaskRun.started_at.desc()).first()
    if last_run:
        run_d = last_run.to_dict()
        _enrich_run_artifacts(run_d, task, base_dir)
        d['last_run_detail'] = run_d
    return standard_response(d)


@bp.route('/<task_id>', methods=['PUT'])
def update_task(task_id):
    task = db.session.get(ScheduledTask, task_id)
    if not task:
        return error_response(404, 'Task {} not found'.format(task_id)), 404
    data = request.get_json()

    # 管理员：interval 最小 60 分钟
    schedule_cfg = data.get('schedule_config', {})
    if isinstance(schedule_cfg, str):
        try:
            schedule_cfg = json.loads(schedule_cfg)
        except Exception:
            schedule_cfg = {}
    stype = data.get('schedule_type', schedule_cfg.get('type', ''))
    if (stype == 'interval' or schedule_cfg.get('type') == 'interval'):
        mins = schedule_cfg.get('interval_minutes') or schedule_cfg.get('minutes') or 0
        if int(mins) < 60:
            return error_response(400, '定时任务间隔不能小于 60 分钟')

    # tags 可以是数组或字符串
    for key in ['name', 'module', 'script', 'schedule_type',
                'enabled', 'deliver_to', 'notify_on_failure', 'description', 'task_type']:
        if key in data:
            setattr(task, key, data[key])
    if 'schedule_config' in data:
        cfg = data['schedule_config']
        # DB 中 schedule_config 存为 JSON 字符串
        if isinstance(cfg, dict):
            cfg = json.dumps(cfg)
        task.schedule_config = cfg
    if 'tags' in data:
        tags_val = data['tags']
        if isinstance(tags_val, list):
            tags_val = ','.join(tags_val)
        task.tags = tags_val
    db.session.commit()
    # 同步到 Worker（编辑后重新注册）
    if task.enabled:
        _worker_register(task)
    else:
        _worker_unregister(task_id)
    return standard_response(task.to_dict())


@bp.route('/<task_id>', methods=['DELETE'])
def delete_task(task_id):
    task = db.session.get(ScheduledTask, task_id)
    if not task:
        return error_response(404, 'Task {} not found'.format(task_id)), 404
    db.session.delete(task)
    _async_jobs.pop(task_id, None)
    db.session.commit()
    # 从 Worker 移除
    _worker_unregister(task_id)
    return standard_response({'deleted': task_id})


@bp.route('/<task_id>/pause', methods=['POST'])
def pause_task(task_id):
    task = db.session.get(ScheduledTask, task_id)
    if not task:
        return error_response(404, 'Task {} not found'.format(task_id)), 404
    task.enabled = False
    db.session.commit()
    # 通知 Worker 暂停
    _worker_pause(task_id)
    return standard_response(task.to_dict())


@bp.route('/<task_id>/resume', methods=['POST'])
def resume_task(task_id):
    task = db.session.get(ScheduledTask, task_id)
    if not task:
        return error_response(404, 'Task {} not found'.format(task_id)), 404
    task.enabled = True
    db.session.commit()
    # 通知 Worker 恢复（重新注册）
    _worker_register(task)
    return standard_response(task.to_dict())


# ── Worker 同步 ──────────────────────────────────────────────────

def _get_worker():
    """获取当前 app 的 Worker 实例"""
    try:
        from flask import current_app
        return getattr(current_app, 'scheduler', None)
    except Exception:
        return None


def _worker_register(task):
    """将任务注册到 Worker"""
    worker = _get_worker()
    if worker:
        try:
            worker.register_task(task)
        except Exception as e:
            logger.warning(f'Worker register failed for {task.id}: {e}')


def _worker_unregister(task_id):
    """从 Worker 移除任务"""
    worker = _get_worker()
    if worker:
        try:
            worker.unregister_task(task_id)
        except Exception as e:
            logger.warning(f'Worker unregister failed for {task_id}: {e}')


def _worker_pause(task_id):
    """暂停 Worker 中的任务"""
    worker = _get_worker()
    if worker:
        try:
            worker.pause_task(task_id)
        except Exception as e:
            logger.warning(f'Worker pause failed for {task_id}: {e}')


def _worker_resume(task_id):
    """恢复 Worker 中的任务"""
    worker = _get_worker()
    if worker:
        try:
            worker.resume_task(task_id)
        except Exception as e:
            logger.warning(f'Worker resume failed for {task_id}: {e}')
