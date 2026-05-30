#!/bin/bash
# Policy Monitor - 10大监管机构政策采集
cd "$(dirname "$0")/../.."
echo "[START] Policy Monitor at $(date '+%Y-%m-%d %H:%M:%S')"
python3 -c "
import sys, os, logging, warnings
warnings.filterwarnings('ignore')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', stream=sys.stdout)
sys.path.insert(0, os.getcwd())
from crawlers.policy.runner import PolicyRunner
runner = PolicyRunner()
results = runner.run_all()
success = sum(1 for r in results if r.get('status') == 'success')
total = len(results)
print(f'Results: {success}/{total} agencies succeeded')
for r in results:
    print(f'  [{r.get(\"agency\",\"?\")}] {r.get(\"name\",\"?\")}: status={r.get(\"status\",\"unknown\")}, items={r.get(\"item_count\",0)}')
" 2>&1
echo "[DONE] Policy Monitor at $(date '+%Y-%m-%d %H:%M:%S')"
