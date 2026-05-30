"""数据 API - 数据预览 + 目录树"""
from flask import Blueprint, request
from app.utils.helpers import standard_response, error_response
import os, json, glob
from datetime import datetime
from collections import defaultdict

bp = Blueprint('data', __name__, url_prefix='/api/v1/data')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, 'data')
REPORTS_DIR = os.path.join(BASE_DIR, 'reports')


def _safe_path(rel_path):
    """将相对路径转为安全绝对路径，防止路径穿越。支持 data/ 开头或不含 data/ 的路径。"""
    # 去掉开头的 data/ 前缀（因为 DATA_DIR 已经是 .../data）
    clean = rel_path
    if clean.startswith('data/') or clean.startswith('data\\'):
        clean = clean[5:]
    full = os.path.normpath(os.path.join(DATA_DIR, clean))
    if not full.startswith(DATA_DIR):
        return None
    return full


@bp.route('/tree', methods=['GET'])
def data_tree():
    """返回 data/ 目录的一级子节点，按天聚合文件"""
    rel_path = request.args.get('path', '')
    dir_path = _safe_path(rel_path) if rel_path else DATA_DIR
    if not dir_path:
        return error_response('Access denied'), 403

    rel_prefix = rel_path
    if rel_prefix.startswith('data/'):
        rel_prefix = rel_prefix[5:]
    rel_prefix = rel_prefix.rstrip('/')

    children = _list_dir(dir_path, rel_prefix)
    return standard_response({'children': children})


def _list_dir(dir_path, rel_prefix='', path_prefix='data/'):
    """列出一个目录的直接子项，文件按天聚合"""
    children = []
    if not os.path.isdir(dir_path):
        return children

    entries = sorted(os.listdir(dir_path))
    dirs = []
    files_by_date = defaultdict(list)
    import re

    for entry in entries:
        if entry.startswith('.'):
            continue
        full = os.path.join(dir_path, entry)
        if not os.path.exists(full):
            continue
        rel = os.path.join(rel_prefix, entry) if rel_prefix else entry
        if os.path.isdir(full):
            try:
                child_count = sum(1 for e in os.listdir(full) if not e.startswith('.'))
            except OSError:
                continue
            dirs.append({
                'name': entry,
                'path': path_prefix + rel + '/',
                'type': 'dir',
                'child_count': child_count,
            })
        else:
            m = re.search(r'(\d{4})(\d{2})(\d{2})_', entry)
            if m:
                date_key = '{}-{}-{}'.format(m.group(1), m.group(2), m.group(3))
            else:
                date_key = 'other'
            file_path = path_prefix + rel
            files_by_date[date_key].append({
                'name': entry,
                'path': file_path,
                'size': os.path.getsize(full),
                'modified': datetime.fromtimestamp(os.path.getmtime(full)).isoformat(),
                'type': 'file',
            })

    children.extend(dirs)

    for date_key in sorted(files_by_date.keys(), reverse=True):
        files = files_by_date[date_key]
        if date_key == 'other':
            for f in files:
                f['type'] = 'file'
                children.append(f)
        else:
            children.append({
                'name': date_key,
                'type': 'date_group',
                'count': len(files),
                'children': files,
            })

    return children


