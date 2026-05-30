#!/bin/bash
# Exchange Announcements - 4大交易所公告采集
cd "$(dirname "$0")/../.."
echo "[START] Exchange Announcements at $(date '+%Y-%m-%d %H:%M:%S')"
python3 -c "
import sys, os, logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', stream=sys.stdout)
sys.path.insert(0, os.getcwd())
from crawlers.exchange.runner import ExchangeRunner
runner = ExchangeRunner()
results = runner.run_all()
success = sum(1 for r in results if r.get('status') == 'success')
total = len(results)
print(f'Results: {success}/{total} exchanges succeeded')
for r in results:
    print(f'  [{r.get(\"exchange\",\"?\")}] {r.get(\"name\",\"?\")}: status={r.get(\"status\",\"unknown\")}, items={r.get(\"item_count\",0)}')
" 2>&1
echo "[DONE] Exchange Announcements at $(date '+%Y-%m-%d %H:%M:%S')"
