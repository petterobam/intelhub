#!/bin/bash
# 聚合分析 - 数据聚合 + 报告
cd "$(dirname "$0")/../.."
echo "[START] Aggregate Analysis at $(date '+%Y-%m-%d %H:%M:%S')"
python3 -c "
import sys, os, json, logging
from datetime import datetime
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', stream=sys.stdout)
sys.path.insert(0, os.getcwd())

# 聚合各模块数据统计
DATA_DIR = 'data/raw'
report = {
    'generated_at': datetime.now().isoformat(),
    'modules': {}
}

for module in ['hot_topics', 'policy', 'exchange', 'financial']:
    base = os.path.join(DATA_DIR, module)
    if not os.path.exists(base):
        report['modules'][module] = {'status': 'missing'}
        continue
    subdirs = [d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d))]
    total_files = 0
    sources = []
    for sd in subdirs:
        sd_path = os.path.join(base, sd)
        files = [f for f in os.listdir(sd_path) if f.endswith('.json')]
        total_files += len(files)
        sources.append({'name': sd, 'files': len(files)})
    report['modules'][module] = {
        'status': 'ok',
        'sources': len(subdirs),
        'total_files': total_files,
        'details': sources[:10],
    }

# 保存聚合报告
os.makedirs('data/reports/aggregate', exist_ok=True)
ts = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
path = f'data/reports/aggregate/aggregate-{ts}.json'
with open(path, 'w') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)

print(f'Aggregate report saved: {path}')
for m, d in report['modules'].items():
    if isinstance(d, dict):
        print(f'  {m}: {d.get(\"sources\",0)} sources, {d.get(\"total_files\",0)} files')
" 2>&1
echo "[DONE] Aggregate Analysis at $(date '+%Y-%m-%d %H:%M:%S')"
