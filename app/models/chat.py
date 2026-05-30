"""Chat models - 对话历史持久化"""

import uuid

from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey, Text
from sqlalchemy.orm import relationship

from app import db
from app.utils.helpers import bj_now


class ChatSession(db.Model):
    """对话会话"""
    __tablename__ = "chat_sessions"

    id = Column(String(64), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(16), nullable=True, index=True)
    title = Column(String(128), nullable=False, default='New Chat')
    created_at = Column(DateTime, nullable=False, default=bj_now)
    updated_at = Column(DateTime, nullable=False, default=bj_now, onupdate=bj_now)

    messages = relationship("ChatMessage", backref="session", cascade="all, delete-orphan",
                            order_by="ChatMessage.id")

    def to_dict(self, include_messages=False):
        d = {
            'session_id': self.id,
            'title': self.title,
            'message_count': len(self.messages),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_messages:
            d['messages'] = [m.to_dict() for m in self.messages]
        return d


class ChatMessage(db.Model):
    """对话消息"""
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), ForeignKey('chat_sessions.id'), nullable=False, index=True)
    role = Column(String(16), nullable=False)  # user | assistant
    content = Column(Text, nullable=False, default='')
    created_at = Column(DateTime, nullable=False, default=bj_now)

    def to_dict(self):
        return {
            'role': self.role,
            'content': self.content,
            'timestamp': self.created_at.isoformat() if self.created_at else None,
        }
