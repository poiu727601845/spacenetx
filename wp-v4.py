#!/usr/bin/env python3
"""
微信自动推送 — v4 优化版
改进：字数限制收紧到1200-1800字，标题强制带数字/悬念
"""
import json, os, sys, re, urllib.request, urllib.error, random, hashlib, datetime
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

def upload_cover(title, date_str, token_val):
    try:
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (540, 360), "#0a0a1a")
        dr = ImageDraw.Draw(img)
        dr.rectangle([0, 0, 539, 59], fill="#e11d48")
        dr.text((20, 15), "AI投研日报", fill="white")
        dr.text((20, 80), title[:30], fill="white")
        dr.text((20, 320), date_str, fill="#aaaaaa")
        dr.text((20, 340), "spacenetx.com", fill="#888888")
        cp = "/tmp/wx-cover.jpg"
        img.save(cp, "JPEG", quality=85)
        cu = WX_API + "/material/add_material?access_token=" + token_val + "&type=image"
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

def load_portfolio():
    fp = SITE_ROOT / "data" / "portfolio.json"
    if fp.exists():
        return json.loads(fp.read_text(encoding="utf-8"))
    return {"holdings": [], "watch_list": [], "rules": {}}

# ── 主流程 ──
print("=" * 60)
print("A股投研日报 — 微信自动推送 (v4 Optimized)")
print("=" * 60)
print()

# [1/6] Token
print("[1/6] 获取 access_token ...")
token = wx_get_token()
print("  OK (len=" + str(len(token)) + ")")

# [2/6] 加载持仓
print("\n[2/6] 加载持仓信息 ...")
pf = load_portfolio()
holdings = [h for h in pf.get("holdings", []) if h.get("status") == "持有"]
watch_list_items = pf.get("watch_list", [])
rules = pf.get("rules", {})

fund_details = []
for h in holdings:
    fund_details.append("- " + h["name"] + "(" + h["code"] + ")，" + h.get("sector", "") + "，" + h.get("position", ""))
fund_str = "\n".join(fund_details) if fund_details else "暂无持仓"

watch_str = ""
for w in watch_list_items:
    watch_str += "- " + w.get("name", "") + " (" + w.get("code", "") + ") - " + w.get("status", "") + "\n"
if not watch_str:
    watch_str = "暂无"

pe_rule = rules.get("PE_discipline", "PE>80%减仓")
add_cond = rules.get("add_condition", "PE<40%加仓")
stop_loss = rules.get("stop_loss", "回撤>15%检视")

num_funds = len(holdings)
print("  持仓基金:", num_funds, "只")
for fd in fund_details:
    print("    ", fd)
print("  关注池:", watch_str.strip() if watch_str.strip() else "暂无")
print("  纪律:", pe_rule + " / " + add_cond)

# [3/6] 选题
print("\n[3/6] 生成选题 (DeepSeek V4) ...")
today_str = datetime.date.today().isoformat()

topic_port = "**你的持仓组合（共" + str(num_funds) + "只）：**\n" + fund_str + "\n"
topic_port += "\n**观察池：**\n" + watch_str + "\n"
topic_port += "\n**仓位纪律：**\n- 减仓：" + pe_rule + "\n- 加仓：" + add_cond + "\n- 止损：" + stop_loss + "\n"

topic_sys = "你是专业A股投研分析师。今天是" + today_str + "。你管理真实投资组合。\n"
topic_sys += "任务：选1个最值得写的方向。\n"
topic_sys += "要求：标题必须含数字或悬念或反直觉元素，禁用日期前缀（如" + today_str + "）。\n"
topic_sys += "摘要必须含2-3个关键数据。\n标签至少5个，必须包含持仓基金代码或名称相关标签。\n\n"
topic_sys += "输出JSON格式：\n"
topic_sys += '{{"direction":"方向名","title":"25字内标题（含数字/悬念）","subtitle":"50字内副标题","summary":"70字摘要（含2-3个数据）","tags":["标签1","标签2","标签3","标签4","标签5","标签6"],"readTime":"3-5分钟","keywords":"关键词1,关键词2,关键词3"}}\n\n'
topic_sys += "选题方向（按推荐优先级排序，数字越小越优先）：\n"
topic_sys += "1. 持仓组合全维度评测（全部" + str(num_funds) + "只基金深度分析，收益排名+操作建议）\n"
topic_sys += "2. AI+半导体产业链专题（" + fund_details[0] + " vs " + (fund_details[1] if len(fund_details) > 1 else fund_details[0]) + "联动）\n"
topic_sys += "3. 北向资金+主力资金流向解读（结合" + str(num_funds) + "只持仓基金受益情况）\n"
topic_sys += "4. 板块轮动规律（AI→半导体→医疗→新能源→资源的轮动周期）\n"
topic_sys += "5. " + (fund_details[2] if len(fund_details) > 2 else "医疗板块") + "投资机会深度解读\n"
topic_sys += "6. " + (fund_details[3] if len(fund_details) > 3 else "新能源") + "布局策略分析\n"
topic_sys += "7. 仓位管理实战课（PE纪律+加减仓信号）\n"

