"""UserUpload model — 用户上传文件记录"""
import uuid

from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey

from app import db
from app.utils.helpers import bj_now


class UserUpload(db.Model):
    __tablename__ = 'user_uploads'

    id = Column(String(16), primary_key=True, default=lambda: uuid.uuid4().hex[:8])
    user_id = Column(String(16), ForeignKey('users.id'), nullable=False, index=True)
    filename = Column(String(256), nullable=False)
    ext = Column(String(8), nullable=False)
    size = Column(Integer, default=0)
    path = Column(String(512), nullable=True)
    source_url = Column(String(1024), nullable=True)
    status = Column(String(16), default='pending')  # pending | parsing | ready | error
    parse_error = Column(Text, nullable=True)
    char_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=bj_now)
    ingested_at = Column(DateTime, nullable=True)

    user = db.relationship('User', backref='uploads')

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'ext': self.ext,
            'size': self.size,
            'source_url': self.source_url,
            'status': self.status,
            'parse_error': self.parse_error,
            'char_count': self.char_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'ingested_at': self.ingested_at.isoformat() if self.ingested_at else None,
        }
