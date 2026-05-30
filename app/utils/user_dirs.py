"""用户目录管理 — 统一的路径计算与初始化"""
import os

BASE_DATA_DIR = os.environ.get(
    'DATA_DIR',
    os.path.join(os.path.dirname(__file__), '..', '..', 'data')
)


def user_dir(user_id: str) -> str:
    return os.path.join(BASE_DATA_DIR, 'users', user_id)


def user_reports_dir(user_id: str) -> str:
    return os.path.join(user_dir(user_id), 'reports', 'daily')


def user_sources_dir(user_id: str) -> str:
    return os.path.join(user_dir(user_id), 'sources')


def user_kb_dir(user_id: str) -> str:
    return os.path.join(user_dir(user_id), 'kb')


def user_uploads_dir(user_id: str) -> str:
    return os.path.join(user_dir(user_id), 'uploads')


def user_rss_dir(user_id: str, slug: str) -> str:
    """个人采集数据存储目录: data/users/{user_id}/rss/{slug}/"""
    d = os.path.join(user_dir(user_id), 'rss', slug)
    os.makedirs(d, exist_ok=True)
    return d


def ensure_user_dirs(user_id: str):
    """创建用户完整目录骨架"""
    for d in [user_reports_dir(user_id), user_sources_dir(user_id),
              user_kb_dir(user_id), user_uploads_dir(user_id),
              os.path.join(user_dir(user_id), 'rss')]:
        os.makedirs(d, exist_ok=True)


def assert_within_user_dir(user_id: str, path: str):
    """安全校验：确保 path 在用户目录内"""
    base = os.path.abspath(user_dir(user_id))
    target = os.path.abspath(path)
    if not target.startswith(base + os.sep):
        raise PermissionError(f'Path escape detected: {path}')