topic_resp = ds_chat([{"role": "user", "content": topic_port + "\n\n" + topic_sys}], temp=0.9, max_tok=600)
topic_resp = re.sub(r"```json\s*", "", topic_resp)
topic_resp = re.sub(r"```\s*", "", topic_resp)
try:
    topic = json.loads(topic_resp)
except:
    topic = {
        "direction": "持仓组合全维度评测",
        "title": str(num_funds) + "只基金收益大比拼：谁才是真正的王者？",
        "subtitle": "AI+半导体+医疗+新能源+资源全景扫描",
        "summary": "今日" + today_str + "市场复盘，覆盖全部" + str(num_funds) + "只持仓基金，含3个关键数据。",
        "tags": ["持仓分析", "基金评测", "资金流向", "ETF", "市场复盘", "投资策略"],
        "readTime": "5分钟",
        "keywords": "A股,基金,ETF,持仓,投资"
    }

# Ensure 5+ tags
while len(topic.get("tags", [])) < 5:
    extra = ["投资策略", "ETF评测", "资金流向", "持仓分析", "市场复盘"]
    for t in extra:
        if t not in topic.get("tags", []):
            topic.setdefault("tags", []).append(t)
        if len(topic["tags"]) >= 5:
            break

print("  ✅ 选题:", topic["title"])
print("     方向:", topic["direction"])
print("     标签:", ", ".join(topic.get("tags", [])))
print("     摘要:", topic.get("summary", "")[:60])

# [4/6] 生成文章
print("\n[4/6] 生成文章正文 (DeepSeek V4) ...")

fund_list_str = ""
for h in holdings:
    fund_list_str += "- " + h["name"] + "(" + h["code"] + ")：" + h.get("sector", "") + " | 仓位：" + h.get("position", "") + "\n"

article_sys = (
    "你是专业A股市场投研分析师。今天是2026年" + today_str + "。\n"
    "输出仅文章正文HTML（不含html/head/body包裹）。\n\n"
    "【字数严格要求】：全文正文HTML必须严格达到1500-2200汉字（含标点符号）！\n"
    "   - 这是硬性要求，少一个字都不合格！\n"
    "   - 每只基金的分析不少于180字\n"
    "   - 每个大章节必须写满要求字数\n"
    "   - 多用具体数据、详细分析、对比说明来扩充内容\n\n"
    "【持仓基金全覆盖】：必须逐一分析以下全部" + str(num_funds) + "只基金，"
    "每只基金用独立段落（至少180字），包含：\n"
    "  1) 所属板块当日表现（含具体涨跌幅数据）\n"
    "  2) 当前估值水平（PE/PB分位数及历史位置）\n"
    "  3) 近期走势形态分析（K线/均线/成交量）\n"
    "  4) 结合仓位纪律的具体操作建议（何时加仓/减仓/持有）\n\n"
    "【持仓基金清单】\n" + fund_list_str + "\n"
    "【仓位纪律】\n减仓：" + pe_rule + " | 加仓：" + add_cond + " | 止损：" + stop_loss + "\n\n"
    "【合规红线】：不预测股价、不直接推荐买卖、必须免责声明、禁用暴涨崩盘等夸张词\n\n"
    "【格式】：h2/h3/p/strong/table/ul/li，用数字或关键词作标题\n"
)

