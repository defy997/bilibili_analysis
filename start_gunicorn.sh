#!/bin/bash
# ============================================================
# Gunicorn 安全启动/停止/重启脚本
# 防止 "Address already in use" 错误
# ============================================================

set -e

# 配置
APP_DIR="/root/bilibili_analysis"
VENV_PYTHON="$APP_DIR/venv/bin/python3"
GUNICORN="$APP_DIR/venv/bin/gunicorn"
CONFIG="$APP_DIR/gunicorn_config.py"
PID_FILE="$APP_DIR/gunicorn.pid"
LOG_FILE="$APP_DIR/logs/gunicorn.log"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# 检查端口是否被占用
check_port() {
    if ss -tlnp 2>/dev/null | grep -q ":8000 "; then
        return 0  # 端口被占用
    else
        return 1  # 端口空闲
    fi
}

# 获取 gunicorn master PID
get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    else
        ps aux | grep -E "gunicorn.*bilibili_analysis.wsgi" | grep -v grep | awk 'NR==1 {print $2}'
    fi
}

# 停止服务
stop() {
    log_info "正在停止 Gunicorn 服务..."
    
    PID=$(get_pid)
    if [ -n "$PID" ]; then
        # 先尝试优雅停止（给 worker 30 秒完成当前请求）
        log_info "发送 SIGTERM 信号到 PID $PID ..."
        kill -TERM "$PID" 2>/dev/null || true
        
        # 等待进程退出
        WAIT_COUNT=0
        while kill -0 "$PID" 2>/dev/null; do
            sleep 1
            WAIT_COUNT=$((WAIT_COUNT + 1))
            if [ $WAIT_COUNT -ge 30 ]; then
                log_warn "优雅停止超时，强制 kill..."
                kill -9 "$PID" 2>/dev/null || true
                break
            fi
        done
        
        log_info "Gunicorn 已停止 (PID $PID)"
    else
        log_warn "Gunicorn 未运行"
    fi
    
    # 清理 PID 文件
    rm -f "$PID_FILE"
}

# 启动服务
start() {
    log_info "正在启动 Gunicorn 服务..."
    
    # 检查端口占用
    if check_port; then
        log_error "8000 端口已被占用！"
        log_info "当前占用 8000 端口的进程："
        ss -tlnp | grep :8000
        log_info ""
        log_info "如果确认没有其他 gunicorn 在运行，请先执行: $0 stop"
        log_info "如果 gunicorn 崩溃未退出，请执行: killall -9 gunicorn"
        exit 1
    fi
    
    # 确保日志目录存在
    mkdir -p "$APP_DIR/logs"
    
    # 启动 gunicorn
    # 使用 --pid 写入 PID 文件，--daemon 后台运行
    $GUNICORN \
        --config "$CONFIG" \
        --pid "$PID_FILE" \
        --daemon \
        bilibili_analysis.wsgi:application
    
    sleep 2
    
    # 验证启动成功
    if check_port; then
        PID=$(get_pid)
        log_info "Gunicorn 启动成功！"
        log_info "Master PID: $PID"
        log_info "监听地址: http://127.0.0.1:8000"
    else
        log_error "Gunicorn 启动失败！请检查日志。"
        exit 1
    fi
}

# 重启服务
restart() {
    log_info "重启 Gunicorn 服务..."
    stop
    sleep 2
    start
}

# 强制重启（用于修复端口占用等异常）
force-restart() {
    log_warn "强制重启 Gunicorn（先 killall）..."
    killall -9 gunicorn 2>/dev/null || true
    sleep 2
    rm -f "$PID_FILE"
    start
}

# 状态检查
status() {
    if check_port; then
        PID=$(get_pid)
        WORKER_COUNT=$(ps aux | grep -E "gunicorn.*bilibili_analysis.wsgi" | grep -v grep | wc -l)
        log_info "Gunicorn 运行中"
        log_info "Master PID: $PID"
        log_info "Worker 数量: $WORKER_COUNT"
        log_info "监听地址: 127.0.0.1:8000"
        echo ""
        ss -tlnp | grep :8000
    else
        log_warn "Gunicorn 未运行"
    fi
}

# ============================================================
# 主逻辑
# ============================================================
case "${1:-start}" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart
        ;;
    force-restart)
        force-restart
        ;;
    status)
        status
        ;;
    *)
        echo "用法: $0 {start|stop|restart|force-restart|status}"
        echo ""
        echo "  start        - 安全启动（端口占用时拒绝启动）"
        echo "  stop         - 优雅停止（等待请求处理完成）"
        echo "  restart      - 重启"
        echo "  force-restart - 强制重启（用于端口占用等异常）"
        echo "  status       - 查看运行状态"
        exit 1
        ;;
esac
