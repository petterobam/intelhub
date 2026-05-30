#!/usr/bin/env bash
#
# 自动提交并推送仓库变更
# 由 crontab 定时调用，每 4 小时执行一次
#
# 冲突策略：
#   本地 → 源码权威，pull --rebase 后推送，冲突时以本地为准
#   远程 → 数据权威（采集数据），pull --rebase 后推送，冲突时以远程为准
#   两边都只提交各自关心的文件，减少冲突面
#
set -euo pipefail

cd "$(dirname "$0")/.."
LOG_FILE=".logs/auto_commit.log"

# ── 判断本地还是远程 ──────────────────────────────────────────
if [ "$(pwd)" = "/root/intel-hub" ]; then
  MODE="remote"
else
  MODE="local"
fi

log() { mkdir -p "$(dirname "$LOG_FILE")" && echo "[$(date '+%Y-%m-%d %H:%M')] [$MODE] $*" >> "$LOG_FILE"; }

# ── 数据备份函数 ──────────────────────────────────────────────

_backup_data() {
  local SOURCE_DIR="$(pwd)"
  BACKUP_DIR="$(dirname "$SOURCE_DIR")/intel-hub-data-backup"
  BACKUP_REPO="git@github.com:petterobam/intel-hub-data-backup.git"

  # 首次克隆
  if [ ! -d "$BACKUP_DIR/.git" ]; then
    log "Cloning backup repo..."
    git clone "$BACKUP_REPO" "$BACKUP_DIR" 2>&1 || {
      log "Failed to clone backup repo"
      return 1
    }
  fi

  cd "$BACKUP_DIR"

  # 确保 git user config 存在（避免 commit 失败）
  git config user.email 2>/dev/null | grep -q . || git config user.email "intelhub@server"
  git config user.name 2>/dev/null | grep -q . || git config user.name "IntelHub Server"

  # 确保在 main 分支（处理空仓库默认 master 的情况）
  local current_branch
  current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
  if [ "$current_branch" != "main" ]; then
    if git show-ref --verify --quiet refs/heads/main 2>/dev/null; then
      git checkout main 2>/dev/null
    else
      git checkout -b main 2>/dev/null
    fi
  fi

  # 拉取最新
  git pull --rebase origin main 2>/dev/null || true

  # rsync 同步 data/（排除 rss 大文件）和 reports/
  rsync -a --delete \
    --exclude='raw/rss/' \
    --exclude='users/uploads/' \
    --exclude='logs/' \
    "$SOURCE_DIR/data/" \
    ./data/ 2>/dev/null || true

  rsync -a --delete \
    "$SOURCE_DIR/reports/" \
    ./reports/ 2>/dev/null || true

  # 检查变更
  if git diff --quiet && [ -z "$(git ls-files --others --exclude-standard 2>/dev/null)" ]; then
    cd "$SOURCE_DIR"
    return 0
  fi

  # 提交推送
  git add -A
  MSG="backup: $(date '+%Y-%m-%d %H:%M')"
  git commit -m "$MSG" --no-verify 2>/dev/null || true

  if git push origin main 2>&1; then
    log "data backup pushed OK"
  else
    log "data backup push failed"
  fi

  cd "$SOURCE_DIR"
}

# ── 暂存各自关心的文件 ────────────────────────────────────────
if [ "$MODE" = "local" ]; then
  git add \
    app/ crawlers/ analysis/ knowledge_base/ commands/ scripts/ \
    frontend/ *.py requirements.txt .gitignore \
    2>/dev/null || true
else
  git add -u knowledge_base/ 2>/dev/null || true
fi

git reset HEAD -- .env .env.local '*.log' .playwright-mcp/ 2>/dev/null || true

# 无变更则跳过
if git diff --cached --quiet; then
  # 即使主仓库无变更，远程仍然需要备份数据
  if [ "$MODE" = "remote" ]; then
    _backup_data
  fi
  exit 0
fi

# 提交
MSG="chore: ${MODE} 自动提交 $(date '+%Y-%m-%d %H:%M')"
git commit -m "$MSG" --no-verify || exit 0

# ── 拉取远端 + rebase，处理冲突 ────────────────────────────────
if ! git pull --rebase origin main 2>/dev/null; then
  if [ "$MODE" = "local" ]; then
    git diff --name-only --diff-filter=U 2>/dev/null | while read -r f; do
      git checkout --ours "$f" 2>/dev/null
      git add "$f" 2>/dev/null
    done
    git rebase --continue 2>/dev/null || git rebase --skip 2>/dev/null || {
      git rebase --abort 2>/dev/null
      log "rebase conflict abort, force push skipped"
      exit 1
    }
    log "resolved conflicts with local (ours)"
  else
    git rebase --abort 2>/dev/null
    log "rebase conflict, reset to remote (data from remote wins)"
    git fetch origin main 2>/dev/null
    git reset --soft origin/main 2>/dev/null
    exit 0
  fi
fi

# 推送
if git push origin main 2>/dev/null; then
  log "pushed OK"
else
  log "push failed"
fi

# ── 远程：备份 data/ 和 reports/ 到独立仓库 ────────────────────
if [ "$MODE" = "remote" ]; then
  _backup_data
fi