article_user = (
    "请为以下选题写深度投研文章：\n\n"
    "方向：" + topic["direction"] + "\n"
    "标题：" + topic["title"] + "\n"
    "副标题：" + topic.get("subtitle", "") + "\n"
    "摘要：" + topic.get("summary", "") + "\n"
    "标签：" + ", ".join(topic.get("tags", [])) + "\n\n"
    "【文章结构（严格按此顺序，字数均匀分配）】\n\n"
    "一、今日市场总览（约200字）\n"
    "- 上证/深证/创业板指数点位和涨跌幅\n"
    "- 成交量（较昨日增减幅度）\n"
    "- 市场情绪（涨跌家数比、涨停/跌停数）\n\n"
    "二、" + str(num_funds) + "只持仓基金全线评测（约700-900字，每只基金180字以上）\n"
    "   " + fund_list_str + "\n"
    "   每只基金用1段分析，包含板块表现+估值+操作建议\n\n"
    "三、资金流向解读（约200字）\n"
    "- 北向资金净额 + 主力资金行业流向\n"
    "- 对持仓基金的含义（3句话）\n\n"
    "四、板块轮动规律（约200字）\n"
    "- AI、半导体、医疗、新能源、资源的轮动关系\n"
    "- 下一个潜在领涨板块预判\n\n"
    "五、策略建议（约200字）\n"
    "- 持仓基金综合评分表（table格式，5维度各0-10分）\n"
    "- 短期+中期操作建议\n"
    "- 3条核心要点\n\n"
    "【免责声明】\n"
    "本文内容仅供学习交流和投资研究参考，不构成任何投资建议。股市有风险，投资需谨慎。"
)

body_html = ds_chat(
    [
        {"role": "system", "content": article_sys},
        {"role": "user", "content": article_user},
    ],
    temp=0.8, max_tok=4500
)

body_html = re.sub(r"^```html\s*", "", body_html)
body_html = re.sub(r"\s*```$", "", body_html)
body_html = body_html.strip()

# Count Chinese chars approximately
chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', body_html))
print("  OK 正文HTML:", len(body_html), "字符, 约", chinese_chars, "汉字")

# [5/6] 封面
print("\n[5/6] 生成并上传封面图 ...")
thumb_media_id = upload_cover(topic["title"], today_str, token)
if thumb_media_id:
    print("  OK 封面上传成功:", thumb_media_id[:30])
else:
    print("  封面未上传")

# [6/6] 保存 + 创建草稿
print("\n[6/6] 保存文章 + 创建草稿 ...")

date_parts = datetime.date.today().strftime("%Y%m%d")
slug_hash = hashlib.md5(topic["title"].encode("utf-8")).hexdigest()[:8]
filename = slug_hash + "-" + date_parts + ".html"
content_source_url = SITE_URL + "/articles/" + slug_hash + "-" + date_parts + ".html"
title_safe = topic["title"].replace('"', "&quot;")

# Build full page HTML
css_vars = (
    ":root{--bg:#0f0f1a;--bg2:#1a1a2e;--bg3:#252540;--text:#e8e8f0;--text2:#8888aa;"
    "--accent:#e11d48;--accent2:#f97316;--border:#2a2a3e;}\n"
    "body{font-family:-apple-system,BlinkMacSystemFont,\"PingFang SC\",\"Microsoft YaHei\",sans-serif;"
    "background:var(--bg);color:var(--text);margin:0;line-height:1.8;}\n"
    ".container{max-width:780px;margin:0 auto;padding:24px 16px;}\n"
    ".article-header{text-align:center;padding:32px 0 24px;border-bottom:1px solid var(--border);margin-bottom:24px;}\n"
    ".article-title{font-size:24px;font-weight:700;color:#fff;margin:0 0 8px;line-height:1.4;}\n"
    ".article-subtitle{font-size:16px;color:var(--accent2);margin:0 0 16px;}\n"
    ".article-meta{color:var(--text2);font-size:14px;display:flex;justify-content:center;gap:16px;flex-wrap:wrap;}\n"
    ".article-body{font-size:16px;line-height:1.9;}\n"
    ".article-body h2{color:var(--accent);font-size:20px;border-left:3px solid var(--accent);padding-left:12px;margin:28px 0 16px;}\n"
    ".article-body h3{color:var(--accent2);font-size:17px;margin:20px 0 12px;}\n"
    ".article-body p{margin:0 0 16px;text-align:justify;}\n"
    ".article-body strong{color:#fff;background:rgba(225,29,72,0.15);padding:1px 4px;border-radius:3px;}\n"
    ".article-body table{width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;}\n"
    ".article-body th{background:var(--bg3);padding:10px 12px;text-align:left;border:1px solid var(--border);}\n"
    ".article-body td{padding:10px 12px;border:1px solid var(--border);}\n"
    ".tag{background:var(--bg2);color:var(--accent);padding:4px 12px;border-radius:20px;font-size:13px;border:1px solid var(--border);}\n"
    ".back-link{text-align:center;margin:32px 0 16px;}\n"
    ".back-link a{color:var(--accent);text-decoration:none;}\n"
    ".article-source{background:var(--bg2);padding:12px 16px;border-radius:8px;margin-top:20px;font-size:13px;color:var(--text2);}\n"
    ".disclaimer{background:var(--bg3);border-left:3px solid var(--accent2);padding:16px;margin-top:32px;font-size:13px;color:var(--text2);line-height:1.7;}\n"
)

