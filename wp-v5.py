#!/usr/bin/env python3
"""
微信自动推送 — v5 最终优化版
核心改进：持仓基金分析合并为表格形式（每只≤100字），总字数600-900字
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
print("A股投研日报 — 微信自动推送 (v5 Final)")
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

num_funds = len(holdings)
recent_titles = set()

fund_details = []
for h in holdings:
    fund_details.append("- " + h["name"] + "(" + h["code"] + ")，" + h.get("sector", "") + "，" + h.get("position", ""))
fund_str = "\n".join(fund_details)

watch_str = ""
for w in watch_list_items:
    watch_str += "- " + w.get("name", "") + " (" + w.get("code", "") + ") - " + w.get("status", "") + "\n"
if not watch_str:
    watch_str = "暂无"

pe_rule = rules.get("PE_discipline", "PE>80%减仓")
add_cond = rules.get("add_condition", "PE<40%加仓")
stop_loss = rules.get("stop_loss", "回撤>15%检视")

print("  持仓基金:", num_funds, "只")
# Load recent titles for dedup
recent_titles = set()
try:
    art_path = SITE_ROOT / "data" / "articles.json"
    with open(art_path, "r", encoding="utf-8") as fj:
        aj = json.load(fj)
        for a in aj[-15:] if isinstance(aj, list) else aj.get("articles", aj.get("items", []))[-15:]:
            t = a.get("title", "")
            if t:
                recent_titles.add(t)
except Exception:
    pass
for fd in fund_details:
    print("    ", fd)
print("  关注池:", watch_str.strip() if watch_str.strip() else "暂无")

# [3/6] 选题
print("\n[3/6] 生成选题 (DeepSeek V4) ...")
today_str = datetime.date.today().isoformat()

topic_port = "**持仓组合（共" + str(num_funds) + "只）：**\n" + fund_str + "\n"
topic_port += "\n**观察池：**\n" + watch_str + "\n"
topic_port += "\n**仓位纪律：**\n- 减仓：" + pe_rule + "\n- 加仓：" + add_cond + "\n- 止损：" + stop_loss + "\n"

topic_sys = "你是专业A股投研分析师。今天是" + today_str + "。\n"
topic_sys += "要求：标题必须含数字或悬念或反直觉元素，禁用日期前缀。摘要必须含2-3个关键数据。\n"
topic_sys += "标签至少6个，必须包含持仓基金代码或名称相关标签。\n\n"
topic_sys += "输出JSON：\n"
topic_sys += '{{"direction":"方向名","title":"25字标题（含数字/悬念，禁用日期前缀）","subtitle":"50字副标题","summary":"70字摘要（含2-3个数据）","tags":["标签1","标签2","标签3","标签4","标签5","标签6"],"readTime":"4-6分钟","keywords":"关键词1,关键词2,关键词3"}}\n\n'
topic_sys += "选题方向（优先级降序）：\n"
topic_sys += "1. 持仓组合全维度评测（全部" + str(num_funds) + "只基金深度分析）\n"
topic_sys += "2. AI+半导体产业链专题\n"
topic_sys += "3. 北向资金+主力资金流向解读\n"
topic_sys += "4. 板块轮动规律（AI→半导体→医疗→新能源→资源）\n"
topic_sys += "5. " + (fund_details[2] if len(fund_details) > 2 else "医疗板块") + "投资机会\n"
topic_sys += "6. " + (fund_details[3] if len(fund_details) > 3 else "新能源") + "布局策略\n"
topic_sys += "7. 仓位管理实战课（PE纪律+加减仓信号）\n"

# Load recent titles for dedup
recent_titles = set()
try:
    with open(str(DATA_DIR / "articles.json"), "r", encoding="utf-8") as fj:
        aj = json.load(fj)
        for a in aj[-15:] if isinstance(aj, list) else aj.get("articles", aj.get("items", []))[-15:]:
            t = a.get("title", "")
            if t:
                recent_titles.add(t)
except:
    pass

topic_resp = ds_chat([{"role": "user", "content": topic_port + "\n\n" + topic_sys}], temp=0.9, max_tok=600)
topic_resp = re.sub(r"```json\s*", "", topic_resp)
topic_resp = re.sub(r"```\s*", "", topic_resp)
try:
    topic = json.loads(topic_resp)
except:
    topic = {
        "direction": "持仓组合全维度评测",
        "title": str(num_funds) + "只基金谁更抗跌：持仓深度体检",
        "subtitle": "AI+半导体+医疗+新能源+资源全景扫描",
        "summary": today_str + "市场复盘，覆盖全部" + str(num_funds) + "只持仓基金。",
        "tags": ["持仓分析", "基金评测", "资金流向", "ETF", "市场复盘", "投资策略"],
        "readTime": "5分钟",
        "keywords": "A股,基金,ETF,持仓,投资"
    }

# Ensure 6+ tags
while len(topic.get("tags", [])) < 6:
    for t in ["投资策略", "ETF评测", "资金流向", "持仓分析", "市场复盘", "基金诊断"]:
        if t not in topic.get("tags", []):
            topic.setdefault("tags", []).append(t)
        if len(topic["tags"]) >= 6:
            break

# Dedup: if title matches recent, force a different one
if topic["title"] in recent_titles:
    print("  ⚠️ 标题重复，强制替换")
    topic["title"] = "半仓调仓实录：科技与医疗的跷跷板游戏"
    topic["subtitle"] = "半导体减仓50%转配医疗，PE纪律下的仓位管理"
    topic["direction"] = "持仓组合实操记录"

print("  ✅ 选题:", topic["title"])
print("     方向:", topic["direction"])
print("     标签:", ", ".join(topic.get("tags", [])))
print("     摘要:", topic.get("summary", "")[:60])

# [4/6] 生成文章 — 表格版持仓分析
print("\n[4/6] 生成文章正文 (DeepSeek V4) ...")

# Build fund list for prompt
fund_list_for_prompt = ""
for i, h in enumerate(holdings, 1):
    fund_list_for_prompt += str(i) + ". " + h["name"] + "(" + h["code"] + ") | " + h.get("sector", "") + " | 仓位：" + h.get("position", "") + "\n"

# Build article_sys as a list and join (avoids implicit concatenation syntax issues)

article_sys_parts = [

    "你是A股投研助手，像一个懂投资的网友在朋友圈聊天。\\n",

    "风格：大白话、亲切、幽默、600-900字短小精悍。\\n\\n",

    "【写作风格要求】：\\n",

    "1. 像在跟朋友聊天：用咱们、你、我，偶尔吐槽，偶尔自嘲\\n",

    "2. 生活化比喻：ETF=一篮子菜、定投=零存整取、板块轮动=换桌吃饭、追高=抢最后一棒\\n",

    "3. 说人话：不通金融的人也能一看就懂，别说那些专业术语\\n",

    "4. 结构：像一篇文章一样自然过渡，不要刻意的\'一、二、三\'小标题\\n",

    "5. 字数：600-900字，宁短勿长！超过900字就是不合格！\\n\\n",

    "【绝对禁止】：\\n",

    "- 禁止评分表格（什么5维打分表，一眼假）\\n",

    "- 禁止堆数据（不要一上来就列一堆百分比和点位）\\n",

    "- 禁止\'一、今日市场总览\'\'二、持仓基金全景表\'这种论文式分段\\n",

    "- 禁止专业术语轰炸，禁止又臭又长的长篇大论\\n\\n",

    "【正确范例风格】：参考用户提供的\'小金属ETF当前能否纳入持仓？\'这篇文章，完全照那个风格写！\\n",

]

article_sys = "".join(article_sys_parts)







article_user = (

    "请根据以下信息写一篇简短投研文章，600-900字，大白话风格：\n\n"

    "方向：" + topic["direction"] + "\n"

    "标题：" + topic["title"] + "\n"

    "副标题：" + topic.get("subtitle", "") + "\n"

    "摘要：" + topic.get("summary", "") + "\n"

    "标签：" + ", ".join(topic.get("tags", [])) + "\n\n"

    "【文章写法，照着这个来】（自由发挥，不用刻板分段）\n\n"

    "开头：用\'最近有人在问我...\'或者\'说真的...\'这种开场白切入，像跟朋友聊天\n"

    "持仓：把" + str(num_funds) + "只基金的表现串起来说，每只2-3句，用生活化语言，别说数据报表\n"

    "板块：今天谁在动？资金往哪流？一句人话讲清楚，别列北向资金净流出XX亿\n"

    "展望：明天的可能走势+你的直觉判断，用比喻，别说\'技术面显示\'这种词\n"

    "结尾：一句人话总结，给读者一个记住的点，可以加个emoji\n\n"

    "【免责声明】（必须原文，放在最后）\n"

    "本文内容仅供学习交流和投资研究参考，不构成任何投资建议。股市有风险，投资需谨慎。"

)




body_html = ds_chat(
    [
        {"role": "system", "content": article_sys},
        {"role": "user", "content": article_user},
    ],
    temp=0.8, max_tok=3500
)

body_html = re.sub(r"^```html\s*", "", body_html)
body_html = re.sub(r"\s*```$", "", body_html)
body_html = body_html.strip()

chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', body_html))
print("  OK 正文HTML:", len(body_html), "字符, 约", chinese_chars, "汉字")
print("  字数状态:", "✅ 达标" if 600 <= chinese_chars <= 900 else "❌ 超标/不足")

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
            print("  正文字数:", chinese_chars, "汉字", "(要求: 600-900)")
            if 600 <= chinese_chars <= 900:
                print("  字数状态: ✅ 达标！")
            else:
                print("  字数状态: ❌ 仍需调整")
            print("  网页:", content_source_url)
            print("=" * 50)
            print("\n  下一步:")
            print("  1. 打开 https://mp.weixin.qq.com")
            print("  2. 草稿箱 -> 预览并发布")
        else:
            print("\n  ❌ FAILED!")
            print("  errcode:", result.get("errcode"))
            print("  errmsg:", result.get("errmsg"))
except urllib.error.HTTPError as e:
    print("\n  ❌ HTTP Error", e.code, e.reason)
    try:
        print(e.read().decode("utf-8"))
    except:
        pass
except Exception as e:
    print("\n  ❌ Error:", type(e).__name__, str(e))
