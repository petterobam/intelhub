"""Plaza API — 情报广场数据接口

面向普通用户的情报聚合 API:
  GET /api/v1/plaza/feed         — 情报流 (按 RSS 任务分类)
  GET /api/v1/plaza/data-tree    — 数据集市目录树
  GET /api/v1/plaza/data-detail  — 渠道详情 (文章列表)
  GET /api/v1/plaza/reports      — 按任务分组的报告
"""

import json
import os
import logging
import threading
import time
from datetime import datetime

from flask import Blueprint, request

from app.utils.helpers import standard_response, error_response

logger = logging.getLogger(__name__)

bp = Blueprint('plaza', __name__, url_prefix='/api/v1/plaza')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, 'data', 'raw')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')

# ── 内存缓存 ──────────────────────────────────────────────────

_cache = {}       # key -> {'data': ..., 'expires': timestamp}
_cache_lock = threading.Lock()
CACHE_TTL = 300   # 5 分钟


def _cache_get(key):
    with _cache_lock:
        entry = _cache.get(key)
        if entry and time.time() < entry['expires']:
            return entry['data']
    return None


def _cache_set(key, data, ttl=CACHE_TTL):
    with _cache_lock:
        _cache[key] = {'data': data, 'expires': time.time() + ttl}

# slug → 展示名映射（非 RSS 模块）
SOURCE_NAMES = {
    # hot_topics
    '36kr': '36氪', 'weibo': '微博热搜', 'zhihu': '知乎热榜', 'douyin': '抖音热点',
    'huxiu': '虎嗅', 'sspai': '少数派', 'eastmoney': '东方财富', 'yicai': '第一财经',
    'huanqiu': '环球网', 'github': 'GitHub Trending', 'paper': '澎湃新闻',
    'wangyi': '网易新闻', 'ithome': 'IT之家', 'wallstreet': '华尔街见闻',
    'bilibili': 'B站热门', 'toutiao': '今日头条', 'caixin': '财新网', '1905': '1905电影网',
    # policy
    'gov': '中国政府网', 'ndrc': '国家发改委', 'pbc': '央行/中国人民银行',
    'csrc': '证监会', 'miit': '工信部', 'mof': '财政部', 'safe': '外汇管理局',
    'sasac': '国资委', 'stats': '国家统计局', 'boc': '中国银行',
    # exchange
    'sse': '上交所', 'szse': '深交所', 'bse': '北交所', 'hkex': '港交所',
    # financial
    'cninfo': '巨潮资讯', 'eastmoney': '东方财富行情', 'sina-finance': '新浪财经个股',
    'boc-rate': '中行外汇牌价',
}


# ── 情报流 ──────────────────────────────────────────────────────

def _item_to_feed_entry(item, slug_dir):
    """将数据条目转为情报流条目，过滤无效数据"""
    title = item.get('title', '')
    url = item.get('url', item.get('link', ''))
    ts = item.get('timestamp', item.get('date', item.get('publishTime', item.get('time', ''))))
    if not title:
        return None
    # 财经数据（指数/汇率）没有 url 但有价值，允许无 url
    if not url and not any(item.get(k) for k in ('index_name', 'stock_name', 'currency', 'keyword')):
        return None
    return {
        'title': title,
        'url': url,
        'source_name': item.get('source_name', SOURCE_NAMES.get(slug_dir, slug_dir)),
        'source_slug': slug_dir,
        'timestamp': ts,
        'category': item.get('source_category', ''),
    }


