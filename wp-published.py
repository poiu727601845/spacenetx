#!/usr/bin/env python3
"""WeChat Official Account Push Script - Final Version"""
import json, os, sys, re, urllib.request, urllib.error, random
from pathlib import Path

# Read .env
env_path = Path("/home/ubuntu/wechat-publisher/.env")
env_vars = {}
with open(env_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            env_vars[k.strip()] = v.strip()

SITE_ROOT = Path(env_vars.get("SITE_ROOT", "/home/ubuntu/wechat-publisher/site"))
DATA_DIR = SITE_ROOT / "data"
WX_API = "https://api.weixin.qq.com/cgi-bin"
APPID = env_vars.get("WECHAT_APPID", "")
SECRET = env_vars.get("WECHAT_SECRET", "")
SITE_URL = env_vars.get("SITE_URL", "https://spacenetx.com")

print("=" * 60)
print("WeChat Publish Script v2")
print("=" * 60)

# 1. Get access_token
print("\n[1/5] Getting access_token...")
turl = WX_API + "/token?grant_type=client_credential&appid=" + APPID + "&secret=" + SECRET
try:
    resp = urllib.request.urlopen(turl, timeout=10)
    td = json.loads(resp.read().decode("utf-8"))
    if "access_token" not in td:
        print("  FAIL:", td)
        sys.exit(1)
    token = td["access_token"]
    print("  OK (len:", len(token), ")")
except Exception as e:
    print("  ERROR:", e)
    sys.exit(1)

# 2. Read articles
print("\n[2/5] Reading articles...")
apath = DATA_DIR / "articles.json"
articles = json.loads(apath.read_text(encoding="utf-8"))
print("  Total:", len(articles))

latest = None
for a in sorted(articles, key=lambda x: x.get("date", ""), reverse=True):
    if "articles/" in str(a.get("url", "")):
        latest = a
        break

if not latest:
    print("  No article with articles/ in URL")
    for a in articles[:2]:
        print("   ", a.get("title", ""), a.get("url", ""))
    sys.exit(1)

print("  Latest:", latest["title"][:60])
print("  Date:", latest.get("date", ""))

# Extract filename from url
au = latest.get("url", "")
m2 = re.search(r"articles/(.+\.html)$", au)
if m2:
    fn = m2.group(1)
else:
    s = latest.get("id", "") or latest.get("slug", "") or latest["title"][:30].replace("/", "-")
    fn = s + ".html"

af = SITE_ROOT / "articles" / fn
print("  File:", fn, "Exists:", af.exists())

if not af.exists():
    ad = SITE_ROOT / "articles"
    print("  Available (newest 5):")
    for ff in sorted(ad.glob("*.html"), key=lambda x: x.stat().st_mtime, reverse=True)[:5]:
        print("   ", ff.name)
    sys.exit(1)

# 3. Generate and upload cover image
print("\n[3/5] Cover image...")
tid = ""
try:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (540, 360), "#0a0a1a")
    dr = ImageDraw.Draw(img)
    dr.rectangle([0, 0, 539, 59], fill="#e11d48")
    dr.text((20, 15), "AI投研日报", fill="white")
    dr.text((20, 80), latest["title"][:30], fill="white")
    dt = latest.get("date", "2026-06-15")
    dr.text((20, 320), dt, fill="#aaaaaa")
    dr.text((20, 340), "spacenetx.com", fill="#888888")
    cp = "/tmp/wx-cover.jpg"
    img.save(cp, "JPEG", quality=85)
    print("  Generated:", cp)

    cu = WX_API + "/material/add_material?access_token=" + token + "&type=image"
    with open(cp, "rb") as cf:
        cn = str(random.randint(0, 999999)).encode()
        bn = b"boundary-" + cn
        bd = b"--" + bn + b"\r\n"
        bd += b'Content-Disposition: form-data; name="media"; filename="cover.jpg"\r\n'
        bd += b"Content-Type: image/jpeg\r\n\r\n"
        bd += cf.read() + b"\r\n"
        bd += b"--" + bn + b"--\r\n"
    rq = urllib.request.Request(cu, data=bd, headers={"Content-Type": "multipart/form-data; boundary=" + bn.decode()})
    rp = urllib.request.urlopen(rq, timeout=15)
    ur = json.loads(rp.read().decode("utf-8"))
    if ur.get("media_id"):
        tid = ur["media_id"]
        print("  Cover uploaded! id:", tid[:30])
    else:
        print("  Cover failed:", ur)
