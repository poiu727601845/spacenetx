import sys
sys.path.insert(0, '/home/ubuntu/.local/bin')

from dotenv import load_dotenv
load_dotenv('/home/ubuntu/wechat-publisher/.env')

import os
import json
import urllib.request
from pathlib import Path

WX_API = 'https://api.weixin.qq.com/cgi-bin'

APPID = os.getenv('WECHAT_APPID')
SECRET = os.getenv('WECHAT_SECRET')
SITE_URL = os.getenv('SITE_URL')
SITE_ROOT = Path(os.getenv('SITE_ROOT', '/home/ubuntu/wechat-publisher/site'))

print('=== 微信推送测试 ===')
print(f'APPID: {APPID}')
print(f'SECRET: {SECRET[:10]}***')
print(f'SITE_URL: {SITE_URL}')
print(f'SITE_ROOT: {SITE_ROOT}')

# Step 1: Get access_token
print('\n[1/3] 获取 access_token ...')
token_url = f'{WX_API}/token?grant_type=client_credential&appid={APPID}&secret={SECRET}'
try:
    req = urllib.request.Request(token_url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        token_data = json.loads(resp.read().decode('utf-8'))
        if 'access_token' in token_data:
            access_token = token_data['access_token']
            print(f'  ✅ Token 获取成功! (有效期: {token_data.get("expires_in", "unknown")}s)')
        else:
            print(f'  ❌ Token 失败: {token_data}')
            sys.exit(1)
except Exception as e:
    print(f'  ❌ Token 请求失败: {e}')
    sys.exit(1)

# Step 2: Upload temporary material (封面图)
print('\n[2/3] 上传封面图 (临时素材) ...')
# 从site目录找封面图
cover_file = SITE_ROOT / 'data' / 'cover.png'
if not cover_file.exists():
    print(f'  ⚠️ 未找到封面图: {cover_file}')
    cover_file = None
else:
    print(f'  ✅ 找到封面图: {cover_file}')

# Step 3: Upload article content
print('\n[3/3] 创建草稿 ...')
# 获取最新文章
articles_file = SITE_ROOT / 'data' / 'articles.json'
if articles_file.exists():
    with open(articles_file, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    
    if articles:
        article = articles[0]
        title = article.get('title', '未命名')
        content_url = article.get('url', '')
        desc = article.get('desc', article.get('excerpt', ''))
        
        print(f'  📝 文章标题: {title}')
        print(f'  📅 日期: {article.get("date", "N/A")}')
        print(f'  📖 摘要: {desc[:50]}...' if len(desc) > 50 else f'  📖 摘要: {desc}')
        print(f'  🔗 URL: {SITE_URL}{content_url}')
        print('\n✅ 微信推送配置正确!')
        print('下一步: 运行 wechat_publish.py 正式发布')
    else:
        print('  ❌ articles.json 为空')
        sys.exit(1)
else:
    print(f'  ❌ 未找到 articles.json: {articles_file}')
    sys.exit(1)