@bp.route('/preview', methods=['GET'])
def data_preview():
    """安全预览 data/ 下的文件内容"""
    rel_path = request.args.get('path', '')
    if not rel_path:
        return standard_response({'error': 'path is required'}), 400

    full_path = _safe_path(rel_path)
    if not full_path:
        return standard_response({'error': 'Access denied'}), 403
    if not os.path.exists(full_path):
        return standard_response({'error': 'File not found: {}'.format(rel_path)}), 404
    if not os.path.isfile(full_path):
        return standard_response({'error': 'Path is not a file'}), 400

    # 文件大小限制 (2MB)
    size = os.path.getsize(full_path)

    # DB 文件：返回元数据，不读内容
    if full_path.endswith('.db') or full_path.endswith('.sqlite') or full_path.endswith('.sqlite3'):
        return standard_response({
            'filename': os.path.basename(full_path),
            'path': rel_path,
            'size': size,
            'modified': datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat(),
            'is_db': True,
        })

    if size > 2 * 1024 * 1024:
        return standard_response({'error': 'File too large (max 2MB)'}), 413

    try:
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read(50000)  # 最多读 50KB

        # 尝试解析 JSON
        is_json = False
        parsed = None
        try:
            parsed = json.loads(content)
            is_json = True
        except Exception:
            parsed = None

        resp = {
            'filename': os.path.basename(full_path),
            'path': rel_path,
            'size': size,
            'modified': datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat(),
            'is_json': is_json,
            'content': content,
            'parsed': parsed,
        }
        return standard_response(resp)
    except Exception as e:
        return standard_response({'error': str(e)}), 500


# --- 原有 API 保持兼容 ---

@bp.route('/latest', methods=['GET'])
def latest_data():
    agg_file = os.path.join(DATA_DIR, 'processed', 'all-platforms-aggregated.json')
    if os.path.exists(agg_file):
        with open(agg_file, 'r', encoding='utf-8') as f:
            return standard_response(json.load(f))
    return standard_response({'items': [], 'meta': {'total': 0}})


@bp.route('/freshness', methods=['GET'])
def freshness():
    freshness_file = os.path.join(DATA_DIR, 'freshness', 'status.json')
    if os.path.exists(freshness_file):
        with open(freshness_file, 'r', encoding='utf-8') as f:
            return standard_response(json.load(f))
    return standard_response({'timestamp': bj_now().isoformat(), 'platforms': [], 'health_score': 100})


@bp.route('/trends', methods=['GET'])
def trends():
    trend_file = os.path.join(BASE_DIR, 'reports', 'insight', 'trend-analysis.json')
    if os.path.exists(trend_file):
        with open(trend_file, 'r', encoding='utf-8') as f:
            return standard_response(json.load(f))
    return standard_response({'generated_at': bj_now().isoformat(), 'top_keywords': [], 'topic_distribution': {}})


@bp.route('/resonance', methods=['GET'])
def resonance():
    res_file = os.path.join(BASE_DIR, 'reports', 'insight', 'cross-platform-resonance.json')
    if os.path.exists(res_file):
        with open(res_file, 'r', encoding='utf-8') as f:
            return standard_response(json.load(f))
    return standard_response({'generated_at': bj_now().isoformat(), 'all_hotspots': []})


# ── 报告文件浏览器 ──────────────────────────────────────────────


def _safe_report_path(rel_path):
    """将相对路径转为安全绝对路径，防止路径穿越"""
    clean = rel_path
    if clean.startswith('reports/') or clean.startswith('reports\\'):
        clean = clean[8:]
    full = os.path.normpath(os.path.join(REPORTS_DIR, clean))
    if not full.startswith(REPORTS_DIR):
        return None
    return full


@bp.route('/report-tree', methods=['GET'])
def report_tree():
    """返回 reports/ 目录的子节点，按天聚合文件"""
    rel_path = request.args.get('path', '')
    dir_path = _safe_report_path(rel_path) if rel_path else REPORTS_DIR
    if not dir_path or not os.path.isdir(dir_path):
        return standard_response({'children': []})

    rel_prefix = rel_path
    if rel_prefix.startswith('reports/'):
        rel_prefix = rel_prefix[8:]
    rel_prefix = rel_prefix.rstrip('/')

    children = _list_dir(dir_path, rel_prefix, path_prefix='reports/')
    return standard_response({'children': children})


