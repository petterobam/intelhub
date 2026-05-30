import os
import yaml

_DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "platforms.yaml")


def load_config(path: str = None) -> dict:
    """加载平台配置文件"""
    if path is None:
        path = _DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


__all__ = ["load_config"]
