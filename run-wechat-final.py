import json, os, sys, re, urllib.request, urllib.error
from pathlib import Path

env_path = '/home/ubuntu/wechat-publisher/.env'
env_vars = {}
with open(env_path, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            key, val = line.split('=', 1)
            env_vars[key.strip()] = val.strip()

SITE_ROOT = Path(env_vars.get('SITE_ROOT', '/home/ubuntu/wechat-publisher/site'))
DATA_DIR = SITE_ROOT / 'data'
WX_API = 'https://api.weixin.qq.com/cgi-bin'
APPID = env_vars.get('WECHAT_APPID', '')
SECRET = env_vars.get('WECHAT_SECRET', '')
SITE_URL = env_vars.get('SITE_URL', 'https://spacenetx.com')

print('=' * 60)
print('微信推送脚本 (Final v2 with Cover)')
print('=' * 60)

# Step 1: Get access_token
print('\n[1/5] Getting access_token...')
token_url = f'{WX_API}/token?grant_type=client_credential&appid={APPID}&secret={SECRET}'
try:
    with urllib.request.urlopen(token_url, timeout=10) as resp:
        token_data = json.loads(resp.read().decode('utf-8'))
        if 'access_token' not in token_data:
            print(f'  FAILED: {token_data}')
            sys.exit(1)
        token = token_data['access_token']
        print(f'  OK (len: {len(token)})')
except Exception as e:
    print(f'  ERROR: {e}')
    sys.exit(1)

# Step 2: Read articles
print('\n[2/5] Reading articles.json...')
articles_path = DATA_DIR / 'articles.json'
articles = json.loads(articles_path.read_text(encoding='utf-8'))
print(f'  Total: {len(articles)} articles')

latest = None
for a in sorted(articles, key=lambda x: x.get('date', ''), reverse=True):
    url = str(a.get('url', ''))
    if 'articles/' in url:
        latest = a
        break

if not latest:
    print('  ERROR: No article with "articles/" in URL!')
    for a in articles[:3]:
        print(f'    - {a.get("title", "?")}: url={a.get("url", "?")}')
    sys.exit(1)

print(f'  Latest: {latest["title"]}')
print(f'  Date: {latest.get("date", "N/A")}')

article_url = latest.get('url', '')
match = re.search(r'articles[/\\](.+\\.html)', article_url)
if match:
    filename = match.group(1)
else:
    slug = latest.get('id', '') or latest.get('slug', '') or latest['title'][:30].replace('/', '-')
    filename = f'{slug}.html'

article_file = SITE_ROOT / 'articles' / filename
print(f'  Filename: {filename}')
print(f'  Exists: {article_file.exists()}')

if not article_file.exists():
    print('\n  Available articles (newest):')
    articles_dir = SITE_ROOT / 'articles'
    if articles_dir.exists():
        for f in sorted(articles_dir.glob('*.html'), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            print(f'    - {f.name}')
    sys.exit(1)

# Step 3: Try to generate and upload cover image
print('\n[3/5] Processing cover image...')
thumb_media_id = ''
try:
    from PIL import Image, ImageDraw
    W, H = 540, 360
    img = Image.new('RGB', (W, H), '#0a0a1a')
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W-1, 60], fill='#e11d48')
    draw.text((20, 15), 'AI投研日报', fill='white')
    draw.text((20, 80), latest['title'][:30], fill='#ffffff')
    draw.text((20, H-40), f'{{latest.get("date", "2026-06-15")}}', fill='#cccccc')
    draw.text((20, H-20), 'spacenetx.com', fill='#888888')
    tmp_cover = '/tmp/wechat-cover.jpg'
    img.save(tmp_cover, 'JPEG', quality=85)

    cover_url = f'{WX_API}/media/upload?access_token={{token}}&type=image'
    with open(tmp_cover, 'rb') as cf:
        boundary = b'demo-boundary'
        body = b'--' + boundary + b'\r\n'
        body += b'Content-Disposition: form-data; name="media"; filename="cover.jpg"\r\n'
        body += b'Content-Type: image/jpeg\r\n\r\n'
        body += cf.read() + b'\r\n'
        body += b'--' + boundary + b'--\r\n'
    req = urllib.request.Request(cover_url, data=body, headers={'Content-Type': f'multipart/form-data; boundary={boundary.decode()}'})
    with urllib.request.urlopen(req, timeout=15) as resp:
        up_result = json.loads(resp.read().decode('utf-8'))
        if up_result.get('media_id'):
            thumb_media_id = up_result['media_id']
            print(f'  Cover uploaded: media_id={{thumb_media_id[:20]}...}')
        else:
            print(f'  Cover upload failed: {{up_result}}')
