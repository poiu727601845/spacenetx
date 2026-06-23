import json, os, sys, re, urllib.request, urllib.error
from pathlib import Path

env_path = "/home/ubuntu/wechat-publisher/.env"
env_vars = {}
with open(env_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"): continue
        if "=" in line:
            key, val = line.split("=", 1)
            env_vars[key.strip()] = val.strip()

SITE_ROOT = Path(env_vars.get("SITE_ROOT", "/home/ubuntu/wechat-publisher/site"))
DATA_DIR = SITE_ROOT / "data"
WX_API = "https://api.weixin.qq.com/cgi-bin"
APPID = env_vars.get("WECHAT_APPID", "")
SECRET = env_vars.get("WECHAT_SECRET", "")
SITE_URL = env_vars.get("SITE_URL", "https://spacenetx.com")

print("=" * 60)
print("微信推送脚本 (Final v2 with Cover)")
print("=" * 60)

print("\n[1/5] Getting access_token...")
token_url = WX_API + "/token?grant_type=client_credential&appid=" + APPID + "&secret=" + SECRET
try:
    with urllib.request.urlopen(token_url, timeout=10) as resp:
        token_data = json.loads(resp.read().decode("utf-8"))
        if "access_token" not in token_data:
            print("  FAILED:", token_data)
            sys.exit(1)
        token = token_data["access_token"]
        print("  OK (len: " + str(len(token)) + ")")
except Exception as e:
    print("  ERROR:", e)
    sys.exit(1)

print("\n[2/5] Reading articles.json...")
articles_path = DATA_DIR / "articles.json"
articles = json.loads(articles_path.read_text(encoding="utf-8"))
print("  Total:", len(articles), "articles")

latest = None
for a in sorted(articles, key=lambda x: x.get("date", ""), reverse=True):
    url = str(a.get("url", ""))
    if "articles/" in url:
        latest = a
        break

if not latest:
    print("  ERROR: No article with articles/ in URL!")
    sys.exit(1)

print("  Latest:", latest["title"])
print("  Date:", latest.get("date", "N/A"))

article_url = latest.get("url", "")
match = re.search(r"articles[/\\\\](.+\\.html)", article_url)
if match:
    filename = match.group(1)
else:
    slug = latest.get("id", "") or latest.get("slug", "") or latest["title"][:30].replace("/", "-")
    filename = slug + ".html"

article_file = SITE_ROOT / "articles" / filename
print("  Filename:", filename)
print("  Exists:", article_file.exists())

if not article_file.exists():
    print("\n  Available articles (newest):")
    articles_dir = SITE_ROOT / "articles"
    if articles_dir.exists():
        for f in sorted(articles_dir.glob("*.html"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
            print("   ", f.name)
    sys.exit(1)

print("\n[3/5] Processing cover image...")
thumb_media_id = ""
try:
    from PIL import Image, ImageDraw
    W, H = 540, 360
    img = Image.new("RGB", (W, H), "#0a0a1a")
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W-1, 60], fill="#e11d48")
    draw.text((20, 15), "AI投研日报", fill="white")
    draw.text((20, 80), latest["title"][:30], fill="#ffffff")
    dt = latest.get("date", "2026-06-15")
    draw.text((20, H-40), dt, fill="#cccccc")
    draw.text((20, H-20), "spacenetx.com", fill="#888888")
    tmp_cover = "/tmp/wechat-cover.jpg"
    img.save(tmp_cover, "JPEG", quality=85)
    print("  Cover generated:", tmp_cover)

    cover_url = WX_API + "/media/upload?access_token=" + token + "&type=image"
    with open(tmp_cover, "rb") as cf:
        boundary = b"demo-boundary-" + str(random.randint(0, 999999)).encode()
        body = b"--" + boundary + b"\r\n"
        body += b"Content-Disposition: form-data; name=\"media\"; filename=\"cover.jpg\"\r\n"
        body += b"Content-Type: image/jpeg\r\n\r\n"
        body += cf.read() + b"\r\n"
        body += b"--" + boundary + b"--\r\n"
    req = urllib.request.Request(cover_url, data=body, headers={"Content-Type": "multipart/form-data; boundary=" + boundary.decode()})
    with urllib.request.urlopen(req, timeout=15) as resp:
        up_result = json.loads(resp.read().decode("utf-8"))
        if up_result.get("media_id"):
            thumb_media_id = up_result["media_id"]
            print("  Cover uploaded! media_id:", thumb_media_id[:20])
        else:
            print("  Cover upload failed:", up_result)
except ImportError:
    print("  [WARN] Pillow not available")
except Exception as e:
    print("  [WARN] Cover failed:", e)

import random
if not thumb_media_id:
    print("  Using blank thumb_media_id")

print("\n[4/5] Extracting article content...")
raw_html = article_file.read_text(encoding="utf-8")
print("  Raw HTML:", len(raw_html), "chars")

html = re.sub(r"<style>.*?</style>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
html = re.sub(r"<p[^>]*class=[^>]*back-link[^>]*>.*?</p>", "", html, flags=re.DOTALL | re.IGNORECASE)
html = re.sub(r"<(?:nav|footer)[^>]*>.*?</(?:nav|footer)>", "", html, flags=re.DOTALL | re.IGNORECASE)

body = None
m = re.search(r"<div[^>]*class=[^"]*article-content[^"]*[^>]*>(.*?)</div>", html, re.DOTALL)
if m: body = m.group(1); print("  Extracted via: .article-content div")

if not body:
    m = re.search(r"<main[^>]*>(.*?)</main>", html, re.DOTALL)
    if m: body = m.group(1); print("  Extracted via: <main> tag")

if not body:
    m = re.search(r"<article[^>]*>(.*?)</article>", html, re.DOTALL)
    if m: body = m.group(1); print("  Extracted via: <article> tag")

if not body:
    m = re.search(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.IGNORECASE)
    if m: body = m.group(1); print("  Extracted via: <body> tag")

if not body: body = html; print("  Extracted: full HTML (fallback)")

body = "<section style=\"padding: 8px; line-height: 1.8; font-family: -apple-system, BlinkMacSystemFont, sans-serif;\">
" + body.strip() + "
</section>"
print("  Body length:", len(body), "chars")

print("\n[5/5] Creating draft...")
slug_for_url = filename.replace(".html", "")
content_source_url = SITE_URL + "/articles/" + slug_for_url + ".html"

payload = {
    "articles": [{
        "title": latest["title"],
        "author": "无缘的人",
        "digest": latest.get("excerpt", latest.get("desc", latest["title"][:54])),
        "content": body,
        "content_source_url": content_source_url,
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }]
}

print("  Title:", payload["articles"][0]["title"][:40])
print("  Content URL:", content_source_url)
print("  Thumb media_id:", thumb_media_id[:20] if thumb_media_id else "(none)")

payload_json = json.dumps(payload, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(
    WX_API + "/draft/add?access_token=" + token,
    data=payload_json,
    headers={"Content-Type": "application/json"}
)

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        if result.get("media_id"):
            mid = result["media_id"]
            print("\n=========================================")
            print("  SUCCESS! media_id:", mid[:40])
            print("=========================================")
            print("\n  稿件已在草稿箱！")
            print("  1. 打开 https://mp.weixin.qq.com")
            print("  2. 检查草稿箱")
            print("  3. 预览并发布")
            if not thumb_media_id:
                print("  注意: 请在后台手动选择封面图")
        else:
            print("\n  FAILED!")
            print("  errcode:", result.get("errcode"))
            print("  errmsg:", result.get("errmsg"))
            print("\n  Content sample:")
            print(body[:800])
except urllib.error.HTTPError as e:
    print("\n  HTTP Error", e.code, e.reason)
    try:
        print("  Response:", e.read().decode("utf-8"))
    except: pass
except Exception as e:
    print("\n  Error:", type(e).__name__, e)
