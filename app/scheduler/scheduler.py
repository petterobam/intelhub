"""APScheduler Worker - 基于 APScheduler 的任务调度引擎

核心职责:
  - 管理所有定时任务的生命周期（注册/移除/暂停/恢复）
  - 根据任务配置生成正确的 APScheduler Trigger
  - 通过 TaskExecutor 执行任务并回写结果到 DB
  - 支持热更新（任务创建/编辑/启用/禁用后自动同步）
  - Worker 心跳与任务运行状态实时追踪
"""
import json
import logging
import socket
import os
from app.utils.helpers import bj_now

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)


def _parse_cfg(cfg):
    """统一解析 schedule_config（可能是 dict 或 JSON 字符串）"""
    if isinstance(cfg, str):
        try:
            return json.loads(cfg)
        except Exception:
            return {}
    return cfg or {}


class TaskScheduler:
    """基于 APScheduler 的 Worker 调度引擎"""

    def __init__(self, app=None, worker_id=None, role=None):
        self.scheduler = BackgroundScheduler()
        self.app = app
        self._job_map = {}      # task_id -> APScheduler Job
        self._executor = None
        self.worker_id = worker_id or 'standalone-0'
        self.role = role or 'system'

    def init_app(self, app):
        self.app = app

    # ── Trigger 构建 ──────────────────────────────────────────────────────

    def _get_trigger(self, task):
        cfg = _parse_cfg(task.schedule_config)
        schedule_type = task.schedule_type

        if schedule_type == 'cron' and not cfg.get('cron') and not cfg.get('hour') and cfg.get('interval_minutes'):
            schedule_type = 'interval'
        elif schedule_type == 'interval' and cfg.get('cron'):
            schedule_type = 'cron'

        if schedule_type == 'cron':
            return self._make_cron_trigger(cfg)
        else:
            return self._make_interval_trigger(cfg)

    def _make_cron_trigger(self, cfg):
        cron_expr = cfg.get('cron', '')
        if cron_expr:
            parts = cron_expr.strip().split()
            if len(parts) == 5:
                try:
                    return CronTrigger(
                        minute=parts[0], hour=parts[1],
                        day=parts[2], month=parts[3], day_of_week=parts[4],
                    )
                except Exception as e:
                    logger.warning(f"Failed to parse cron '{cron_expr}': {e}")

        return CronTrigger(
            hour=cfg.get('hour', 0), minute=cfg.get('minute', 0),
            day_of_week=cfg.get('day_of_week', '*'),
            day=cfg.get('day', '*'), month=cfg.get('month', '*'),
        )

    def _make_interval_trigger(self, cfg):
        mins = cfg.get('interval_minutes') or cfg.get('minutes') or 60
        try:
            mins = int(mins)
        except (ValueError, TypeError):
            mins = 60
        return IntervalTrigger(minutes=mins)

    # ── 任务生命周期 ────────────────────────────────────────────────────────

    def _get_executor(self):
        if self._executor is None:
            from app.scheduler.executor import TaskExecutor
            base_dir = self.app.config.get('BASE_DIR', '') if self.app else ''
            self._executor = TaskExecutor(base_dir)
        return self._executor

    def _update_task_status(self, task_id, status, started_at=None):
        """更新 task_run_status 表的实时状态"""
        if not self.app:
            return
        try:
            from app import db
            from sqlalchemy import text
            now = bj_now()
            if status == 'running':
                db.session.execute(text(
                    "INSERT OR REPLACE INTO task_run_status (task_id, worker_id, status, started_at, updated_at) "
                    "VALUES (:tid, :wid, 'running', :sa, :now)"
                ), {'tid': task_id, 'wid': self.worker_id, 'sa': started_at or now, 'now': now})
            else:
                db.session.execute(text(
                    "UPDATE task_run_status SET status=:st, updated_at=:now WHERE task_id=:tid"
                ), {'st': status, 'now': now, 'tid': task_id})
            db.session.commit()
        except Exception as e:
            logger.warning(f"Failed to update task_run_status: {e}")

    def _make_job_func(self, task):
        """创建任务执行函数（在 worker 线程中运行）"""
        scheduler_self = self

        def job_func():
            import uuid as _uuid
            start_dt = bj_now()
            scheduler_self._update_task_status(task.id, 'running', started_at=start_dt)
            result = None
            if scheduler_self.app:
                with scheduler_self.app.app_context():
                    executor = scheduler_self._get_executor()
                    result = executor.execute(task)
            else:
                executor = scheduler_self._get_executor()
                result = executor.execute(task)
            end_dt = bj_now()
            duration_ms = int((end_dt - start_dt).total_seconds() * 1000)
            # 回写执行结果到 DB
            if scheduler_self.app:
                with scheduler_self.app.app_context():
                    from app import db
                    from app.models.task import ScheduledTask
                    from app.models.task_run import TaskRun
                    run_status = 'done' if result.get('exit_code', 0) == 0 else 'failed'
                    if result.get('status') == 'timeout':
                        run_status = 'timeout'
                    elif result.get('status') == 'error':
                        run_status = 'failed'
                    task_run = TaskRun(
                        id=str(_uuid.uuid4())[:8],
                        task_id=task.id,
                        status=run_status,
                        started_at=start_dt,
                        finished_at=end_dt,
                        duration_ms=duration_ms,
                        exit_code=result.get('exit_code', 0),
                        stdout=result.get('stdout', '')[-10000:],
                        stderr=result.get('stderr', '')[-3000:],
                        artifacts=json.dumps(result.get('artifacts', []), ensure_ascii=False),
                        trigger_type='scheduled',
                    )
                    db.session.add(task_run)
                    t = db.session.get(ScheduledTask, task.id)
                    if t:
                        t.last_run = end_dt
                        t.run_count = (t.run_count or 0) + 1
                        if result.get('status') in ('success', 'offline'):
                            t.success_count = (t.success_count or 0) + 1
                        else:
                            t.fail_count = (t.fail_count or 0) + 1
                            t.last_error = result.get('stderr', '')[:500]
                    db.session.commit()

                    # 报告任务成功后触发推送
                    if task.task_type == 'report' and run_status == 'done':
                        try:
                            from app.models.report import Report
                            latest = Report.query.filter_by(task_id=task.id)\
                                .order_by(Report.generated_at.desc()).first()
                            if latest and latest.file_path:
                                from app.services.report_notifier import notify_report
                                task_name = t.name if t else task.name
                                date_str = bj_now().strftime('%Y-%m-%d')
                                push_title = f'{task_name} · {date_str}' if task_name else date_str
                                notify_report(latest.file_path, latest.report_type, title=push_title, app=scheduler_self.app)
                        except Exception as ne:
                            import traceback
                            logger.warning("Report notification failed: %s\n%s", ne, traceback.format_exc())

                    # 任务失败时触发告警
                    if run_status in ('failed', 'timeout'):
                        try:
                            from app.services.alert_service import send_task_alert
                            send_task_alert(task, result, run_status, scheduler_self.worker_id)
                        except Exception as ae:
                            logger.warning(f"Alert dispatch failed: {ae}")

            # 更新实时状态为 idle
            scheduler_self._update_task_status(task.id, 'idle')
            logger.info(f'[{scheduler_self.worker_id}] Task "{task.name}" ({task.id}) -> {result.get("status")}')
        return job_func

    def register_task(self, task):
        """注册一个新任务到调度器"""
        self.unregister_task(task.id)
        trigger = self._get_trigger(task)
        func = self._make_job_func(task)
        job = self.scheduler.add_job(func, trigger, id=task.id, replace_existing=True)
        self._job_map[task.id] = job
        logger.info(f'[{self.worker_id}] Registered task "{task.name}" ({task.id})')

    def unregister_task(self, task_id):
        """从调度器移除任务"""
        if task_id in self._job_map:
            try:
                self._job_map[task_id].remove()
            except Exception:
                pass
            del self._job_map[task_id]
            logger.info(f'[{self.worker_id}] Unregistered task {task_id}')

    def pause_task(self, task_id):
        if task_id in self._job_map:
            self._job_map[task_id].pause()
            logger.info(f'[{self.worker_id}] Paused task {task_id}')

    def resume_task(self, task_id):
        if task_id in self._job_map:
            self._job_map[task_id].resume()
            logger.info(f'[{self.worker_id}] Resumed task {task_id}')

    def is_task_paused(self, task_id):
        if task_id in self._job_map:
            return self._job_map[task_id].next_run_time is None
        return False

    def get_next_run_time(self, task_id):
        if task_id in self._job_map:
            nrt = self._job_map[task_id].next_run_time
            return nrt.isoformat() if nrt else None
        return None

    # ── 启动/停止 ──────────────────────────────────────────────────────────

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info(f'[{self.worker_id}] TaskScheduler started (role={self.role})')

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            # 清理本 worker 的心跳记录
            self._remove_heartbeat()
            logger.info(f'[{self.worker_id}] TaskScheduler shutdown')

    def load_tasks_from_db(self, system_only=False, user_only=False):
        """启动时从 DB 加载启用的任务，支持按角色过滤"""
        if not self.app:
            return
        with self.app.app_context():
            from app.models.task import ScheduledTask
            query = ScheduledTask.query.filter_by(enabled=True)
            if system_only:
                query = query.filter(ScheduledTask.user_id.is_(None))
            elif user_only:
                query = query.filter(ScheduledTask.user_id.isnot(None))
            tasks = query.all()
            for task in tasks:
                self.register_task(task)
            logger.info(f'[{self.worker_id}] Loaded {len(tasks)} tasks from DB (system={system_only}, user={user_only})')

    # ── 心跳机制 ──────────────────────────────────────────────────────────

    def start_heartbeat(self):
        """注册心跳 job：每 30 秒更新一次 scheduler_workers 表"""
        if not self.app:
            return
        with self.app.app_context():
            self._register_worker()
        self.scheduler.add_job(
            self._heartbeat_tick,
            'interval', seconds=30,
            id=f'_heartbeat_{self.worker_id}',
            replace_existing=True,
        )
        logger.info(f'[{self.worker_id}] Heartbeat started')

    def _register_worker(self):
        """在 scheduler_workers 表注册本 worker"""
        if not self.app:
            return
        try:
            from app import db
            from sqlalchemy import text
            now = bj_now()
            db.session.execute(text(
                "INSERT OR REPLACE INTO scheduler_workers "
                "(worker_id, role, pid, started_at, last_heartbeat, hostname) "
                "VALUES (:wid, :role, :pid, :now, :now, :host)"
            ), {
                'wid': self.worker_id,
                'role': self.role,
                'pid': os.getpid(),
                'now': now,
                'host': socket.gethostname(),
            })
            db.session.commit()
        except Exception as e:
            logger.warning(f"Failed to register worker: {e}")

    def _heartbeat_tick(self):
        """定时更新心跳 + 清理过期 worker"""
        if not self.app:
            return
        try:
            with self.app.app_context():
                from app import db
                from sqlalchemy import text
                now = bj_now()
                db.session.execute(text(
                    "UPDATE scheduler_workers SET last_heartbeat=:now WHERE worker_id=:wid"
                ), {'now': now, 'wid': self.worker_id})
                # 清理心跳超过 5 分钟的过期 worker（进程已死但记录残留）
                db.session.execute(text(
                    "DELETE FROM scheduler_workers WHERE last_heartbeat < :cutoff"
                ), {'cutoff': now - __import__('datetime').timedelta(minutes=5)})
                db.session.commit()
        except Exception as e:
            logger.warning(f"Heartbeat failed: {e}")

    def _remove_heartbeat(self):
        """移除本 worker 的心跳记录"""
        if not self.app:
            return
        try:
            with self.app.app_context():
                from app import db
                from sqlalchemy import text
                db.session.execute(text(
                    "DELETE FROM scheduler_workers WHERE worker_id=:wid"
                ), {'wid': self.worker_id})
                db.session.commit()
        except Exception:
            pass

    # ── 状态查询 ──────────────────────────────────────────────────────────

    def get_status(self):
        """获取调度器整体状态"""
        jobs = []
        for tid, job in self._job_map.items():
            nrt = job.next_run_time
            jobs.append({
                'task_id': tid,
                'next_run_time': nrt.isoformat() if nrt else None,
                'pending': job.pending,
            })
        return {
            'worker_id': self.worker_id,
            'role': self.role,
            'running': self.scheduler.running,
            'total_jobs': len(jobs),
            'jobs': jobs,
        }
