#!/bin/bash
# 洞察报告生成 - 深度LLM分析
cd "$(dirname "$0")/../.."
echo "[START] Insight Report at $(date '+%Y-%m-%d %H:%M:%S')"
python3 -c "
import sys, os, logging, json
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', stream=sys.stdout)
sys.path.insert(0, os.getcwd())
from analysis.agents import InsightAgent
agent = InsightAgent()
result = agent.run()
print(json.dumps({k: v for k, v in result.items() if k != 'response'}, ensure_ascii=False, indent=2))
if result.get('response'):
    print('\\n=== 洞察报告 ===')
    print(result['response'][:3000])
" 2>&1
echo "[DONE] Insight Report at $(date '+%Y-%m-%d %H:%M:%S')"
