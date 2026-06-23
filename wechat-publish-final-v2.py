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

print('='*60)
print('微信推送脚本 (Final v2)')
print('='*60)
print(f'SITE_ROOT: {SITE_ROOT}')
print(f'APPID: {APPID}')
print()

# Step 1: Get access_token
print('[1/4] Getting access_token...')
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
print('\n[2/4] Reading articles.json...')
articles_path = DATA_DIR / 'articles.json'
articles = json.loads(articles_path.read_text(encoding='utf-8'))
print(f'  Total: {len(articles)} articles')

# Sort by date, preferring articles with "articles/" in URL
def sort_key(a):
    date = a.get('date', '')
    url = str(a.get('url', ''))
    has_articles = 1 if 'articles/' in url else 0
    return (has_articles, date)

articles_sorted = sorted(articles, key=sort_key, reverse=True)

latest = None
for a in articles_sorted:
    if a.get('url') and 'articles/' in str(a.get('url', '')):
        latest = a
        break

if not latest:
    print('  ERROR: No article with "articles/" in URL!')
    print('  Showing first 3 articles:')
    for a in articles[:3]:
        print(f'    - {a.get("title", "?")}')
        print(f'      url={a.get("url", "?")}')
        print(f'      id={a.get("id", "?")}, slug={a.get("slug", "?")}')
    sys.exit(1)

print(f'  Latest: {latest["title"]}')
print(f'  Date: {latest.get("date", "N/A")}')

# Extract filename from url
article_url = latest.get('url', '')
match = re.search(r'articles[/\\](.+\.html)', article_url)
if match:
    filename = match.group(1)
else:
    # Fallback
    slug = latest.get('id', '') or latest.get('slug', '')
    if not slug:
        slug = latest['title'][:30].replace('/', '-').replace('\\', '-')
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

# Step 3: Extract body
print('\n[3/4] Extracting article content...')
raw_html = article_file.read_text(encoding='utf-8')
print(f'  Raw HTML: {len(raw_html)} chars')

# Clean HTML
html = re.sub(r'<style>.*?</style>', '', raw_html, flags=re.DOTALL | re.IGNORECASE)
html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
html = re.sub(r'<p[^>]*class="[^"]*back-link[^"]*"[^>]*>.*?</p>', '', html, flags=re.DOTALL | re.IGNORECASE)
html = re.sub(r'<(?:nav|footer)[^>]*>.*?</(?:nav|footer)>', '', html, flags=re.DOTALL | re.IGNORECASE)

# Try to extract content
body = None
for tag, cls in [
    ('article-content', 'div'),
    (None, 'main'),
    (None, 'article'),
    (None, 'body'),
]:
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
    # Just use cleaned html
    body = html
    print('  Extracted: full cleaned HTML (fallback)')

# Wrap for WeChat
body = (
    '<section style="padding: 8px; line-height: 1.8; '
    'font-family: -apple-system, BlinkMacSystemFont, '
    '"Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif;">\n'
    + body.strip() + '\n</section>'
)
print(f'  Body length: {len(body)} chars')

# Check for invalid characters
has_ctrl = any(ord(c) < 32 and c not in ('\n', '\r', '\t') for c in body)
has_null = '\x00' in body
print(f'  Control chars: {has_ctrl}')
print(f'  Null bytes: {has_null}')

# Step 4: Create draft
print('\n[4/4] Creating draft...')
slug_for_url = filename.replace('.html', '')
content_source_url = f'{SITE_URL}/articles/{slug_for_url}.html'

payload = {
    "articles": [{
        "title": latest['title'],
        "author": "无缘的人",
        "digest": latest.get('excerpt', latest.get('desc', latest['title'][:54])),
        "content": body,
        "content_source_url": content_source_url,
        "thumb_media_id": "",
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }]
}

print(f'  Title: {payload["articles"][0]["title"]}')
print(f'  Content URL: {content_source_url}')
print(f'  Digest: {payload["articles"][0]["digest"][:60]}...')
print()

payload_json = json.dumps(payload, ensure_ascii=False).encode('utf-8')
req = urllib.request.Request(
    f'{WX_API}/draft/add?access_token={token}',
    data=payload_json,
    headers={'Content-Type': 'application/json'}
)

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode('utf-8'))
        if result.get('media_id'):
            mid = result['media_id']
            print(f'  ===========================')
            print(f'  ✅ SUCCESS! media_id: {mid[:40]}...')
            print(f'  ===========================')
            print(f'\n  稿件已在草稿箱！')
            print(f'  1. 打开 https://mp.weixin.qq.com')
            print(f'  2. 左侧菜单 "草稿箱"')
            print(f'  3. 找到这篇文章，预览并发布')
        else:
            print(f'  ❌ FAILED!')
            print(f'  errcode: {result.get("errcode")}')
            print(f'  errmsg: {result.get("errmsg")}')
            print(f'\n  Content sample (first 1000 chars):')
            print('-' * 60)
            print(body[:1000])
except urllib.error.HTTPError as e:
    print(f'  ❌ HTTP Error {e.code}: {e.reason}')
    try:
        error_body = e.read().decode('utf-8')
        print(f'  Response: {error_body}')
    except:
        pass
except Exception as e:
    print(f'  ❌ Error: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
