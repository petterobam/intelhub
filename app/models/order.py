"""Order model — 支付订单"""
import uuid

from sqlalchemy import Column, String, Integer, DateTime

from app import db
from app.utils.helpers import bj_now


class Order(db.Model):
    __tablename__ = "orders"

    id = Column(String(32), primary_key=True, default=lambda: uuid.uuid4().hex[:12])
    user_id = Column(String(16), nullable=False, index=True)
    tier = Column(String(16), nullable=False)
    amount = Column(Integer, nullable=False)  # 金额（分）
    currency = Column(String(8), nullable=False, default='cny')
    provider = Column(String(16), nullable=False)  # alipay / stripe
    provider_id = Column(String(128))  # 支付商订单号
    status = Column(String(16), nullable=False, default='pending')  # pending / paid / failed / refunded
    paid_at = Column(DateTime)
    created_at = Column(DateTime, default=bj_now)

    def to_dict(self):
        return {
            'id': self.id,
            'tier': self.tier,
            'amount': self.amount,
            'currency': self.currency,
            'provider': self.provider,
            'status': self.status,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
