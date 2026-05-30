#!/usr/bin/env python3
"""
趋势分析器 - 关键词提取、话题分类、热度评分
"""
import json
import os
import re
from datetime import datetime, timedelta
from collections import Counter
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_DIR = os.path.join(BASE_DIR, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
AGGREGATED_FILE = os.path.join(PROCESSED_DIR, "all-platforms-aggregated.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "reports", "insight", "trend-analysis.json")

# 停用词表
STOP_WORDS = {
    '的', '了', '是', '在', '和', '有', '我', '你', '他', '她', '它', '这', '那',
    '个', '中', '上', '下', '与', '及', '或', '但', '而', '等', '都', '要', '会',
    '就', '也', '不', '还', '能', '到', '说', '被', '把', '让', '给', '从', '将',
    '对', '以', '为', '如', '当', '可', '已', '很', '更', '最', '多', '着', '过'
}

# 话题分类映射
TOPIC_MAP = {
    "国际政治": ["伊朗", "特朗普", "美国", "巴基", "斯坦", "东京", "审判", "朝鲜", 
                "外交", "国台办", "赖清德", "窜访", "以色列", "俄罗斯", "欧盟", "英国",
                "德国", "法国", "泽连斯基", "普京", "拜登", "中美", "中日", "中欧"],
    "体育赛事": ["国乒", "CBA", "篮球", "网球", "斯诺克", "辽篮", "广东", "辽宁",
                "季后赛", "乒乓球", "羽毛球", "足球", "中超", "欧冠", "奥运"],
    "娱乐圈": ["票房", "电影", "演唱会", "李荣浩", "粉丝", "演员", "导演", "综艺",
              "电视剧", "歌手", "明星", "官宣", "塌房", "热搜"],
    "财经市场": ["财报", "业绩", "同比增长", "股价", "股市", "投资", "利润", "收入",
                "A股", "港股", "美股", "基金", "ETF", "牛市", "熊市", "指数"],
    "科技数码": ["AI", "人工智能", "芯片", "手机", "建模", "特效", "大模型", "LLM",
               "英伟达", "华为", "苹果", "特斯拉", "电动车", "电池"],
    "游戏动漫": ["火影", "手游", "王者", "第五人格", "游戏", "网游", "Switch", "Steam"],
    "教育文化": ["教资", "试卷", "老师", "学校", "考生", "考试", "高考", "考研"],
    "社会民生": ["五一", "假期", "旅游", "景区", "交通", "天气", "暴雨", "高温", 
               "地震", "火灾", "医疗", "医保", "养老金", "工资", "物价"]
}


def load_aggregated_data():
    """加载聚合数据"""
    if not os.path.exists(AGGREGATED_FILE):
        logger.warning(f"聚合文件不存在: {AGGREGATED_FILE}")
        return []
    with open(AGGREGATED_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("items", [])


def extract_keywords(text, top_n=10):
    """提取关键词（字符级，长度>=2）"""
    if not text:
        return []
    clean = re.sub(r'[^\w\u4e00-\u9fff]', ' ', str(text))
    words = [w for w in clean if len(w) >= 2 and w not in STOP_WORDS]
    return words[:top_n]


def classify_topic(title):
    """话题分类"""
    for topic, keywords in TOPIC_MAP.items():
        if any(kw in title for kw in keywords):
            return topic
    return "综合热点"


def calculate_time_decay(timestamp_str, base_time=None):
    """计算时间衰减分数（小时为单位）"""
    if not timestamp_str:
        return 0
    try:
        if 'T' in timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
        if base_time is None:
            base_time = datetime.now()
        hours_ago = (base_time - dt).total_seconds() / 3600
        if hours_ago < 0:
            hours_ago = 0
        # 指数衰减：每6小时减半
        return max(0, 100 * (0.5 ** (hours_ago / 6)))
    except (ValueError, TypeError):
        return 0


def analyze(data):
    """执行趋势分析"""
    logger.info(f"分析 {len(data)} 条数据...")
    
    # 统计关键词频率
    all_keywords = []
    topic_counts = Counter()
    
    for item in data:
        title = item.get("title", "")
        keywords = extract_keywords(title)
        all_keywords.extend(keywords)
        topic = classify_topic(title)
        topic_counts[topic] += 1
    
    # 关键词频率排行
    keyword_freq = Counter(all_keywords).most_common(50)
    
    # 话题分布
    topic_dist = dict(topic_counts.most_common())
    
    # 计算热度分
    hot_items = []
    base_time = datetime.now()
    for item in data:
        hotness = calculate_time_decay(item.get("timestamp", ""), base_time)
        item["_hotness"] = round(hotness, 2)
        hot_items.append(item)
    
    hot_items.sort(key=lambda x: x["_hotness"], reverse=True)
    top_items = hot_items[:20]
    
    result = {
        "generated_at": datetime.now().isoformat(),
        "total_analyzed": len(data),
        "top_keywords": [{"keyword": k, "count": c} for k, c in keyword_freq[:20]],
        "topic_distribution": topic_dist,
        "top_hot_items": [
            {
                "title": item.get("title", ""),
                "platform": item.get("_platform", ""),
                "timestamp": item.get("timestamp", ""),
                "hotness": item.get("_hotness", 0)
            }
            for item in top_items
        ]
    }
    
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"趋势分析完成: {OUTPUT_FILE}")
    
    return result


if __name__ == "__main__":
    data = load_aggregated_data()
    if data:
        result = analyze(data)
        print(f"分析了 {result['total_analyzed']} 条数据")
        print(f"Top话题: {list(result['topic_distribution'].keys())[:5]}")
    else:
        print("没有数据可分析")
