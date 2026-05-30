"""IntelHub Flask application factory — open-source version."""

import os
from pathlib import Path

from flask import Flask
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app(config_name=None):
    """Application factory."""

    # --- Load .env early if present ---
    try:
        from dotenv import load_dotenv
        env_path = Path(__file__).resolve().parent.parent / ".env"
        load_dotenv(dotenv_path=env_path)
    except ImportError:
        pass

    # --- Determine config ---
    if config_name is None:
        config_name = os.environ.get("FLASK_ENV", "development")

    from app.config import config_map
    config_class = config_map.get(config_name, config_map["development"])

    # --- Create & configure app ---
    flaskapp = Flask(__name__)
    flaskapp.config.from_object(config_class)

    # --- Extensions ---
    db.init_app(flaskapp)
    CORS(flaskapp)

    # --- Ensure data directories exist ---
    with flaskapp.app_context():
        from app.utils.helpers import ensure_dirs
        ensure_dirs()

        import app.models  # noqa: F401
        try:
            db.create_all()
        except Exception as e:
            flaskapp.logger.warning(f"db.create_all() skipped (likely concurrent worker): {e}")

        # 迁移：给已有 subscriptions 表添加 task_id 列
        try:
            result = db.session.execute(db.text("PRAGMA table_info(subscriptions)"))
            columns = [row[1] for row in result]
            if 'task_id' not in columns:
                db.session.execute(db.text(
                    "ALTER TABLE subscriptions ADD COLUMN task_id VARCHAR(16)"
                ))
                db.session.commit()
                flaskapp.logger.info("Migration: added task_id to subscriptions")
        except Exception as e:
            flaskapp.logger.warning(f"Migration check skipped: {e}")

        # 迁移：给 chat_sessions 表添加 user_id 列
        try:
            result = db.session.execute(db.text("PRAGMA table_info(chat_sessions)"))
            columns = [row[1] for row in result]
            if 'user_id' not in columns:
                db.session.execute(db.text(
                    "ALTER TABLE chat_sessions ADD COLUMN user_id VARCHAR(16)"
                ))
                db.session.commit()
                flaskapp.logger.info("Migration: added user_id to chat_sessions")
        except Exception as e:
            flaskapp.logger.warning(f"Migration check skipped: {e}")

        # 迁移：给 reports 表添加 scope / html_path / summary_path / task_id
        try:
            result = db.session.execute(db.text("PRAGMA table_info(reports)"))
            columns = [row[1] for row in result]
            for col, col_type in [
                ('scope', 'VARCHAR(16) DEFAULT "platform"'),
                ('html_path', 'VARCHAR(512)'),
                ('summary_path', 'VARCHAR(512)'),
                ('task_id', 'VARCHAR(36)'),
            ]:
                if col not in columns:
                    db.session.execute(db.text(f"ALTER TABLE reports ADD COLUMN {col} {col_type}"))
                    db.session.commit()
                    flaskapp.logger.info(f"Migration: added {col} to reports")
        except Exception as e:
            flaskapp.logger.warning(f"Migration check skipped: {e}")

        # 迁移：给 feedbacks 表添加 status 列
        try:
            result = db.session.execute(db.text("PRAGMA table_info(feedbacks)"))
            columns = [row[1] for row in result]
            if 'status' not in columns:
                db.session.execute(db.text("ALTER TABLE feedbacks ADD COLUMN status VARCHAR(32) DEFAULT 'pending'"))
                db.session.commit()
                flaskapp.logger.info("Migration: added status to feedbacks")
        except Exception as e:
            flaskapp.logger.warning(f"Migration (feedbacks status) skipped: {e}")

        # 迁移：创建 push_channels 表（如果不存在）
        try:
            result = db.session.execute(db.text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='push_channels'"
            ))
            if not result.fetchone():
                db.session.execute(db.text("""
                    CREATE TABLE push_channels (
                        id VARCHAR(16) NOT NULL,
                        user_id VARCHAR(16),
                        channel_type VARCHAR(32) NOT NULL,
                        name VARCHAR(64) NOT NULL,
                        config_json TEXT,
                        enabled BOOLEAN DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id)
                    )
                """))
                db.session.execute(db.text(
                    "CREATE INDEX ix_push_channels_user_id ON push_channels (user_id)"
                ))
                db.session.commit()
                flaskapp.logger.info("Migration: created push_channels table")
        except Exception as e:
            flaskapp.logger.warning(f"Migration check skipped: {e}")

        # 迁移：给 subscriptions 表添加 channel_id / channel_ids 列
        try:
            result = db.session.execute(db.text("PRAGMA table_info(subscriptions)"))
            columns = [row[1] for row in result]
            if 'channel_id' not in columns:
                db.session.execute(db.text(
                    "ALTER TABLE subscriptions ADD COLUMN channel_id VARCHAR(16)"
                ))
                db.session.commit()
                flaskapp.logger.info("Migration: added channel_id to subscriptions")
            if 'channel_ids' not in columns:
                db.session.execute(db.text(
                    "ALTER TABLE subscriptions ADD COLUMN channel_ids JSON DEFAULT '[]'"
                ))
                db.session.commit()
                flaskapp.logger.info("Migration: added channel_ids to subscriptions")
        except Exception as e:
            flaskapp.logger.warning(f"Migration (subscriptions.channel_ids) skipped: {e}")

        # 迁移：创建 rss_sources 表
        try:
            result = db.session.execute(db.text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='rss_sources'"
            ))
            if not result.fetchone():
                db.session.execute(db.text("""
                    CREATE TABLE rss_sources (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name VARCHAR(256) NOT NULL,
                        url VARCHAR(512) NOT NULL UNIQUE,
                        category VARCHAR(64) NOT NULL DEFAULT '其他',
                        description VARCHAR(512),
                        enabled BOOLEAN DEFAULT 1,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                db.session.commit()
                flaskapp.logger.info("Migration: created rss_sources table")
        except Exception as e:
            flaskapp.logger.warning(f"Migration check skipped: {e}")

        # 迁移：scheduled_tasks.script 从 VARCHAR(256) → TEXT
        try:
            result = db.session.execute(db.text("PRAGMA table_info(scheduled_tasks)"))
            for row in result:
                if row[1] == 'script' and 'varchar' in (row[2] or '').lower():
                    db.session.execute(db.text("DROP TABLE IF EXISTS scheduled_tasks_tmp"))
                    db.session.execute(db.text(
                        "CREATE TABLE scheduled_tasks_tmp AS SELECT * FROM scheduled_tasks"
                    ))
                    cols = [r[1] for r in db.session.execute(db.text("PRAGMA table_info(scheduled_tasks_tmp)"))]
                    col_defs = ', '.join(cols)
                    db.session.execute(db.text("DROP TABLE scheduled_tasks"))
                    db.session.execute(db.text("""
                        CREATE TABLE scheduled_tasks (
                            id VARCHAR(36) PRIMARY KEY,
                            name VARCHAR(128) NOT NULL,
                            task_type VARCHAR(32) NOT NULL DEFAULT 'crawler',
                            module VARCHAR(32) NOT NULL,
                            script TEXT NOT NULL,
                            description TEXT,
                            tags VARCHAR(256),
                            schedule_type VARCHAR(16) NOT NULL DEFAULT 'cron',
                            schedule_config TEXT NOT NULL DEFAULT '{}',
                            enabled BOOLEAN NOT NULL DEFAULT 1,
                            status VARCHAR(16) NOT NULL DEFAULT 'idle',
                            last_run DATETIME,
                            next_run DATETIME,
                            run_count INTEGER NOT NULL DEFAULT 0,
                            success_count INTEGER NOT NULL DEFAULT 0,
                            fail_count INTEGER NOT NULL DEFAULT 0,
                            last_error TEXT,
                            last_log TEXT,
                            deliver_to VARCHAR(32) NOT NULL DEFAULT 'local',
                            notify_on_failure BOOLEAN NOT NULL DEFAULT 0,
                            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                        )
                    """))
                    db.session.execute(db.text(
                        "INSERT INTO scheduled_tasks ({}) SELECT {} FROM scheduled_tasks_tmp".format(col_defs, col_defs)
                    ))
                    db.session.execute(db.text("DROP TABLE scheduled_tasks_tmp"))
                    db.session.commit()
                    flaskapp.logger.info("Migration: changed scheduled_tasks.script to TEXT")
                    break
        except Exception as e:
            flaskapp.logger.warning(f"Migration (script→Text) skipped: {e}")

        # 迁移：scheduled_tasks 加 user_id
        try:
            result = db.session.execute(db.text("PRAGMA table_info(scheduled_tasks)"))
            columns = [row[1] for row in result]
            if 'user_id' not in columns:
                db.session.execute(db.text(
                    "ALTER TABLE scheduled_tasks ADD COLUMN user_id VARCHAR(16)"
                ))
                db.session.execute(db.text(
                    "CREATE INDEX IF NOT EXISTS ix_scheduled_tasks_user_id ON scheduled_tasks (user_id)"
                ))
                db.session.commit()
                flaskapp.logger.info("Migration: added user_id to scheduled_tasks")
        except Exception as e:
            flaskapp.logger.warning(f"Migration (scheduled_tasks.user_id) skipped: {e}")

        # 迁移：task_runs 加 user_id + report_id
        try:
            result = db.session.execute(db.text("PRAGMA table_info(task_runs)"))
            columns = [row[1] for row in result]
            if 'user_id' not in columns:
                db.session.execute(db.text(
                    "ALTER TABLE task_runs ADD COLUMN user_id VARCHAR(16)"
                ))
                db.session.execute(db.text(
                    "CREATE INDEX IF NOT EXISTS ix_task_runs_user_id ON task_runs (user_id)"
                ))
                db.session.commit()
                flaskapp.logger.info("Migration: added user_id to task_runs")
            if 'report_id' not in columns:
                db.session.execute(db.text(
                    "ALTER TABLE task_runs ADD COLUMN report_id VARCHAR(36) REFERENCES reports(id)"
                ))
                db.session.commit()
                flaskapp.logger.info("Migration: added report_id to task_runs")
        except Exception as e:
            flaskapp.logger.warning(f"Migration (task_runs columns) skipped: {e}")

        # 迁移：创建 scheduler_workers 表
        try:
            result = db.session.execute(db.text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='scheduler_workers'"
            ))
            if not result.fetchone():
                db.session.execute(db.text("""
                    CREATE TABLE scheduler_workers (
                        worker_id VARCHAR(32) PRIMARY KEY,
                        role VARCHAR(16) NOT NULL,
                        pid INTEGER,
                        started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_heartbeat DATETIME,
                        hostname VARCHAR(64)
                    )
                """))
                db.session.commit()
                flaskapp.logger.info("Migration: created scheduler_workers table")
        except Exception as e:
            flaskapp.logger.warning(f"Migration (scheduler_workers) skipped: {e}")

        # 迁移：创建 task_run_status 表
        try:
            result = db.session.execute(db.text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='task_run_status'"
            ))
            if not result.fetchone():
                db.session.execute(db.text("""
                    CREATE TABLE task_run_status (
                        task_id VARCHAR(36) PRIMARY KEY,
                        worker_id VARCHAR(32),
                        status VARCHAR(16) DEFAULT 'idle',
                        started_at DATETIME,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """))
                db.session.commit()
                flaskapp.logger.info("Migration: created task_run_status table")
        except Exception as e:
            flaskapp.logger.warning(f"Migration (task_run_status) skipped: {e}")

        # 迁移：push_channels 加 is_alert 字段
        try:
            result = db.session.execute(db.text("PRAGMA table_info(push_channels)"))
            columns = [row[1] for row in result]
            if 'is_alert' not in columns:
                db.session.execute(db.text(
                    "ALTER TABLE push_channels ADD COLUMN is_alert BOOLEAN DEFAULT 0"
                ))
                db.session.commit()
                flaskapp.logger.info("Migration: added is_alert to push_channels")
        except Exception as e:
            flaskapp.logger.warning(f"Migration (push_channels.is_alert) skipped: {e}")

        # 初始化默认 admin 用户
        try:
            from app.models.user import User
            if not User.query.filter_by(email='admin@intelhub.local').first():
                admin = User(email='admin@intelhub.local', display_name='Admin', role='admin')
                admin.set_password('admin123')
                db.session.add(admin)
                db.session.commit()
                flaskapp.logger.info("Created default admin user")
        except Exception as e:
            flaskapp.logger.warning(f"Admin user creation skipped: {e}")

    # --- Register blueprints ---
    try:
        from app.api.tasks import bp as _tasks_bp
        from app.api.crawlers import bp as _crawlers_bp
        from app.api.data import bp as _data_bp
        from app.api.reports import bp as _reports_bp
        from app.api.health import bp as _health_bp
        from app.api.report_templates import bp as _report_templates_bp
        from app.api.scripts import bp as _scripts_bp
        from app.api.chat import bp as _chat_bp
        from app.api.knowledge import bp as _kb_bp
        from app.api.settings import bp as _settings_bp
        from app.api.subscriptions import bp as _subs_bp
        from app.api.prompt_optimizer import bp as _prompt_bp
        from app.api.push_channels import bp as _push_ch_bp

        flaskapp.register_blueprint(_tasks_bp)
        flaskapp.register_blueprint(_crawlers_bp)
        flaskapp.register_blueprint(_data_bp)
        flaskapp.register_blueprint(_reports_bp)
        flaskapp.register_blueprint(_health_bp)
        flaskapp.register_blueprint(_report_templates_bp)
        flaskapp.register_blueprint(_scripts_bp)
        flaskapp.register_blueprint(_chat_bp)
        flaskapp.register_blueprint(_kb_bp)
        flaskapp.register_blueprint(_settings_bp)
        flaskapp.register_blueprint(_subs_bp)
        flaskapp.register_blueprint(_prompt_bp)
        flaskapp.register_blueprint(_push_ch_bp)

        try:
            from app.api.admin import bp as _admin_bp
            flaskapp.register_blueprint(_admin_bp)
        except ImportError as e:
            flaskapp.logger.info(f"Admin blueprint not found: {e}")

        try:
            from app.api.feedback import bp as _feedback_bp
            flaskapp.register_blueprint(_feedback_bp)
        except ImportError as e:
            flaskapp.logger.info(f"Feedback blueprint not found: {e}")

        try:
            from app.api.rss_sources import bp as _rss_bp
            flaskapp.register_blueprint(_rss_bp)
        except ImportError as e:
            flaskapp.logger.info(f"RSS sources blueprint not found: {e}")

        try:
            from app.api.plaza import bp as _plaza_bp
            flaskapp.register_blueprint(_plaza_bp)
        except ImportError as e:
            flaskapp.logger.info(f"Plaza blueprint not found: {e}")
    except ImportError as e:
        flaskapp.logger.info(f"API blueprints not found: {e}")

    # --- Report viewer route ---
    @flaskapp.route('/r/<report_id>')
    def view_report(report_id):
        import os
        from flask import abort, request as req, make_response
        from app.models.report import Report

        report = Report.query.get(report_id)
        if not report:
            abort(404)

        if not report.html_path:
            abort(404)

        static_dir = flaskapp.static_folder
        full_path = os.path.join(static_dir, report.html_path)
        if not os.path.exists(full_path):
            abort(404)

        with open(full_path, 'r', encoding='utf-8') as f:
            html = f.read()
        resp = make_response(html)
        resp.headers['Content-Type'] = 'text/html; charset=utf-8'
        return resp

    # --- Configure logging ---
    import logging as _logging
    _gunicorn_logger = _logging.getLogger('gunicorn.error')

    def _forward_app_loggers():
        if _gunicorn_logger.handlers:
            for name in list(_logging.root.manager.loggerDict):
                if name.startswith('app.') or name.startswith('analysis.'):
                    lg = _logging.getLogger(name)
                    if not lg.handlers:
                        lg.handlers = _gunicorn_logger.handlers
                        lg.propagate = False
                        lg.setLevel(_logging.INFO)

    _forward_app_loggers()

    # --- Initialize and start scheduler ---
    _sched_role = os.environ.get("INTElHUB_SCHEDULER_ROLE", "system")
    _worker_id = os.environ.get("INTElHUB_WORKER_ID", "standalone")

    _scheduler_initialized = getattr(flaskapp, '_scheduler_initialized', False) or os.environ.get('_INTELHUB_SCHED_INIT')

    if _scheduler_initialized:
        flaskapp.logger.warning(f"Worker-{_worker_id}: scheduler already initialized, skipping")
        flaskapp.scheduler = getattr(flaskapp, 'scheduler', None)
    elif _sched_role == "none":
        flaskapp.logger.info(f"Worker-{_worker_id}: pure web role, scheduler disabled")
        flaskapp.scheduler = None
        flaskapp._scheduler_initialized = True
        os.environ['_INTELHUB_SCHED_INIT'] = '1'
    else:
        try:
            from app.scheduler import TaskScheduler
            scheduler = TaskScheduler(flaskapp, worker_id=f"{_sched_role}-{_worker_id}", role=_sched_role)
            scheduler.init_app(flaskapp)
            scheduler.start()
            if _sched_role == "system":
                scheduler.load_tasks_from_db(system_only=True)
            else:
                scheduler.load_tasks_from_db(user_only=True)
            _forward_app_loggers()
            flaskapp.scheduler = scheduler
            flaskapp._scheduler_initialized = True
            os.environ['_INTELHUB_SCHED_INIT'] = '1'

            scheduler.start_heartbeat()

            job_count = len(scheduler._job_map)
            flaskapp.logger.info(f"Worker-{_worker_id} ({_sched_role}): TaskScheduler started — {job_count} tasks registered")
            for tid, job in scheduler._job_map.items():
                nrt = job.next_run_time
                flaskapp.logger.info(f"  ✓ {tid} | next_run: {nrt.isoformat() if nrt else 'paused'}")
        except Exception as e:
            flaskapp.logger.warning(f"Scheduler init failed: {e}")
            flaskapp.scheduler = None

    return flaskapp
