"""Report model."""
import uuid

from sqlalchemy import Column, DateTime, String, Text, ForeignKey

from app import db
from app.utils.helpers import bj_now


class Report(db.Model):
    """Represents a generated report (daily brief, insight, heartbeat, trend)."""

    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(256), nullable=False)
    report_type = Column(String(32), nullable=False)
    file_path = Column(String(512), nullable=True)
    generated_at = Column(DateTime, nullable=False, default=bj_now)
    summary = Column(Text, nullable=True)
    user_id = Column(String(16), ForeignKey('users.id'), nullable=True)
    scope = Column(String(16), default='platform')  # platform | personal
    html_path = Column(String(512), nullable=True)
    summary_path = Column(String(512), nullable=True)  # LLM 摘要 MD 文件路径
    task_id = Column(String(36), ForeignKey('scheduled_tasks.id'), nullable=True)

    def __repr__(self):
        return f"<Report {self.title} ({self.report_type})>"

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "report_type": self.report_type,
            "file_path": self.file_path,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "summary": self.summary,
            "user_id": self.user_id,
            "scope": self.scope,
            "html_path": self.html_path,
            "summary_path": self.summary_path,
            "task_id": self.task_id,
        }
