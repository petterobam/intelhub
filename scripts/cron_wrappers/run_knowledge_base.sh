#!/bin/bash
# 知识库构建 - 实体抽取 + 关系建模 + 索引更新
cd "$(dirname "$0")/../.."
echo "[START] Knowledge Base Build at $(date '+%Y-%m-%d %H:%M:%S')"
python3 -c "
import sys, os, logging, json
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', stream=sys.stdout)
sys.path.insert(0, os.getcwd())
from knowledge_base.kb_manager import KnowledgeBaseManager
kb = KnowledgeBaseManager()
result = kb.ingest('all')
print(json.dumps(result, ensure_ascii=False, indent=2))
" 2>&1
echo "[DONE] Knowledge Base Build at $(date '+%Y-%m-%d %H:%M:%S')"
