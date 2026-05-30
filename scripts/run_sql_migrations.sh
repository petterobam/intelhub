#!/usr/bin/env bash
# SQL 迁移执行器
# 扫描 sql/todo/ 下的 .sql 文件，逐个在 intel_hub.db 上执行
# 成功 → sql/done/，失败 → sql/fail/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DB="$PROJECT_DIR/data/intel_hub.db"
TODO="$PROJECT_DIR/sql/todo"
DONE="$PROJECT_DIR/sql/done"
FAIL="$PROJECT_DIR/sql/fail"

if [ ! -f "$DB" ]; then
  echo "[ERROR] Database not found: $DB"
  exit 1
fi

mkdir -p "$DONE" "$FAIL"

count=0
failed=0

for sql_file in "$TODO"/*.sql; do
  [ -f "$sql_file" ] || continue
  name=$(basename "$sql_file")
  echo -n "  [$name] ... "

  if sqlite3 "$DB" < "$sql_file" 2>&1; then
    mv "$sql_file" "$DONE/$name"
    echo "OK"
    count=$((count + 1))
  else
    mv "$sql_file" "$FAIL/$name"
    echo "FAILED"
    failed=$((failed + 1))
  fi
done

if [ "$count" -eq 0 ] && [ "$failed" -eq 0 ]; then
  echo "  No pending SQL migrations."
else
  echo "  Migrations: $count done, $failed failed"
fi

[ "$failed" -eq 0 ]
