#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据字段标准化工具 v2.0
将各平台的不同字段格式统一转换为标准格式 (title, url, time)
自动发现并处理所有去重后的数据文件
"""

import json
import os
import glob
import re
from pathlib import Path

# 字段映射配置：平台 -> {原始字段: 标准字段}
FIELD_MAPPINGS = {
    # 抖音: word -> title, event_time -> time
    "douyin": {
        "word": "title",
        "event_time": "time",
    },
    # 微博: word -> title
    "weibo": {
        "word": "title",
    },
    # 东方财富
    "eastmoney": {
        "title": "title",
    },
    # 知乎
    "zhihu": {
        "title": "title",
    },
    # B站
    "bilibili": {
        "title": "title",
    },
    # 36kr
    "36kr": {
        "title": "title",
    },
    # 虎嗅
    "huxiu": {
        "title": "title",
    },
    # 澎湃
    "paper": {
        "title": "title",
    },
    # 环球网
    "huanqiu": {
        "title": "title",
    },
    # 网易
    "wangyi": {
        "title": "title",
    },
    # 毒眸
    "dumere": {
        "title": "title",
    },
}

def normalize_timestamp(value):
    """标准化时间戳"""
    if not value:
        return None
    
    # 如果已经是字符串，直接返回
    if isinstance(value, str):
        return value
    
    # 如果是Unix时间戳（10位或13位数字）
    if isinstance(value, (int, float)):
        # 13位毫秒时间戳
        if value > 1000000000000:
            value = value / 1000
        # 转换为ISO格式
        from datetime import datetime
        try:
            dt = datetime.fromtimestamp(value)
            return dt.isoformat()
        except:
            return str(value)
    
    return str(value)

def generate_search_url(platform, title):
    """生成搜索URL"""
    if not title:
        return None
    
    import urllib.parse
    encoded = urllib.parse.quote(title)
    
    urls = {
        "douyin": f"https://www.douyin.com/search/{encoded}",
        "weibo": f"https://s.weibo.com/weibo/{encoded}",
        "zhihu": f"https://www.zhihu.com/search?q={encoded}",
        "bilibili": f"https://search.bilibili.com/search?keyword={encoded}",
        "36kr": f"https://36kr.com/newsflashes",
        "huxiu": f"https://www.huxiu.com/search?keyword={encoded}",
        "paper": f"https://www.thepaper.cn/search?keyword={encoded}",
        "huanqiu": f"https://search.huanqiu.com/search?keyword={encoded}",
        "wangyi": f"https://news.163.com/search?keyword={encoded}",
        "dumere": f"https://www.dumere.cn/search?keyword={encoded}",
    }
    
    return urls.get(platform)

def normalize_item(item, platform):
    """标准化单条数据"""
    mapping = FIELD_MAPPINGS.get(platform, {})
    
    normalized = {}
    
    # 字段映射
    for original_field, standard_field in mapping.items():
        if original_field in item:
            value = item[original_field]
            # 时间戳特殊处理
            if standard_field == "time" and original_field == "event_time":
                value = normalize_timestamp(value)
            normalized[standard_field] = value
    
    # 复制已存在的标准字段
    for field in ["title", "url", "time"]:
        if field in item and field not in normalized:
            value = item[field]
            if field == "time":
                value = normalize_timestamp(value)
            normalized[field] = value
    
    # 生成URL（如果缺失且平台支持）
    if "url" not in normalized or not normalized.get("url"):
        generated_url = generate_search_url(platform, normalized.get("title"))
        if generated_url:
            normalized["url"] = generated_url
    
    # 添加平台标识
    normalized["_platform"] = platform
    
    return normalized

def normalize_platform_data(platform, data):
    """标准化整个平台的数据"""
    if not isinstance(data, list):
        return data
    
    normalized_data = []
    for item in data:
        normalized = normalize_item(item, platform)
        normalized_data.append(normalized)
    
    return normalized_data

def extract_platform(filename):
    """从文件名提取平台名"""
    # 例如: douyin-latest-deduplicated.json -> douyin
    name = filename.replace('-latest-deduplicated.json', '')
    return name

def process_file(filepath):
    """处理单个文件"""
    platform = extract_platform(filepath.name)
    
    if not filepath.exists():
        print(f"  ⚠️ 文件不存在: {filepath}")
        return False
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 标准化数据
        normalized = normalize_platform_data(platform, data)
        
        # 写回文件
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(normalized, f, ensure_ascii=False, indent=2)
        
        print(f"  ✅ [{platform}] 已标准化 {len(normalized)} 条记录")
        return True
    except json.JSONDecodeError as e:
        print(f"  ⚠️ JSON解析错误 {filepath}: {e}")
        return False
    except Exception as e:
        print(f"  ❌ 处理失败 {filepath}: {e}")
        return False

def main():
    """主函数"""
    print("🔧 数据字段标准化工具 v2.0")
    print("=" * 50)
    
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent.parent / "data"  # 从 06-ops/temp/ 向上两级到 crawler-notes/
    
    # 自动发现所有去重后的数据文件
    pattern = str(data_dir / "*-latest-deduplicated.json")
    files = sorted(glob.glob(pattern))
    
    if not files:
        print("⚠️ 未发现去重后的数据文件")
        return 0
    
    print(f"📁 发现 {len(files)} 个待处理文件:")
    for f in files:
        print(f"   - {os.path.basename(f)}")
    print()
    
    success_count = 0
    for filepath in files:
        filepath = Path(filepath)
        print(f"📄 处理 {filepath.name}...")
        if process_file(filepath):
            success_count += 1
    
    print("\n" + "=" * 50)
    print(f"✅ 完成: 成功处理 {success_count}/{len(files)} 个文件")
    
    return success_count

if __name__ == "__main__":
    main()
