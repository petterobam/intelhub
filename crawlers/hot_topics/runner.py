"""Hot Topics Runner - 调用迁移的 Node.js 爬虫脚本 + Python fallback"""
import os
import json
import logging
import subprocess
import re
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, 'scripts', 'hot_topics')
DATA_DIR = os.path.join(BASE_DIR, '..', 'data', 'raw', 'hot_topics')

PLATFORMS = {
    'weibo': {
        'script': 'weibo-crawler.js',
        'name': '微博热搜',
        'subdir': 'weibo',
    },
    'douyin': {
        'script': 'douyin-hot-crawler.js',
        'name': '抖音热榜',
        'subdir': 'douyin',
    },
    'zhihu': {
        'script': 'zhihu-crawler.js',
        'name': '知乎热榜',
        'subdir': 'zhihu',
    },
    '36kr': {
        'script': '36kr-crawler.js',
        'name': '36氪',
        'subdir': '36kr',
    },
    'huxiu': {
        'script': 'huxiu-crawler.js',
        'name': '虎嗅',
        'subdir': 'huxiu',
    },
    'eastmoney': {
        'script': 'eastmoney-crawler.js',
        'name': '东方财富',
        'subdir': 'eastmoney',
    },
    'paper': {
        'script': 'paper-crawler.js',
        'name': '澎湃',
        'subdir': 'paper',
    },
    'wangyi': {
        'script': 'wangyi-browser-crawler.js',
        'name': '网易',
        'subdir': 'wangyi',
    },
    'huanqiu': {
        'script': 'huanqiu-crawler.js',
        'name': '环球网',
        'subdir': 'huanqiu',
    },
    'sspai': {
        'script': 'sspai-crawler.js',
        'name': '少数派',
        'subdir': 'sspai',
        'scripts_dir': 'tech',
    },
    'ithome': {
        'script': 'ithome-crawler.js',
        'name': 'IT之家',
        'subdir': 'ithome',
        'scripts_dir': 'tech',
    },
    'github': {
        'script': 'github-trending-crawler.js',
        'name': 'GitHub Trending',
        'subdir': 'github',
        'scripts_dir': 'tech',
    },
    'wallstreet': {
        'script': 'wallstreet-crawler.js',
        'name': '华尔街见闻',
        'subdir': 'wallstreet',
        'scripts_dir': 'finance',
    },
    'yicai': {
        'script': 'yicai-crawler.js',
        'name': '第一财经',
        'subdir': 'yicai',
        'scripts_dir': 'finance',
    },
    'bilibili': {
        'script': 'bilibili-crawler.js',
        'name': 'B站热门',
        'subdir': 'bilibili',
    },
    'toutiao': {
        'script': 'toutiao-crawler.js',
        'name': '今日头条',
        'subdir': 'toutiao',
    },
    'caixin': {
        'script': 'caixin-crawler.js',
        'name': '财新网',
        'subdir': 'caixin',
    },
    '1905': {
        'script': '1905-crawler.js',
        'name': '1905电影网',
        'subdir': '1905',
    },
}


