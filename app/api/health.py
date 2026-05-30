"""健康检查 API"""
from flask import Blueprint
from app.utils.helpers import standard_response, bj_now
from datetime import datetime, timedelta
import os, json, glob

bp = Blueprint('health', __name__, url_prefix='/api/v1/health')

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MODULE_LABELS = {
    'hot_topics': '热点话题',
    'policy': '政策法规',
    'exchange': '交易所',
    'financial': '财经数据',
}

@bp.route('', methods=['GET'])
def health():
    freshness_file = os.path.join(_BASE_DIR, 'data', 'freshness', 'status.json')

    health_score = 100
    if os.path.exists(freshness_file):
        try:
            with open(freshness_file, 'r') as f:
                data = json.load(f)
                health_score = data.get('health_score', 100)
        except Exception:
            pass

    status = 'ok' if health_score >= 70 else ('degraded' if health_score >= 40 else 'critical')
    return standard_response({
        'status': status,
        'health_score': health_score,
        'timestamp': bj_now().isoformat()
    })


def _scan_module_data(module, now):
    """Scan data/raw/{module} for freshness."""
    module_path = os.path.join(_BASE_DIR, 'data', 'raw', module)
    if not os.path.isdir(module_path):
        return []
    platforms = []
    for entry in sorted(os.listdir(module_path)):
        fpath = os.path.join(module_path, entry)
        if os.path.isdir(fpath):
            newest = 0
            for root, dirs, files in os.walk(fpath):
                for f in files:
                    if f.endswith('.json'):
                        try:
                            ft = os.path.getmtime(os.path.join(root, f))
                            if ft > newest:
                                newest = ft
                        except Exception:
                            pass
            if newest > 0:
                age = int((now.timestamp() - newest) / 60)
                platforms.append({
                    'platform': entry,
                    'status': 'fresh' if age < 120 else ('stale' if age < 360 else 'critical'),
                    'age_minutes': age,
                })
            else:
                platforms.append({'platform': entry, 'status': 'missing', 'age_minutes': 9999})
        elif entry.endswith('.json'):
            try:
                ft = os.path.getmtime(fpath)
                age = int((now.timestamp() - ft) / 60)
                name = entry.replace('.json', '').replace(f'{module}-', '').replace('-crawler', '')
                platforms.append({
                    'platform': name,
                    'status': 'fresh' if age < 120 else ('stale' if age < 360 else 'critical'),
                    'age_minutes': age,
                })
            except Exception:
                pass
    return platforms


def _scan_rss_sources(now):
    """Build RSS source health from data files + DB."""
    from app import db
    from sqlalchemy import text

    platforms = []
    rss_dir = os.path.join(_BASE_DIR, 'data', 'raw', 'rss')
    if os.path.isdir(rss_dir):
        for entry in sorted(os.listdir(rss_dir)):
            fpath = os.path.join(rss_dir, entry)
            if os.path.isdir(fpath):
                newest = 0
                for root, dirs, files in os.walk(fpath):
                    for f in files:
                        if f.endswith('.json'):
                            try:
                                ft = os.path.getmtime(os.path.join(root, f))
                                if ft > newest:
                                    newest = ft
                            except Exception:
                                pass
                if newest > 0:
                    age = int((now.timestamp() - newest) / 60)
                    platforms.append({
                        'platform': entry,
                        'status': 'fresh' if age < 180 else ('stale' if age < 720 else 'critical'),
                        'age_minutes': age,
                    })
                else:
                    platforms.append({'platform': entry, 'status': 'missing', 'age_minutes': 9999})
            elif entry.endswith('.json'):
                try:
                    ft = os.path.getmtime(fpath)
                    age = int((now.timestamp() - ft) / 60)
                    name = entry.replace('.json', '')
                    platforms.append({
                        'platform': name,
                        'status': 'fresh' if age < 180 else ('stale' if age < 720 else 'critical'),
                        'age_minutes': age,
                    })
                except Exception:
                    pass

    # Also add RSS sources from DB that have no data yet
    try:
        existing = {p['platform'] for p in platforms}
        for row in db.session.execute(text(
            "SELECT name FROM rss_sources WHERE enabled = 1"
        )).fetchall():
            slug = row[0].lower().replace(' ', '-').replace('/', '-')[:40]
            if slug not in existing:
                platforms.append({'platform': slug, 'status': 'missing', 'age_minutes': 9999})
    except Exception:
        pass

    return platforms


