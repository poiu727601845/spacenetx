#!/usr/bin/env python3
"""
微信公众号自动发布脚本（直连版，不走代理）
用法: python scripts/wechat_publish.py [--publish] [--article article-xxx.html]

环境变量:
  WECHAT_APPID      微信公众号 AppID
  WECHAT_SECRET     微信公众号 AppSecret
  SITE_URL          站点地址
"""

import json, sys, os, re, argparse, io, urllib.request, urllib.parse, tempfile
from pathlib import Path
from datetime import datetime

# ── 加载 .env 文件 ─────────────────────────────────
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass

SITE_ROOT  = Path(os.environ.get("SITE_ROOT", str(Path(__file__).parent.parent / "site")))
DATA_DIR   = SITE_ROOT / "data"
SITE_URL   = os.environ.get("SITE_URL", "https://spacenetx.com")

APPID   = os.environ.get("WECHAT_APPID", "")
SECRET  = os.environ.get("WECHAT_SECRET", "")

WX_API = "https://api.weixin.qq.com/cgi-bin"

# ── 依赖检查 ────────────────────────────────────────
try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# ── 工具 ────────────────────────────────────────────

def wx_get(path, params=None):
    """GET 请求微信 API"""
    url = WX_API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"errcode": -1, "errmsg": str(e)}