except ImportError:
    print('  [WARN] Pillow not available')
except Exception as e:
    print(f'  [WARN] Cover failed: {{e}}')

if not thumb_media_id:
    print('  Using blank thumb_media_id')

# Step 4: Extract content
print('\n[4/5] Extracting article content...')
raw_html = article_file.read_text(encoding='utf-8')
html = re.sub(r'<style>.*?</style>', '', raw_html, flags=re.DOTALL | re.IGNORECASE)
html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
html = re.sub(r'<p[^>]*class="[^"]*back-link[^"]*"[^>]*>.*?</p>', '', html, flags=re.DOTALL | re.IGNORECASE)
html = re.sub(r'<(?:nav|footer)[^>]*>.*?</(?:nav|footer)>', '', html, flags=re.DOTALL | re.IGNORECASE)

body = None
for tag, cls in [('article-content', 'div'), (None, 'main'), (None, 'article'), (None, 'body')]:
    if tag and cls == 'div':
        m = re.search(r'<div[^>]*class="[^"]*' + tag + r'[^"]*"[^>]*>(.*?)</div>', html, re.DOTALL)
        if m:
            body = m.group(1)
            print(f'  Extracted via: .{tag} div')
            break
    elif cls in ('main', 'article', 'body'):
        m = re.search(r'<' + cls + r'[^>]*>(.*?)</' + cls + r'>', html, re.DOTALL | re.IGNORECASE)
        if m:
            body = m.group(1)
            print(f'  Extracted via: <{cls}> tag')
            break

if not body:
    body = html
    print('  Extracted: full cleaned HTML (fallback)')

body = '<section style="padding: 8px; line-height: 1.8; font-family: -apple-system, BlinkMacSystemFont, sans-serif;">\n' + body.strip() + '\n</section>'
print(f'  Body length: {{len(body)}} chars')

# Step 5: Create draft
print('\n[5/5] Creating draft...')
slug_for_url = filename.replace('.html', '')
content_source_url = f'{SITE_URL}/articles/{{slug_for_url}}.html'

payload = {{
    "articles": [{{
        "title": latest['title'],
        "author": "无缘的人",
        "digest": latest.get('excerpt', latest.get('desc', latest['title'][:54])),
        "content": body,
        "content_source_url": content_source_url,
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }}]
}}

print(f'  Title: {{payload["articles"][0]["title"]}}')
print(f'  Content URL: {{content_source_url}}')
print(f'  Thumb media_id: {{thumb_media_id[:30] if thumb_media_id else "(none)"}}')

payload_json = json.dumps(payload, ensure_ascii=False).encode('utf-8')
req = urllib.request.Request(
    f'{WX_API}/draft/add?access_token={{token}}',
    data=payload_json,
    headers={{'Content-Type': 'application/json'}}
)

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        if result.get('media_id'):
            mid = result['media_id']
            print(f'\n  SUCCESS! media_id: {{mid[:40]}...}')
            print(f'  Draft created. Check https://mp.weixin.qq.com')
        else:
            print(f'\n  FAILED!')
            print(f'  errcode: {{result.get("errcode")}}')
            print(f'  errmsg: {{result.get("errmsg")}}')
except urllib.error.HTTPError as e:
    print(f'\n  HTTP Error {{e.code}}: {{e.reason}}')
    try:
        print(f'  Response: {{e.read().decode("utf-8")}}')
    except:
        pass
except Exception as e:
    print(f'\n  Error: {{type(e).__name__}}: {{e}}')
