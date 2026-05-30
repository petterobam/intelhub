"""CrawlerNode model - 可编辑的爬虫节点配置"""
import uuid, json

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text

from app import db
from app.utils.helpers import bj_now


class CrawlerNode(db.Model):
    """单个爬虫节点（平台/数据源）"""

    __tablename__ = "crawler_nodes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4())[:8])
    name = Column(String(64), nullable=False)           # 显示名，如 "36氪"
    platform_id = Column(String(32), nullable=False, unique=True)  # 唯一标识，如 "36kr"
    category = Column(String(32), nullable=False)        # hot_topics / policy / exchange / financial
    url = Column(String(512), nullable=True)
    method = Column(String(16), nullable=False, default="browser")  # browser / api
    schedule = Column(String(64), nullable=True)         # cron 表达式或 "90m"
    priority = Column(String(16), nullable=True)         # high / medium / low
    enabled = Column(Boolean, nullable=False, default=True)
    # 灵活配置（CSS选择器、认证、特殊字段等）
    config_json = Column(Text, nullable=True, default="{}")
    # 关联的任务ID（可选）
    task_id = Column(String(36), nullable=True)
    created_at = Column(DateTime, nullable=False, default=bj_now)
    updated_at = Column(DateTime, nullable=False, default=bj_now, onupdate=bj_now)

    def __repr__(self):
        return f"<CrawlerNode {self.platform_id} ({self.category})>"

    def get_config(self):
        if not self.config_json:
            return {}
        try:
            return json.loads(self.config_json)
        except Exception:
            return {}

    def set_config(self, cfg_dict):
        self.config_json = json.dumps(cfg_dict, ensure_ascii=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "platform_id": self.platform_id,
            "category": self.category,
            "url": self.url,
            "method": self.method,
            "schedule": self.schedule,
            "priority": self.priority,
            "enabled": self.enabled,
            "config": self.get_config(),
            "task_id": self.task_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
