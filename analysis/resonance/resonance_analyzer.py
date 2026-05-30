#!/usr/bin/env python3
"""
跨平台共振分析 - 找出多平台同时出现的热点
"""
import json
import os
import re
from datetime import datetime
from collections import Counter, defaultdict
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
AGGREGATED_FILE = os.path.join(PROCESSED_DIR, "all-platforms-aggregated.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "reports", "insight", "cross-platform-resonance.json")

STOP_WORDS = {
    '的', '了', '是', '在', '和', '有', '我', '你', '他', '她', '它', '这', '那',
    '个', '中', '上', '下', '与', '及', '或', '但', '而', '等', '都', '要', '会',
    '就', '也', '不', '还', '能', '到', '说', '被', '把', '让', '给', '从', '将',
    '对', '以', '为', '如', '当', '可', '已', '很', '更', '最', '多', '着', '过'
}


def load_aggregated_data():
    if not os.path.exists(AGGREGATED_FILE):
        return []
    with open(AGGREGATED_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("items", [])


def extract_keywords(text):
    """提取2字及以上有效词"""
    if not text:
        return []
    clean = re.sub(r'[^\w\u4e00-\u9fff]', ' ', str(text))
    words = [w for w in clean if len(w) >= 2 and w not in STOP_WORDS]
    return words


def calculate_resonance(data):
    """计算跨平台共振分"""
    keyword_platforms = defaultdict(set)
    keyword_counts = Counter()
    
    for item in data:
        platform = item.get("_platform", "unknown")
        title = item.get("title", "")
        keywords = extract_keywords(title)
        
        for kw in keywords:
            keyword_platforms[kw].add(platform)
            keyword_counts[kw] += 1
    
    # 计算共振分 = 出现平台数 × 总出现次数
    resonance_scores = []
    for kw, platforms in keyword_platforms.items():
        score = len(platforms) * keyword_counts[kw]
        resonance_scores.append({
            "keyword": kw,
            "platform_count": len(platforms),
            "total_mentions": keyword_counts[kw],
            "resonance_score": score,
            "platforms": sorted(list(platforms))
        })
    
    return sorted(resonance_scores, key=lambda x: x["resonance_score"], reverse=True)


def find_cross_platform_hotspots(data, top_n=20):
    """找出跨平台热点"""
    resonance = calculate_resonance(data)
    return resonance[:top_n]


def analyze(data):
    """完整共振分析"""
    logger.info(f"跨平台共振分析: {len(data)} 条数据")
    
    hotspots = find_cross_platform_hotspots(data, 30)
    
    # 分层：高共振（3+平台）、中共振（2平台）
    high_resonance = [h for h in hotspots if h["platform_count"] >= 3]
    medium_resonance = [h for h in hotspots if h["platform_count"] == 2]
    
    result = {
        "generated_at": datetime.now().isoformat(),
        "total_data_points": len(data),
        "high_resonance": high_resonance,
        "medium_resonance": medium_resonance,
        "all_hotspots": hotspots[:20],
        "summary": {
            "high_resonance_count": len(high_resonance),
            "medium_resonance_count": len(medium_resonance),
            "most_cross_platform": [h["keyword"] for h in high_resonance[:5]] if high_resonance else []
        }
    }
    
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"共振分析完成: {OUTPUT_FILE}")
    
    return result


if __name__ == "__main__":
    data = load_aggregated_data()
    if data:
        result = analyze(data)
        print(f"分析了 {result['total_data_points']} 条数据")
        print(f"高共振热点({len(result['high_resonance'])}个): {result['summary']['most_cross_platform'][:5]}")
    else:
        print("没有数据可分析")
