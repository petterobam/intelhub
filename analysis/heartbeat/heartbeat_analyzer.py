#!/usr/bin/env python3
"""
心跳分析器 - 系统健康检查与快速洞察
"""
import json
import os
import glob
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw", "hot_topics")
FRESHNESS_DIR = os.path.join(DATA_DIR, "freshness")
REPORTS_SUBDIR = os.path.join(BASE_DIR, "reports", "heartbeat")
OUTPUT_FILE = os.path.join(REPORTS_SUBDIR, "heartbeat-latest.json")

FRESH_THRESHOLD = 120
STALE_THRESHOLD = 360

PLATFORMS = ["weibo", "douyin", "zhihu", "36kr", "huanqiu", "huxiu", "eastmoney", "paper", "wangyi"]


def get_file_age(filepath):
    try:
        mtime = os.path.getmtime(filepath)
        age_seconds = (datetime.now() - datetime.fromtimestamp(mtime)).total_seconds()
        return int(age_seconds / 60)
    except:
        return 9999


def get_latest_file(platform):
    subdir = os.path.join(RAW_DIR, platform)
    if os.path.isdir(subdir):
        pattern = os.path.join(subdir, "*.json")
    else:
        pattern = os.path.join(RAW_DIR, f"{platform}-*.json")
    files = glob.glob(pattern)
    if not files:
        return None
    return max(files, key=os.path.getmtime)


def check_freshness():
    results = []
    for platform in PLATFORMS:
        latest = get_latest_file(platform)
        if latest:
            age = get_file_age(latest)
            status = "fresh" if age < FRESH_THRESHOLD else ("stale" if age < STALE_THRESHOLD else "critical")
            item_count = 0
            try:
                with open(latest, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    item_count = len(data.get("items", [])) if isinstance(data, dict) else (len(data) if isinstance(data, list) else 0)
            except:
                pass
            results.append({"platform": platform, "latest_file": os.path.basename(latest), "age_minutes": age, "status": status, "item_count": item_count})
        else:
            results.append({"platform": platform, "latest_file": None, "age_minutes": 9999, "status": "missing", "item_count": 0})
    return results


def calculate_health_score(platform_stats):
    if not platform_stats:
        return 0
    score = 100
    for p in platform_stats:
        status = p.get("status", "unknown")
        if status == "stale":
            score -= 10
        elif status == "critical":
            score -= 25
        elif status == "missing":
            score -= 35
    total_items = sum(p.get("item_count", 0) for p in platform_stats)
    avg_items = total_items / len(platform_stats)
    if avg_items < 5:
        score -= 20
    return max(0, min(100, score))


def get_alerts(platform_stats):
    alerts = []
    for p in platform_stats:
        if p["status"] == "critical":
            alerts.append(f"WARNING: [{p['platform']}] 数据超过6小时未更新")
        elif p["status"] == "missing":
            alerts.append(f"CRITICAL: [{p['platform']}] 数据完全缺失")
    return alerts


def generate_heartbeat():
    logger.info("生成心跳报告...")
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    os.makedirs(REPORTS_SUBDIR, exist_ok=True)
    os.makedirs(FRESHNESS_DIR, exist_ok=True)
    
    platform_stats = check_freshness()
    health_score = calculate_health_score(platform_stats)
    alerts = get_alerts(platform_stats)
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "health_score": health_score,
        "platforms": platform_stats,
        "fresh_count": sum(1 for p in platform_stats if p["status"] == "fresh"),
        "stale_count": sum(1 for p in platform_stats if p["status"] == "stale"),
        "critical_count": sum(1 for p in platform_stats if p["status"] in ("critical", "missing")),
        "alerts": alerts,
        "summary": f"健康分 {health_score} | 正常 {sum(1 for p in platform_stats if p['status'] == 'fresh')} | 过期 {sum(1 for p in platform_stats if p['status'] in ('stale', 'critical', 'missing'))}"
    }
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    freshness_file = os.path.join(FRESHNESS_DIR, "status.json")
    with open(freshness_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    logger.info(f"心跳报告完成: 健康分={health_score}")
    return result


if __name__ == "__main__":
    result = generate_heartbeat()
    print(f"健康分: {result['health_score']}")
    print(f"告警: {result['alerts'] or '无'}")
