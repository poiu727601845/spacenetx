import sys
sys.path.insert(0, '/home/ubuntu/.local/bin')

from dotenv import load_dotenv
load_dotenv('/home/ubuntu/wechat-publisher/.env')

import os
print('=== 环境配置测试 ===')
print(f'APPID: {os.getenv("WECHAT_APPID")}')
print(f'SECRET: {os.getenv("WECHAT_SECRET")[:10]}***')
print(f'SITE_ROOT: {os.getenv("SITE_ROOT")}')
print(f'SITE_URL: {os.getenv("SITE_URL")}')
print('dotenv: OK')
print(f'python-dotenv installed: Yes')
print('\n=== 目录检查 ===')
from pathlib import Path
sr = Path(os.getenv('SITE_ROOT', ''))
print(f'SITE_ROOT exists: {sr.exists()}')
print(f'contents: {list(sr.iterdir())[:5] if sr.exists() else "N/A"}')
print(f'articles.json: {(sr / "data" / "articles.json").exists()}')
