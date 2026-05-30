"""PushChannel model — 推送渠道配置"""
import uuid
import json

from sqlalchemy import Column, String, Text, Boolean, DateTime

from app import db
from app.utils.helpers import bj_now


class PushChannel(db.Model):
    __tablename__ = "push_channels"

    id = Column(String(16), primary_key=True, default=lambda: uuid.uuid4().hex[:8])
    user_id = Column(String(16), nullable=True, index=True)
    channel_type = Column(String(32), nullable=False)  # email | feishu | dingtalk | telegram
    name = Column(String(64), nullable=False)
    config_json = Column(Text, default='{}')
    enabled = Column(Boolean, default=True)
    is_alert = Column(Boolean, default=False)
    created_at = Column(DateTime, default=bj_now)

    CHANNEL_TYPES = {
        'email': '邮件',
        'feishu': '飞书',
        'dingtalk': '钉钉',
        'telegram': 'Telegram',
    }

    def get_config(self):
        if not self.config_json:
            return {}
        try:
            return json.loads(self.config_json)
        except Exception:
            return {}

    def set_config(self, cfg):
        self.config_json = json.dumps(cfg, ensure_ascii=False)

    def to_dict(self):
        cfg = self.get_config()
        # 脱敏：隐藏敏感字段
        safe_cfg = {}
        for k, v in cfg.items():
            if 'secret' in k or 'token' in k or 'password' in k:
                safe_cfg[k] = '******' if v else ''
            else:
                safe_cfg[k] = v
        return {
            'id': self.id,
            'user_id': self.user_id,
            'channel_type': self.channel_type,
            'channel_label': self.CHANNEL_TYPES.get(self.channel_type, self.channel_type),
            'name': self.name,
            'config': safe_cfg,
            'enabled': self.enabled,
            'is_alert': self.is_alert,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
