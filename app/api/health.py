"""健康检查 API"""
from flask import Blueprint
from app.utils.helpers import standard_response, bj_now
from datetime import datetime, timedelta
import os, json

bp = Blueprint('health', __name__, url_prefix='/api/v1/health')

@bp.route('', methods=['GET'])
def health():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    freshness_file = os.path.join(base_dir, 'data', 'freshness', 'status.json')

    health_score = 100
    if os.path.exists(freshness_file):
        try:
            with open(freshness_file, 'r') as f:
                data = json.load(f)
                health_score = data.get('health_score', 100)
        except:
            pass

    status = 'ok' if health_score >= 70 else ('degraded' if health_score >= 40 else 'critical')
    return standard_response({
        'status': status,
        'health_score': health_score,
        'timestamp': bj_now().isoformat()
    })

@bp.route('/crawlers', methods=['GET'])
def crawlers_health():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    freshness_file = os.path.join(base_dir, 'data', 'freshness', 'status.json')
    if os.path.exists(freshness_file):
        with open(freshness_file, 'r') as f:
            return standard_response(json.load(f))
    return standard_response({'platforms': [], 'health_score': 100})


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
