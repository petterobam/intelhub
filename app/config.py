"""Configuration"""

import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-prod")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    BASE_DIR = BASE_DIR
    DATA_DIR = os.path.join(BASE_DIR, "data")
    RAW_DIR = os.path.join(DATA_DIR, "raw")
    PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
    REPORTS_DIR = os.path.join(BASE_DIR, "reports")
    LOGS_DIR = os.path.join(DATA_DIR, "logs")
    FRESHNESS_DIR = os.path.join(DATA_DIR, "freshness")
    REPORT_TYPE_DIRS = {
        'heartbeat': os.path.join(REPORTS_DIR, 'heartbeat'),
        'insight': os.path.join(REPORTS_DIR, 'insight'),
        'aggregate': os.path.join(REPORTS_DIR, 'aggregate'),
        'agent': os.path.join(REPORTS_DIR, 'agent'),
    }


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'data', 'intel_hub.db')}"
    )


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'data', 'intel_hub.db')}"
    )


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)
