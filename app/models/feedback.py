"""Feedback model — 用户反馈"""
import uuid
from sqlalchemy import Column, String, Text, DateTime
from app import db
from app.utils.helpers import bj_now


class Feedback(db.Model):
    __tablename__ = "feedbacks"

    id = Column(String(16), primary_key=True, default=lambda: uuid.uuid4().hex[:8])
    user_id = Column(String(16), nullable=True, index=True)
    content = Column(Text, nullable=False)
    category = Column(String(32), default='general')  # general | bug | feature | other
    status = Column(String(32), default='pending')  # pending | replied | scheduled | evaluating | archived
    reply = Column(Text, default='')
    created_at = Column(DateTime, default=bj_now)

    def to_dict(self, include_reply=False, include_user=False):
        d = {
            'id': self.id,
            'content': self.content,
            'category': self.category,
            'status': self.status or 'pending',
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
        if self.user_id:
            from app.models.user import User
            u = User.query.get(self.user_id)
            if u:
                d['nickname'] = u.display_name or u.email.split('@')[0]
                d['user_email'] = u.email
        if not self.user_id or 'nickname' not in d:
            d['nickname'] = ''
            d['user_email'] = ''
        if include_reply:
            d['reply'] = self.reply or ''
        return d
