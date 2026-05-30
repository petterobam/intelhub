"""UserSource model — 用户内容订阅源"""
import uuid

from sqlalchemy import Column, String, Boolean, Integer, DateTime, Text, ForeignKey, UniqueConstraint

from app import db
from app.utils.helpers import bj_now


class UserSource(db.Model):
    __tablename__ = 'user_sources'
    __table_args__ = (
        UniqueConstraint('user_id', 'type', 'source_id', name='uq_user_source'),
    )

    id = Column(String(16), primary_key=True, default=lambda: uuid.uuid4().hex[:8])
    user_id = Column(String(16), ForeignKey('users.id'), nullable=False, index=True)
    type = Column(String(16), nullable=False)  # rss | bilibili | youtube | wechat
    source_id = Column(String(512), nullable=False)  # URL / UID / Channel ID
    display_name = Column(String(128), default='')
    enabled = Column(Boolean, default=True)
    last_fetched = Column(DateTime, nullable=True)
    item_count = Column(Integer, default=0)
    status = Column(String(16), default='active')  # active | error | rate_limited | paused
    last_error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=bj_now)

    user = db.relationship('User', backref='sources')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'type': self.type,
            'source_id': self.source_id,
            'display_name': self.display_name,
            'enabled': self.enabled,
            'last_fetched': self.last_fetched.isoformat() if self.last_fetched else None,
            'item_count': self.item_count or 0,
            'status': self.status,
            'last_error': self.last_error,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
