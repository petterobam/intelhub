#!/bin/bash
# Hot Topics crawler - 9平台热点数据采集
cd "$(dirname "$0")/../.."
echo "[START] Hot Topics crawler at $(date '+%Y-%m-%d %H:%M:%S')"
python3 -c "
import sys, os, logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', stream=sys.stdout)
sys.path.insert(0, os.getcwd())
from crawlers.hot_topics.runner import HotTopicsRunner
runner = HotTopicsRunner()
results = runner.run_all()
success = sum(1 for r in results if r.get('status') == 'success')
total = len(results)
print(f'Results: {success}/{total} platforms succeeded')
for r in results:
    print(f'  [{r.get(\"platform\",\"?\")}] {r.get(\"name\",\"?\")}: status={r.get(\"status\",\"unknown\")}, items={r.get(\"item_count\",0)}')
" 2>&1
echo "[DONE] Hot Topics at $(date '+%Y-%m-%d %H:%M:%S')"