@bp.route('/crawlers', methods=['GET'])
def crawlers_health():
    now = bj_now()

    # Build category_groups like production
    category_groups = {}
    all_platforms = []
    for module, label in MODULE_LABELS.items():
        platforms = _scan_module_data(module, now)
        if platforms:
            fresh = sum(1 for p in platforms if p['status'] == 'fresh')
            stale = sum(1 for p in platforms if p['status'] == 'stale')
            critical = sum(1 for p in platforms if p['status'] in ('critical', 'missing'))
            category_groups[module] = {
                'total': len(platforms), 'fresh': fresh, 'stale': stale, 'critical': critical,
                'platforms': platforms,
            }
            all_platforms.extend(platforms)

    # RSS category
    rss_platforms = _scan_rss_sources(now)
    if rss_platforms:
        fresh = sum(1 for p in rss_platforms if p['status'] == 'fresh')
        stale = sum(1 for p in rss_platforms if p['status'] == 'stale')
        critical = sum(1 for p in rss_platforms if p['status'] in ('critical', 'missing'))
        category_groups['rss'] = {
            'total': len(rss_platforms), 'fresh': fresh, 'stale': stale, 'critical': critical,
            'platforms': rss_platforms,
        }
        all_platforms.extend(rss_platforms)

    # Fallback: try reading freshness file if it exists
    freshness_file = os.path.join(_BASE_DIR, 'data', 'freshness', 'status.json')
    if os.path.exists(freshness_file):
        try:
            with open(freshness_file, 'r') as f:
                fdata = json.load(f)
                if fdata.get('category_groups'):
                    category_groups = fdata['category_groups']
                if fdata.get('platforms'):
                    all_platforms = fdata['platforms']
        except Exception:
            pass

    fresh_count = sum(1 for p in all_platforms if p.get('status') == 'fresh')
    critical_count = sum(1 for p in all_platforms if p.get('status') in ('critical', 'missing'))
    health_score = int((fresh_count / max(len(all_platforms), 1)) * 100)

    return standard_response({
        'platforms': all_platforms,
        'category_groups': category_groups,
        'health_score': health_score,
        'fresh_count': fresh_count,
        'critical_count': critical_count,
    })


@bp.route('/task-stats', methods=['GET'])
def task_stats():
    """24h 任务执行统计"""
    from app import db
    from sqlalchemy import text

    now = bj_now()
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

    return standard_response({
        'last_24h': h24,
    })


