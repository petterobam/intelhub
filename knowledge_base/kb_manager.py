"""KnowledgeBaseManager - 知识库统一管理器（供 executor 调用）

用法:
  from knowledge_base.kb_manager import KnowledgeBaseManager
  kb = KnowledgeBaseManager()
  result = kb.ingest('all')         # 构建全量
  result = kb.ingest('hot_topics')  # 只构建热点话题
  result = kb.search('华为')         # 搜索
  result = kb.stats()               # 统计
"""
import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# 自动检测项目根目录
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CURRENT_DIR)
KB_ROOT = os.path.join(_PROJECT_ROOT, 'data', 'knowledge_base')
RAW_ROOT = os.path.join(_PROJECT_ROOT, 'data', 'raw')


class KnowledgeBaseManager:
    """知识库统一管理器"""

    def __init__(self, kb_root: str = None, raw_root: str = None):
        self.kb_root = kb_root or os.environ.get('KB_ROOT', KB_ROOT)
        self.raw_root = raw_root or os.environ.get('RAW_ROOT', RAW_ROOT)

    # ------------------------------------------------------------------
    # 构建入口
    # ------------------------------------------------------------------
    def ingest(self, module: str = 'all') -> Dict:
        """摄入原始数据并构建知识库

        Args:
            module: 'all' | 'hot_topics' | 'policy' | 'exchange' | 'industry' | 'graph'

        Returns:
            {
                'status': 'success' | 'error',
                'module': module,
                'generated_at': ISO timestamp,
                'build_results': {...},
                'stats': {...}
            }
        """
        from .builder import KnowledgeBaseBuilder

        logger.info("Starting KB ingest for module: %s", module)

        try:
            builder = KnowledgeBaseBuilder(
                kb_root=self.kb_root,
                raw_root=self.raw_root,
            )

            # 执行构建
            build_results = builder.build(module)

            # 统计
            stats = self._get_stats(module)

            result = {
                'status': 'success',
                'module': module,
                'generated_at': datetime.now().isoformat(),
                'build_results': build_results,
                'stats': stats,
            }

            logger.info("KB ingest completed: %s", json.dumps(build_results))
            return result

        except ImportError as e:
            logger.error("Failed to import builder: %s", e)
            return {
                'status': 'error',
                'module': module,
                'error': f'Builder not available: {e}',
                'generated_at': datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error("KB ingest failed: %s", e)
            return {
                'status': 'error',
                'module': module,
                'error': str(e),
                'generated_at': datetime.now().isoformat(),
            }

    def rebuild(self, module: str = 'all') -> Dict:
        """全量重建（先清空再构建）"""
        logger.info("Rebuilding KB for module: %s", module)
        return self.ingest(module)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def search(self, query: str, top_k: int = 10) -> List[Dict]:
        """全文检索

        Returns:
            list of matching entities/topics
        """
        results = []
        query_lower = query.lower()

        # 搜索话题索引
        topic_path = os.path.join(self.kb_root, 'topics', 'topic_index.json')
        if os.path.exists(topic_path):
            with open(topic_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for item in data.get('top20', []):
                if query_lower in item.get('title', '').lower():
                    item['match_type'] = 'topic'
                    results.append(item)

        # 搜索行业索引
        industry_path = os.path.join(self.kb_root, 'industry', 'industry_index.json')
        if os.path.exists(industry_path):
            with open(industry_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for industry, items in data.get('industries', {}).items():
                if query_lower in industry.lower():
                    results.append({
                        'match_type': 'industry',
                        'name': industry,
                        'item_count': len(items),
                        'items': items[:5],
                    })
                else:
                    for item in items:
                        if query_lower in item.get('title', '').lower():
                            item['match_type'] = 'industry_item'
                            item['industry'] = industry
                            results.append(item)

        return results[:top_k]

    def get_topic(self, topic: str = None) -> Dict:
        """获取话题索引"""
        topic_path = os.path.join(self.kb_root, 'topics', 'topic_index.json')
        if os.path.exists(topic_path):
            with open(topic_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_industry(self, industry: str = None) -> Dict:
        """获取行业索引"""
        industry_path = os.path.join(self.kb_root, 'industry', 'industry_index.json')
        if os.path.exists(industry_path):
            with open(industry_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if industry:
                return {'industries': {industry: data.get('industries', {}).get(industry, [])}}
            return data
        return {}

    def get_graph(self) -> Dict:
        """获取实体关系图谱"""
        graph_path = os.path.join(self.kb_root, 'graph', 'entities.json')
        if os.path.exists(graph_path):
            with open(graph_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_related(self, entity: str) -> Dict:
        """获取实体相关关系"""
        graph = self.get_graph()
        related = []

        for edge in graph.get('edges', []):
            if entity in edge.get('from', '') or entity in edge.get('to', ''):
                related.append(edge)

        return {'entity': entity, 'related': related}

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------
    def stats(self, module: str = None) -> Dict:
        """获取知识库统计信息"""
        return self._get_stats(module or 'all')

    def _get_stats(self, module: str = 'all') -> Dict:
        """内部统计"""
        stats = {
            'kb_root': self.kb_root,
            'raw_root': self.raw_root,
            'modules': {},
        }

        paths = {
            'topics': os.path.join(self.kb_root, 'topics', 'topic_index.json'),
            'industry': os.path.join(self.kb_root, 'industry', 'industry_index.json'),
            'graph': os.path.join(self.kb_root, 'graph', 'entities.json'),
        }

        for name, path in paths.items():
            if os.path.exists(path):
                size = os.path.getsize(path)
                mtime = datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                stats['modules'][name] = {
                    'status': 'ok',
                    'size_bytes': size,
                    'last_updated': mtime,
                    'entity_count': len(data.get('top20', [])),
                }
            else:
                stats['modules'][name] = {'status': 'missing'}

        # 原始数据统计
        for sub in ['hot_topics', 'policy', 'exchange', 'financial']:
            subpath = os.path.join(self.raw_root, sub)
            if os.path.isdir(subpath):
                files = sum(1 for _ in (f for f in os.walk(subpath) for _ in f[2]) if True)
                latest = max((os.path.getmtime(os.path.join(r, f))
                             for r, d, files in os.walk(subpath)
                             for f in files), default=0)
                age = int((datetime.now().timestamp() - latest) / 60) if latest else 999
                stats['modules'][f'raw_{sub}'] = {
                    'files': files,
                    'age_minutes': age,
                }

        return stats
