#!/bin/bash
# 投资分析心跳 - 多轮LLM分析
cd "$(dirname "$0")/../.."
echo "[START] Heartbeat Analysis at $(date '+%Y-%m-%d %H:%M:%S')"
python3 -c "
import sys, os, logging, json
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', stream=sys.stdout)
sys.path.insert(0, os.getcwd())
from analysis.agents import HeartbeatAgent
agent = HeartbeatAgent()
result = agent.run()
print(json.dumps({k: v for k, v in result.items() if k != 'response'}, ensure_ascii=False, indent=2))
if result.get('response'):
    print('\\n=== 分析结果 ===')
    print(result['response'][:2000])
" 2>&1
echo "[DONE] Heartbeat Analysis at $(date '+%Y-%m-%d %H:%M:%S')"
