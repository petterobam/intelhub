"""Exchange Runner - 四大交易所公告采集 (CNInfo 统一接口)"""
import os
import json
import logging
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, '..', 'data', 'raw', 'exchange')

EXCHANGES = {
    'sse': {
        'name': '上交所',
        'column': 'sse',
    },
    'szse': {
        'name': '深交所',
        'column': 'szse',
    },
    'bse': {
        'name': '北交所',
        'column': 'bse',
    },
    'hkex': {
        'name': '港交所',
        'column': 'hkex',
    },
}


class ExchangeRunner:

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.cninfo.com.cn/',
    }

    def __init__(self):
        self.data_dir = os.path.abspath(DATA_DIR)
        os.makedirs(self.data_dir, exist_ok=True)

    def run_all(self) -> List[Dict]:
        results = []
        for eid, ecfg in EXCHANGES.items():
            logger.info("Collecting %s (%s)...", ecfg['name'], eid)
            result = self._collect_exchange(eid, ecfg)
            results.append(result)
            self._save_result(eid, result)
        return results

    def run_exchange(self, exchange_id: str) -> Dict:
        ecfg = EXCHANGES.get(exchange_id)
        if not ecfg:
            return {'exchange': exchange_id, 'status': 'error', 'error': 'Unknown exchange'}
        result = self._collect_exchange(exchange_id, ecfg)
        self._save_result(exchange_id, result)
        return result

    def _collect_exchange(self, eid: str, ecfg: Dict) -> Dict:
        import requests
        base = {
            'exchange': eid,
            'name': ecfg['name'],
            'source_name': ecfg['name'],
            'collected_at': datetime.now().isoformat(),
        }
        try:
            session = requests.Session()
            session.trust_env = False
            data = {
                'stock': '',
                'tabName': 'fulltext',
                'pageSize': 20,
                'column': ecfg['column'],
                'pageNum': 1,
                'searchkey': '',
            }
            resp = session.post(
                'https://www.cninfo.com.cn/new/hisAnnouncement/query',
                headers=self.HEADERS,
                data=data,
                timeout=20,
            )
            result = resp.json()
            raw = result.get('announcements', [])
            items = []
            for ann in raw:
                title = ann.get('announcementTitle', '').strip()
                if not title:
                    continue
                sec_name = ann.get('secName', '')
                ts = ann.get('announcementTime', 0)
                date_str = ''
                if ts:
                    try:
                        date_str = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d %H:%M')
                    except Exception:
                        pass
                adjunct = ann.get('adjunctUrl', '')
                ann_id = ann.get('announcementId', '')
                url = f'https://www.cninfo.com.cn/new/disclosure/detail?announcementId={ann_id}' if ann_id else (f'https://static.cninfo.com.cn/{adjunct}' if adjunct else '')
                items.append({
                    'title': f'{title}' + (f' ({sec_name})' if sec_name else ''),
                    'url': url,
                    'date': date_str,
                    'source_name': ecfg['name'],
                    'stock_code': ann.get('secCode', ''),
                })
            base['status'] = 'success'
            base['item_count'] = len(items)
            base['items'] = items
        except Exception as e:
            base['status'] = 'error'
            base['error'] = str(e)
            base['item_count'] = 0
            base['items'] = []
        return base

    def _save_result(self, eid: str, result: Dict):
        subdir = os.path.join(self.data_dir, eid)
        os.makedirs(subdir, exist_ok=True)
        ts = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
        outpath = os.path.join(subdir, f'{eid}-{ts}.json')
        with open(outpath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        latest_path = os.path.join(subdir, f'{eid}-latest.json')
        with open(latest_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
