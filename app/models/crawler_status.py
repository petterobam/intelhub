"""CrawlerStatus model."""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from app import db


class CrawlerStatus(db.Model):
    """Tracks the latest status of each data crawler / platform."""

    __tablename__ = "crawler_status"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    platform = Column(String(64), nullable=False, unique=True)
    latest_file = Column(String(256), nullable=True)
    item_count = Column(Integer, nullable=False, default=0)
    age_minutes = Column(Integer, nullable=True)
    status = Column(String(16), nullable=False, default="fresh")
    last_collected = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

    def __repr__(self):
        return f"<CrawlerStatus {self.platform} ({self.status})>"

    def to_dict(self):
        return {
            "id": self.id,
            "platform": self.platform,
            "latest_file": self.latest_file,
            "item_count": self.item_count,
            "age_minutes": self.age_minutes,
            "status": self.status,
            "last_collected": self.last_collected.isoformat() if self.last_collected else None,
            "error_message": self.error_message,
        }
