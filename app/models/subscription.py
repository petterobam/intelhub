"""Subscription model — 订阅者"""
import uuid

from sqlalchemy import Column, String, Text, Boolean, DateTime, JSON

from app import db
from app.utils.helpers import bj_now


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id = Column(String(16), primary_key=True, default=lambda: uuid.uuid4().hex[:8])
    email = Column(String(256), nullable=False, index=True)
    name = Column(String(64), default='')
    task_id = Column(String(16), nullable=True, index=True)
    channel_id = Column(String(16), nullable=True, index=True)
    channel_ids = Column(JSON, default=list)
    report_types = Column(JSON, default=list)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=bj_now)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'name': self.name or '',
            'task_id': self.task_id,
            'channel_ids': self.channel_ids or [],
            'report_types': self.report_types or [],
            'enabled': self.enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
