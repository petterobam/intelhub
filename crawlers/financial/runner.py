"""Financial Runner - 多源财经数据采集 (纯 Python)"""
import os
import json
import logging
import re
from datetime import datetime
from typing import List, Dict

logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, '..', 'data', 'raw', 'financial')


class FinancialRunner:

    def __init__(self):
        self.data_dir = os.path.abspath(DATA_DIR)
        os.makedirs(self.data_dir, exist_ok=True)

    def run_all(self) -> List[Dict]:
        results = []
        collectors = [
            ('eastmoney', '东方财富', self._collect_eastmoney),
            ('sina-finance', '新浪财经', self._collect_sina),
            ('boc-rate', '中国银行汇率', self._collect_boc_rate),
            ('cninfo', '巨潮资讯', self._collect_cninfo),
        ]
        for slug, name, fn in collectors:
            logger.info("Collecting %s (%s)...", name, slug)
            result = fn()
            results.append(result)
            self._save_result(slug, result)
        return results

    def run_source(self, slug: str) -> Dict:
        collectors = {
            'eastmoney': self._collect_eastmoney,
            'sina-finance': self._collect_sina,
            'boc-rate': self._collect_boc_rate,
            'cninfo': self._collect_cninfo,
        }
        fn = collectors.get(slug)
        if not fn:
            return {'slug': slug, 'status': 'error', 'error': 'Unknown source'}
        result = fn()
        self._save_result(slug, result)
        return result

    def _make_session(self):
        import requests
        session = requests.Session()
        session.trust_env = False
        return session

    def _collect_eastmoney(self) -> Dict:
        """东方财富 - A股三大指数 + 热门板块"""
        import requests
        base = {
            'slug': 'eastmoney',
            'source_name': '东方财富',
            'collected_at': datetime.now().isoformat(),
        }
        try:
            session = self._make_session()
            headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://quote.eastmoney.com/'}
            # 三大指数
            resp = session.get(
                'https://push2.eastmoney.com/api/qt/ulist.np/get',
                headers=headers,
                params={
                    'fltt': 2, 'fields': 'f2,f3,f4,f12,f14,f6',
                    'secids': '1.000001,0.399001,0.399006',
                    'ut': 'fa5fd1943c7b386f172d6893dbbd12d0',
                },
                timeout=10,
            )
            data = resp.json()
            items = []
            for d in data.get('data', {}).get('diff', []):
                items.append({
                    'title': f"{d.get('f14', '')} {d.get('f2', '')} ({d.get('f3', '')}%)",
                    'index_name': d.get('f14', ''),
                    'price': d.get('f2', 0),
                    'change_pct': d.get('f3', 0),
                    'change': d.get('f4', 0),
                    'volume': d.get('f6', 0),
                    'url': 'https://quote.eastmoney.com/',
                    'source_name': '东方财富',
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

    def _collect_sina(self) -> Dict:
        """新浪财经 - 龙头个股实时行情"""
        import requests
        base = {
            'slug': 'sina-finance',
            'source_name': '新浪财经',
            'collected_at': datetime.now().isoformat(),
        }
        # 龙头股票代码
        stocks = {
            'sh600519': '贵州茅台', 'sz300750': '宁德时代', 'sh601318': '中国平安',
            'sz000858': '五粮液', 'sh600036': '招商银行', 'sz300059': '东方财富',
            'sh601012': '隆基绿能', 'sz002594': '比亚迪', 'sh688981': '中芯国际',
            'sh601899': '紫金矿业', 'sz000001': '平安银行', 'sh600900': '长江电力',
        }
        try:
            session = self._make_session()
            codes = ','.join(stocks.keys())
            headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn/'}
            resp = session.get(f'https://hq.sinajs.cn/list={codes}', headers=headers, timeout=10)
            items = []
            for line in resp.text.strip().split('\n'):
                if '=' not in line:
                    continue
                code_part = line.split('=')[0].split('_')[-1]
                val = line.split('"')[1] if '"' in line else ''
                if not val:
                    continue
                fields = val.split(',')
                if len(fields) < 4:
                    continue
                name = stocks.get(code_part, fields[0])
                price = fields[3]
                prev_close = fields[2]
                try:
                    change_pct = round((float(price) - float(prev_close)) / float(prev_close) * 100, 2) if float(prev_close) else 0
                except (ValueError, ZeroDivisionError):
                    change_pct = 0
                items.append({
                    'title': f"{name} {price} ({change_pct:+.2f}%)",
                    'stock_name': name,
                    'stock_code': code_part,
                    'price': price,
                    'change_pct': change_pct,
                    'url': f'https://finance.sina.com.cn/realstock/company/{code_part}/nc.shtml',
                    'source_name': '新浪财经',
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

    def _collect_boc_rate(self) -> Dict:
        """中国银行 - 外汇牌价"""
        import requests
        base = {
            'slug': 'boc-rate',
            'source_name': '中国银行',
            'collected_at': datetime.now().isoformat(),
        }
        try:
            session = self._make_session()
            headers = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.boc.cn/'}
            resp = session.get('https://www.boc.cn/sourcedb/whpj/', headers=headers, timeout=15)
            resp.encoding = 'utf-8'

            # 解析汇率表格
            items = []
            # 匹配 <tr data-currency='...'> 行中的 td 值
            rows = re.findall(
                r"<tr[^>]*data-currency='([^']+)'\s*>\s*(?:<td[^>]*>([^<]*)</td>\s*){5}",
                resp.text, re.DOTALL,
            )
            # 更简单的方式：逐行匹配 data-currency
            rows = re.findall(
                r"data-currency='([^']+)'>\s*<td>\1</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>",
                resp.text,
            )

            currency_map = {
                '美元': 'USD', '欧元': 'EUR', '日元': 'JPY', '英镑': 'GBP',
                '港币': 'HKD', '澳大利亚元': 'AUD', '加拿大元': 'CAD',
                '瑞士法郎': 'CHF', '新加坡元': 'SGD', '新西兰元': 'NZD',
            }
            for row in rows:
                name = row[0].strip()
                if name not in currency_map:
                    continue
                buy_rate = row[1].strip() or row[2].strip()
                sell_rate = row[3].strip() or row[4].strip()
                items.append({
                    'title': f"{name} 买入{buy_rate} 卖出{sell_rate}",
                    'currency': name,
                    'code': currency_map[name],
                    'buy_rate': buy_rate,
                    'sell_rate': sell_rate,
                    'url': 'https://www.boc.cn/sourcedb/whpj/',
                    'source_name': '中国银行',
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

    def _collect_cninfo(self) -> Dict:
        """巨潮资讯 - 重大公告筛选"""
        import requests
        base = {
            'slug': 'cninfo',
            'source_name': '巨潮资讯',
            'collected_at': datetime.now().isoformat(),
        }
        # 筛选重大事项关键词
        keywords = ['业绩', '增持', '减持', '重组', '分红', '回购', '退市', '风险', '违规', '处罚']
        try:
            session = self._make_session()
            headers = {
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json',
                'Referer': 'https://www.cninfo.com.cn/',
            }
            items = []
            for kw in keywords:
                data = {
                    'stock': '',
                    'tabName': 'fulltext',
                    'pageSize': 5,
                    'column': 'szse',
                    'pageNum': 1,
                    'searchkey': kw,
                }
                resp = session.post(
                    'https://www.cninfo.com.cn/new/hisAnnouncement/query',
                    headers=headers,
                    data=data,
                    timeout=20,
                )
                result = resp.json()
                for ann in result.get('announcements', []):
                    title = ann.get('announcementTitle', '').strip()
                    if not title:
                        continue
                    sec_name = ann.get('secName', '')
                    ts = ann.get('announcementTime', 0)
                    date_str = ''
                    if ts:
                        try:
                            date_str = datetime.fromtimestamp(ts / 1000).strftime('%Y-%m-%d')
                        except Exception:
                            pass
                    adjunct = ann.get('adjunctUrl', '')
                    ann_id = ann.get('announcementId', '')
                    url = f'https://www.cninfo.com.cn/new/disclosure/detail?announcementId={ann_id}' if ann_id else (f'https://static.cninfo.com.cn/{adjunct}' if adjunct else '')
                    items.append({
                        'title': f"{title}" + (f" ({sec_name})" if sec_name else ""),
                        'url': url,
                        'date': date_str,
                        'keyword': kw,
                        'source_name': '巨潮资讯',
                    })
                if len(items) >= 30:
                    break
            # 去重
            seen = set()
            unique = []
            for it in items:
                if it['title'] not in seen:
                    seen.add(it['title'])
                    unique.append(it)
            base['status'] = 'success'
            base['item_count'] = len(unique)
            base['items'] = unique[:30]
        except Exception as e:
            base['status'] = 'error'
            base['error'] = str(e)
            base['item_count'] = 0
            base['items'] = []
        return base

    def _save_result(self, slug: str, result: Dict):
        subdir = os.path.join(self.data_dir, slug)
        os.makedirs(subdir, exist_ok=True)
        ts = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
        outpath = os.path.join(subdir, f'{slug}-{ts}.json')
        with open(outpath, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        latest_path = os.path.join(subdir, f'{slug}-latest.json')
        with open(latest_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
