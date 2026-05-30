#!/bin/bash
# 迁移 hot_topics 根目录中的散落文件到正确位置
# 原则：只 mv，不删除
set -euo pipefail

HOT_DIR="$(cd "$(dirname "$0")/.." && pwd)/data/raw/hot_topics"
FINANCIAL_DIR="$(cd "$(dirname "$0")/.." && pwd)/data/raw/financial/cninfo"

echo "=== hot_topics 数据迁移 ==="
echo "源目录: $HOT_DIR"
echo ""

# -------------------------------------------------------
# 1. cninfo-* 文件 → data/raw/financial/cninfo/
# -------------------------------------------------------
cninfo_count=$(ls "$HOT_DIR"/cninfo-*.json 2>/dev/null | wc -l | tr -d ' ')
if [ "$cninfo_count" -gt 0 ]; then
    echo "[1/4] 迁移 $cninfo_count 个 cninfo 文件 → $FINANCIAL_DIR"
    mkdir -p "$FINANCIAL_DIR"
    mv "$HOT_DIR"/cninfo-*.json "$FINANCIAL_DIR/"
    echo "  完成"
else
    echo "[1/4] 无 cninfo 文件需要迁移"
fi

# -------------------------------------------------------
# 2. 旧格式 {platform}-YYYYMMDD_*.json → 对应子目录
# -------------------------------------------------------
moved=0
for f in "$HOT_DIR"/*-20[0-9][0-9][0-1][0-9][0-3][0-9]_*.json; do
    [ -f "$f" ] || continue
    basename=$(basename "$f")
    # 提取平台前缀 (weibo-20260508_xxx.json → weibo)
    platform="${basename%%-20*}"
    target_dir="$HOT_DIR/$platform"
    if [ -d "$target_dir" ]; then
        mv "$f" "$target_dir/"
        moved=$((moved + 1))
    else
        echo "  跳过 $basename (子目录 $platform 不存在)"
    fi
done
echo "[2/4] 迁移 $moved 个旧格式 {platform}-YYYYMMDD_*.json → 对应子目录"

# -------------------------------------------------------
# 3. eastmoney-{ISO timestamp}.json → eastmoney 子目录
# -------------------------------------------------------
east_moved=0
for f in "$HOT_DIR"/eastmoney-2026-*.json; do
    [ -f "$f" ] || continue
    target_dir="$HOT_DIR/eastmoney"
    if [ -d "$target_dir" ]; then
        mv "$f" "$target_dir/"
        east_moved=$((east_moved + 1))
    fi
done
echo "[3/4] 迁移 $east_moved 个 eastmoney 时间戳文件 → eastmoney/"

# -------------------------------------------------------
# 4. {platform}-latest.json → 对应子目录
# -------------------------------------------------------
latest_moved=0
for f in "$HOT_DIR"/*-latest.json; do
    [ -f "$f" ] || continue
    basename=$(basename "$f")
    platform="${basename%%-latest*}"
    target_dir="$HOT_DIR/$platform"
    if [ -d "$target_dir" ]; then
        mv "$f" "$target_dir/"
        latest_moved=$((latest_moved + 1))
    else
        echo "  跳过 $basename (子目录 $platform 不存在)"
    fi
done
echo "[4/4] 迁移 $latest_moved 个 *-latest.json → 对应子目录"

# -------------------------------------------------------
# 5. 清理空子目录
# -------------------------------------------------------
echo ""
echo "检查空子目录..."
for d in "$HOT_DIR"/*/; do
    count=$(ls "$d" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$count" -eq 0 ]; then
        echo "  空目录: $(basename "$d") — 保留（未来爬虫可能需要）"
    fi
done

# -------------------------------------------------------
# 汇总
# -------------------------------------------------------
echo ""
echo "=== 迁移完成 ==="
echo "根目录残留文件:"
remaining=$(ls "$HOT_DIR"/*.json 2>/dev/null | wc -l | tr -d ' ')
echo "  JSON 文件: $remaining"
echo "子目录:"
ls -d "$HOT_DIR"/*/ 2>/dev/null | while read d; do
    echo "  $(basename "$d"): $(ls "$d" | wc -l | tr -d ' ') 文件"
done
