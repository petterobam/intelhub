"""TaskRun model - 每次任务执行的完整记录."""
import uuid
import json

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, ForeignKey

from app import db
from app.utils.helpers import bj_now


class TaskRun(db.Model):
    """Represents a single execution run of a scheduled task."""

    __tablename__ = "task_runs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    task_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(16), nullable=True, index=True)
    report_id = Column(String(36), ForeignKey('reports.id'), nullable=True)
    status = Column(String(16), nullable=False, default="running")  # running|done|failed|timeout
    started_at = Column(DateTime, nullable=False, default=bj_now)
    finished_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    exit_code = Column(Integer, nullable=True)
    stdout = Column(Text, nullable=True)
    stderr = Column(Text, nullable=True)
    artifacts = Column(Text, nullable=True)   # JSON: [{path, size, name}]
    trigger_type = Column(String(16), nullable=False, default="manual")  # manual|scheduled
    created_at = Column(DateTime, nullable=False, default=bj_now)

    def __repr__(self):
        return f"<TaskRun {self.task_id} {self.status} at {self.started_at}>"

    def to_dict(self):
        arts = self.artifacts
        if isinstance(arts, str):
            try:
                arts = json.loads(arts)
            except Exception:
                arts = []
        return {
            "id": self.id,
            "task_id": self.task_id,
            "user_id": self.user_id,
            "report_id": self.report_id,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
            "exit_code": self.exit_code,
            "stdout": self.stdout or "",
            "stderr": self.stderr or "",
            "artifacts": arts or [],
            "trigger_type": self.trigger_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
