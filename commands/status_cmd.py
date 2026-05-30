"""status_cmd.py - 查看系统状态"""
import os
import sys
import json
import sqlite3
import glob
import urllib.request
from datetime import datetime
from app.utils.helpers import bj_now

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'intel_hub.db')


def _fmt_table(headers, rows):
    cols = list(zip(*([headers] + rows)))
    widths = [max(len(str(x)) for x in col) for col in cols]
    fmt = '  '.join(f'{{:<{w}}}' for w in widths)
    return fmt.format(*headers) + '\n' + '\n'.join(fmt.format(*row) for row in rows)


def _data_freshness():
    DATA_DIR = os.path.join(PROJECT_ROOT, 'data', 'raw')
    FRESH_THRESHOLD = 120
    now_ts = bj_now().timestamp()
    rows = []
    for mod in ['hot_topics', 'policy', 'exchange', 'financial']:
        mp = os.path.join(DATA_DIR, mod)
        if not os.path.isdir(mp):
            rows.append([mod, 'missing', '-', '-'])
            continue
        newest, count = 0, 0
        for root, dirs, files in os.walk(mp):
            for f in files:
                if f.endswith('.json'):
                    count += 1
                    ft = os.path.getmtime(os.path.join(root, f))
                    if ft > newest:
                        newest = ft
        if newest == 0:
            rows.append([mod, 'empty', 0, '-'])
            continue
        age = int((now_ts - newest) / 60)
        status = 'fresh' if age < FRESH_THRESHOLD else 'normal' if age < 360 else 'stale'
        rows.append([mod, status, age, count])
    return rows


def _task_status():
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT name, task_type, enabled, schedule_config FROM scheduled_tasks ORDER BY name"
    ).fetchall()
    conn.close()
    result = []
    for name, ttype, en, cfg in rows:
        cfg = json.loads(cfg or '{}')
        sched = cfg.get('cron') or f"{cfg.get('interval_minutes', '?')}min"
        result.append([name, ttype, 'ON' if en else 'OFF', sched])
    return result


def _kb_status():
    KB_DIR = os.path.join(PROJECT_ROOT, 'knowledge_base')
    rows = []
    for name, fname in [('topics', 'topic_index.json'), ('industry', 'industry_index.json'), ('graph', 'entities.json')]:
        path = os.path.join(KB_DIR, name, fname)
        if os.path.exists(path):
            age = int((bj_now().timestamp() - os.path.getmtime(path)) / 60)
            rows.append([name, 'ok', age, os.path.getsize(path)])
        else:
            rows.append([name, 'missing', '-', '-'])
    return rows


def status_cmd(args):
    print("=" * 55)
    print(f" IntelHub Status  ({bj_now().strftime('%Y-%m-%d %H:%M:%S')})")
    print("=" * 55)

    # Tasks
    print("\n[TASKS]")
    tasks = _task_status()
    if tasks:
        print(_fmt_table(['Name', 'Type', 'En', 'Schedule'], tasks))
    else:
        print("  (no tasks)")

    # Data freshness
    print("[DATA]")
    rows = _data_freshness()
    print(_fmt_table(['Module', 'Status', 'Age(min)', 'Files'], rows))

    # KB
    print("[KNOWLEDGE BASE]")
    krows = _kb_status()
    print(_fmt_table(['Module', 'Status', 'Age(min)', 'Size'], krows))

    # Reports
    rc = len(glob.glob(os.path.join(PROJECT_ROOT, 'reports', '**', '*'), recursive=True))
    print(f"\n[REPORTS] {rc} files")

    # Backend
    try:
        req = urllib.request.urlopen('http://localhost:18923/api/v1/health', timeout=3)
        health = json.loads(req.read())
        print(f"[BACKEND] OK - {health['data']['status']} (score={health['data']['health_score']})")
    except:
        print("[BACKEND] not running")

    if args.verbose:
        print(f"\n[PATHS]")
        print(f"  project : {PROJECT_ROOT}")
        print(f"  database : {DB_PATH}")
        print(f"  data dir : {os.path.join(PROJECT_ROOT, 'data')}")

    return 0
