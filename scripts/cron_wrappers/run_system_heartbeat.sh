#!/bin/bash
# 系统心跳 - 健康检查 + 数据新鲜度 + 服务状态
cd "$(dirname "$0")/../.."
echo "[START] System Heartbeat at $(date '+%Y-%m-%d %H:%M:%S')"
python3 << 'PYEOF'
import sys, os, logging, json
from datetime import datetime
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', stream=sys.stdout)
sys.path.insert(0, os.getcwd())

DATA_DIR = 'data/raw'
report = {'generated_at': datetime.now().isoformat(), 'checks': {}}

FRESH_THRESHOLD = 120
for module in ['hot_topics', 'policy', 'exchange', 'financial']:
    module_path = os.path.join(DATA_DIR, module)
    if not os.path.isdir(module_path):
        report['checks'][module] = {'status': 'missing'}
        continue
    newest_time = 0
    file_count = 0
    for root, dirs, files in os.walk(module_path):
        for f in files:
            if f.endswith('.json'):
                file_count += 1
                ft = os.path.getmtime(os.path.join(root, f))
                if ft > newest_time:
                    newest_time = ft
    if newest_time > 0:
        age_min = int((datetime.now().timestamp() - newest_time) / 60)
        if age_min < FRESH_THRESHOLD:
            freshness = 'fresh'
        elif age_min < 360:
            freshness = 'normal'
        else:
            freshness = 'stale'
        report['checks'][module] = {
            'status': 'ok', 'freshness': freshness,
            'age_minutes': age_min, 'files': file_count,
            'newest': datetime.fromtimestamp(newest_time).isoformat(),
        }
    else:
        report['checks'][module] = {'status': 'empty'}

import sqlite3
db_path = 'data/intel_hub.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    task_count = conn.execute('SELECT COUNT(*) FROM scheduled_tasks').fetchone()[0]
    run_count = conn.execute('SELECT COUNT(*) FROM task_runs').fetchone()[0]
    conn.close()
    report['database'] = {'status': 'ok', 'tasks': task_count, 'runs': run_count}
else:
    report['database'] = {'status': 'missing'}

os.makedirs('reports/heartbeat', exist_ok=True)
report_path = 'reports/heartbeat/system-heartbeat-latest.json'
with open(report_path, 'w') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

healthy = all(
    c.get('freshness', 'stale') != 'stale' and c.get('status') != 'missing'
    for c in report['checks'].values() if isinstance(c, dict)
)
report['overall'] = 'healthy' if healthy else 'warning'
print(f"System status: {report['overall']}")
for m, c in report['checks'].items():
    if isinstance(c, dict):
        print(f"  {m}: {c.get('freshness', c.get('status'))} ({c.get('age_minutes', '?')} min ago, {c.get('files', 0)} files)")
print(f"Database: {report['database']['status']} ({report['database'].get('tasks', 0)} tasks)")
print(f"Report saved: {report_path}")
PYEOF
echo "[DONE] System Heartbeat at $(date '+%Y-%m-%d %H:%M:%S')"