@bp.route('/feed', methods=['GET'])
def feed():
    """聚合 RSS 情报流，支持按 task_id 筛选"""
    task_id = request.args.get('task_id', '')
    limit = min(int(request.args.get('limit', 100)), 200)

    # 缓存 key 包含筛选参数
    cache_key = f"feed:{task_id}:{limit}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    # 获取 RSS 采集任务映射
    tasks = _get_rss_tasks()
    task_map = {t['task_id']: t for t in tasks}

    # 确定要读取的 slug 列表
    if task_id and task_id in task_map:
        slugs = task_map[task_id].get('slugs', [])
    else:
        slugs = None  # 全部

    items = []

    # 扫描 RSS 数据
    rss_dir = os.path.join(DATA_DIR, 'rss')
    if os.path.isdir(rss_dir):
        for slug_dir in os.listdir(rss_dir):
            slug_path = os.path.join(rss_dir, slug_dir)
            if not os.path.isdir(slug_path):
                continue
            if slugs and slug_dir not in slugs:
                continue

            latest_file = os.path.join(slug_path, f'{slug_dir}-latest.json')
            if not os.path.exists(latest_file):
                continue
            try:
                with open(latest_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                batch = data.get('items', []) if isinstance(data, dict) else data if isinstance(data, list) else []
                for item in batch:
                    entry = _item_to_feed_entry(item, slug_dir)
                    if entry:
                        items.append(entry)
            except Exception:
                pass

    # RSS 数据为空时，聚合所有非 RSS 模块作为情报流
    if not items:
        for module in ('hot_topics', 'policy', 'exchange', 'financial'):
            module_dir = os.path.join(DATA_DIR, module)
            if not os.path.isdir(module_dir):
                continue
            for slug_dir in sorted(os.listdir(module_dir)):
                slug_path = os.path.join(module_dir, slug_dir)
                if not os.path.isdir(slug_path):
                    continue
                latest_file = os.path.join(slug_path, f'{slug_dir}-latest.json')
                if not os.path.exists(latest_file):
                    continue
                try:
                    with open(latest_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    batch = data.get('items', []) if isinstance(data, dict) else data if isinstance(data, list) else []
                    for item in batch:
                        entry = _item_to_feed_entry(item, slug_dir)
                        if entry:
                            items.append(entry)
                except Exception:
                    pass

    # 按时间倒序
    items.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
    items = items[:limit]

    result = standard_response({'items': items, 'tasks': tasks})
    _cache_set(cache_key, result)
    return result


def _get_rss_tasks():
    """获取所有 RSS 采集任务及其关联的 slug 列表"""
    try:
        from app.models.task import ScheduledTask
        from app.models.rss_source import RssSource
        from app import db

        tasks = ScheduledTask.query.filter_by(task_type='crawler', module='rss', enabled=True).all()
        result = []
        for t in tasks:
            cfg = {}
            try:
                cfg = json.loads(t.script) if t.script and t.script.strip().startswith('{') else {}
            except Exception:
                pass

            source_ids = cfg.get('source_ids', [])
            slugs = []
            if source_ids:
                sources = RssSource.query.filter(RssSource.id.in_(source_ids)).all()
                slugs = [s.slug or str(s.id) for s in sources]

            # 统计该任务最新数据时间
            latest_time = ''
            for slug in slugs[:5]:
                lf = os.path.join(DATA_DIR, 'rss', slug, f'{slug}-latest.json')
                if os.path.exists(lf):
                    try:
                        mtime = os.path.getmtime(lf)
                        ts = datetime.fromtimestamp(mtime).isoformat()
                        if ts > latest_time:
                            latest_time = ts
                    except Exception:
                        pass

            result.append({
                'task_id': t.id,
                'task_name': t.name,
                'source_count': len(source_ids),
                'slugs': slugs,
                'latest_time': latest_time,
            })
        return result
    except Exception as e:
        logger.warning(f'Failed to get RSS tasks: {e}')
        return []


# ── 数据集市目录 ──────────────────────────────────────────────────

def _extract_source_name(data):
    """从数据文件中提取 source_name"""
    try:
        items = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get('items', data.get('data', []))
        for item in items[:5]:
            if isinstance(item, dict):
                sn = item.get('source_name', '')
                if sn and len(sn) < 50:
                    return sn
    except Exception:
        pass
    return ''


def _clean_item_url(title, url):
    """清洗条目的 title 和 url，处理 GitHub 等特殊格式"""
    if not url:
        return title, url
    # GitHub login?return_to=%2Fowner%2Frepo → owner/repo
    if 'login?return_to=' in url:
        from urllib.parse import unquote
        path = unquote(url.split('return_to=')[-1])
        parts = [p for p in path.strip('/').split('/') if p]
        if len(parts) >= 2:
            repo_name = '/'.join(parts[:2])
            clean_url = f'https://github.com/{repo_name}'
            if not title or 'login?' in title:
                title = repo_name
            return title, clean_url
    # GitHub sponsors/xxx → 清洗 title
    if 'github.com/sponsors/' in url and '/' in (title or ''):
        name = url.split('sponsors/')[-1].split('?')[0]
        if not title or title.startswith('sponsors/'):
            title = f'{name} (Sponsor)'
    return title, url

@bp.route('/data-tree', methods=['GET'])
def data_tree():
    """返回数据目录树 — 保留模块分类，RSS 内部按采集任务分组"""
    cached = _cache_get('data-tree')
    if cached is not None:
        return cached
    modules = {
        'hot_topics': '热点舆情',
        'policy': '政策法规',
        'exchange': '交易所公告',
        'financial': '财经数据',
        'rss': 'RSS 资讯',
    }

    result = {}
    for module_key, module_label in modules.items():
        module_dir = os.path.join(DATA_DIR, module_key)
        if not os.path.isdir(module_dir):
            continue

        if module_key == 'rss':
            # RSS: 按采集任务分组
            rss_tasks = _get_rss_tasks()
            task_groups = []
            all_slugs = set()

            for t in rss_tasks:
                slugs = t.get('slugs', [])
                children = []
                for slug in slugs:
                    info = _scan_source_dir('rss', slug)
                    if info and info['item_count'] > 0:
                        children.append(info)
                        all_slugs.add(slug)
                if not children:
                    continue
                total = sum(c['item_count'] for c in children)
                task_groups.append({
                    'task_id': t['task_id'],
                    'task_name': t['task_name'],
                    'source_count': len(children),
                    'total_items': total,
                    'children': children,
                })

            # 未被任务覆盖的源
            orphan_children = []
            rss_dir = os.path.join(DATA_DIR, 'rss')
            if os.path.isdir(rss_dir):
                for entry in sorted(os.listdir(rss_dir)):
                    if os.path.isdir(os.path.join(rss_dir, entry)) and entry not in all_slugs:
                        info = _scan_source_dir('rss', entry)
                        if info and info['item_count'] > 0:
                            orphan_children.append(info)
            if orphan_children:
                task_groups.append({
                    'task_id': '_other',
                    'task_name': '其他',
                    'source_count': len(orphan_children),
                    'total_items': sum(c['item_count'] for c in orphan_children),
                    'children': orphan_children,
                })

            total_items = sum(g['total_items'] for g in task_groups)
            total_sources = sum(g['source_count'] for g in task_groups)
            result[module_key] = {
                'label': module_label,
                'children': [],  # 兼容旧字段
                'source_count': total_sources,
                'total_items': total_items,
                'task_groups': task_groups,
            }
        else:
            # 非 RSS 模块：直接列出子目录
            children = _scan_module_dir(module_key, module_dir)
            children = [c for c in children if c['item_count'] > 0]
            total = sum(c['item_count'] for c in children)
            result[module_key] = {
                'label': module_label,
                'children': children,
                'source_count': len(children),
                'total_items': total,
            }

    result = standard_response(result)
    _cache_set('data-tree', result)
    return result


def _scan_module_dir(module_key, module_dir):
    """扫描非 RSS 模块的子目录"""
    children = []
    for entry in sorted(os.listdir(module_dir)):
        entry_path = os.path.join(module_dir, entry)
        if not os.path.isdir(entry_path):
            continue
        info = _scan_source_dir(module_key, entry)
        if info:
            children.append(info)
    return children


def _scan_source_dir(module, slug):
    """扫描单个数据源目录，返回 children 条目"""
    source_dir = os.path.join(DATA_DIR, module, slug)
    if not os.path.isdir(source_dir):
        return None

    json_files = sorted(
        [f for f in os.listdir(source_dir) if f.endswith('.json')],
        key=lambda f: os.path.getmtime(os.path.join(source_dir, f)),
        reverse=True,
    )

    item_count = 0
    latest_time = ''
    display_name = SOURCE_NAMES.get(slug, '')
    if json_files:
        try:
            latest_path = os.path.join(source_dir, json_files[0])
            latest_time = datetime.fromtimestamp(os.path.getmtime(latest_path)).isoformat()
            with open(latest_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                item_count = len(data.get('items', data.get('data', data.get('newsflash', []))))
                # 尝试从数据中提取 display_name
                if not display_name:
                    # RSS 数据取 source.name
                    src_info = data.get('source', {})
                    if isinstance(src_info, dict) and src_info.get('name'):
                        display_name = src_info['name']
                    else:
                        display_name = _extract_source_name(data)
            elif isinstance(data, list):
                item_count = len(data)
        except Exception:
            pass

    return {
        'name': slug,
        'display_name': display_name or slug,
        'item_count': item_count,
        'file_count': len(json_files),
        'latest_time': latest_time,
    }


# ── 渠道详情 ──────────────────────────────────────────────────

@bp.route('/data-detail', methods=['GET'])
def data_detail():
    """返回指定渠道的最新文章列表"""
    module = request.args.get('module', '')
    subdir = request.args.get('subdir', '')

    if not module or not subdir:
        return error_response(400, 'module 和 subdir 必填')

    # 安全检查：防止路径遍历
    if '..' in module or '..' in subdir or '/' in module or '/' in subdir:
        return error_response(400, '参数非法')

    cache_key = f"detail:{module}:{subdir}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    target_dir = os.path.join(DATA_DIR, module, subdir)
    if not os.path.isdir(target_dir):
        return error_response(404, '目录不存在')

    json_files = sorted(
        [f for f in os.listdir(target_dir) if f.endswith('.json')],
        key=lambda f: os.path.getmtime(os.path.join(target_dir, f)),
        reverse=True,
    )

    items = []
    if json_files:
        try:
            with open(os.path.join(target_dir, json_files[0]), 'r', encoding='utf-8') as f:
                data = json.load(f)

            raw = []
            if isinstance(data, dict):
                raw = data.get('items', data.get('data', data.get('newsflash', [])))
            elif isinstance(data, list):
                raw = data

            for item in raw[:50]:
                if not isinstance(item, dict):
                    continue
                title = item.get('title', item.get('keyword', ''))
                url = item.get('url', item.get('link', ''))
                ts = item.get('timestamp', item.get('date', item.get('publishTime', item.get('time', ''))))
                summary = item.get('summary', item.get('content', ''))
                # 无 summary 时，用额外字段拼接摘要
                if not summary:
                    parts = []
                    for k in ('stock_name', 'index_name', 'currency', 'keyword', 'source_name', 'stock_code', 'code'):
                        v = item.get(k)
                        if v:
                            label = {'stock_name': '股票', 'index_name': '指数', 'currency': '货币', 'source_name': '来源', 'stock_code': '代码', 'code': '代码'}.get(k, k.title())
                            parts.append(f'{label}: {v}')
                    for k in ('change_pct', 'price', 'buy_rate', 'sell_rate'):
                        v = item.get(k)
                        if v is not None:
                            parts.append(f'{k.replace("_", " ")}: {v}')
                    if parts:
                        summary = ' | '.join(parts)
                if isinstance(summary, str) and len(summary) > 200:
                    summary = summary[:200] + '...'
                # 清洗 GitHub 等特殊 URL
                title, url = _clean_item_url(title, url)
                items.append({'title': title, 'url': url, 'timestamp': ts, 'summary': summary})
        except Exception as e:
            logger.warning(f'Failed to read {target_dir}: {e}')

    result = standard_response({
        'module': module,
        'subdir': subdir,
        'items': items,
        'file_count': len(json_files),
    })
    _cache_set(cache_key, result)
    return result


# ── 按任务分组的报告 ──────────────────────────────────────────────

@bp.route('/reports', methods=['GET'])
def reports():
    """返回按系统报告任务分组的报告列表（从数据库查询）"""
    limit = min(int(request.args.get('limit', 10)), 50)

    # 管理员看到"其他报告"，需区分缓存
    is_admin = False
    try:
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            from app.utils.auth import decode_token
            payload = decode_token(auth[7:])
            is_admin = payload.get('role') == 'admin'
    except Exception:
        pass

    cache_key = f"reports:{limit}:{is_admin}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        from app.models.task import ScheduledTask
        from app.models.report import Report
        from app import db

        # 获取所有启用的报告任务
        report_tasks = ScheduledTask.query.filter_by(
            task_type='report', enabled=True
        ).order_by(ScheduledTask.updated_at.desc()).all()
        task_map = {t.id: t for t in report_tasks}
    except Exception as e:
        logger.warning(f"Failed to load report tasks: {e}")
        return standard_response({'groups': []})

    # 查询所有平台级报告
    all_platform_reports = Report.query.filter(
        Report.scope == 'platform',
    ).order_by(Report.generated_at.desc()).all()

    linked_task_ids = set(task_map.keys())

    # 按 task_id 分组
    task_report_map = {}
    orphan_reports = []
    for r in all_platform_reports:
        tid = r.task_id
        if tid and tid in linked_task_ids:
            if tid not in task_report_map:
                task_report_map[tid] = []
            task_report_map[tid].append(r)
        else:
            orphan_reports.append(r)

    groups = []
    for task in report_tasks:
        task_reports = task_report_map.get(task.id, [])
        if not task_reports:
            continue
        reports_data = [_report_to_plaza_item(r) for r in task_reports[:limit]]
        groups.append({
            'task_id': task.id,
            'task_name': task.name,
            'report_count': len(task_reports),
            'reports': reports_data,
        })

    # 未关联定时任务的报告（手动生成等）归入"其他报告"，仅管理员可见
    if is_admin and orphan_reports:
        reports_data = [_report_to_plaza_item(r) for r in orphan_reports[:limit]]
        groups.append({
            'task_id': '_other',
            'task_name': '其他报告',
            'report_count': len(orphan_reports),
            'reports': reports_data,
        })

    result = standard_response({'groups': groups})
    _cache_set(cache_key, result)
    return result


def _report_to_plaza_item(report):
    """将 Report ORM 对象转为前端展示用的 dict"""
    fp = report.file_path or ''
    name = os.path.splitext(os.path.basename(fp))[0] if fp else report.id
    subdir = os.path.basename(os.path.dirname(fp)) if fp else ''
    has_md = fp.endswith('.md') and os.path.isfile(fp) if fp else False
    # 如果 file_path 是 .json，检查同目录下是否有 .md
    if not has_md and fp.endswith('.json'):
        md_path = fp.replace('.json', '.md')
        has_md = os.path.isfile(md_path)

    return {
        'id': report.id,
        'title': report.title or name,
        'name': name,
        'type': report.report_type,
        'mtime': report.generated_at.isoformat() if report.generated_at else '',
        'has_md': has_md,
        'subdir': subdir,
        'summary': report.summary or '',
    }