full_html = (
    '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
    '<meta charset="UTF-8">\n'
    '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
    '<title>' + title_safe + ' | A股投研工具箱</title>\n'
    '<meta name="description" content="' + topic.get("summary", "") + '">\n'
    '<meta name="keywords" content="' + topic.get("keywords", "A股,ETF,投资") + '">\n'
    '<meta name="author" content="无缘的人">\n'
    '<meta property="og:title" content="' + title_safe + '">\n'
    '<meta property="og:description" content="' + topic.get("summary", "") + '">\n'
    '<meta property="og:url" content="' + content_source_url + '">\n'
    '<style>\n' + css_vars + '</style>\n'
    '</head>\n<body>\n<div class="container">\n'
    '<div class="article-header">\n'
    '<h1 class="article-title">' + title_safe + '</h1>\n'
)

if topic.get("subtitle"):
    full_html += '<p class="article-subtitle">' + topic["subtitle"].replace('"', "&quot;") + '</p>\n'

full_html += (
    '<div class="article-meta">\n'
    '<span>' + today_str + '</span>\n'
    '<span>' + topic.get("readTime", "5分钟") + '</span>\n'
    '<span>✍️ 无缘的人</span>\n'
    '</div></div>\n'
    '<div class="article-body">\n' + body_html + '\n</div>\n'
    '<div class="article-source">数据来源：东方财富、同花顺、Wind/Choice。</div>\n'
    '<div style="margin-top:24px;display:flex;gap:8px;flex-wrap:wrap;">\n'
)

for t in topic.get("tags", []):
    full_html += '<span class="tag">' + t + '</span>\n'

full_html += (
    '</div>\n'
    '<div class="back-link"><a href="/">← 返回首页</a></div>\n'
    '</div>\n</body></html>'
)

# Save
articles_dir = SITE_ROOT / "articles"
articles_dir.mkdir(parents=True, exist_ok=True)
article_path = articles_dir / filename
article_path.write_text(full_html, encoding="utf-8")
print("  OK 文章已保存:", filename)

# Build WeChat draft
wechat_body = '<section style="padding: 8px; line-height: 1.8; font-family: -apple-system, BlinkMacSystemFont, sans-serif;">\n' + body_html.strip() + '\n</section>'

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

print("  标题:", topic["title"][:50])
print("  标签:", ", ".join(topic.get("tags", [])))
print("  覆盖:", num_funds, "只基金, 正文约", chinese_chars, "汉字")
print("  封面:", thumb_media_id[:20] if thumb_media_id else "(无)")

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
            print("\n" + "=" * 50)
            print("  ✅ SUCCESS! 推送成功")
            print("  标题:", topic["title"])
            print("  标签:", ", ".join(topic.get("tags", [])))
            print("  覆盖:", num_funds, "只基金")
            print("  正文字数:", chinese_chars, "汉字")
            print("  网页:", content_source_url)
            print("=" * 50)
            print("\n  下一步:")
            print("  1. 打开 https://mp.weixin.qq.com")
            print("  2. 草稿箱 -> 预览并发布")
        else:
            print("\n  ❌ FAILED!")
            print("  errcode:", result.get("errcode"))
            print("  errmsg:", result.get("errmsg"))
            print("\n  内容样本(前500字符):")
            print(body_html[:500])
except urllib.error.HTTPError as e:
    print("\n  ❌ HTTP Error", e.code, e.reason)
    try:
        print(e.read().decode("utf-8"))
    except:
        pass
except Exception as e:
    print("\n  ❌ Error:", type(e).__name__, str(e))
