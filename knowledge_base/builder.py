"""Knowledge Base Builder - 知识库构建器"""
import json
import os
import re
import glob
import logging
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional
from urllib.parse import quote

from .entity_extractor import EntityExtractor

logger = logging.getLogger(__name__)

PLATFORM_NAMES = {
    'weibo': '微博', 'zhihu': '知乎', 'douyin': '抖音',
    '36kr': '36氪', 'huxiu': '虎嗅', 'eastmoney': '东方财富',
    'paper': '澎湃', 'wangyi': '网易', 'huanqiu': '环球网',
    'boc': '央行', 'sse': '上交所', 'hkex': '港交所', 'bse': '北交所',
    'cninfo': '巨潮资讯',
}


class KnowledgeBaseBuilder:
    """知识库构建器 - 将原始数据转换为结构化知识"""

    def __init__(self, kb_root: str, raw_root: str):
        self.kb_root = kb_root
        self.raw_root = raw_root
        self.extractor = EntityExtractor()

        # 确保目录存在
        self._ensure_dirs()

    def _ensure_dirs(self):
        """创建知识库目录结构"""
        dirs = [
            os.path.join(self.kb_root, 'company'),
            os.path.join(self.kb_root, 'industry'),
            os.path.join(self.kb_root, 'topics'),
            os.path.join(self.kb_root, 'graph'),
            os.path.join(self.kb_root, 'company', 'financial_reports'),
            os.path.join(self.kb_root, 'company', 'announcements'),
            os.path.join(self.kb_root, 'topics', 'hot_topics'),
            os.path.join(self.kb_root, 'topics', 'topic_timeline'),
        ]
        for d in dirs:
            os.makedirs(d, exist_ok=True)

    # ------------------------------------------------------------------
    # 数据加载 (归一化 + 去重)
    # ------------------------------------------------------------------

    def _extract_items(self, data) -> list:
        """从各种 JSON 结构中提取 item 列表"""
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            items = []
            for key in ('items', 'data', 'list', 'newsflash', 'hotlist', 'articles'):
                val = data.get(key)
                if isinstance(val, list):
                    items.extend(val)
            return items
        return []

    def _normalize_item(self, item: dict, platform: str) -> dict:
        """将不同平台的原始数据归一化为统一字段"""
        # 标题
        title = (item.get('title') or item.get('word') or
                 item.get('keyword') or item.get('name') or '').strip()

        # 热度
        hotness = (item.get('hotness') or item.get('hot') or
                   item.get('hot_value') or item.get('heat') or
                   item.get('score') or 0)
        try:
            hotness = int(float(hotness))
        except (ValueError, TypeError):
            hotness = 0

        # 来源
        source = item.get('source') or item.get('platform') or ''
        if not source:
            source = PLATFORM_NAMES.get(platform, platform)

        # URL — 优先取原始值
        url = item.get('url') or item.get('link') or item.get('href') or ''

        # URL 补全: 对缺失 URL 的平台基于规则构造
        if not url:
            item_id = str(item.get('id') or item.get('group_id') or '')
            if platform == '36kr' and item_id:
                url = f'https://36kr.com/newsflashes/{item_id}'
            elif platform == 'douyin' and title:
                url = f'https://www.douyin.com/search/{quote(title)}'
            elif platform == 'weibo' and not url and title:
                url = f'https://s.weibo.com/weibo?q={quote(title)}'

        # 摘要
        summary = item.get('summary') or item.get('content') or item.get('excerpt') or ''
        if isinstance(summary, str):
            summary = summary[:500]
        else:
            summary = str(summary)[:500]

        return {
            'title': title,
            'url': url,
            'source': source,
            'hotness': hotness,
            'summary': summary,
            'timestamp': (item.get('timestamp') or item.get('time') or
                          item.get('publishTime') or ''),
            '_platform': platform,
        }

    def _dedup_items(self, items: list) -> list:
        """按标题去重，保留最高热度版本，合并 URL"""
        best = {}
        for item in items:
            key = re.sub(r'\s+', '', item.get('title', '')).lower()
            if not key or len(key) < 3:
                continue
            existing = best.get(key)
            if existing is None:
                best[key] = dict(item)
            else:
                if not existing.get('url') and item.get('url'):
                    existing['url'] = item['url']
                if item.get('hotness', 0) > existing.get('hotness', 0):
                    existing['hotness'] = item['hotness']
        return sorted(best.values(), key=lambda x: x.get('hotness', 0), reverse=True)

    def _load_file_items(self, fpath: str, platform: str) -> List[Dict]:
        """从单个 JSON 文件加载并归一化数据"""
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            raw = self._extract_items(data)
            return [self._normalize_item(item, platform)
                    for item in raw if isinstance(item, dict)]
        except Exception as e:
            logger.warning("Failed to load %s: %s", fpath, e)
            return []

    def _load_dir_items(self, base_dir: str, fallback_platform: str, hours: int = 24) -> List[Dict]:
        """扫描目录下的 JSON 文件（含子目录），归一化 + 去重"""
        items = []
        cutoff = datetime.now().timestamp() - hours * 3600

        # 直接文件
        for fpath in glob.glob(os.path.join(base_dir, '*.json')):
            if os.path.getmtime(fpath) < cutoff:
                continue
            items.extend(self._load_file_items(fpath, fallback_platform))

        # 子目录
        for subdir in glob.glob(os.path.join(base_dir, '*')):
            if not os.path.isdir(subdir):
                continue
            platform = os.path.basename(subdir)
            for fpath in glob.glob(os.path.join(subdir, '*.json')):
                if os.path.getmtime(fpath) < cutoff:
                    continue
                items.extend(self._load_file_items(fpath, platform))

        return self._dedup_items(items)

    def load_hot_topics(self, hours: int = 24) -> List[Dict]:
        """加载热点数据 (归一化 + 去重)"""
        return self._load_dir_items(
            os.path.join(self.raw_root, 'hot_topics'), 'hot_topics', hours)

    def load_policy(self, hours: int = 48) -> List[Dict]:
        """加载政策数据 (归一化 + 去重)"""
        return self._load_dir_items(
            os.path.join(self.raw_root, 'policy'), 'policy', hours)

    def load_exchange(self, hours: int = 24) -> List[Dict]:
        """加载交易所数据 (归一化 + 去重)"""
        return self._load_dir_items(
            os.path.join(self.raw_root, 'exchange'), 'exchange', hours)

    # ------------------------------------------------------------------
    # 知识构建
    # ------------------------------------------------------------------
    def build_topic_index(self, hot_items: List[Dict]) -> Dict:
        """构建话题索引"""
        # 实体抽取
        entities = self.extractor.extract_all(hot_items)

        # 按热度排序
        sorted_topics = sorted(
            hot_items,
            key=lambda x: x.get('hotness', 0),
            reverse=True
        )[:100]

        topic_index = {
            'generated_at': datetime.now().isoformat(),
            'total_items': len(hot_items),
            'unique_sources': len(set(i.get('source', '') for i in hot_items)),
            'top20': [
                {
                    'title': t.get('title', ''),
                    'source': t.get('source', ''),
                    'hotness': t.get('hotness', 0),
                    'timestamp': t.get('timestamp', ''),
                    'url': t.get('url', ''),
                }
                for t in sorted_topics[:20]
            ],
            'entities': entities['top_entities'],
        }

        return topic_index

    def build_industry_map(self, items: List[Dict]) -> Dict:
        """构建行业知识图谱"""
        industry_map = defaultdict(list)
        seen = defaultdict(set)

        # 行业关键词
        industry_keywords = {
            '新能源': ['光伏', '锂电', '储能', '风电', '氢能', '新能源汽车', '动力电池'],
            '半导体': ['芯片', '集成电路', '半导体', '晶圆', '代工', '封测'],
            '医药': ['生物医药', '医疗器械', '疫苗', '中药', 'CXO', '创新药'],
            '消费': ['白酒', '食品', '饮料', '乳业', '调味品', '家电', '纺织服装'],
            '金融': ['银行', '保险', '证券', '信托', '基金', '资管'],
            '科技': ['AI', '大模型', '云计算', '5G', '物联网', '网络安全'],
            '地产': ['房地产', '物业', '建筑', '建材', '家居'],
        }

        for item in items:
            title = item.get('title', '') + item.get('summary', '')
            for industry, keywords in industry_keywords.items():
                if any(kw in title for kw in keywords):
                    # 按标题去重
                    norm_title = re.sub(r'\s+', '', item.get('title', '')).lower()
                    if norm_title in seen[industry]:
                        break
                    seen[industry].add(norm_title)
                    industry_map[industry].append({
                        'title': item.get('title', ''),
                        'source': item.get('source', ''),
                        'url': item.get('url', ''),
                        'hotness': item.get('hotness', 0),
                    })
                    break

        return {
            'generated_at': datetime.now().isoformat(),
            'industries': {k: list(v) for k, v in industry_map.items()},
        }

    def build_entity_graph(self, items: List[Dict]) -> Dict:
        """构建实体关系图谱"""
        entities = self.extractor.extract_all(items)

        # 转换为图格式
        graph_nodes = []
        graph_edges = []

        # 实体节点
        for etype, top_list in entities['top_entities'].items():
            for name, count in top_list[:30]:
                graph_nodes.append({
                    'id': f"{etype}:{name}",
                    'type': etype,
                    'name': name,
                    'weight': count,
                })

        # 公司-行业边（基于公司名中的行业词）
        company_industry_map = {}
        for node in graph_nodes:
            if node['type'] == 'company':
                name = node['name']
                for ind in ['新能源', '半导体', '医药', '消费', '金融', '科技', '地产']:
                    if ind in name:
                        company_industry_map[name] = ind
                        graph_edges.append({
                            'from': f"company:{name}",
                            'to': f"industry:{ind}",
                            'relation': 'belongs_to',
                            'weight': node['weight'],
                        })

        return {
            'generated_at': datetime.now().isoformat(),
            'nodes': graph_nodes,
            'edges': graph_edges,
            'stats': {
                'total_nodes': len(graph_nodes),
                'total_edges': len(graph_edges),
                'by_type': {n['type']: sum(1 for n in graph_nodes if n['type'] == n['type']) 
                           for n in graph_nodes},
            },
        }

    # ------------------------------------------------------------------
    # 主构建流程
    # ------------------------------------------------------------------
    def build(self, module: str = 'all') -> Dict:
        """执行知识库构建

        Args:
            module: 'all' | 'hot_topics' | 'policy' | 'exchange' | 'industry' | 'graph'

        Returns:
            构建结果统计
        """
        results = {}

        # 加载数据
        hot_items = []
        policy_items = []
        exchange_items = []

        if module in ('all', 'hot_topics', 'topics', 'graph'):
            hot_items = self.load_hot_topics()
            logger.info("Loaded %d hot topic items", len(hot_items))

        if module in ('all', 'policy', 'industry'):
            policy_items = self.load_policy()
            logger.info("Loaded %d policy items", len(policy_items))

        if module in ('all', 'exchange', 'industry'):
            exchange_items = self.load_exchange()
            logger.info("Loaded %d exchange items", len(exchange_items))

        # 构建话题索引
        if module in ('all', 'hot_topics', 'topics'):
            topic_index = self.build_topic_index(hot_items)
            out_path = os.path.join(self.kb_root, 'topics', 'topic_index.json')
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(topic_index, f, ensure_ascii=False, indent=2)
            results['topics'] = {
                'path': out_path,
                'items': len(hot_items),
                'entity_types': len(topic_index.get('entities', {})),
            }
            logger.info("Saved topic index: %s", out_path)

        # 构建行业图谱
        if module in ('all', 'industry'):
            all_items = hot_items + policy_items
            industry_map = self.build_industry_map(all_items)
            out_path = os.path.join(self.kb_root, 'industry', 'industry_index.json')
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(industry_map, f, ensure_ascii=False, indent=2)
            results['industry'] = {
                'path': out_path,
                'industries': len(industry_map.get('industries', {})),
            }
            logger.info("Saved industry index: %s", out_path)

        # 构建实体图谱
        if module in ('all', 'graph'):
            graph = self.build_entity_graph(hot_items + policy_items)
            out_path = os.path.join(self.kb_root, 'graph', 'entities.json')
            with open(out_path, 'w', encoding='utf-8') as f:
                json.dump(graph, f, ensure_ascii=False, indent=2)
            results['graph'] = {
                'path': out_path,
                'nodes': graph.get('stats', {}).get('total_nodes', 0),
                'edges': graph.get('stats', {}).get('total_edges', 0),
            }
            logger.info("Saved entity graph: %s", out_path)

        results['generated_at'] = datetime.now().isoformat()
        return results
