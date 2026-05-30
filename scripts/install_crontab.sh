#!/usr/bin/env bash
#
# 安装 crontab 定时任务
# - 每 4 小时自动提交推送变更
# - 每天凌晨 3 点清理 30 天前的采集数据
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/.logs"
mkdir -p "$LOG_DIR"

AUTO_COMMIT="$SCRIPT_DIR/auto_commit.sh"
CLEAN_DATA="$SCRIPT_DIR/clean_data.sh"
CRON_LOG="$LOG_DIR/cron.log"

# 确保脚本可执行
chmod +x "$AUTO_COMMIT" "$CLEAN_DATA"

# 构建定时任务条目
CRON_ENTRIES="# IntelHub 定时任务
0 */4 * * * $AUTO_COMMIT >> $CRON_LOG 2>&1
0 3 * * * $CLEAN_DATA 30 >> $CRON_LOG 2>&1
# END IntelHub"

# 读取现有 crontab，去掉旧的 IntelHub 段落
EXISTING=$(crontab -l 2>/dev/null | awk '
  /^# IntelHub/,/^# END IntelHub/ { next }
  { print }
' || true)

# 合并现有任务 + 新任务
TMP=$(mktemp)
[ -n "$EXISTING" ] && echo "$EXISTING" >> "$TMP"
echo "" >> "$TMP"
echo "$CRON_ENTRIES" >> "$TMP"
crontab "$TMP"
rm -f "$TMP"

echo "已安装 crontab 定时任务:"
echo "  - 每 4 小时: 自动提交推送 ($AUTO_COMMIT)"
echo "  - 每天 03:00: 清理 30 天前数据 ($CLEAN_DATA)"
echo "  - 日志: $CRON_LOG"
echo ""
echo "当前 crontab:"
crontab -l
