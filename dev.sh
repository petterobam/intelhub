#!/usr/bin/env bash
#
# IntelHub 一键启动脚本
# 同时启动后端 (Flask :18923) 和前端 (Vite :18432)
# Ctrl+C 同时关闭所有服务
#
# Usage:
#   ./dev.sh          启动开发环境
#   ./dev.sh stop     停止运行中的服务
#   ./dev.sh status   查看服务状态
#   ./dev.sh restart  重启

# 获取所有本地 IP 地址
get_all_ips() {
    local ips=""
    # 方法1: ifconfig (macOS/Linux)
    if command -v ifconfig &>/dev/null; then
        ips=$(ifconfig 2>/dev/null | grep 'inet ' | awk '{print $2}' | grep -v '^127\.')
    fi
    # 方法2: ip addr (Linux)
    if [ -z "$ips" ] && command -v ip &>/dev/null; then
        ips=$(ip addr show 2>/dev/null | grep 'inet ' | awk '{print $2}' | cut -d/ -f1 | grep -v '^127\.')
    fi
    # 方法3: hostname
    if [ -z "$ips" ]; then
        local hn=$(hostname 2>/dev/null || echo "localhost")
        ips=$(getent hosts "$hn" 2>/dev/null | awk '{print $1}' || echo "")
    fi
    # 兜底 localhost
    if [ -z "$ips" ]; then
        ips="127.0.0.1"
    fi
    echo "$ips"
}
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_PORT=18923
FRONTEND_PORT=18432
PID_DIR="$ROOT_DIR/.pids"
LOG_DIR="$ROOT_DIR/.logs"

