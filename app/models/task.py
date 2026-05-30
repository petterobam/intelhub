"""ScheduledTask model."""
import uuid, json

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, JSON, ForeignKey

from app import db
from app.utils.helpers import bj_now


class ScheduledTask(db.Model):
    """Represents a scheduled data-collection or analysis task."""

    __tablename__ = "scheduled_tasks"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    user_id = Column(String(16), ForeignKey('users.id'), nullable=True, index=True)
    name = Column(String(128), nullable=False)
    task_type = Column(String(32), nullable=False, default="crawler")   # crawler | analysis
    module = Column(String(32), nullable=False)
    script = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    tags = Column(String(256), nullable=True)   # comma-separated
    schedule_type = Column(String(16), nullable=False, default="cron")
    schedule_config = Column(Text, nullable=False, default="{}")
    enabled = Column(Boolean, nullable=False, default=True)
    status = Column(String(16), nullable=False, default="idle")   # idle | running | error
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    run_count = Column(Integer, nullable=False, default=0)
    success_count = Column(Integer, nullable=False, default=0)
    fail_count = Column(Integer, nullable=False, default=0)
    last_error = Column(Text, nullable=True)
    last_log = Column(Text, nullable=True)
    deliver_to = Column(String(32), nullable=False, default="local")
    notify_on_failure = Column(Boolean, nullable=False, default=False)
    is_auto = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=bj_now)
    updated_at = Column(DateTime, nullable=False, default=bj_now, onupdate=bj_now)

    def __repr__(self):
        return f"<ScheduledTask {self.name} ({self.module})>"

    def to_dict(self):
        cfg = self.schedule_config
        if isinstance(cfg, str):
            try:
                cfg = json.loads(cfg)
            except Exception:
                cfg = {}
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "task_type": self.task_type,
            "module": self.module,
            "script": self.script,
            "description": self.description,
            "tags": self.tags.split(",") if self.tags else [],
            "schedule_type": self.schedule_type,
            "schedule_config": cfg,
            "enabled": self.enabled,
            "status": self.status,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "last_error": self.last_error,
            "last_log": self.last_log,
            "deliver_to": self.deliver_to,
            "notify_on_failure": self.notify_on_failure,
            "is_auto": self.is_auto,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
