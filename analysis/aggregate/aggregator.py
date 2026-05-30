#!/usr/bin/env python3
"""
数据聚合器 - 将多平台数据整合为统一数据集
"""
import json
import os
import glob
from datetime import datetime
from collections import defaultdict
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# 配置路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw", "hot_topics")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
OUTPUT_FILE = os.path.join(PROCESSED_DIR, "all-platforms-aggregated.json")

# 要聚合的平台
PLATFORMS = ["weibo", "douyin", "zhihu", "36kr", "huanqiu", "huxiu", "eastmoney", "paper", "wangyi"]


def load_json_file(filepath):
    """加载 JSON 文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"加载失败 {filepath}: {e}")
        return None


def parse_timestamp(timestamp_str):
    """解析时间戳，返回秒数（用于排序）"""
    if not timestamp_str:
        return 0
    if isinstance(timestamp_str, (int, float)):
        return int(timestamp_str)
    if isinstance(timestamp_str, str):
        iso_pattern = r'(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})'
        match = re.search(iso_pattern, timestamp_str)
        if match:
            try:
                year, month, day, hour, minute, second = map(int, match.groups())
                dt = datetime(year, month, day, hour, minute, second)
                return int(dt.timestamp())
            except ValueError:
                pass
        # 尝试简单格式
        simple_pattern = r'(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})'
        match = re.search(simple_pattern, timestamp_str)
        if match:
            try:
                year, month, day, hour, minute, second = map(int, match.groups())
                dt = datetime(year, month, day, hour, minute, second)
                return int(dt.timestamp())
            except ValueError:
                pass
    return 0


def load_platform_data(platform):
    """加载指定平台最新数据"""
    subdir = os.path.join(RAW_DIR, platform)
    if os.path.isdir(subdir):
        pattern = os.path.join(subdir, "*.json")
    else:
        pattern = os.path.join(RAW_DIR, f"{platform}-*.json")
    files = glob.glob(pattern)
    if not files:
        return []
    latest_file = max(files, key=os.path.getmtime)
    data = load_json_file(latest_file)
    if not data:
        return []
    if isinstance(data, dict) and "items" in data:
        return data["items"]
    if isinstance(data, list):
        return data
    return []


def deduplicate(items):
    """基于 id + title 去重"""
    seen = set()
    unique = []
    for item in items:
        item_id = item.get("id", "")
        title = item.get("title", "")
        key = f"{item_id}:{title}"
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def normalize_timestamp(item):
    """确保时间戳为 ISO 格式"""
    ts = item.get("timestamp", "")
    if ts and isinstance(ts, str) and 'T' not in ts and re.match(r'\d{4}-\d{2}-\d{2}', ts):
        # 尝试补全为 ISO 格式
        if re.match(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', ts):
            item["timestamp"] = ts.replace(" ", "T") + "+08:00"
    return item


def aggregate_all():
    """聚合所有平台数据"""
    logger.info("开始聚合多平台数据...")
    os.makedirs(PROCESSED_DIR, exist_ok=True)

    all_items = []
    platform_stats = {}

    for platform in PLATFORMS:
        items = load_platform_data(platform)
        logger.info(f"  {platform}: {len(items)} 条")
        platform_stats[platform] = {"raw_count": len(items)}

        for item in items:
            item["_platform"] = platform
        all_items.extend(items)

    # 去重
    all_items = deduplicate(all_items)
    logger.info(f"去重后: {len(all_items)} 条")

    # 标准化时间戳
    all_items = [normalize_timestamp(item) for item in all_items]

    # 按时间排序（新的在前）
    all_items.sort(key=lambda x: parse_timestamp(x.get("timestamp", "")), reverse=True)

    # 构建结果
    result = {
        "items": all_items,
        "meta": {
            "aggregated_at": datetime.now().isoformat(),
            "platform_count": len(PLATFORMS),
            "total_items": len(all_items),
            "platforms": platform_stats,
            "platforms_list": PLATFORMS
        }
    }

    # 保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"聚合完成，保存到: {OUTPUT_FILE}")

    return result


if __name__ == "__main__":
    result = aggregate_all()
    print(f"聚合完成: {result['meta']['total_items']} 条数据")