# 颜色
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()  { echo -e "${CYAN}[IntelHub]${NC} $*"; }
ok()   { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# 通过端口杀进程（递进式：SIGTERM -> SIGKILL）
kill_by_port() {
    local port=$1 pids
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    [ -z "$pids" ] && return
    for p in $pids; do kill "$p" 2>/dev/null; done
    sleep 1
    pids=$(lsof -ti :"$port" 2>/dev/null || true)
    [ -z "$pids" ] && return
    for p in $pids; do kill -9 "$p" 2>/dev/null; done
}

# 等待端口就绪
wait_for_port() {
    local port=$1 label=$2 timeout=${3:-30} i=0
    while ! lsof -i :"$port" -sTCP:LISTEN &>/dev/null; do
        i=$((i+1))
        [ $i -ge $timeout ] && { err "$label 启动超时 (${timeout}s)"; return 1; }
        sleep 1
    done
    return 0
}

# 清理所有子进程
shutdown() {
    # 只执行一次
    [ "$_SHUTDOWN_DONE" = "1" ] && return
    _SHUTDOWN_DONE=1

    echo ""
    log "正在关闭所有服务..."
    kill_by_port $BACKEND_PORT
    kill_by_port $FRONTEND_PORT
    rm -f "$PID_DIR"/*.pid 2>/dev/null
    ok "全部服务已关闭"
}

do_stop() {
    log "停止服务..."
    kill_by_port $BACKEND_PORT
    kill_by_port $FRONTEND_PORT
    rm -f "$PID_DIR"/*.pid 2>/dev/null
    ok "已停止"
}

do_status() {
    local rc=0
    if lsof -i :$BACKEND_PORT -sTCP:LISTEN &>/dev/null; then
        ok "后端  :$BACKEND_PORT 运行中"
    else
        warn "后端  :$BACKEND_PORT 未运行"; rc=1
    fi
    if lsof -i :$FRONTEND_PORT -sTCP:LISTEN &>/dev/null; then
        ok "前端  :$FRONTEND_PORT 运行中"
        echo ""
        for ip in $(get_all_ips); do
            ok "访问  http://$ip:$FRONTEND_PORT"
        done
    else
        warn "前端  :$FRONTEND_PORT 未运行"; rc=1
    fi
    return $rc
}

do_start() {
    # 端口被占用时自动关闭旧进程
    if lsof -i :$BACKEND_PORT -sTCP:LISTEN &>/dev/null; then
        warn "端口 $BACKEND_PORT 已被占用，正在关闭旧进程..."
        kill_by_port $BACKEND_PORT
    fi
    if lsof -i :$FRONTEND_PORT -sTCP:LISTEN &>/dev/null; then
        warn "端口 $FRONTEND_PORT 已被占用，正在关闭旧进程..."
        kill_by_port $FRONTEND_PORT
    fi
    # 读 PID 文件精准杀残留 gunicorn master
    if [ -f "$PID_DIR/backend.pid" ]; then
      OLD_PID=$(cat "$PID_DIR/backend.pid" 2>/dev/null)
      if [ -n "$OLD_PID" ] && kill -0 "$OLD_PID" 2>/dev/null; then
        warn "杀死残留 gunicorn master (PID $OLD_PID)..."
        kill "$OLD_PID" 2>/dev/null; sleep 1
        kill -0 "$OLD_PID" 2>/dev/null && kill -9 "$OLD_PID" 2>/dev/null || true
      fi
      rm -f "$PID_DIR/backend.pid"
    fi

    mkdir -p "$PID_DIR" "$LOG_DIR"

    # 注册清理函数
    _SHUTDOWN_DONE=0
    trap 'shutdown; exit 0' SIGINT SIGTERM
    trap 'shutdown' EXIT

    echo ""
    log "====================================="
    log "  IntelHub 开发环境启动"
    log "====================================="
    echo ""

    # ---- 后端 ----
    log "启动后端 (Gunicorn :$BACKEND_PORT)..."
    PYTHON="$ROOT_DIR/.venv/bin/python"
    [ ! -x "$PYTHON" ] && PYTHON=python3
    $PYTHON -m gunicorn \
        --bind "0.0.0.0:$BACKEND_PORT" \
        --workers 3 \
        --threads 4 \
        --timeout 120 \
        --chdir "$ROOT_DIR" \
        --daemon \
        --pid "$PID_DIR/backend.pid" \
        --access-logfile "$LOG_DIR/backend.log" \
        --error-logfile "$LOG_DIR/backend.log" \
        "app:create_app()"
    BACKEND_PID=$(cat "$PID_DIR/backend.pid" 2>/dev/null)

    if ! wait_for_port $BACKEND_PORT "后端" 30; then
        echo "--- backend.log (last 20 lines) ---"
        tail -20 "$LOG_DIR/backend.log" 2>/dev/null
        shutdown; exit 1
    fi
    ok "后端就绪  →  http://localhost:$BACKEND_PORT/api/v1/health"

    # ---- 前端 ----
    log "启动前端 (Vite :$FRONTEND_PORT)..."
    (cd "$ROOT_DIR/frontend" && exec npx vite --host 0.0.0.0 --port $FRONTEND_PORT \
        > "$LOG_DIR/frontend.log" 2>&1) &
    FRONTEND_PID=$!
    echo "$FRONTEND_PID" > "$PID_DIR/frontend.pid"

    if ! wait_for_port $FRONTEND_PORT "前端" 30; then
        echo "--- frontend.log (last 20 lines) ---"
        tail -20 "$LOG_DIR/frontend.log" 2>/dev/null
        shutdown; exit 1
    fi
    ok "前端就绪  →  http://localhost:$FRONTEND_PORT"

    echo ""
    log "====================================="
    log "  全部就绪！"
    log "  后端:  http://localhost:$BACKEND_PORT"
    echo ""

    local all_ips=$(get_all_ips)
    local first_ip=""
    for ip in $all_ips; do
        [ -z "$first_ip" ] && first_ip=$ip
        ok "前端:  http://$ip:$FRONTEND_PORT"
    done
    if [ -n "$first_ip" ] && [ "$first_ip" != "127.0.0.1" ] && [ "$first_ip" != "::1" ]; then
        echo ""
        warn "局域网访问: http://$first_ip:$FRONTEND_PORT"
    fi

    echo ""
    log "  日志:  $LOG_DIR/"
    log "====================================="
    echo ""
    log "按 Ctrl+C 停止所有服务"
    echo ""

    # 等待任意子进程退出
    wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true
    # 如果到这里，说明有子进程退出了
    shutdown
}

case "${1:-}" in
    stop)   do_stop   ;;
    status) do_status ;;
    restart) do_stop; sleep 1; do_start ;;
    *)      do_start  ;;
esac
