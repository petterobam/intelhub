"""Admin Dashboard API — system stats + push stats (open-source version)"""
from flask import Blueprint, request
from app.utils.helpers import standard_response, bj_now
from app.utils.auth import admin_required
from app import db
from sqlalchemy import text
from datetime import datetime, timedelta
import os, json

bp = Blueprint('admin', __name__, url_prefix='/api/v1/admin')

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception:
        return None


@bp.route('/dashboard', methods=['GET'])
@admin_required
def dashboard():
    now = bj_now()
    today_str = now.strftime('%Y-%m-%d')

    tasks_enabled = db.session.execute(text(
        "SELECT COUNT(*) FROM scheduled_tasks WHERE enabled = 1"
    )).scalar() or 0

    running_row = db.session.execute(text(
        "SELECT COUNT(*) FROM task_run_status WHERE status = 'running'"
    )).scalar() or 0

    reports_today = db.session.execute(text(
        "SELECT COUNT(*) FROM reports WHERE date(generated_at) = :today"
    ), {'today': today_str}).scalar() or 0

    rss_sources = db.session.execute(text(
        "SELECT COUNT(*) FROM rss_sources WHERE enabled = 1"
    )).scalar() or 0

    data_items_today = 0
    try:
        raw_dir = os.path.join(_BASE_DIR, 'data', 'raw')
        if os.path.exists(raw_dir):
            import glob
            for f in glob.glob(os.path.join(raw_dir, '**', '*.json'), recursive=True):
                try:
                    mtime = os.path.getmtime(f)
                    if mtime >= (now - timedelta(hours=24)).timestamp():
                        with open(f, 'r') as fp:
                            content = json.load(fp)
                            if isinstance(content, list):
                                data_items_today += len(content)
                            elif isinstance(content, dict):
                                for v in content.values():
                                    if isinstance(v, list):
                                        data_items_today += len(v)
                except Exception:
                    pass
    except Exception:
        pass

    recent_runs = []
    for row in db.session.execute(text(
        "SELECT tr.id, st.name, tr.status, tr.started_at, tr.duration_ms, tr.trigger_type "
        "FROM task_runs tr LEFT JOIN scheduled_tasks st ON tr.task_id = st.id "
        "ORDER BY tr.started_at DESC LIMIT 20"
    )).fetchall():
        recent_runs.append({
            'id': row[0],
            'task_name': row[1] or '未知',
            'status': row[2],
            'started_at': row[3].isoformat() if row[3] and not isinstance(row[3], str) else row[3],
            'duration_ms': row[4],
            'trigger_type': row[5],
        })

    yesterday = (now - timedelta(hours=24)).isoformat()
    h24 = {'total': 0, 'done': 0, 'failed': 0, 'timeout': 0, 'avg_duration_ms': 0}
    for row in db.session.execute(text(
        "SELECT status, COUNT(*), AVG(duration_ms) "
        "FROM task_runs WHERE started_at >= :y GROUP BY status"
    ), {'y': yesterday}).fetchall():
        h24['total'] += row[1]
        if row[0] == 'done':
            h24['done'] = row[1]
            h24['avg_duration_ms'] = int(row[2] or 0)
        elif row[0] == 'failed':
            h24['failed'] = row[1]
        elif row[0] == 'timeout':
            h24['timeout'] = row[1]

    last_failures = []
    for row in db.session.execute(text(
        "SELECT st.name, tr.started_at, tr.stderr "
        "FROM task_runs tr LEFT JOIN scheduled_tasks st ON tr.task_id = st.id "
        "WHERE tr.status IN ('failed', 'error') "
        "ORDER BY tr.started_at DESC LIMIT 5"
    )).fetchall():
        last_failures.append({
            'task_name': row[0] or '未知',
            'started_at': row[1].isoformat() if row[1] and not isinstance(row[1], str) else row[1],
            'error': (row[2] or '')[:200],
        })

    workers_alive = 0
    workers_total = 0
    try:
        stale = timedelta(seconds=90)
        for row in db.session.execute(text(
            "SELECT last_heartbeat FROM scheduler_workers"
        )).fetchall():
            workers_total += 1
            hb = row[0]
            if hb:
                if isinstance(hb, str):
                    hb = datetime.fromisoformat(hb)
                if (now - hb) < stale:
                    workers_alive += 1
    except Exception:
        pass

    freshness_file = os.path.join(_BASE_DIR, 'data', 'freshness', 'status.json')
    freshness_data = _read_json(freshness_file) or {}
    health_score = freshness_data.get('health_score', 100)
    platforms_raw = freshness_data.get('platforms', [])
    alerts = freshness_data.get('alerts', [])
    platforms_fresh = sum(1 for p in platforms_raw if p.get('status') == 'fresh')
    platforms_stale = sum(1 for p in platforms_raw if p.get('status') == 'stale')
    platforms_critical = sum(1 for p in platforms_raw if p.get('status') in ('error', 'critical'))

    resonance_file = os.path.join(_BASE_DIR, 'reports', 'insight', 'cross-platform-resonance.json')
    resonance_data = _read_json(resonance_file) or {}
    hotspots = resonance_data.get('all_hotspots', [])[:8]

    events = []
    for row in db.session.execute(text(
        "SELECT title, report_type, generated_at FROM reports "
        "ORDER BY generated_at DESC LIMIT 5"
    )).fetchall():
        events.append({
            'type': 'report',
            'desc': row[0] or '报告生成',
            'time': row[2].isoformat() if row[2] and not isinstance(row[2], str) else (row[2] or ''),
        })
    for r in recent_runs[:5]:
        if r['status'] == 'done':
            events.append({
                'type': 'task_done',
                'desc': f'{r["task_name"]} 执行完成',
                'time': r['started_at'] or '',
            })
    events.sort(key=lambda e: e.get('time', ''), reverse=True)
    activity_feed = events[:15]

    return standard_response({
        'top_stats': {
            'tasks_total': tasks_enabled,
            'tasks_running': running_row,
            'reports_today': reports_today,
            'rss_sources': rss_sources,
            'data_items_24h': data_items_today,
        },
        'system_health': {
            'health_score': health_score,
            'status': 'ok' if health_score >= 70 else ('degraded' if health_score >= 40 else 'critical'),
            'workers_total': workers_total,
            'workers_alive': workers_alive,
            'platforms_total': len(platforms_raw),
            'platforms_fresh': platforms_fresh,
            'platforms_stale': platforms_stale,
            'platforms_critical': platforms_critical,
            'platforms': platforms_raw[:12],
            'alerts': alerts[:5],
        },
        'task_exec': {
            'recent_runs': recent_runs,
            'last_24h': h24,
            'last_failures': last_failures,
        },
        'activity_feed': activity_feed,
        'hotspots': hotspots,
    })


