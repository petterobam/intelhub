"""User model — admin-only for open-source version"""
import uuid

from sqlalchemy import Column, String, Boolean, DateTime

from app import db
from app.utils.helpers import bj_now


class User(db.Model):
    __tablename__ = "users"

    id = Column(String(16), primary_key=True, default=lambda: uuid.uuid4().hex[:8])
    email = Column(String(256), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    display_name = Column(String(64), default='')
    role = Column(String(16), nullable=False, default='admin')
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=bj_now)
    llm_api_key = Column(String(512), default='')
    llm_base_url = Column(String(512), default='')
    llm_model = Column(String(128), default='')

    def set_password(self, password):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')

    def check_password(self, password):
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'display_name': self.display_name or '',
            'role': self.role,
            'tier': 'v4',
            'enabled': self.enabled,
            'llm_configured': bool(self.llm_api_key),
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
