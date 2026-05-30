"""UserProfile model — 用户兴趣偏好"""

from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app import db
from app.utils.helpers import bj_now


class UserProfile(db.Model):
    __tablename__ = "user_profiles"

    user_id = Column(String(16), ForeignKey('users.id'), primary_key=True)
    interest_tags = Column(db.JSON, default=list)
    # [{"type": "company", "value": "华为"}, {"type": "topic", "value": "新能源"}]
    platforms = Column(db.JSON, default=list)
    # ["weibo", "zhihu", "36kr"]
    report_time = Column(String(8), default='08:00')
    push_mode = Column(String(16), default='summary')  # summary | full
    rss_source_ids = Column(db.JSON, default=list)
    user_source_ids = Column(db.JSON, default=list)
    push_channel_ids = Column(db.JSON, default=list)
    updated_at = Column(DateTime, default=bj_now, onupdate=bj_now)

    user = relationship('User', backref='profile')

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'interest_tags': self.interest_tags or [],
            'platforms': self.platforms or [],
            'report_time': self.report_time or '08:00',
            'push_mode': self.push_mode or 'summary',
            'rss_source_ids': self.rss_source_ids or [],
            'user_source_ids': self.user_source_ids or [],
            'push_channel_ids': self.push_channel_ids or [],
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
