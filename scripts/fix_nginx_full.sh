#!/bin/bash
# fix_nginx_full.sh
# 全自动化修复脚本：在 certbot 更新或系统重启后自动恢复完整 Nginx 配置
# 部署位置: /home/ubuntu/wechat-publisher/scripts/fix_nginx_full.sh
# 使用方法: 
#   1. 手动执行: bash /home/ubuntu/wechat-publisher/scripts/fix_nginx_full.sh
#   2. Cron 定时: 0 */6 * * * /home/ubuntu/wechat-publisher/scripts/fix_nginx_full.sh >> /home/ubuntu/wechat-publisher/scripts/fix_nginx_full.log 2>&1
#   3. Certbot post-hook: 在 /etc/systemd/system/certbot.service.d/override.conf 中添加 PostExec=/home/ubuntu/wechat-publisher/scripts/fix_nginx_full.sh

set -e

NGINX_GLOBAL="/etc/nginx/nginx.conf"
NGINX_CONF="/etc/nginx/sites-available/spacenetx"
LOG_FILE="/home/ubuntu/wechat-publisher/scripts/fix_nginx_full.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== 开始自动修复 Nginx 配置 ==="

# ============================================
# 第一部分：恢复全局 Nginx 优化配置
# ============================================
log "检查全局 Nginx 配置..."

# 检查 SSL 协议是否被重置为 TLSv1.2
if grep -q "ssl_protocols TLSv1.2;" "$NGINX_GLOBAL" 2>/dev/null; then
    log "[OK] SSL 协议配置正确 (TLSv1.2)"
else
    log "[FIX] 修复 SSL 协议配置为 TLSv1.2..."
    sudo sed -i 's/ssl_protocols TLSv1.2 TLSv1.3;/ssl_protocols TLSv1.2;/g' "$NGINX_GLOBAL"
    # 如果没有找到替换目标，则直接追加
    if ! grep -q "ssl_protocols TLSv1.2;" "$NGINX_GLOBAL" 2>/dev/null; then
        sudo sed -i '/ssl_protocols/a\    ssl_protocols TLSv1.2;' "$NGINX_GLOBAL"
    fi
    log "[OK] SSL 协议已修复"
fi

# 检查是否开启了 Gzip 压缩
if grep -q "^    gzip on;" "$NGINX_GLOBAL" 2>/dev/null; then
    log "[OK] Gzip 压缩已启用"
else
    log "[FIX] 启用 Gzip 压缩..."
    if grep -q "^    # Gzip Compression" "$NGINX_GLOBAL" 2>/dev/null; then
        # 取消注释 Gzip 相关配置
        sudo sed -i 's/^    # gzip on;/    gzip on;/' "$NGINX_GLOBAL"
        sudo sed -i 's/^    # gzip_vary on;/    gzip_vary on;/' "$NGINX_GLOBAL"
        sudo sed -i 's/^    # gzip_proxied any;/    gzip_proxied any;/' "$NGINX_GLOBAL"
        sudo sed -i 's/^    # gzip_comp_level 6;/    gzip_comp_level 6;/' "$NGINX_GLOBAL"
        sudo sed -i 's/^    # gzip_buffers 16 8k;/    gzip_buffers 16 8k;/' "$NGINX_GLOBAL"
        sudo sed -i 's/^    # gzip_http_version 1.1;/    gzip_http_version 1.1;/' "$NGINX_GLOBAL"
        sudo sed -i 's/^    # gzip_types .*/    gzip_types text\/plain text\/css application\/json application\/javascript text\/xml application\/xml application\/xml+rss text\/javascript image\/svg\+xml;/' "$NGINX_GLOBAL"
    fi
    log "[OK] Gzip 压缩已启用"
fi

# ============================================
# 第二部分：恢复站点 Nginx 配置
# ============================================
log "检查站点 Nginx 配置..."

# 检查 /api/fund 路由
if grep -q 'location /api/fund' "$NGINX_CONF" 2>/dev/null; then
    log "[OK] /api/fund 路由已存在"
else
    log "[FIX] /api/fund 路由丢失！正在修复..."
    sudo cp "$NGINX_CONF" "${NGINX_CONF}.bak.$(date +%Y%m%d%H%M%S)"
    sudo sed -i '/^    location \/ {$/i\
    # 基金数据 API - 代理到本地 fund-proxy\
    location /api/fund {\
        proxy_pass http://127.0.0.1:8199;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_connect_timeout 5s;\
        proxy_read_timeout 10s;\
        add_header Cache-Control "no-cache, no-store, must-revalidate";\
    }\
' "$NGINX_CONF"
    log "[OK] /api/fund 路由已添加"
fi

# 检查 /api/digest 路由
if grep -q 'location /api/digest' "$NGINX_CONF" 2>/dev/null; then
    log "[OK] /api/digest 路由已存在"
else
    log "[FIX] /api/digest 路由丢失！正在修复..."
    sudo sed -i '/^    location \/api\/fund {$/,/^    }$/{ /^    }$/a\
\
    # AI Digest API\
    location /api/digest {\
        proxy_pass http://127.0.0.1:8200;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        proxy_connect_timeout 5s;\
        proxy_read_timeout 10s;\
        add_header Cache-Control "no-cache, no-store, must-revalidate";\
        add_header Access-Control-Allow-Origin "*";\
    }
}' "$NGINX_CONF"
    log "[OK] /api/digest 路由已添加"
fi

# 检查 SSL 证书路径
if grep -q 'ssl_certificate /etc/nginx/ssl/spacenetx.com/fullchain.pem;' "$NGINX_CONF" 2>/dev/null; then
    log "[OK] SSL 证书路径正确"
else
    log "[WARN] SSL 证书路径可能需要检查"
fi

# ============================================
# 第三部分：重载 Nginx 并验证
# ============================================
log "测试并重载 Nginx 配置..."

if sudo nginx -t 2>&1 | grep -q "syntax is ok"; then
    sudo systemctl reload nginx
    log "[SUCCESS] Nginx 重载成功"
else
    log "[ERROR] Nginx 配置测试失败！请检查错误日志"
    sudo nginx -t 2>&1 | tee -a "$LOG_FILE"
    exit 1
fi

# 验证 fund-proxy 服务
if systemctl is-active --quiet fund-proxy.service 2>/dev/null; then
    log "[OK] fund-proxy 服务正常运行"
else
    log "[WARN] fund-proxy 服务未运行，尝试启动..."
    sudo systemctl start fund-proxy.service
    log "[OK] fund-proxy 已启动"
fi

log "=== 自动修复完成 ==="

