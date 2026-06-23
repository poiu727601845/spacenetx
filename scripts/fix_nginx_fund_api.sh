#!/bin/bash
# fix_nginx_fund_api.sh
# 自动检测并修复 /api/fund 路由丢失问题
# 防止 certbot 更新导致 Nginx 配置被重置
# 部署位置: /home/ubuntu/wechat-publisher/scripts/fix_nginx_fund_api.sh

set -e

NGINX_CONF="/etc/nginx/sites-available/spacenetx"
NGINX_ENABLED="/etc/nginx/sites-enabled/spacenetx"
SITE_DIR="/home/ubuntu/wechat-publisher/site"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] 检查 /api/fund 路由是否存在..."

# 检查 Nginx 配置中是否包含 /api/fund 路由
if grep -q 'location /api/fund' "$NGINX_CONF" 2>/dev/null; then
    echo "[OK] /api/fund 路由已存在于 Nginx 配置"
else
    echo "[WARNING] /api/fund 路由丢失！正在修复..."
    
    # 备份当前配置
    cp "$NGINX_CONF" "${NGINX_CONF}.bak.$(date +%Y%m%d%H%M%S)"
    
    # 在 location / 之前插入 /api/fund 路由
    sudo sed -i '/^    location \/ {$/i\
    # 基金数据 API - 代理到本地 fund-proxy\
    location /api/fund {\
        proxy_pass http://127.0.0.1:8199;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        add_header Cache-Control "no-cache, no-store, must-revalidate";\
    }\
' "$NGINX_CONF"
    
    echo "[OK] /api/fund 路由已添加到 Nginx 配置"
fi

# 检查 /api/digest 路由是否存在（同理修复）
if grep -q 'location /api/digest' "$NGINX_CONF" 2>/dev/null; then
    echo "[OK] /api/digest 路由已存在于 Nginx 配置"
else
    echo "[WARNING] /api/digest 路由丢失！正在修复..."
    
    sudo sed -i '/^    location \/api\/fund {$/,/^    }$/{ /^    }$/a\
\
    # AI Digest API\
    location /api/digest {\
        proxy_pass http://127.0.0.1:8200;\
        proxy_set_header Host $host;\
        proxy_set_header X-Real-IP $remote_addr;\
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\
        add_header Cache-Control "no-cache, no-store, must-revalidate";\
        add_header Access-Control-Allow-Origin "*";\
    }
}' "$NGINX_CONF"
    
    echo "[OK] /api/digest 路由已添加到 Nginx 配置"
fi

# 重载 Nginx
echo "重载 Nginx..."
sudo nginx -t 2>&1 && sudo systemctl reload nginx

echo "[SUCCESS] Nginx 配置检查和修复完成"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 修复完成"
