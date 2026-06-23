import json, os, sys, re, urllib.request
from pathlib import Path

SITE_ROOT = '/home/ubuntu/wechat-publisher/site'
DATA_DIR = Path(SITE_ROOT) / 'data'

# Load .env
from dotenv import load_dotenv
load_dotenv('/home/ubuntu/wechat-publisher/.env')

APPID = os.getenv('WECHAT_APPID')
SECRET = os.getenv('WECHAT_SECRET')
SITE_URL = os.getenv('SITE_URL')
WX_API = 'https://api.weixin.qq.com/cgi-bin'

# Get access_token
print('[1/3] Getting access_token...')
token_url = f'{WX_API}/token?grant_type=client_credential&appid={APPID}&secret={SECRET}'
with urllib.request.urlopen(token_url, timeout=10) as resp:
    token_data = json.loads(resp.read().decode('utf-8'))
    token = token_data['access_token']
    print(f'  OK (token len: {len(token)})')

# Read articles.json
articles_json = DATA_DIR / 'articles.json'
data = json.loads(articles_json.read_text(encoding='utf-8'))
latest = max(data, key=lambda a: a.get('date', ''))
slug = latest.get('id', '') or latest.get('slug', '')
article_file = SITE_ROOT / 'articles' / f'{slug}.html'

print(f'\n[2/3] Article: {latest["title"]}')
print(f'  Slug: {slug}')
print(f'  File: {article_file}')
print(f'  Exists: {article_file.exists()}')

if not article_file.exists():
    print('\nFiles in articles/:')
    for f in sorted(Path(SITE_ROOT / 'articles').glob('*'))[-5:]:
        print(f'  {f.name}')
    sys.exit(1)

# Clean HTML - remove <body> wrapper, <p class="back-link">, navigation, style blocks
content = article_file.read_text(encoding='utf-8')

# Remove <style> blocks
content = re.sub(r'<style>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)

# Remove back link paragraph
content = re.sub(r'<p[^>]*class="[^"]*back-link[^"]*"[^>]*>.*?</p>', '', content, flags=re.DOTALL | re.IGNORECASE)

# Extract body content (everything inside <body> but not inside <head>)
body_match = re.search(r'<body[^>]*>(.*)</body>', content, re.DOTALL | re.IGNORECASE)
if body_match:
    body = body_match.group(1)
    # Wrap in <section> for WeChat
    body = '<section style="padding:24px 16px;">\n' + body + '\n</section>'
else:
    body = content

print(f'  Body length: {len(body)} chars')

# Create draft
print('\n[3/3] Creating draft...')
payload = {
    "articles": [{
        "title": latest['title'],
        "author": "无缘的人",
        "digest": latest['title'][:54],
        "content": body,
        "content_source_url": f"{SITE_URL}/articles/{slug}.html",
        "thumb_media_id": "",
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }]
}

body_bytes = json.dumps(payload, ensure_ascii=False).encode('utf-8')
req = urllib.request.Request(f'{WX_API}/draft/add?access_token={token}', data=body_bytes)
with urllib.request.urlopen(req, timeout=10) as resp:
    result = json.loads(resp.read().decode('utf-8'))
    if result.get('media_id'):
        print(f'  ✅ Draft created! media_id: {result["media_id"][:30]}...')
    else:
        print(f'  ❌ Failed: {result}')
