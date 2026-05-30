"""PushLog model — 推送记录，用于去重和统计。"""
import uuid
from sqlalchemy import Column, DateTime, String

from app import db
from app.utils.helpers import bj_now


class PushLog(db.Model):
    __tablename__ = "push_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    report_path = Column(String(512), nullable=False, index=True)
    channel_type = Column(String(32), nullable=False)
    channel_key = Column(String(128), nullable=False)
    user_id = Column(String(16), nullable=True, index=True)
    status = Column(String(16), nullable=False, default="sent")
    error = Column(String(512), nullable=True)
    created_at = Column(DateTime, nullable=False, default=bj_now)