@bp.route('/report-preview', methods=['GET'])
def report_preview():
    """预览 reports/ 下的文件内容"""
    rel_path = request.args.get('path', '')
    if not rel_path:
        return standard_response({'error': 'path is required'}), 400

    full_path = _safe_report_path(rel_path)
    if not full_path:
        return standard_response({'error': 'Access denied'}), 403
    if not os.path.exists(full_path):
        return standard_response({'error': 'File not found'}), 404
    if not os.path.isfile(full_path):
        return standard_response({'error': 'Path is not a file'}), 400

    size = os.path.getsize(full_path)

    if full_path.endswith('.db') or full_path.endswith('.sqlite') or full_path.endswith('.sqlite3'):
        return standard_response({
            'filename': os.path.basename(full_path),
            'path': rel_path,
            'size': size,
            'modified': datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat(),
            'is_db': True,
        })

    if size > 2 * 1024 * 1024:
        return standard_response({'error': 'File too large (max 2MB)'}), 413

    try:
        with open(full_path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read(50000)

        is_json = False
        parsed = None
        try:
            parsed = json.loads(content)
            is_json = True
        except Exception:
            parsed = None

        return standard_response({
            'filename': os.path.basename(full_path),
            'path': rel_path,
            'size': size,
            'modified': datetime.fromtimestamp(os.path.getmtime(full_path)).isoformat(),
            'is_json': is_json,
            'is_markdown': rel_path.endswith('.md'),
            'content': content,
            'parsed': parsed,
        })
    except Exception as e:
        return standard_response({'error': str(e)}), 500


# ── DB 控制台 ──────────────────────────────────────────────────

import sqlite3

FORBIDDEN_KEYWORDS = ('INSERT', 'UPDATE', 'DELETE', 'DROP', 'ALTER', 'CREATE', 'ATTACH', 'DETACH', 'REPLACE', 'PRAGMA')


def _resolve_db_path(rel_path):
    """解析 .db 文件路径，支持 data/ 和 reports/ 前缀"""
    if rel_path.startswith('reports/'):
        full = _safe_report_path(rel_path)
    else:
        full = _safe_path(rel_path)
    if not full or not os.path.isfile(full):
        return None
    if not full.endswith(('.db', '.sqlite', '.sqlite3')):
        return None
    return full


@bp.route('/db-tables', methods=['GET'])
def db_tables():
    """列出 SQLite 数据库的所有表及行数"""
    rel_path = request.args.get('path', '')
    full_path = _resolve_db_path(rel_path)
    if not full_path:
        return standard_response({'error': 'DB file not found'}), 404

    try:
        conn = sqlite3.connect(f'file:{full_path}?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
        tables = []
        for row in cur.fetchall():
            name = row[0]
            try:
                cnt_cur = conn.cursor()
                cnt_cur.execute(f'SELECT COUNT(*) FROM "{name}"')
                row_count = cnt_cur.fetchone()[0]
            except Exception:
                row_count = -1
            tables.append({'name': name, 'row_count': row_count})
        conn.close()
        return standard_response({'tables': tables})
    except Exception as e:
        return standard_response({'error': str(e)}), 500


@bp.route('/db-query', methods=['POST'])
def db_query():
    """执行只读 SQL 查询"""
    data = request.get_json(silent=True) or {}
    rel_path = data.get('path', '')
    sql = (data.get('sql') or '').strip()

    if not rel_path or not sql:
        return standard_response({'error': 'path and sql required'}), 400

    sql_upper = sql.upper().split()
    if not sql_upper or sql_upper[0] != 'SELECT':
        return standard_response({'error': '只允许 SELECT 查询'}), 400
    for kw in FORBIDDEN_KEYWORDS:
        if kw in sql_upper:
            return standard_response({'error': f'不允许的 SQL 关键字: {kw}'}), 400

    full_path = _resolve_db_path(rel_path)
    if not full_path:
        return standard_response({'error': 'DB file not found'}), 404

    MAX_ROWS = 500
    try:
        conn = sqlite3.connect(f'file:{full_path}?mode=ro', uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = []
        truncated = False
        for i, row in enumerate(cur):
            if i >= MAX_ROWS:
                truncated = True
                break
            rows.append([None if v is None else str(v) for v in row])
        conn.close()
        return standard_response({
            'columns': columns,
            'rows': rows,
            'row_count': len(rows),
            'truncated': truncated,
        })
    except Exception as e:
        return standard_response({'error': str(e)}), 500