def wx_post(path, data, params=None):
    """POST 请求微信 API（JSON）"""
    url = WX_API + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    body = json.dumps(data, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else "{}"
        return {"errcode": e.code, "errmsg": err_body}
    except Exception as e:
        return {"errcode": -1, "errmsg": str(e)}


def wx_upload_image(token, image_path):
    """上传永久素材（封面图），返回 media_id"""
    import mimetypes
    url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=image"
    filename = os.path.basename(image_path)
    mime = mimetypes.guess_type(image_path)[0] or "image/jpeg"

    boundary = "WxBoundary12345"
    with open(image_path, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else "{}"
        return {"errcode": e.code, "errmsg": err_body}
    except Exception as e:
        return {"errcode": -1, "errmsg": str(e)}


def get_access_token():
    """直接获取 access_token"""
    print("[1/3] 获取 access_token ...")
    resp = wx_get("/token", {
        "grant_type": "client_credential",
        "appid": APPID,
        "secret": SECRET,
    })
    if "errcode" in resp and resp["errcode"] != 0:
        print(f"  [FAIL] access_token 失败\n  errcode: {resp.get('errcode')}\n  errmsg: {resp.get('errmsg')}")
        sys.exit(1)
    token = resp.get("access_token", "")
    if not token:
        print(f"  [FAIL] 返回内容异常: {resp}")
        sys.exit(1)
    print(f"  [OK] token 获取成功 ({len(token)} 字符)")
    return token


# ── 封面图 ──────────────────────────────────────────

def make_cover(text, date_str, save_path):
    """生成 900×500 封面图"""
    if not HAS_PIL:
        print("  [WARN] 缺少 Pillow，跳过封面图生成")
        return None
    img = Image.new("RGB", (900, 500), "#0d1b2a")
    draw = ImageDraw.Draw(img)

    font_paths = [
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "C:/Windows/Fonts/msyh.ttc",
    ]
    font = None
    for fp in font_paths:
        try:
            font = ImageFont.truetype(fp, 48)
            break
        except Exception:
            pass
    if font is None:
        font = ImageFont.load_default()

    draw.rectangle([0, 0, 900, 8], fill="#1b2838")
    draw.rectangle([0, 492, 900, 500], fill="#1b2838")

    y = 160
    for line in text[:20]:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (900 - w) // 2
        draw.text((x, y), line, fill="#ffffff", font=font)
        y += 70

    draw.text((350, 420), f"{date_str}", fill="#8da3b8", font=font)
    img.save(save_path, "JPEG", quality=90)
    return save_path


# ── HTML 清理 ───────────────────────────────────────

def clean_html(raw_html):
    """清理 HTML 适配微信图文格式：去广告/去免责声明/去订阅框/去相关文章"""
    text = raw_html

    # 1. 移除不可见区域
    text = re.sub(r'(?s)<!DOCTYPE.*?>', '', text)
    text = re.sub(r'(?s)<html[^>]*>', '', text)
    text = re.sub(r'(?s)</html>', '', text)
    text = re.sub(r'(?s)<head>.*?</head>', '', text)
    text = re.sub(r'(?s)<script[^>]*>.*?</script>', '', text)
    text = re.sub(r'(?s)<style[^>]*>.*?</style>', '', text)

    # 2. 移除结构性干扰元素
    text = re.sub(r'<body[^>]*>', '<section>', text)
    text = text.replace('</body>', '</section>')
    text = re.sub(r'(?s)<nav[^>]*>.*?</nav>', '', text)
    text = re.sub(r'(?s)<footer[^>]*>.*?</footer>', '', text)
    text = re.sub(r'(?s)<aside[^>]*>.*?</aside>', '', text)

    # 3. 移除广告位（ad-top / ad-inline）
    text = re.sub(r'(?s)<div[^>]*class="[^"]*ad-top[^"]*"[^>]*>.*?</div>', '', text)
    text = re.sub(r'(?s)<div[^>]*class="[^"]*ad-inline[^"]*"[^>]*>.*?</div>', '', text)
    text = re.sub(r'(?s)<div[^>]*class="[^"]*ad-banner[^"]*"[^>]*>.*?</div>', '', text)

    # 4. 移除免责声明
    text = re.sub(r'(?s)<div[^>]*class="[^"]*disclaimer[^"]*"[^>]*>.*?</div>', '', text)

    # 5. 移除订阅框
    text = re.sub(r'(?s)<div[^>]*class="[^"]*subscribe-box[^"]*"[^>]*>.*?</div>', '', text)
    text = re.sub(r'(?s)<div[^>]*class="[^"]*subscribe-form[^"]*"[^>]*>.*?</div>', '', text)

    # 6. 移除相关文章区块
    text = re.sub(r'(?s)<div[^>]*class="[^"]*related[^"]*"[^>]*>.*?</div>', '', text)
    text = re.sub(r'(?s)<div[^>]*class="[^"]*related-articles[^"]*"[^>]*>.*?</div>', '', text)

    # 7. 移除"查看原始来源"等外链
    text = re.sub(r'(?s)<a[^>]*class="[^"]*source-link[^"]*"[^>]*>.*?</a>', '', text)
    text = re.sub(r'(?s)<a[^>]*href=[^>]*>.*?[查看原始来源|阅读原文|查看原文].*?</a>', '', text)

    # 8. 移除文章末尾固定的免责声明段落（纯文本匹配）
    text = re.sub(r'<p><strong>本文内容仅供学习参考，不构成投资建议，投资有风险，决策请做独立研究。</strong></p>', '', text)

    # 9. 移除 img（微信不支持外链图片）
    text = re.sub(r'<img[^>]+>', '', text)

    # 10. 清理多余属性（id / style / class 等）
    text = re.sub(r'\sid="[^"]*"', '', text)
    text = re.sub(r'\sstyle="[^"]*"', '', text)
    text = re.sub(r'\sclass="[^"]*"', '', text)
    text = re.sub(r'\starget="[^"]*"', '', text)
    text = re.sub(r'\srel="[^"]*"', '', text)

    # 11. 清理多余空白
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'>\s+<', '><', text)

    return text.strip()


def extract_title(html_path):
    content = html_path.read_text(encoding="utf-8")
    m = re.search(r'<title>(.*?)</title>', content)
    return m.group(1).strip() if m else html_path.stem


def make_summary_card(h2_titles):
    """生成「文章要点总结」卡片（插在第2个h2后）"""
    # 只取前3个h2作为要点预览
    items = ''.join(
        f'<p style="margin:6px 0;color:#ccc;font-size:13px;line-height:1.8;">'
        f'　　• {t}</p>'
        for t in h2_titles[:3]
    )
    return (
        '<section style="margin:28px 0;padding:20px 24px;'
        'background:#0d0d10;border-left:4px solid #e11d48;border-radius:0 12px 12px 0;">'
        '<p style="margin:0 0 12px;color:#e11d48;font-size:14px;font-weight:700;">'
        '📌 本文要点</p>'
        f'{items}'
        '<p style="margin:14px 0 0;color:#888;font-size:12px;">'
        '　　「无缘的人」——每天一篇A股ETF深度复盘 ↑</p>'
        '</section>'
    )


def make_preview_card():
    """生成「下期预告 + 关注引导」卡片（插在末尾前）"""
    return (
        '<section style="margin:28px 0;padding:20px 24px;'
        'background:linear-gradient(135deg,#1a1a2e,#16213e);'
        'border:1px solid #333;border-radius:12px;">'
        '<p style="margin:0 0 8px;color:#f59e0b;font-size:14px;font-weight:700;">'
        '🔮 下期预告</p>'
        '<p style="margin:0 0 12px;color:#ccc;font-size:13px;line-height:1.8;">'
        '下一期将展开：<strong style="color:#f59e0b;">电网ETF（025832）'
        ' vs 半导体ETF（007300）</strong>'
        '——同样的价格信号框架，实战测算加仓时机。</p>'
        '<p style="margin:0;color:#22c55e;font-size:13px;">'
        '👉 关注公众号，不错过每次信号</p>'
        '</section>'
    )


def extract_content(html_path):
    """提取正文，并自动插入：要点总结卡 + 下期预告卡"""
    content = html_path.read_text(encoding="utf-8")

    # 1. 优先提取 .article-content
    m = re.search(r'(?s)<div[^>]*class="[^"]*article-content[^"]*"[^>]*>(.*?)</div>', content)
    if not m:
        m = re.search(r'(?s)<main[^>]*>(.*?)</main>', content)
    if not m:
        m = re.search(r'(?s)<article[^>]*>(.*?)</article>', content)
    if not m:
        m = re.search(r'(?s)<body[^>]*>(.*?)</body>', content)
    if not m:
        return clean_html(content)

    body = m.group(1)

    # 2. 提取 h2 标题列表（用于要点总结卡）
    h2_titles = re.findall(r'<h2[^>]*>(.*?)</h2>', body)
    # 去掉 h2 内部可能的 <span> 等标签
    h2_titles = [re.sub(r'<[^>]+>', '', t).strip() for t in h2_titles]

    # 3. 清洗 HTML
    body = clean_html(body)

    # 4. 重新提取清洗后的 h2 分隔片段
    parts = re.split(r'(<h2[^>]*>.*?</h2>)', body)
    # parts = [文字, h2, 文字, h2, 文字, ...]

    summary_card = make_summary_card(h2_titles)
    preview_card = make_preview_card()

    insert_at = []
    if len(parts) >= 5:
        insert_at.append(3)   # 第2个h2之后 → 要点总结
    if len(parts) >= 7:
        insert_at.append(len(parts) - 2)  # 倒数第2个h2之后 → 下期预告
    else:
        insert_at.append(len(parts) - 1)  # 末尾前

    if insert_at:
        for idx in sorted(set(insert_at), reverse=True):
            if 0 <= idx < len(parts):
                card = preview_card if idx == max(insert_at) else summary_card
                parts.insert(idx, card)
        body = ''.join(parts)
    else:
        mid = len(body) // 2
        body = body[:mid] + summary_card + body[mid:] + preview_card

    return body.strip()


# ── 主流程 ──────────────────────────────────────────

def push_draft(article_path=None):
    if not APPID or not SECRET:
        print("[WARN] 未配置 WECHAT_APPID / WECHAT_SECRET，跳过公众号发布")
        return False

    print(f"\n{'='*50}")
    print(f"微信公众号自动发布（直连版）")
    print(f"站点: {SITE_URL}")
    print(f"{'='*50}\n")

    # 1) 获取 access_token
    token = get_access_token()

    # 2) 获取文章
    if article_path:
        article_file = Path(article_path)
    else:
        articles_json = DATA_DIR / "articles.json"
        if not articles_json.exists():
            print("[FAIL] articles.json 不存在")
            return False
        data = json.loads(articles_json.read_text(encoding="utf-8"))
        if not data:
            print("[FAIL] articles.json 为空")
            return False
        latest = max(data, key=lambda a: a.get("date", ""))
        slug = latest.get("id", "") or latest.get("slug", "")
        article_file = SITE_ROOT / "articles" / f"{slug}.html"
        if not article_file.exists():
            print(f"[FAIL] 文章文件不存在: {article_file}")
            return False

    title = extract_title(article_file)
    body = extract_content(article_file)
    print(f"[2/3] 准备文章: {title}")
    print(f"  文件: {article_file.name}")
    print(f"  正文长度: {len(body)} 字符")

    # 2b) 封面图（可选）
    thumb_media_id = ""
    if HAS_PIL:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            cover_path = tmp.name
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            make_cover(title, today, cover_path)
            print("  [IMG] 封面图生成成功，上传中 ...")
            up_resp = wx_upload_image(token, cover_path)
            if up_resp.get("media_id"):
                thumb_media_id = up_resp["media_id"]
                print(f"  [OK] 封面图上传成功，media_id: {thumb_media_id}")
            else:
                print(f"  [WARN] 封面图上传失败: {up_resp}，继续（无封面）")
        except Exception as e:
            print(f"  [WARN] 封面图处理失败: {e}，继续（无封面）")
        finally:
            try:
                os.unlink(cover_path)
            except Exception:
                pass

    # 3) 创建草稿
    print("[3/3] 创建微信公众号草稿 ...")

    articles_payload = [{
        "title": title,
        "author": "无缘的人",
        "digest": title[:54],
        "content": body,
        "content_source_url": f"{SITE_URL}/articles/{article_file.stem}.html",
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }]

    resp = wx_post("/draft/add", {"articles": articles_payload},
                   params={"access_token": token})

    if resp.get("errcode"):
        print(f"  [FAIL] 创建草稿失败\n  errcode: {resp.get('errcode')}\n  errmsg: {resp.get('errmsg')}")
        return False

    draft_id = resp.get("media_id", "unknown")
    print(f"  [OK] 草稿创建成功！media_id: {draft_id}")
    print(f"\n{'='*50}")
    print(f"请去 mp.weixin.qq.com → 草稿箱查看并发布")
    print(f"{'='*50}")
    return True


# ── CLI ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="微信公众号草稿推送")
    parser.add_argument("--article", help="指定文章 HTML 文件路径")
    parser.add_argument("--publish", action="store_true", help="直接发布（默认只创建草稿）")
    args = parser.parse_args()

    if args.publish:
        print("[WARN] --publish 暂不支持，默认只创建草稿")

    success = push_draft(args.article)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