except ImportError:
    print("  [WARN] Pillow not installed")
except Exception as e:
    print("  Cover err:", e)

if not tid:
    print("  No cover image")

# 4. Extract article content
print("\n[4/5] Extracting content...")
raw = af.read_text(encoding="utf-8")
html = raw
# Remove style blocks
html = re.sub(r"<style>.*?</style>", "", html, flags=re.DOTALL | re.I)
# Remove script blocks
html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.I)
# Remove nav/footer
html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL | re.I)
html = re.sub(r"<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL | re.I)

body = None

# Try: class="...article-content..."
for mm in re.finditer(r'<div\b[^>]*class\s*=\s*"([^"]*article-content[^"]*)"[^>]*>(.*?)</div>', html, re.DOTALL):
    body = mm.group(2)
    print("  Source: article-content div")
    break

# Try: <main>
if not body:
    for mm in re.finditer(r"<main[^>]*>(.*?)</main>", html, re.DOTALL):
        body = mm.group(1)
        print("  Source: <main>")
        break

# Try: <article>
if not body:
    for mm in re.finditer(r"<article[^>]*>(.*?)</article>", html, re.DOTALL):
        body = mm.group(1)
        print("  Source: <article>")
        break

# Try: <body>
if not body:
    for mm in re.finditer(r"<body[^>]*>(.*?)</body>", html, re.DOTALL | re.I):
        body = mm.group(1)
        print("  Source: <body>")
        break

if not body:
    body = html
    print("  Source: full HTML (fallback)")

# Build wrapped body for WeChat
css_style = "padding: 8px; line-height: 1.8; font-family: -apple-system, BlinkMacSystemFont, sans-serif;"
body_html = '<section style="' + css_style + '">' + body.strip() + '</section>'
print("  Body length:", len(body_html), "chars")

# 5. Create draft
print("\n[5/5] Creating draft...")
sfu = fn.replace(".html", "")
csu = SITE_URL + "/articles/" + sfu + ".html"

payload = {
    "articles": [{
        "title": latest["title"],
        "author": "无缘的人",
        "digest": latest.get("excerpt", latest.get("desc", latest["title"][:54])),
        "content": body_html,
        "content_source_url": csu,
        "thumb_media_id": tid,
        "need_open_comment": 0,
        "only_fans_can_comment": 0
    }]
}

print("  Title:", payload["articles"][0]["title"][:50])
print("  Content URL:", csu)
print("  Thumb:", tid[:30] if tid else "(none)")

pj = json.dumps(payload, ensure_ascii=False).encode("utf-8")
rq2 = urllib.request.Request(
    WX_API + "/draft/add?access_token=" + token,
    data=pj,
    headers={"Content-Type": "application/json"}
)

try:
    rp2 = urllib.request.urlopen(rq2, timeout=15)
    r2 = json.loads(rp2.read().decode("utf-8"))
    if r2.get("media_id"):
        print("\n===============================")
        print("  SUCCESS! media_id:", r2["media_id"][:50])
        print("===============================")
        print("\n  稿件已添加到微信公众号草稿箱！")
        print("  操作步骤：")
        print("  1. 打开 https://mp.weixin.qq.com")
        print("  2. 左侧菜单 -> 草稿箱")
        print("  3. 找到这篇稿件，预览后发布")
        if not tid:
            print("  4. 注意：未上传封面，需在后台手动选择")
    else:
        print("\n  FAILED!")
        print("  errcode:", r2.get("errcode"))
        print("  errmsg:", r2.get("errmsg"))
        print("\n  Content sample (first 800 chars):")
        print("-" * 60)
        print(body_html[:800])
        print("-" * 60)
except urllib.error.HTTPError as e:
    print("\n  HTTP Error:", e.code, e.reason)
    try:
        eb = e.read().decode("utf-8")
        print("  Response:", eb)
    except:
        pass
except Exception as e:
    print("\n  Error:", type(e).__name__, str(e))
