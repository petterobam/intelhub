"""LlmConfig - 全局 LLM 配置 (key-value store)"""

from sqlalchemy import Column, String, Text

from app import db


class LlmConfig(db.Model):
    """Key-value table for global LLM configuration.

    Stores keys: api_key, base_url, model
    """
    __tablename__ = "llm_config"

    key = Column(String(64), primary_key=True)
    value = Column(Text, nullable=True)

    @staticmethod
    def get(key: str, default: str = '') -> str:
        """Read a config value from DB."""
        row = db.session.get(LlmConfig, key)
        return row.value if row and row.value else default

    @staticmethod
    def set(key: str, value: str):
        """Write a config value to DB (upsert)."""
        row = db.session.get(LlmConfig, key)
        if row:
            row.value = value
        else:
            db.session.add(LlmConfig(key=key, value=value))
        db.session.commit()

    @staticmethod
    def get_all() -> dict:
        """Return all config as a dict."""
        rows = db.session.query(LlmConfig).all()
        return {r.key: (r.value or '') for r in rows}
