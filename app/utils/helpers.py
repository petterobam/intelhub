"""General-purpose helper utilities for IntelHub."""

import os
from datetime import datetime, timezone, timedelta

from app.config import BaseConfig

_BJ_TZ = timezone(timedelta(hours=8))

def bj_now():
    """返回当前北京时间（固定 UTC+8，不受服务器时区影响）"""
    return datetime.now(_BJ_TZ).replace(tzinfo=None)


def standard_response(data=None, success: bool = True) -> dict:
    """Return a unified API response envelope.

    Example success::
        {"success": True, "data": {...}, "timestamp": "..."}

    Example error (call via error_response)::
        {"success": False, "error": {"code": 404, "message": "..."}, "timestamp": "..."}
    """
    return {
        "success": success,
        "data": data,
        "timestamp": get_timestamp(),
    }


def error_response(code: int, message: str) -> tuple[dict, int]:
    """Return a unified error response with HTTP status code.

    Returns (body_dict, http_status).
    """
    body = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
        "timestamp": get_timestamp(),
    }
    return body, code


def get_timestamp() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    """Create all required data directories if they do not already exist."""
    dirs = [
        BaseConfig.DATA_DIR,
        BaseConfig.RAW_DIR,
        BaseConfig.PROCESSED_DIR,
        BaseConfig.REPORTS_DIR,
        BaseConfig.LOGS_DIR,
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    for d in BaseConfig.REPORT_TYPE_DIRS.values():
        os.makedirs(d, exist_ok=True)


def get_proxies() -> dict:
    """从数据库读取代理配置，返回 requests 库可用的 proxies dict"""
    from app.models.llm_config import LlmConfig
    proxy_url = LlmConfig.get('proxy_url', '')
    if not proxy_url:
        return {}
    return {'http': proxy_url, 'https': proxy_url}