@bp.route('/push-stats', methods=['GET'])
@admin_required
def push_stats():
    now = bj_now()
    today_str = now.strftime('%Y-%m-%d')
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    def _stats(start_filter=''):
        q = f"SELECT status, COUNT(*) FROM push_logs {start_filter} GROUP BY status"
        rows = db.session.execute(text(q)).fetchall()
        total = sent = failed = 0
        for r in rows:
            total += r[1]
            if r[0] == 'sent':
                sent = r[1]
            else:
                failed += r[1]
        return {'total': total, 'sent': sent, 'failed': failed}

    today = _stats(f"WHERE date(created_at) = '{today_str}'")
    month = _stats(f"WHERE created_at >= '{month_start.isoformat()}'")
    all_time = _stats()

    channel_dist = {}
    for row in db.session.execute(text(
        "SELECT channel_type, status, COUNT(*) FROM push_logs "
        "WHERE created_at >= :m GROUP BY channel_type, status"
    ), {'m': month_start.isoformat()}).fetchall():
        ct = row[0]
        if ct not in channel_dist:
            channel_dist[ct] = {'total': 0, 'sent': 0, 'failed': 0}
        channel_dist[ct]['total'] += row[2]
        if row[1] == 'sent':
            channel_dist[ct]['sent'] += row[2]
        else:
            channel_dist[ct]['failed'] += row[2]

    seven_days_ago = (now - timedelta(days=6)).strftime('%Y-%m-%d')
    trend_rows = db.session.execute(text(
        "SELECT date(created_at) as d, status, COUNT(*) "
        "FROM push_logs WHERE date(created_at) >= :start "
        "GROUP BY date(created_at), status ORDER BY d"
    ), {'start': seven_days_ago}).fetchall()
    trend_map = {}
    for r in trend_rows:
        d = r[0]
        if d not in trend_map:
            trend_map[d] = {'total': 0, 'sent': 0, 'failed': 0}
        trend_map[d]['total'] += r[2]
        if r[1] == 'sent':
            trend_map[d]['sent'] += r[2]
        else:
            trend_map[d]['failed'] += r[2]
    daily_trend = []
    for i in range(6, -1, -1):
        d = (now - timedelta(days=i)).strftime('%Y-%m-%d')
        v = trend_map.get(d, {'total': 0, 'sent': 0, 'failed': 0})
        daily_trend.append({'date': d, **v})

    return standard_response({
        'today': today,
        'month': month,
        'total': all_time['total'],
        'channel_dist': channel_dist,
        'daily_trend_7d': daily_trend,
    })


@bp.route('/push-logs', methods=['GET'])
@admin_required
def push_logs():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    status_filter = request.args.get('status', '')
    channel_type_filter = request.args.get('channel_type', '')

    query = "SELECT id, report_path, channel_type, channel_key, user_id, status, error, created_at FROM push_logs"
    conditions = []
    params = {}
    if status_filter:
        conditions.append("status = :status")
        params['status'] = status_filter
    if channel_type_filter:
        conditions.append("channel_type = :ct")
        params['ct'] = channel_type_filter
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    total = db.session.execute(text(
        f"SELECT COUNT(*) FROM push_logs"
        + (" WHERE " + " AND ".join(conditions) if conditions else "")
    ), params).scalar() or 0

    query += " ORDER BY created_at DESC LIMIT :lim OFFSET :off"
    params['lim'] = per_page
    params['off'] = (page - 1) * per_page

    rows = db.session.execute(text(query), params).fetchall()

    items = []
    for r in rows:
        path = r[1] or ''
        report_name = path.split('/')[-1] if '/' in path else path
        if report_name.endswith('.md'):
            report_name = report_name[:-3]
        if report_name.endswith('.json'):
            report_name = report_name[:-5]

        items.append({
            'id': r[0],
            'report_name': report_name,
            'report_path': path,
            'channel_type': r[2],
            'channel_key': r[3],
            'user_email': r[3] if r[3] and '@' in r[3] else '',
            'user_nickname': '',
            'status': r[5],
            'error': r[6],
            'created_at': r[7].isoformat() if r[7] and not isinstance(r[7], str) else (r[7] or ''),
        })

    return standard_response({
        'items': items,
        'total': total,
        'page': page,
        'per_page': per_page,
    })
