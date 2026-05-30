#!/usr/bin/env bash
#
# 清理 N 天前的采集数据（保留 -latest.json 和最近 N 天的文件）
# 由 crontab 定时调用，每天执行一次
#
# Usage: ./clean_data.sh [保留天数，默认 30]
#
set -euo pipefail

KEEP_DAYS="${1:-30}"
DATA_DIR="$(dirname "$0")/../data/raw"
FIND_CMD="find"

if [ "$(uname)" = "Darwin" ]; then
  FIND_CMD="gfind"
  if ! command -v "$FIND_CMD" &>/dev/null; then
    FIND_CMD="find"
  fi
fi

count=0

# 清理 data/raw/ 下所有子目录中超过 KEEP_DAYS 的 .json 文件
# 保留 *-latest.json 文件（用于 API 读取）
while IFS= read -r -d '' dir; do
  deleted=$($FIND_CMD "$dir" -maxdepth 1 -name '*.json' ! -name '*-latest.json' -mtime +${KEEP_DAYS} -delete -print 2>/dev/null | wc -l)
  count=$((count + deleted))
done < <($FIND_CMD "$DATA_DIR" -mindepth 1 -type d -print0 2>/dev/null)

if [ "$count" -gt 0 ]; then
  echo "[clean_data] $(date '+%Y-%m-%d %H:%M') deleted $count files older than ${KEEP_DAYS} days"
fi
