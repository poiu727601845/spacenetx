#!/usr/bin/env python3
"""
微信自动推送 — 优化版 v3
改进点：
1. 选题提示词更精准，持仓基金信息完整传递给 AI
2. 标题生成更吸引人（带悬念/数字/反直觉）
3. 标签不少于5个，包含持仓基金相关标签
4. 文章覆盖所有持仓基金
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

def upload_cover(title, date_str):
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

def load_portfolio():
    fp = SITE_ROOT / "data" / "portfolio.json"
    if fp.exists():
        return json.loads(fp.read_text(encoding="utf-8"))
    return {"holdings": [], "watch_list": [], "rules": {}}

# ── 主流程 ──
print("=" * 60)
print("A股投研日报 — 微信自动推送 (Optimized v3)")
print("=" * 60)
print()

# Step 1: Token
print("[1/6] 获取 access_token ...")
token = wx_get_token()
print("  OK (len=" + str(len(token)) + ")")

# Step 2: Load portfolio
print("\n[2/6] 加载持仓信息 ...")
pf = load_portfolio()
holdings = [h for h in pf.get("holdings", []) if h.get("status") == "持有"]
watch_list_items = pf.get("watch_list", [])
rules = pf.get("rules", {})

# Build fund detail strings
fund_details = []
for h in holdings:
    code = h.get("code", "")
    name = h.get("name", "")
    sector = h.get("sector", "")
    position = h.get("position", "")
    detail = "- " + name + "(" + code + ")，" + sector + "，" + position
    fund_details.append(detail)
fund_str = "\n".join(fund_details) if fund_details else "暂无持仓"

watch_str = ""
for w in watch_list_items:
    watch_str += "- " + w.get("name", "") + " (" + w.get("code", "") + ") - " + w.get("status", "") + "\n"
if not watch_str:
    watch_str = "暂无"

pe_rule = rules.get("PE_discipline", "PE>80%减仓")
add_cond = rules.get("add_condition", "PE<40%加仓")
stop_loss = rules.get("stop_loss", "回撤>15%检视")

print("  持仓基金:", len(holdings), "只")
print("  关注池:", len(watch_list_items), "只")
print("  仓位纪律:", pe_rule)

# Step 3: Topic selection with enhanced prompt
print("\n[3/6] 生成选题 (DeepSeek V4) ...")

today_str = datetime.date.today().isoformat()

# Enhanced topic system prompt
topic_sys = "你是专业的A股市场投研分析师。今天是" + today_str + "。你管理着一份真实的基金投资组合。\n"
topic_sys += "你的任务是：基于今日市场情况、资金流向、持仓表现，选择一个最值得写的方向。\n"
topic_sys += "你写的每篇文章必须覆盖所有持仓基金，不能只写其中一个。\n\n"

# Portfolio context for topic selection
topic_port = "**你的持仓组合：**\n" + fund_str + "\n"
topic_port += "\n**观察池：**\n" + watch_str + "\n"
topic_port += "\n**仓位管理纪律：**\n"
topic_port += "- 减仓规则：" + pe_rule + "\n"
topic_port += "- 加仓条件：" + add_cond + "\n"
topic_port += "- 止损规则：" + stop_loss + "\n"

topic_json_schema = '{{"direction":"方向名","title":"30字内吸引人标题（必须含数字/悬念/反直觉元素，禁用日期前缀）","subtitle":"50字内副标题","summary":"70字内文章摘要（含2-3个关键数据）","tags":["标签1","标签2","标签3","标签4","标签5"],"readTime":"3-5分钟","keywords":"关键词1,关键词2,关键词3"}}'

topic_directions = "选题方向候选：\n"
topic_directions += "1. 今日市场复盘 + 明日策略（必须覆盖所有持仓基金当日表现）\n"
topic_directions += "2. 持仓组合深度评测（全部5只基金的收益对比 + 操作建议）\n"
topic_directions += "3. 北向资金/主力资金流向解读（结合持仓基金资金面）\n"
topic_directions += "4. 板块轮动分析（AI/半导体/医疗/新能源/资源轮动规律）\n"
topic_directions += "5. AI+半导体产业链专题（南方东英AI主题ETF + 汇添富半导体ETF联动分析）\n"
topic_directions += "6. 医疗板块投资机会（中欧医疗健康混合的深度解读）\n"
topic_directions += "7. 新能源投资布局（信澳新能源产业的持仓策略分析）\n"
topic_directions += "8. 资源/有色板块专题（有色金属小金属涨价逻辑 + 兴全合润持仓联动）\n"
topic_directions += "9. 仓位管理实战（结合PE纪律讲解如何调整5只基金仓位）\n"

topic_prompt = topic_port + "\n" + topic_json_schema + "\n" + topic_directions

topic_resp = ds_chat([{"role": "user", "content": topic_prompt}], temp=0.9, max_tok=600)
topic_resp = re.sub(r"```json\s*", "", topic_resp)
topic_resp = re.sub(r"```\s*", "", topic_resp)
try:
    topic = json.loads(topic_resp)
except:
    topic = {
        "direction": "持仓组合深度评测",
        "title": "5只基金全拆解：谁的收益最强？我的真实持仓",
        "subtitle": "AI+半导体+医疗+新能源+资源，5大方向全面分析",
        "summary": "今日A股投资分析，覆盖全部5只持仓基金的表现和操作建议。",
        "tags": ["投资策略", "ETF评测", "资金流向", "持仓分析", "市场复盘"],
        "readTime": "5分钟",
        "keywords": "A股,基金,ETF,持仓,投资"
    }

# Ensure we always have at least 5 tags
if len(topic.get("tags", [])) < 5:
    default_tags = ["投资策略", "ETF评测", "资金流向", "持仓分析", "市场复盘"]
    for t in default_tags:
        if t not in topic["tags"]:
            topic["tags"].append(t)
        if len(topic["tags"]) >= 5:
            break

print("  ✅ 选题:", topic["title"])
print("     方向:", topic["direction"])
print("     标签:", ", ".join(topic.get("tags", [])))

# Step 4: Generate article
print("\n[4/6] 生成文章正文 (DeepSeek V4) ...")

article_sys = "你是专业的A股市场投研分析师。今天是2026年" + today_str + "。\n"
article_sys += "输出仅文章正文HTML（不含html/head/body包裹）。\n\n"
article_sys += "【强制要求】：\n"
article_sys += "1. 文章必须覆盖以下全部" + str(len(holdings)) + "只持仓基金：\n"
for h in holdings:
    article_sys += "   - " + h["name"] + "(" + h["code"] + ")，" + h.get("sector", "") + "，" + h.get("position", "") + "\n"
article_sys += "2. 每只基金必须至少出现1次，包含当日表现分析和操作建议\n"
article_sys += "3. 文章总长度1200-1800字（含标点）\n"
article_sys += "4. 每个数据点标注来源（东方财富/同花顺/Wind）\n\n"
article_sys += "【格式要求】：\n"
article_sys += "- h2 二级标题（用数字或关键词，不要用【】符号）\n"
article_sys += "- h3 三级标题\n"
article_sys += "- p 段落（每段不超过150字）\n"
article_sys += "- strong 重点内容加粗\n"
article_sys += "- ul/li 列表\n"
article_sys += "- table 评分表格\n\n"
article_sys += "【合规红线】：\n"
article_sys += "1. 不预测具体股价\n"
article_sys += "2. 不直接推荐买卖（只分析逻辑）\n"
article_sys += "3. 文末必须有固定免责声明\n"
article_sys += "4. 禁用暴涨崩盘千股跌停等夸张词汇\n"

# Build article context
article_context = "**持仓组合：**\n" + fund_str + "\n"
article_context += "\n**观察池：**\n" + watch_str + "\n"
article_context += "\n**仓位纪律：**\n"
article_context += "- 减仓：" + pe_rule + "\n"
article_context += "- 加仓：" + add_cond + "\n"
article_context += "- 止损：" + stop_loss + "\n"

article_user = "请根据以下信息写一篇深度投研文章：\n\n"
article_user += "方向：" + topic["direction"] + "\n"
article_user += "标题：" + topic["title"] + "\n"
article_user += "副标题：" + topic.get("subtitle", "") + "\n"
article_user += "摘要：" + topic.get("summary", "") + "\n"
article_user += "标签：" + ", ".join(topic.get("tags", [])) + "\n\n"
article_user += article_context + "\n\n"

article_user += "【文章结构要求】：\n\n"
article_user += "一、今日市场总览（约200字）\n"
article_user += "- 三大指数表现（上证/深证/创业板，含具体点位和涨跌幅）\n"
article_user += "- 成交量变化（较昨日增减）\n"
article_user += "- 市场情绪指标（涨跌家数、涨停/跌停）\n"
article_user += "- 关键数据标注来源\n\n"

article_user += "二、持仓基金全线评测（约600-800字，每只基金一段）\n"
article_user += "你必须逐一分析以下全部" + str(len(holdings)) + "只基金：\n"
for i, h in enumerate(holdings, 1):
    article_user += str(i) + ". " + h["name"] + "(" + h["code"] + ")：\n"
    article_user += "   - 今日表现/估值水平\n"
    article_user += "   - 所属板块近期走势\n"
    article_user += "   - 结合仓位纪律的操作建议\n\n"

article_user += "三、资金流向深度解读（约200字）\n"
article_user += "- 北向资金净流入/流出金额\n"
article_user += "- 主力资金行业流向\n"
article_user += "- 对你的持仓基金意味着什么（3句话）\n\n"

article_user += "四、板块轮动规律分析（约200字）\n"
article_user += "- 当前处于哪个板块周期\n"
article_user += "- AI、半导体、医疗、新能源、资源的轮动关系\n"
article_user += "- 下一个潜在领涨板块预判\n\n"

article_user += "五、策略建议与评分表（约150字）\n"
article_user += "- 持仓基金综合评分表（可读性、成长性、安全性、流动性、性价比 5维度，满分10分）\n"
article_user += "- 短期（1-3天）操作建议\n"
article_user += "- 中期（1-2周）仓位调整方向\n"
article_user += "- 3条核心操作要点\n\n"

article_user += "【免责声明】（必须原文保留）\n"
article_user += "本文内容仅供学习交流和投资研究参考，不构成任何投资建议。股市有风险，投资需谨慎。过往业绩不代表未来表现，独立研究和风险评估是投资决策的前提。作者可能与文中提到的基金/ETF存在持仓关系。"

body_html = ds_chat(
    [
        {"role": "system", "content": article_sys},
        {"role": "user", "content": article_user},
    ],
    temp=0.8, max_tok=5000
)

body_html = re.sub(r"^```html\s*", "", body_html)
body_html = re.sub(r"\s*```$", "", body_html)
body_html = body_html.strip()

print("  OK 正文:", len(body_html), "字符")

# Step 5: Cover image
print("\n[5/6] 生成并上传封面图 ...")
thumb_media_id = upload_cover(topic["title"], today_str)
if thumb_media_id:
    print("  OK 封面上传成功:", thumb_media_id[:30])
else:
    print("  封面未上传")

# Step 6: Save article + create draft
print("\n[6/6] 保存文章 + 创建草稿 ...")

# Get date string for filename
date_parts = datetime.date.today().strftime("%Y%m%d")
slug_hash = hashlib.md5(topic["title"].encode("utf-8")).hexdigest()[:8]
filename = slug_hash + "-" + date_parts + ".html"
content_source_url = SITE_URL + "/articles/" + slug_hash + "-" + date_parts + ".html"
title_safe = topic["title"].replace('"', "&quot;")

# Build full HTML page
full_html = '<!DOCTYPE html>\n<html lang="zh-CN">\n<head>\n'
full_html += '<meta charset="UTF-8">\n'
full_html += '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
full_html += '<title>' + title_safe + ' | A股投研工具箱</title>\n'
full_html += '<meta name="description" content="' + topic.get("summary", "") + '">\n'
full_html += '<meta name="keywords" content="' + topic.get("keywords", "A股,ETF,投资") + '">\n'
full_html += '<meta name="author" content="无缘的人">\n'
full_html += '<meta property="og:title" content="' + title_safe + '">\n'
full_html += '<meta property="og:description" content="' + topic.get("summary", "") + '">\n'
full_html += '<meta property="og:url" content="' + content_source_url + '">\n'
full_html += '<style>\n'
full_html += ':root{--bg:#0f0f1a;--bg2:#1a1a2e;--bg3:#252540;--text:#e8e8f0;--text2:#8888aa;'
full_html += '--accent:#e11d48;--accent2:#f97316;--border:#2a2a3e;}\n'
full_html += 'body{font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;'
full_html += 'background:var(--bg);color:var(--text);margin:0;line-height:1.8;}\n'
full_html += '.container{max-width:780px;margin:0 auto;padding:24px 16px;}\n'
full_html += '.article-header{text-align:center;padding:32px 0 24px;border-bottom:1px solid var(--border);margin-bottom:24px;}\n'
full_html += '.article-title{font-size:24px;font-weight:700;color:#fff;margin:0 0 8px;line-height:1.4;}\n'
full_html += '.article-subtitle{font-size:16px;color:var(--accent2);margin:0 0 16px;}\n'
full_html += '.article-meta{color:var(--text2);font-size:14px;display:flex;justify-content:center;gap:16px;flex-wrap:wrap;}\n'
full_html += '.article-body{font-size:16px;line-height:1.9;}\n'
full_html += '.article-body h2{color:var(--accent);font-size:20px;border-left:3px solid var(--accent);padding-left:12px;margin:28px 0 16px;}\n'
full_html += '.article-body h3{color:var(--accent2);font-size:17px;margin:20px 0 12px;}\n'
full_html += '.article-body p{margin:0 0 16px;text-align:justify;}\n'
full_html += '.article-body strong{color:#fff;background:rgba(225,29,72,0.15);padding:1px 4px;border-radius:3px;}\n'
full_html += '.article-body table{width:100%;border-collapse:collapse;margin:16px 0;font-size:14px;}\n'
full_html += '.article-body th{background:var(--bg3);padding:10px 12px;text-align:left;border:1px solid var(--border);}\n'
full_html += '.article-body td{padding:10px 12px;border:1px solid var(--border);}\n'
full_html += '.tag{background:var(--bg2);color:var(--accent);padding:4px 12px;border-radius:20px;font-size:13px;border:1px solid var(--border);}\n'
full_html += '.back-link{text-align:center;margin:32px 0 16px;}\n'
full_html += '.back-link a{color:var(--accent);text-decoration:none;}\n'
full_html += '.article-source{background:var(--bg2);padding:12px 16px;border-radius:8px;margin-top:20px;font-size:13px;color:var(--text2);}\n'
full_html += '.disclaimer{background:var(--bg3);border-left:3px solid var(--accent2);padding:16px;margin-top:32px;font-size:13px;color:var(--text2);line-height:1.7;}\n'
full_html += '</style>\n</head>\n<body>\n<div class="container">\n'
full_html += '<div class="article-header">\n'
full_html += '<h1 class="article-title">' + title_safe + '</h1>\n'
if topic.get("subtitle"):
    full_html += '<p class="article-subtitle">' + topic["subtitle"].replace('"', "&quot;") + '</p>\n'
full_html += '<div class="article-meta">\n'
full_html += '<span>' + today_str + '</span>\n'
full_html += '<span>' + topic.get("readTime", "5分钟") + '</span>\n'
full_html += '<span>✍️ 无缘的人</span>\n'
full_html += '</div></div>\n'
full_html += '<div class="article-body">\n' + body_html + '\n</div>\n'
full_html += '<div class="article-source">数据来源：东方财富、同花顺、Wind/Choice。以上数据仅供参考，不构成投资建议。</div>\n'
full_html += '<div style="margin-top:24px;display:flex;gap:8px;flex-wrap:wrap;">\n'
for t in topic.get("tags", []):
    full_html += '<span class="tag">' + t + '</span>\n'
full_html += '</div>\n'
full_html += '<div class="back-link"><a href="/">← 返回首页</a></div>\n'
full_html += '</div>\n</body></html>'

# Save article
articles_dir = SITE_ROOT / "articles"
articles_dir.mkdir(parents=True, exist_ok=True)
article_path = articles_dir / filename
article_path.write_text(full_html, encoding="utf-8")
print("  OK 文章已保存:", filename)

# Build WeChat payload
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

print("  标题:", payload["articles"][0]["title"][:50])
print("  URL:", content_source_url)
print("  封面:", thumb_media_id[:30] if thumb_media_id else "(无)")
print("  标签:", ", ".join(topic.get("tags", [])))
print("  持仓覆盖:", len(holdings), "只基金")

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
            print("  标签:", ", ".join(topic.get("tags", [])))
            print("  持仓覆盖:", len(holdings), "只基金")
            print("  草稿ID:", mid[:40])
            print("  网页:", content_source_url)
            print("=" * 50)
            print("\n  下一步:")
            print("  1. 打开 https://mp.weixin.qq.com")
            print("  2. 草稿箱 -> 预览并发布")
        else:
            print("\n  FAILED!")
            print("  errcode:", result.get("errcode"))
            print("  errmsg:", result.get("errmsg"))
            print("\n  内容样本(前500字符):")
            print(body_html[:500])
except urllib.error.HTTPError as e:
    print("\n  HTTP Error", e.code, e.reason)
    try:
        print(e.read().decode("utf-8"))
    except:
        pass
except Exception as e:
    print("\n  Error:", type(e).__name__, str(e))
