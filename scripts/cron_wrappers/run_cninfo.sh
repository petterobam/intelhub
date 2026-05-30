#!/bin/bash
# Cninfo Financial Data - 巨潮资讯 500+股票批量采集
# 注意: 全量采集耗时较长(约1小时), 默认只采集前50只股票
# 设置环境变量 CNINFO_BATCH_SIZE=all 采集全部
cd "$(dirname "$0")/../.."
BATCH_SIZE="${CNINFO_BATCH_SIZE:-50}"
echo "[START] Cninfo Financial Data (batch=$BATCH_SIZE) at $(date '+%Y-%m-%d %H:%M:%S')"
python3 -c "
import sys, os, logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', stream=sys.stdout)
sys.path.insert(0, os.getcwd())
from crawlers.financial.runner import FinancialRunner
runner = FinancialRunner()
if '$BATCH_SIZE' == 'all':
    results = runner.run_all()
else:
    stocks = runner._load_stock_list()[:int('$BATCH_SIZE')]
    print(f'Collecting {len(stocks)} stocks (limited mode)...')
    codes = [c for c, n in stocks]
    results = runner.run_batch(codes)
    print(f'Results: {len(results)} stocks processed')
    for r in results:
        status = r.get('status', 'unknown')
        print(f'  [{r.get(\"code\",\"?\")}] {r.get(\"name\",\"?\")}: {status}')
" 2>&1
echo "[DONE] Cninfo Financial Data at $(date '+%Y-%m-%d %H:%M:%S')"
