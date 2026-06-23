#!/bin/bash
# watchdog_spacenetx.sh v3
# 使用 golden master 进行恢复

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="/home/ubuntu/wechat-publisher/logs"
LOG="$LOG_DIR/watchdog.log"
SITE_DIR="/home/ubuntu/wechat-publisher/site"
INDEX_HTML="$SITE_DIR/index.html"
GOLDEN="$SITE_DIR/index.html.golden"
NGINX_CONF="/etc/nginx/sites-available/spacenetx"
FIX_SCRIPT="/home/ubuntu/wechat-publisher/scripts/fix_nginx_full.sh"

mkdir -p "$LOG_DIR" 2>/dev/null || true

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$LOG"
}

FIXED=0

# 检查1: Nginx 是否在运行
if ! systemctl is-active --quiet nginx 2>/dev/null; then
    log "[FIX] Nginx 未运行，正在启动..."
    systemctl start nginx 2>&1 | tee -a "$LOG"
    sleep 1
    if systemctl is-active --quiet nginx 2>/dev/null; then
        log "[OK] Nginx 已启动"
    else
        log "[ERR] Nginx 启动失败"
    fi
    FIXED=1
fi

# 检查2: fund-proxy 是否在运行（systemd 服务）
if ! systemctl is-active --quiet fund-proxy 2>/dev/null; then
    log "[FIX] fund-proxy 服务未运行，正在启动..."
    systemctl restart fund-proxy 2>&1 | tee -a "$LOG"
    sleep 2
    if systemctl is-active --quiet fund-proxy 2>/dev/null; then
        log "[OK] fund-proxy 已启动"
    else
        log "[ERR] fund-proxy 启动失败，尝试 nohup..."
        nohup python3 /home/ubuntu/wechat-publisher/fund_proxy.py > "$LOG_DIR/fund-proxy.log" 2>&1 &
    fi
    FIXED=1
fi

# 检查3: /api/fund 是否能正常响应
API_TEST=$(curl -s --connect-timeout 3 http://127.0.0.1:8199/api/fund?code=159915 2>/dev/null | head -c 20)
if [ -z "$API_TEST" ]; then
    log "[FIX] /api/fund 无响应，重启 fund-proxy..."
    systemctl restart fund-proxy 2>&1 | tee -a "$LOG"
    sleep 3
    API_TEST2=$(curl -s --connect-timeout 3 http://127.0.0.1:8199/api/fund?code=159915 2>/dev/null | head -c 20)
    if [ -n "$API_TEST2" ]; then
        log "[OK] fund-proxy 已重启"
    else
        log "[ERR] fund-proxy 重启后仍无响应"
    fi
    FIXED=1
fi

# 检查4: index.html 是否包含 retryFetch（关键！）
if [ -f "$INDEX_HTML" ]; then
    # 检查是否有 retryFetch
    if ! grep -q "retryFetch" "$INDEX_HTML" 2>/dev/null; then
        log "[FIX] index.html 缺少 retryFetch，从 golden master 恢复..."
        if [ -f "$GOLDEN" ] && grep -q "retryFetch" "$GOLDEN" 2>/dev/null; then
            cp "$GOLDEN" "$INDEX_HTML"
            log "[OK] 从 golden master 恢复"
            nginx -s reload 2>/dev/null || systemctl reload nginx 2>/dev/null || true
        else
            log "[ERR] golden master 不存在或无效！"
        fi
        FIXED=1
    fi
    
    # 检查文件是否被截断
    SIZE=$(stat -c%s "$INDEX_HTML" 2>/dev/null || echo 0)
    if [ "$SIZE" -lt 45000 ]; then
        log "[FIX] index.html 大小异常 ($SIZE 字节)，从 golden master 恢复..."
        if [ -f "$GOLDEN" ]; then
            cp "$GOLDEN" "$INDEX_HTML"
            log "[OK] 从 golden master 恢复"
            nginx -s reload 2>/dev/null || systemctl reload nginx 2>/dev/null || true
        fi
        FIXED=1
    fi
else
    log "[ERR] index.html 不存在！从 golden master 恢复..."
    if [ -f "$GOLDEN" ]; then
        cp "$GOLDEN" "$INDEX_HTML"
        log "[OK] 从 golden master 恢复"
    fi
    FIXED=1
fi

# 检查5: Nginx 配置是否被重置
if [ -f "$NGINX_CONF" ]; then
    if ! grep -q "server_name www.spacenetx.com" "$NGINX_CONF" 2>/dev/null; then
        log "[FIX] Nginx 配置缺少 www 重定向，执行修复脚本..."
        if [ -x "$FIX_SCRIPT" ]; then
            bash "$FIX_SCRIPT" >> "$LOG" 2>&1 || true
        fi
        nginx -t >> "$LOG" 2>&1 && systemctl reload nginx >> "$LOG" 2>&1 || true
        log "[OK] Nginx 配置已修复"
        FIXED=1
    fi
else
    log "[ERR] Nginx 配置文件不存在: $NGINX_CONF"
fi

# 检查6: 磁盘空间
DISK=$(df / | awk 'NR==2 {gsub(/%/,""); print $5}' 2>/dev/null || echo 0)
if [ "$DISK" -gt 90 ] 2>/dev/null; then
    log "[WARN] 磁盘空间不足: ${DISK}%"
fi

# 总结
if [ "$FIXED" -eq 0 ]; then
    NOW=$(date +%s)
    LAST_LOG=$(stat -c%Y "$LOG" 2>/dev/null || echo 0)
    if [ $((NOW - LAST_LOG)) -gt 1800 ]; then
        FUND_CNT=$(ps aux | grep -c '[f]und_proxy' || echo 0)
        log "[OK] 所有检查通过，系统正常 (fund-proxy: $FUND_CNT 进程)"
    fi
else
    log "=== 本轮修复完成，共修复 $FIXED 项问题 ==="
fi