@bp.route('/schedulers', methods=['GET'])
def schedulers_status():
    """实时调度器监控：Worker 心跳 + 任务运行状态"""
    from app import db
    from sqlalchemy import text

    now = bj_now()
    heartbeat_stale_threshold = timedelta(seconds=90)

    # 查询所有注册的 worker
    workers_result = db.session.execute(text(
        "SELECT worker_id, role, pid, started_at, last_heartbeat, hostname "
        "FROM scheduler_workers ORDER BY role, worker_id"
    )).fetchall()

    workers = []
    for row in workers_result:
        wid, role, pid, started_at, last_hb, hostname = row
        alive = False
        if last_hb:
            if isinstance(last_hb, str):
                last_hb = datetime.fromisoformat(last_hb)
            alive = (now - last_hb) < heartbeat_stale_threshold
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at)
        workers.append({
            'worker_id': wid,
            'role': role,
            'pid': pid,
            'started_at': started_at.isoformat() if started_at else None,
            'last_heartbeat': last_hb.isoformat() if last_hb else None,
            'alive': alive,
        })

    # 查询任务实时状态
    task_status_result = db.session.execute(text(
        "SELECT trs.task_id, trs.worker_id, trs.status, trs.started_at, trs.updated_at, "
        "st.name as task_name "
        "FROM task_run_status trs "
        "LEFT JOIN scheduled_tasks st ON trs.task_id = st.id "
        "ORDER BY trs.status DESC, trs.updated_at DESC"
    )).fetchall()

    tasks = []
    for row in task_status_result:
        tid, wid, status, started_at, updated_at, task_name = row
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at)
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        tasks.append({
            'task_id': tid,
            'task_name': task_name,
            'worker_id': wid,
            'status': status,
            'started_at': started_at.isoformat() if started_at else None,
            'updated_at': updated_at.isoformat() if updated_at else None,
        })

    # 统计注册任务数
    sys_task_count = db.session.execute(text(
        "SELECT COUNT(*) FROM scheduled_tasks WHERE enabled=1 AND user_id IS NULL"
    )).scalar() or 0
    user_task_count = db.session.execute(text(
        "SELECT COUNT(*) FROM scheduled_tasks WHERE enabled=1 AND user_id IS NOT NULL"
    )).scalar() or 0
    running_count = sum(1 for t in tasks if t['status'] == 'running')
    alive_count = sum(1 for w in workers if w['alive'])

    # 每个任务的状态 + 所属 worker
    running_map = {t['task_id']: t for t in tasks}

    # 系统任务明细
    sys_tasks = db.session.execute(text(
        "SELECT id, name, task_type, schedule_type, schedule_config, enabled, "
        "last_run, next_run, run_count, fail_count "
        "FROM scheduled_tasks WHERE user_id IS NULL ORDER BY name"
    )).fetchall()
    system_task_list = []
    for r in sys_tasks:
        tid = r[0]
        rt = running_map.get(tid)
        system_task_list.append({
            'id': tid, 'name': r[1], 'task_type': r[2],
            'schedule_type': r[3], 'schedule_config': r[4],
            'enabled': bool(r[5]),
            'last_run': r[6].isoformat() if r[6] and not isinstance(r[6], str) else (r[6] or None),
            'run_count': r[8] or 0, 'fail_count': r[9] or 0,
            'running': rt['status'] == 'running' if rt else False,
        })

    # 用户任务明细
    user_tasks_list = db.session.execute(text(
        "SELECT st.id, st.name, st.task_type, st.schedule_type, st.schedule_config, st.enabled, "
        "st.last_run, st.run_count, st.fail_count, u.email "
        "FROM scheduled_tasks st LEFT JOIN users u ON st.user_id = u.id "
        "WHERE st.user_id IS NOT NULL ORDER BY u.email, st.name"
    )).fetchall()
    user_task_list = []
    for r in user_tasks_list:
        tid = r[0]
        rt = running_map.get(tid)
        user_task_list.append({
            'id': tid, 'name': r[1], 'task_type': r[2],
            'schedule_type': r[3], 'schedule_config': r[4],
            'enabled': bool(r[5]),
            'last_run': r[6].isoformat() if r[6] and not isinstance(r[6], str) else (r[6] or None),
            'run_count': r[7] or 0, 'fail_count': r[8] or 0,
            'owner': r[9] or '',
            'running': rt['status'] == 'running' if rt else False,
        })

    return standard_response({
        'workers': workers,
        'tasks': tasks,
        'system_tasks': system_task_list,
        'user_tasks': user_task_list,
        'summary': {
            'total_workers': len(workers),
            'alive_workers': alive_count,
            'system_tasks': sys_task_count,
            'user_tasks': user_task_count,
            'total_tasks': sys_task_count + user_task_count,
            'running_tasks': running_count,
        },
        'timestamp': now.isoformat(),
    })
