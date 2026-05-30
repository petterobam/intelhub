"""task_cmd.py - 任务管理命令"""
import os, sys, json, sqlite3
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'intel_hub.db')

def task_cmd(args):
    """任务管理"""
    action = args.action

    if not os.path.exists(DB_PATH):
        print(f"Database not found: {DB_PATH}")
        return 1

    conn = sqlite3.connect(DB_PATH)

    if action == 'list':
        rows = conn.execute(
            "SELECT id, name, task_type, module, enabled, schedule_config FROM scheduled_tasks ORDER BY name"
        ).fetchall()
        print(f"\nTotal: {len(rows)} tasks")
        for rid, name, ttype, module, enabled, cfg in rows:
            cfg = json.loads(cfg or '{}')
            sched = cfg.get('cron', f"{cfg.get('interval_minutes','?')}min")
            en = 'ON' if enabled else 'OFF'
            print(f"  [{rid[:8]}] {name:20s} type={ttype:8s} mod={module:10s} {en:3s} {sched}")

    elif action == 'run':
        task_id = args.task_id
        row = conn.execute("SELECT name, script, task_type, module FROM scheduled_tasks WHERE id=?", (task_id,)).fetchone()
        if not row:
            print(f"Task not found: {task_id}")
            return 1
        name, script, ttype, module = row
        print(f">>> Running task: {name}")

        if ttype == 'script':
            from app.scheduler.executor import TaskExecutor
            from app.models.task import ScheduledTask
            task = type('Task', (), {'id': task_id, 'script': script, 'task_type': ttype, 'module': module})()
            executor = TaskExecutor(PROJECT_ROOT)
            result = executor.execute(task)
            print(f"  Status: {result.get('status')}")
            print(f"  Duration: {result.get('duration_seconds')}s")
            if result.get('stdout'):
                print(f"  Output: {result['stdout'][:300]}")
        else:
            print(f"  Use API to run analysis tasks: curl -X POST http://localhost:18923/api/v1/tasks/{task_id}/run")

    elif action == 'enable':
        conn.execute("UPDATE scheduled_tasks SET enabled=1 WHERE id=?", (args.task_id,))
        conn.commit()
        print(f"Task enabled: {args.task_id}")

    elif action == 'disable':
        conn.execute("UPDATE scheduled_tasks SET enabled=0 WHERE id=?", (args.task_id,))
        conn.commit()
        print(f"Task disabled: {args.task_id}")

    else:
        print(f"Unknown action: {action}")
        print("Available: list, run, enable, disable")
        return 1

    conn.close()
    return 0
