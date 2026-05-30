"""Entity Extractor - 从文本中抽取实体（公司/行业/人物/地区）"""
import re
import json
import os
from collections import defaultdict
from typing import List, Dict, Set, Tuple

# 已知大公司（整词匹配）
KNOWN_COMPANIES = {
    '华为', '阿里巴巴', '腾讯', '字节跳动', '百度', '京东', '美团',
    '拼多多', '小米', 'vivo', 'OPPO', '比亚迪', '宁德时代',
    '特斯拉', '微软', '谷歌', '亚马逊', '英伟达',
    '贵州茅台', '五粮液', '泸州老窖', '洋河股份',
    '海康威视', '中芯国际', '中国移动', '中国平安', '招商银行',
    '工商银行', '建设银行', '中国银行', '农业银行',
    '中国石油', '中国石化', '中国建筑', '中国中免',
    '美的集团', '格力电器', '万科A', '中国神华', '紫金矿业',
    '中信证券', '华泰证券', '国泰君安', '东方财富', '同花顺',
    '药明康德', '恒瑞医药', '迈瑞医疗', '片仔癀', '云南白药',
    '隆基绿能', '通威股份', '阳光电源', '三峡能源', '晶澳科技',
    '中航光电', '中国商飞', '中国商飞',
}

# 实体模式
ENTITY_PATTERNS = {
    "company": [
        r'[一-龥]{2,6}(?:股份|集团|有限公司|有限责任公司|控股|投资|资本|资产管理)',
        r'ST[一-龥]{1,4}',
        r'\*?ST[一-龥]{1,4}',
    ],
    "industry": [
        r'新能源|光伏|锂电|储能|风电|氢能',
        r'半导体|芯片|集成电路',
        r'医药|生物医药|医疗器械|CXO',
        r'消费|白酒|食品|饮料|乳业',
        r'金融|银行|保险|证券|基金',
        r'AI|大模型|人工智能|云计算',
        r'科技|5G|通信|物联网',
        r'地产|房地产|物业',
    ],
    "policy": [
        r'央行|银保监|证监会|财政部|发改委|工信部',
        r'统计局|国资委|外管局|国务院',
        r'中国人民银行',
    ],
    "region": [
        r'北京|上海|深圳|广州|杭州|成都|武汉|南京|西安|苏州',
        r'[一-龥]{2,6}(?:省|市|自治区)',
    ],
}

STOP_WORDS = {
    '的', '了', '是', '在', '和', '有', '我', '你', '他', '她',
    '个', '中', '上', '下', '与', '等', '都', '会', '就', '也',
    '公司', '今天', '这个', '一个',
}


def _tokenize(text):
    """简单分词，返回所有可能的中文词组"""
    chars = list(text)
    tokens = []
    for length in range(2, 7):  # 2-6字词
        for i in range(len(chars) - length + 1):
            token = ''.join(chars[i:i+length])
            tokens.append(token)
    return tokens


class EntityExtractor:
    def __init__(self):
        self.compiled = {}
        for etype, patterns in ENTITY_PATTERNS.items():
            self.compiled[etype] = [re.compile(p) for p in patterns]

    def extract(self, text: str) -> Dict[str, List[Dict]]:
        if not text:
            return {}
        result = defaultdict(list)
        seen = defaultdict(set)

        # 已知公司检测（整词）
        words = set(_tokenize(text))
        for company in KNOWN_COMPANIES:
            if company in words:
                # 找到位置
                start = text.find(company)
                if start >= 0:
                    key = f"{company}_{start}"
                    if key not in seen['company']:
                        seen['company'].add(key)
                        result['company'].append({'text': company, 'start': start, 'end': start + len(company)})

        # 正则检测
        for etype, regexes in self.compiled.items():
            for regex in regexes:
                for m in regex.finditer(text):
                    entity_text = m.group()
                    start, end = m.span()
                    key = f"{entity_text}_{start}"
                    if key not in seen[etype] and entity_text not in STOP_WORDS:
                        seen[etype].add(key)
                        result[etype].append({'text': entity_text, 'start': start, 'end': end})

        return dict(result)

    def extract_all(self, items: List[Dict]) -> Dict:
        all_entities = defaultdict(lambda: defaultdict(int))
        for item in items:
            text = ' '.join(filter(None, [item.get('title', ''), item.get('summary', '')]))
            extracted = self.extract(text)
            for etype, entities in extracted.items():
                for entity in entities:
                    all_entities[etype][entity['text']] += 1
        return {
            'total_items': len(items),
            'entities': {etype: dict(counts) for etype, counts in all_entities.items()},
            'top_entities': {
                etype: sorted(counts.items(), key=lambda x: x[1], reverse=True)[:20]
                for etype, counts in all_entities.items()
            },
        }
