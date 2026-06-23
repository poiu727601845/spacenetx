#!/usr/bin/env python3
"""
微信自动推送 — 按用户确认的新提示词模板生成文章并推送
执行方式: python3 wp-new-template.py
"""
import json, os, sys, re, urllib.request, urllib.error, random, hashlib, datetime, base64
from pathlib import Path

# ── 配置 ──
ENV_FILE = Path("/home/ubuntu/wechat-publisher/.env")
ENV = {}
with open(ENV_FILE, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            ENV[k.strip()] = v.strip()

SITE_ROOT = Path(ENV.get("SITE_ROOT", "/home/ubuntu/wechat-publisher/site"))
DATA_DIR = SITE_ROOT / "data"
WX_API = "https://api.weixin.qq.com/cgi-bin"
APPID = ENV.get("WECHAT_APPID", "")
SECRET = ENV.get("WECHAT_SECRET", "")
SITE_URL = ENV.get("SITE_URL", "https://spacenetx.com")
DS_API_KEY = ENV.get("DS_API_KEY", "sk-2d2b6f8f1d354828966faba35899eada")

# ── 工具函数 ──
def wx_get_token():
    url = WX_API + "/token?grant_type=client_credential&appid=" + APPID + "&secret=" + SECRET
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            d = json.loads(resp.read().decode("utf-8"))
            return d["access_token"]
    except Exception as e:
        print("  ERROR Token:", e)
        sys.exit(1)

def ds_chat(messages, temp=0.8, max_tok=4000):
    payload = json.dumps({
        "model": "deepseek-v4-flash",
        "messages": messages,
        "temperature": temp,
        "max_tokens": max_tok,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=payload, method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + DS_API_KEY,
        },
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"].strip()

def upload_cover(title):
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (540, 360), "#0a0a1a")
        dr = ImageDraw.Draw(img)
        dr.rectangle([0, 0, 539, 59], fill="#e11d48")
        dr.text((20, 15), "AI投研日报", fill="white")
        dr.text((20, 80), title[:30], fill="white")
        dr.text((20, 320), datetime.date.today().isoformat(), fill="#aaaaaa")
        dr.text((20, 340), "spacenetx.com", fill="#888888")
        cp = "/tmp/wx-cover.jpg"
        img.save(cp, "JPEG", quality=85)

        cu = WX_API + "/material/add_material?access_token=" + token + "&type=image"
        with open(cp, "rb") as cf:
            bn = b"boundary-" + str(random.randint(0, 999999)).encode()
            bd = b"--" + bn + b"\r\n"
            bd += b'Content-Disposition: form-data; name="media"; filename="cover.jpg"\r\n'
            bd += b"Content-Type: image/jpeg\r\n\r\n"
            bd += cf.read() + b"\r\n--" + bn + b"--\r\n"
        rq = urllib.request.Request(cu, data=bd, headers={"Content-Type": "multipart/form-data; boundary=" + bn.decode()})
        with urllib.request.urlopen(rq, timeout=15) as rp:
            ur = json.loads(rp.read().decode("utf-8"))
            if ur.get("media_id"):
                return ur["media_id"]
            return ""
    except ImportError:
        print("  [WARN] Pillow 未安装")
        return ""
    except Exception as e:
        print("  [WARN] 封面失败:", e)
        return ""

# ── 主流程 ──
print("=" * 60)
print("A股投研日报 — 微信自动推送 (New Template)")
print("=" * 60)
print()

# Step 1: Token
print("[1/5] 获取 access_token ...")
token = wx_get_token()
print("  OK (len=" + str(len(token)) + ")")

# Step 2: Dynamic topic selection
print("\n[2/5] 生成选题 (DeepSeek V4) ...")

fp = SITE_ROOT / "data" / "portfolio.json"
portfolio = {}
if fp.exists():
    portfolio = json.loads(fp.read_text(encoding="utf-8"))

holdings = [h for h in portfolio.get("holdings", []) if h.get("status") == "持有"]
fund_names = "、".join([h["name"] + "(" + h["code"] + ")" for h in holdings])
watch = portfolio.get("watch_list", [])
watch_list = "、".join([w.get("name", "") for w in watch])

today_str = datetime.date.today().isoformat()
json_sample = '{{"direction":"选题方向", "title":"25字标题", "subtitle":"副标题", "summary":"70字摘要", "tags":["标签1","标签2"], "readTime":"3-5分钟", "keywords":"关键词"}}'

system_topic = "你是专业的A股市场投研分析师，当前日期是" + today_str + "。\n"
system_topic += "任务：从以下主题中选择一个最值得写的方向。\n\n"
system_topic += "可用持仓基金：" + (fund_names if fund_names else "无") + "\n"
system_topic += "关注池：" + (watch_list if watch_list else "无") + "\n\n"
system_topic += "输出 JSON 格式：\n"
system_topic += json_sample + "\n\n"
system_topic += "选题方向候选：\n"
system_topic += "1. 今日市场复盘 + 明日策略\n"
system_topic += "2. ETF深度评测（结合持仓基金）\n"
system_topic += "3. 资金流向解读（北向/主力/机构）\n"
system_topic += "4. 板块轮动分析（识别下一个风口）\n"
system_topic += "5. 持仓基金深度分析\n"
system_topic += "6. 行业深度解读（半导体/AI/电网/消费等）"

topic_resp = ds_chat([{"role": "user", "content": system_topic}], temp=0.9, max_tok=500)
topic_resp = re.sub(r"```json\s*", "", topic_resp)
topic_resp = re.sub(r"```\s*", "", topic_resp)
try:
    topic = json.loads(topic_resp)
except:
    topic = {
        "direction": "今日市场复盘 + 明日策略",
        "title": datetime.date.today().strftime("%m/%d") + " A股投研日报",
        "subtitle": "",
        "summary": "今日A股市场复盘与投资策略分析",
        "tags": ["投资策略"],
        "readTime": "5分钟",
        "keywords": "A股,ETF,投资"
    }

print("  OK 选题:", topic["title"])
print("     方向:", topic["direction"])
print("     摘要:", topic.get("summary", ""))

# Step 3: Generate article content
print("\n[3/5] 生成文章正文 (DeepSeek V4) ...")

article_system = "你是一个专业的A股市场投研分析师，具备深厚金融知识和行业洞察力。\n"
article_system += "当前年份是2026年，所有内容必须基于2026年市场背景，禁止出现2025年或更早年份的表述。\n"
article_system += "输出仅文章正文HTML（不含html/head/body包裹）。\n\n"
article_system += "格式要求：\n"
article_system += "- h2 二级标题\n- h3 三级标题\n- p 段落（每段不超过150字）\n"
article_system += "- strong 重点内容加粗\n- ul/li 列表\n- table 表格\n"
article_system += "- K线、均线等专业术语准确使用\n"
article_system += "- 文章总长度900-1500字（含标点）\n"
article_system += "- 数据必须标注来源（如数据来源：东方财富）\n\n"
article_system += "合规红线：\n"
article_system += "1. 不预测具体股价（禁止明天涨到3500点）\n"
article_system += "2. 不明确推荐个股（只分析行业/板块）\n"
article_system += "3. 文末必须有固定免责声明\n"
article_system += "4. 禁用暴涨崩盘千股跌停赶紧买必涨等夸张情绪化词汇\n"

dir_val = topic.get("direction", "今日市场复盘")
title_val = topic.get("title", "投研日报")
subtitle_val = topic.get("subtitle", title_val)
summary_val = topic.get("summary", "")
keywords_val = topic.get("keywords", "")

article_user = "请为以下选题写一篇完整的A股投研深度分析文章：\n\n"
article_user += "方向：" + dir_val + "\n"
article_user += "标题：" + title_val + "\n"
article_user += "副标题：" + subtitle_val + "\n"
article_user += "摘要：" + summary_val + "\n"
article_user += "关键词：" + keywords_val + "\n"
article_user += "当前持仓：" + (fund_names if fund_names else "暂无持仓") + "\n"
article_user += "关注池：" + (watch_list if watch_list else "暂无") + "\n\n"
article_user += "文章结构（严格遵循）：\n\n"
article_user += "【今日市场复盘】（约150字）\n"
article_user += "- 大盘表现（上证/深证/创业板涨跌幅）\n"
article_user += "- 成交量对比（较昨日变化）\n"
article_user += "- 市场情绪（涨跌家数、涨停板数量）\n"
article_user += "- 引用最新真实数据\n\n"
article_user += "【资金流向深度解读】（约200字）\n"
article_user += "- 北向资金净流入/流出（东方财富/同花顺数据）\n"
article_user += "- 主力资金流向（行业/板块）\n"
article_user += "- 关键信号分析（3句话以内）\n\n"
article_user += "【深度分析】（约400-600字）\n"
article_user += "- 选取1-2个重点方向深入分析\n"
article_user += "- 产业链逻辑阐述\n"
article_user += "- 估值水平（PE/PB分位数）\n"
article_user += "- 催化因素（政策/业绩/资金面）\n"
article_user += "- 如有关联持仓基金，重点分析\n\n"
article_user += "【投资策略建议】（约150-200字）\n"
article_user += "- 短期策略（1-3天）\n"
article_user += "- 中期策略（1-2周）\n"
article_user += "- 操作要点总结（3条以内）\n\n"
article_user += "【免责声明】（必须保留以下原文）\n"
article_user += "本文内容仅供学习交流和投资研究参考，不构成任何投资建议。股市有风险，投资需谨慎。"

body_html = ds_chat(
    [
        {"role": "system", "content": article_system},
        {"role": "user", "content": article_user},
    ],
    temp=0.8, max_tok=4000
)

body_html = re.sub(r"^```html\s*", "", body_html)
body_html = re.sub(r"\s*```$", "", body_html)
body_html = body_html.strip()

print("  OK 正文:", len(body_html), "字符")

# Step 4: Generate cover
print("\n[4/5] 生成并上传封面图 ...")
thumb_media_id = upload_cover(topic["title"])
if thumb_media_id:
    print("  OK 封面上传成功:", thumb_media_id[:30])
else:
    print("  封面未上传")

# Step 5: Save article + Create draft
print("\n[5/5] 创建草稿 ...")

today = datetime.date.today().strftime("%Y-%m-%d")
slug_hash = hashlib.md5(topic["title"].encode("utf-8")).hexdigest()[:8]
article_id = slug_hash + "-" + today
filename = article_id + ".html"

# Build full page HTML
today_iso = datetime.date.today().isoformat()
title_safe = topic["title"].replace('"', "&quot;")
content_source_url = SITE_URL + "/articles/" + article_id + ".html"

full_html = '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
full_html += '<meta charset="UTF-8">\n'
full_html += '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
full_html += '<title>' + title_safe + ' | A股投研工具箱</title>\n'
full_html += '<meta name="description" content="' + summary_val + '">\n'
full_html += '<meta name="keywords" content="' + keywords_val + '">\n'
full_html += '<meta name="author" content="无缘的人">\n'
full_html += '<meta property="og:title" content="' + title_safe + '">\n'
full_html += '<meta property="og:description" content="' + summary_val + '">\n'
full_html += '<meta property="og:url" content="' + content_source_url + '">\n'
full_html += '<style>\n'
full_html += ':root{--bg:#0f0f1a;--bg2:#1a1a2e;--bg3:#252540;--text:#e8e8f0;--text2:#8888aa;'
full_html += '--accent:#e11d48;--accent2:#f97316;--border:#2a2a3e;}\n'
full_html += 'body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;'
full_html += 'background:var(--bg);color:var(--text);margin:0;line-height:1.8;}\n'
full_html += '.container{max-width:780px;margin:0 auto;padding:24px 16px;}\n'
full_html += '.article-header{text-align:center;padding:32px 0 24px;border-bottom:1px solid var(--border);margin-bottom:24px;}\n'
full_html += '.article-title{font-size:26px;font-weight:700;color:#fff;margin:0 0 12px;line-height:1.4;}\n'
full_html += '.article-meta{color:var(--text2);font-size:14px;display:flex;justify-content:center;gap:16px;flex-wrap:wrap;}\n'
full_html += '.article-body{font-size:16px;line-height:1.9;}\n'
full_html += '.article-body h2{color:var(--accent);font-size:20px;border-left:3px solid var(--accent);padding-left:12px;margin:28px 0 16px;}\n'
full_html += '.article-body h3{color:var(--accent2);font-size:17px;margin:20px 0 12px;}\n'
full_html += '.article-body p{margin:0 0 16px;text-align:justify;}\n'
full_html += '.article-body strong{color:var(--accent);}\n'
full_html += '.article-body table{width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;}\n'
full_html += '.article-body th{background:var(--bg3);padding:10px 12px;border:1px solid var(--border);}\n'
full_html += '.article-body td{padding:10px 12px;border:1px solid var(--border);}\n'
full_html += '.tag{background:var(--bg2);color:var(--accent);padding:4px 12px;border-radius:20px;font-size:13px;border:1px solid var(--border);}\n'
full_html += '.back-link{text-align:center;margin:32px 0 16px;}\n'
full_html += '.back-link a{color:var(--accent);text-decoration:none;}\n'
full_html += '.article-source{background:var(--bg2);padding:12px 16px;border-radius:8px;margin-top:20px;font-size:13px;color:var(--text2);}\n'
full_html += '</style>\n</head>\n<body>\n<div class="container">\n'
full_html += '<div class="article-header">\n'
full_html += '<h1 class="article-title">' + title_safe + '</h1>\n'
full_html += '<div class="article-meta">\n'
full_html += '<span>' + today + '</span>\n'
full_html += '<span>' + topic.get("readTime", "5分钟") + '</span>\n'
full_html += '<span>无缘的人</span>\n'
full_html += '</div></div>\n'
full_html += '<div class="article-body">\n' + body_html + '\n</div>\n'
full_html += '<div class="article-source">数据来源：东方财富、同花顺、Wind/Choice。以上数据仅供参考，不构成投资建议。</div>\n'
full_html += '<div style="margin-top:24px;display:flex;gap:8px;flex-wrap:wrap;">\n'
for t in topic.get("tags", ["A股", "ETF"]):
    full_html += '<span class="tag">' + t + '</span>\n'
full_html += '</div>\n'
full_html += '<div class="back-link"><a href="/">返回首页</a></div>\n'
full_html += '</div>\n</body></html>'

# Save article
articles_dir = SITE_ROOT / "articles"
articles_dir.mkdir(parents=True, exist_ok=True)
article_path = articles_dir / filename
article_path.write_text(full_html, encoding="utf-8")
print("  OK 文章已保存:", filename)

# Build WeChat draft payload
wechat_body = '<section style="padding: 8px; line-height: 1.8; font-family: -apple-system, BlinkMacSystemFont, sans-serif;">\n'
wechat_body += body_html.strip() + '\n</section>'

payload = {
    "articles": [{
        "title": topic["title"],
        "author": "无缘的人",
        "digest": topic.get("summary", topic["title"][:54]),
        "content": wechat_body,
        "content_source_url": content_source_url,
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }]
}

print("  标题:", payload["articles"][0]["title"][:40])
print("  URL:", content_source_url)
print("  封面:", thumb_media_id[:30] if thumb_media_id else "(无)")

payload_json = json.dumps(payload, ensure_ascii=False).encode("utf-8")
req = urllib.request.Request(
    WX_API + "/draft/add?access_token=" + token,
    data=payload_json,
    headers={"Content-Type": "application/json"},
)

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        if result.get("media_id"):
            mid = result["media_id"]
            print()
            print("=" * 50)
            print("  SUCCESS! 推送成功")
            print("  标题:", topic["title"])
            print("  草稿ID:", mid[:40])
            print("  URL:", content_source_url)
            print("=" * 50)
            print("\n  下一步:")
            print("  1. 打开 https://mp.weixin.qq.com")
            print("  2. 草稿箱 -> 预览并发布")
            if not thumb_media_id:
                print("  3. 封面图未上传，请手动选择")
        else:
            print("\n  FAILED!")
            print("  errcode:", result.get("errcode"))
            print("  errmsg:", result.get("errmsg"))
except urllib.error.HTTPError as e:
    print("\n  HTTP Error", e.code, e.reason)
    try:
        print("  Response:", e.read().decode("utf-8"))
    except:
        pass
except Exception as e:
    print("\n  Error:", type(e).__name__, str(e))