class HotTopicsRunner:
    """热点平台采集 - Node.js脚本优先 + Python requests降级"""

    def __init__(self):
        self.data_dir = os.path.abspath(DATA_DIR)
        os.makedirs(self.data_dir, exist_ok=True)

    def run_all(self) -> List[Dict]:
        results = []
        for pid, pcfg in PLATFORMS.items():
            logger.info("Collecting %s (%s)...", pcfg['name'], pid)
            result = self._run_js_crawler(pid, pcfg)
            if result.get('status') != 'success':
                logger.warning("JS crawler failed for %s, trying fallback", pid)
                result = self._fallback(pid, pcfg)
            results.append(result)
        # 执行去重
        self._dedup()
        return results

    def run_platform(self, platform_id: str) -> Dict:
        """运行单个平台"""
        pcfg = PLATFORMS.get(platform_id)
        if not pcfg:
            return {'platform': platform_id, 'status': 'error', 'error': 'Unknown platform'}
        result = self._run_js_crawler(platform_id, pcfg)
        if result.get('status') != 'success':
            result = self._fallback(platform_id, pcfg)
        return result

    def _run_js_crawler(self, pid: str, pcfg: Dict) -> Dict:
        """调用 Node.js 爬虫脚本"""
        scripts_dir = os.path.join(os.path.dirname(SCRIPTS_DIR), pcfg.get('scripts_dir', 'hot_topics'))
        script_path = os.path.join(scripts_dir, pcfg['script'])
        if not os.path.exists(script_path):
            return {
                'platform': pid, 'name': pcfg['name'],
                'status': 'error', 'error': f'Script not found: {pcfg["script"]}',
                'item_count': 0, 'items': [],
                'collected_at': datetime.now().isoformat(),
            }

        try:
            env = os.environ.copy()
            output_subdir = os.path.join(self.data_dir, pcfg['subdir'])
            os.makedirs(output_subdir, exist_ok=True)
            env['INTELHUB_DATA_DIR'] = output_subdir
            proc = subprocess.run(
                ['node', script_path],
                capture_output=True, text=True, timeout=120,
                cwd=scripts_dir, env=env,
            )
            # 扫描输出目录获取采集结果
            items = self._scan_output(pid, pcfg)
            return {
                'platform': pid, 'name': pcfg['name'],
                'status': 'success' if proc.returncode == 0 else 'partial',
                'item_count': len(items), 'items': items,
                'stdout': proc.stdout[-2000:] if proc.stdout else '',
                'collected_at': datetime.now().isoformat(),
            }
        except subprocess.TimeoutExpired:
            return {
                'platform': pid, 'name': pcfg['name'],
                'status': 'timeout', 'error': 'Node.js script timed out (120s)',
                'item_count': 0, 'items': [],
                'collected_at': datetime.now().isoformat(),
            }
        except Exception as e:
            return {
                'platform': pid, 'name': pcfg['name'],
                'status': 'error', 'error': str(e),
                'item_count': 0, 'items': [],
                'collected_at': datetime.now().isoformat(),
            }

    def _scan_output(self, pid: str, pcfg: Dict) -> List[Dict]:
        """扫描输出目录获取最新采集的数据"""
        subdir = os.path.join(self.data_dir, pcfg['subdir'])
        if not os.path.exists(subdir):
            return []

        items = []
        # 查找最新的 JSON 文件
        json_files = sorted(
            [f for f in os.listdir(subdir) if f.endswith('.json')],
            reverse=True,
        )
        if json_files:
            latest = os.path.join(subdir, json_files[0])
            try:
                with open(latest, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # 适配不同格式
                if isinstance(data, list):
                    items = data
                elif isinstance(data, dict):
                    items = data.get('items', data.get('data', data.get('hotlist',
                        data.get('newsflash', data.get('list', [])))))
            except Exception as e:
                logger.error("Failed to parse %s: %s", latest, e)
        return items[:100]  # 限制最多100条

    def _fallback(self, pid: str, pcfg: Dict) -> Dict:
        """Python requests 降级采集"""
        import requests
        url_map = {
            'weibo': 'https://weibo.com/ajax/side/hotSearch',
            'douyin': 'https://www.douyin.com/aweme/v1/web/hot/search/list/',
            'zhihu': 'https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total',
            '36kr': 'https://www.36kr.com/newsflashes',
            'huxiu': 'https://www.huxiu.com/article/',
            'eastmoney': 'https://www.eastmoney.com/',
            'paper': 'https://www.thepaper.cn/',
            'wangyi': 'https://news.163.com/',
            'huanqiu': 'https://www.huanqiu.com/',
            'bilibili': 'https://api.bilibili.com/x/web-interface/popular?ps=20',
            'toutiao': 'https://www.toutiao.com/hot-event/hot-board/?origin=hot_board&widen=1',
            'caixin': 'https://gateway.caixin.com/api/extapi/homeInterface.jsp?subject=100589266&start=1&count=20&type=2',
            '1905': 'https://www.1905.com/news/',
        }
        url = url_map.get(pid, '')
        base = {
            'platform': pid, 'name': pcfg['name'], 'url': url,
            'status': 'fallback',
            'collected_at': datetime.now().isoformat(),
            'item_count': 0, 'items': [],
        }
        if not url:
            base['status'] = 'skipped'
            return base

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'text/html,application/json',
            }
            resp = requests.get(url, headers=headers, timeout=15)
            # 简单提取标题
            items = self._parse_html_items(resp.text, pid)
            base['items'] = items
            base['item_count'] = len(items)
            base['status'] = 'success'
            # 保存降级结果
            self._save_result(pid, base)
        except Exception as e:
            base['error'] = str(e)
        return base

    def _parse_html_items(self, html: str, pid: str) -> List[Dict]:
        """简单 HTML 解析提取标题"""
        items = []
        # 通用标题提取: 查找 <a> 标签中的文本
        titles = re.findall(r'<a[^>]*>([^<]{10,100})</a>', html)
        seen = set()
        for t in titles:
            t = t.strip()
            if t not in seen and len(t) > 5:
                seen.add(t)
                items.append({'title': t, 'platform': pid})
        return items[:30]

    def _save_result(self, pid: str, result: Dict):
        """保存采集结果到 JSON"""
        subdir = os.path.join(self.data_dir, PLATFORMS[pid]['subdir'])
        os.makedirs(subdir, exist_ok=True)
        ts = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
        outpath = os.path.join(subdir, f'{pid}-{ts}.json')
        with open(outpath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        latest_path = os.path.join(subdir, f'{pid}-latest.json')
        with open(latest_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    def _dedup(self):
        """执行去重"""
        dedup_script = os.path.join(BASE_DIR, 'scripts', 'utils', 'deduplicate-data.py')
        if os.path.exists(dedup_script):
            try:
                subprocess.run(
                    ['python3', dedup_script],
                    capture_output=True, text=True, timeout=60,
                    cwd=BASE_DIR,
                )
            except Exception as e:
                logger.warning("Dedup failed: %s", e)
