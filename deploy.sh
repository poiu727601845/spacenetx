#!/bin/bash
# spacenetx.com 部署脚本（含内嵌数据）
set -e
TOKEN="$VERCEL_TOKEN"
DIR="/home/ubuntu/wechat-publisher"

echo "================================"
echo "  spacenetx.com 部署流程"
echo "================================"

echo ""
echo "[1/3] 获取基金估值数据并内嵌到HTML..."
python3 "$DIR/embed_fund_data.py" || echo "内嵌失败，继续使用旧数据"

echo ""
echo "[2/3] 部署到 Vercel 生产环境..."
cd "$DIR"
vercel --prod --yes --token "$TOKEN"

echo ""
echo "================================"
echo "部署完成! https://spacenetx.com"
echo "================================"
