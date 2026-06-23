#!/usr/bin/env python3
import sys, os, json, re, datetime, random, urllib.request, hashlib
import base64
from pathlib import Path

OLD_WS = Path("/home/ubuntu/wechat-publisher")
DS_API_KEY = "sk-2d2b6f8f1d354828966faba35899eada"

# ── 持仓动态读取 ──────────────────────────────────────────────
def load_portfolio():
    fp = OLD_WS / "site" / "data" / "portfolio.json"
    if fp.exists():
        return json.loads(fp.read_text(encoding="utf-8"))
    return {"holdings": [], "watch_list": []}

def get_portfolio_funds():
    """返回持仓基金代码列表，用于选题和prompt"""
    p = load_portfolio()
    return [h["code"] for h in p.get("holdings", []) if h.get("status") == "持有"]

def get_portfolio_names():
    """返回 'name(code)' 格式列表，用于选题"""
    p = load_portfolio()
    return [f"{h['name']}({h['code']})" for h in p.get("holdings", []) if h.get("status") == "持有"]

def build_dynamic_topics():
    """根据持仓动态生成选题方向"""
    funds = get_portfolio_names()
    holdings = load_portfolio().get("holdings", [])
    watch   = load_portfolio().get("watch_list", [])

    topics = []
    # 对每个持仓基金生成评测/分析选题
    for h in holdings:
        if h.get("status") != "持有":
            continue
        code = h["code"]
        name = h["name"]
        sector = h.get("sector", "")
        topics.append(f"{name}持仓分析与操作策略")
        topics.append(f"ETF评测：{name}深度解读")
        if sector:
            topics.append(f"{sector}板块轮动与{code}配置价值")
    # 持仓组合类选题
    if len(funds) >= 2:
        topics.append(f"持仓基金组合评测：" + " vs ".join(funds[:3]))
        topics.append("资金流向信号解读与持仓调整逻辑")
        topics.append("板块轮动规律与持仓再平衡策略")
    # 观察池选题
    for w in watch:
        topics.append(f"{w['name']}观察：能否纳入持仓？")
    # 保底通用选题
    topics += ["ETF筛选工具横向评测", "主力资金流向信号解读", "定投纪律与仓位管理实战"]
    return topics

def update_portfolio_after_review(add_funds=None, remove_codes=None, note=""):
    """复盘后更新 portfolio.json（由AI调用）"""
    fp = OLD_WS / "site" / "data" / "portfolio.json"
    if not fp.exists():
        return False
    p = json.loads(fp.read_text(encoding="utf-8"))
    changed = False
    if add_funds:
        for f in add_funds:
            if not any(h.get("code") == f["code"] for h in p["holdings"]):
                f["status"] = "持有"
                p["holdings"].append(f)
                changed = True
    if remove_codes:
        for rc in remove_codes:
            for h in p["holdings"]:
                if h.get("code") == rc:
                    h["status"] = "已清仓"
                    changed = True
    if changed:
        p["meta"]["last_update"] = datetime.date.today().isoformat()
        if note:
            p["meta"]["description"] = note
        fp.write_text(json.dumps(p, ensure_ascii=False, indent=2), encoding="utf-8")
    return changed
# ─────────────────────────────────────────────────────────────




def make_article_banner(title, summary, date_str, save_path):
    """生成文章内联横幅图 900x400，用于文章标题下方展示"""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("  [WARN] Pillow 未安装，跳过横幅图生成")
        return None

    W, H = 900, 400
    img = Image.new("RGB", (W, H), "#0a0a0f")
    draw = ImageDraw.Draw(img)

    # 顶部装饰渐变线（品牌色 #e11d48）
    for y in range(8):
        val = int(225 * (1 - y / 8))
        draw.line([(0, y), (W, y)], fill=(val, 29, 72))

    # 找中文字体
    font_paths = [
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    font_title = None
    for fp in font_paths:
        try:
            font_title = ImageFont.truetype(fp, 42)
            break
        except Exception:
            pass
    if font_title is None:
        font_title = ImageFont.load_default()

    font_sub = None
    for fp in font_paths:
        try:
            font_sub = ImageFont.truetype(fp, 24)
            break
        except Exception:
            pass
    if font_sub is None:
        for fp in font_paths:
            try:
                font_sub = ImageFont.truetype(fp, 20)
                break
            except Exception:
                pass

    # 标题文字自适应换行
    lines_text = []
    max_w = W - 80
    for ch in title:
        test_line = "".join(lines_text) + ch
        bbox = draw.textbbox((0, 0), test_line, font=font_title)
        if bbox[2] - bbox[0] <= max_w:
            lines_text.append(ch)
        else:
            if lines_text:
                lines_text.append("...")
                break
    title_text = "".join(lines_text)

    ty = 120
    bbox = draw.textbbox((0, 0), title_text, font=font_title)
    tw = bbox[2] - bbox[0]
    tx = (W - tw) // 2
    draw.text((tx, ty), title_text, fill="#ffffff", font=font_title)

    # 摘要文字（灰色）
    if summary and font_sub:
        summary_text = summary[:80]
        sy = 210
        bbox = draw.textbbox((0, 0), summary_text, font=font_sub)
        sw = bbox[2] - bbox[0]
        sx = (W - sw) // 2
        draw.text((sx, sy), summary_text, fill="#8888a8", font=font_sub)

    # 日期和标签
    if font_sub:
        date_text = f"{date_str} | 阅读量约 5 分钟"
        bbox = draw.textbbox((0, 0), date_text, font=font_sub)
        dw = bbox[2] - bbox[0]
        dx = (W - dw) // 2
        draw.text((dx, 320), date_text, fill="#ff6b6b", font=font_sub)

    # 底部装饰线
    for y in range(H - 8, H):
        val = int(255 * (1 - (H - y) / 8))
        draw.line([(0, y), (W, y)], fill=(val, 107, 107))

    img.save(save_path, "JPEG", quality=90)
    return save_path


def call_ds(messages, temp=0.8, max_tok=4000):
    payload = json.dumps({
        "model": "deepseek-v4-flash",
        "messages": messages,
        "temperature": temp,
        "max_tokens": max_tok,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=payload, method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {DS_API_KEY}"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"].strip()


print("=" * 50)
print("1/3 生成文章（DeepSeek V4）")
print("=" * 50)

# 动态选题
topics = build_dynamic_topics()
direction = random.sample(topics, 1)[0]
print(f"选题: {direction}")

meta_prompt = f"基于方向「{direction}」生成今日文章选题。JSON格式："
meta_prompt += '{"title":"25字内标题","desc":"70字内摘要","tags":["标签1"],"readTime":"5分钟","keywords":"关键词"}'

meta_resp = call_ds([{"role":"user","content":meta_prompt}], temp=0.9, max_tok=500)
meta_resp = re.sub(r"```json\s*","", meta_resp)
meta_resp = re.sub(r"```\s*","", meta_resp)
try:
    meta = json.loads(meta_resp)
except:
    meta = {"title":f"{direction}深度解读", "desc":"今日A股投研分析", "tags":["投资策略"], "readTime":"5分钟", "keywords":"A股,ETF,投资"}

print(f"[OK] 标题: {meta['title']}")

# 动态组装 fund_codes 供 prompt 使用
fund_codes_str = "、".join([f"{h['code']}({h['name']})" for h in load_portfolio().get("holdings", []) if h.get("status")=="持有"])
rules_str = "；".join([f"{k}:{v}" for k,v in load_portfolio().get("rules", {}).items()])

system_prompt = """你是一个懂投资的普通人，在公众号上和朋友聊理财。当前年份是2026年，文章内容必须基于2026年的市场背景，禁止出现"2025年"或更早年份的表述。输出仅文章正文HTML（不含<html><head><body>包裹）。

写作风格要求（最重要！）：
- 用大白话聊天，像跟朋友微信聊天一样自然
- 多用"咱们""你""我"这样的人称，拉近距离
- 用生活化比喻解释专业概念（比如把ETF比作"一篮子菜"，把定投比作"零存整取"）
- 可以偶尔加一点个人感受："说实话，看到这个数据我也有点意外"
- 不要用太学术的术语，碰到专业词汇要翻译成大白话
- 段落要短，一段最多3-4行，读起来不累
- 可以加轻松的emoji点缀，但不要太多

格式：
- <h2 id="hN">二级标题</h2>
- <h3>三级标题</h3>
- <p>段落</p>
- <strong>重点</strong>
- <ul><li>列表</li></ul>
- 文章长度600-900字（短而精，别长篇大论）
- 禁止做评分表格（太像产品评测）
- 禁止堆数据表格（最多1个简单对比表）
- 多用"咱们""你""我"拉近距离，可以偶尔说"说实话""我个人的感觉"
- 用大白话和生活化比喻，比如ETF比作"一篮子菜"、定投比作"零存整取"
- 不要写"建议关注""建议买入"这种话术，改为"如果你对方向感兴趣可以了解下"
- 段落要短，最多一段3-4行
- 最后一个H2写「划重点：几句大实话」，用轻松口吻总结
- 结尾必须加：本文内容仅供学习参考，不构成投资建议，投资有风险，入市需谨慎哦~"""

user_prompt = f"""给公众号朋友写一篇聊理财的文章，标题和方向如下：

标题：{meta['title']}
摘要：{meta['desc']}
关键词：{meta.get('keywords','')}
当前持仓基金：{fund_codes_str if fund_codes_str else '无'}
仓位管理纪律：{rules_str if rules_str else 'PE>80%减仓，PE<40%可加仓'}

写作要求：
1. 想象你在微信群里跟朋友聊这个话题，用最通俗的语言，比如"你有没有注意到..."、"说实话最近这个行情挺有意思的"
2. 代码和数字只是参考，不要堆数据，重点是讲逻辑和思路
3. 有持仓就聊聊持仓里的基金，没有就聊方向本身
4. 文章最后用「划重点：几句大实话」收尾，给3-5条最实用的建议
5. 不要做评分表格，太像产品测评了，用自然语言点评就行
6. 文章控制在600-900字，别写太多，精悍比长篇好
7. 最核心的一条：让一个完全不懂金融的朋友也能看得下去
6. 结尾加免责声明
"""

body_html = call_ds(
    [{"role":"system","content":system_prompt},{"role":"user","content":user_prompt}],
    temp=0.85, max_tok=4000
)
print(f"[OK] 正文: {len(body_html)} 字符")
# 生成横幅图
slug_hash = hashlib.md5(meta["title"].encode()).hexdigest()[:8]
article_id = f"{slug_hash}-{datetime.date.today().strftime('%Y%m%d')}"
date_str = datetime.date.today().isoformat()
banner_path = f"/tmp/banner_{article_id}.jpg"

print("=" * 50)
print("1.5/3 生成文章横幅图")
print("=" * 50)
try:
    make_article_banner(meta["title"], meta.get("desc", ""), date_str, banner_path)
    with open(banner_path, "rb") as bf:
        banner_b64 = base64.b64encode(bf.read()).decode("utf-8")
    banner_html = f"<div style=margin:16px 0 24px;border-radius:12px;overflow:hidden;border:1px solid #2a2a3e> <img src=data:image/jpeg;base64,{banner_b64} alt=meta_title style=width:100%;height:auto;display:block> </div>".replace("meta_title", meta["title"].replace('"', '&quot;'))
    print(f"[OK] 横幅图已生成并转 base64 ({len(banner_b64)} 字符)")
    os.unlink(banner_path)
except Exception as e:
    banner_html = ""
    print(f"[WARN] 横幅图生成失败: {e}，使用纯文本排版")

# 组装完整HTML（含SEO元素）
article_id = f"{slug_hash}-{datetime.date.today().strftime('%Y%m%d')}"
date_str = datetime.date.today().isoformat()
safe_title = meta['title'].replace('"', '&quot;')
canonical_url = f"https://spacenetx.com/articles/{article_id}.html"
desc_short = meta['desc'][:160]
og_image = "https://spacenetx.com/favicon-og.png"
tags_html = " ".join([f'<span style="background:#f0f0f0;padding:2px 8px;border-radius:4px;font-size:0.78rem;margin-right:4px;">{t}</span>' for t in meta.get('tags', [])])

full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{safe_title} | A股投研工具箱</title>
  <meta name="description" content="{desc_short}">
  <meta name="keywords" content="{meta.get('keywords','')}">
  <meta name="author" content="无缘的人">
  <meta name="robots" content="index,follow,max-image-preview:large">
  <meta property="og:title" content="{safe_title}">
  <meta property="og:description" content="{desc_short}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical_url}">
  <meta property="og:image" content="{og_image}">
  <meta property="og:image:width" content="1200">
  <meta property="og:image:height" content="630">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{safe_title}">
  <meta name="twitter:description" content="{desc_short}">
  <meta name="twitter:image" content="{og_image}">
  <link rel="canonical" href="{canonical_url}">
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Article",
    "headline": "{safe_title}",
    "description": "{desc_short}",
    "author": {{"@type": "Person", "name": "无缘的人"}},
    "datePublished": "{date_str}",
    "dateModified": "{date_str}",
    "mainEntityOfPage": {{"@type": "WebPage", "@id": "{canonical_url}"}},
    "publisher": {{"@type": "Organization", "name": "A股投研工具箱", "logo": {{"@type": "ImageObject", "url": "https://spacenetx.com/favicon-og.png"}}}}
  }}
  </script>
  <style>
    body {{ font-family:'PingFang SC','Microsoft YaHei',system-ui,sans-serif; max-width:780px; margin:40px auto; padding:0 20px; line-height:1.8; color:#e8e8f0; background:#0a0a0f; }}
    h1 {{ font-size:1.6rem; margin:24px 0 8px; line-height:1.4; color:#e8e8f0; }}
    h2 {{ color:#ff6b6b; margin:20px 0 10px; font-size:1.2rem; }}
    h3 {{ color:#ff6b6b; margin:16px 0 8px; font-size:1.05rem; }}
    p {{ margin:10px 0; font-size:0.95rem; }}
    ul,ol {{ margin:8px 0 12px 20px; }}
    li {{ margin:4px 0; font-size:0.93rem; }}
    table {{ border-collapse:collapse; width:100%; margin:14px 0; font-size:0.88rem; }}
    th,td {{ border:1px solid #2a2a3e; padding:8px 10px; text-align:left; }}
    th {{ background:#1a1a26; color:#e8e8f0; }}
    strong {{ color:#ff6b6b; }}
    a {{ color:#ff6b6b; text-decoration:none; }}
    .disclaimer {{ background:#1a1a26; border:1px solid #2a2a3e; border-radius:8px; padding:12px 16px; margin:24px 0; font-size:0.85rem; color:#8888a8; }}
    .back-link {{ font-size:0.85rem; color:#8888a8; text-decoration:none; }}
  </style>
</head>
<body>
  <p class="back-link"><a href="/" style="color:#8888a8;text-decoration:none;">← 返回首页</a> · {date_str}</p>
  <h1>{meta['title']}</h1>
{banner_html}
  <p style="color:#8888a8;font-size:0.88rem;margin-bottom:20px;">⏱️ {meta.get('readTime','5分钟')} · 标签：{tags_html}</p>
{body_html}
  <div class="disclaimer">⚠️ 免责声明：本站内容由 AI 自动生成，仅供学习参考，<strong>不构成投资建议</strong>。投资有风险，决策前请做好独立研究。</div>
  <p style="margin-top:32px;font-size:0.85rem;"><a href="/articles/" style="color:#8888a8;text-decoration:none;">← 全部文章</a> · <a href="/faq.html">常见问题 →</a></p>
</body>
</html>"""

articles_dir = OLD_WS / "site" / "articles"
articles_dir.mkdir(parents=True, exist_ok=True)
article_file = articles_dir / f"{article_id}.html"
article_file.write_text(full_html, encoding="utf-8")
print(f"[OK] 已写入: {article_file}")

# 更新 articles.json
articles_json_path = OLD_WS / "site" / "data" / "articles.json"
existing = json.loads(articles_json_path.read_text(encoding="utf-8")) if articles_json_path.exists() else []
entry = {
    "id": article_id,
    "title": meta["title"],
    "desc": meta["desc"],
    "date": date_str,
    "tags": meta.get("tags", ["AI工具"]),
    "readTime": meta.get("readTime", "5分钟"),
    "url": f"articles/{article_id}.html",
    "featured": True,
}
updated = [entry] + [a for a in existing if isinstance(a, dict) and a.get("id") != article_id]
updated = updated[:100]
(OLD_WS / "site" / "data").mkdir(parents=True, exist_ok=True)
articles_json_path.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[OK] articles.json 已更新 (共{len(updated)}篇)")

# 更新 sitemap.xml
sitemap_path = OLD_WS / "site" / "sitemap.xml"
if sitemap_path.exists():
    sitemap_content = sitemap_path.read_text(encoding="utf-8")
    new_entry = f"""  <!-- {date_str} -->
  <url>
    <loc>{canonical_url}</loc>
    <lastmod>{date_str}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.9</priority>
  </url>
</urlset>"""
    sitemap_content = sitemap_content.replace("</urlset>", new_entry)
    sitemap_path.write_text(sitemap_content, encoding="utf-8")
    print(f"[OK] sitemap.xml 已更新")
else:
    print("[WARN] sitemap.xml 不存在，跳过更新")

# 推送微信
print("\n" + "=" * 50)
print("2/2 推送至微信草稿箱")
print("=" * 50)

sys.path.insert(0, str(OLD_WS / "scripts"))
import wechat_publish as wxpub

os.environ["WECHAT_APPID"] = "wx8317fbdafcbcd670"
os.environ["WECHAT_SECRET"] = "50e971193da871fd6b939b3467a75396"
os.environ["SITE_URL"] = "https://spacenetx.com"

wxpub.APPID = os.environ["WECHAT_APPID"]
wxpub.SECRET = os.environ["WECHAT_SECRET"]
wxpub.SITE_URL = os.environ["SITE_URL"]
wxpub.SITE_ROOT = OLD_WS / "site"
wxpub.DATA_DIR = wxpub.SITE_ROOT / "data"

try:
    success = wxpub.push_draft(str(article_file))
    if success:
        print("\n✅ 全部完成！请去 mp.weixin.qq.com → 草稿箱查看并发布")
    else:
        print("\n⚠️ 推送失败")
except Exception as e:
    print(f"\n❌ 推送异常: {e}")
    import traceback
    traceback.print_exc()


# ============================================================================
# 行业轮动模块 - 新增功能
# ============================================================================

import json
import os
from datetime import datetime

ROTATION_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site", "data", "marquee_rotations.json")


def load_rotation_data():
    """加载行业轮动数据"""
    try:
        with open(ROTATION_DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[WARN] 轮动数据文件不存在: {ROTATION_DATA_PATH}")
        return None
    except json.JSONDecodeError as e:
        print(f"[ERROR] 轮动数据JSON解析失败: {e}")
        return None


def generate_rotation_daily_report():
    """生成每日轮动分析简报"""
    data = load_rotation_data()
    if not data:
        return None

    sectors = data.get("sectors", [])
    signal = data.get("rotation_signal", {})

    lines = []
    lines.append("=" * 50)
    lines.append("  [Chart] SpaceNetX 行业轮动日报")
    lines.append(f"  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("=" * 50)

    # 板块情绪指数
    lines.append("")
    lines.append("[情绪指数]")
    lines.append("-" * 40)
    emotion_ranked = sorted(sectors, key=lambda s: s.get("emotion", 0), reverse=True)
    for s in emotion_ranked:
        name = s["name"]
        emotion = s.get("emotion", 0)
        status = s.get("status", "")
        rsi = s.get("rsi", 50)
        bar_len = 10
        filled = int(emotion / 10)
        bar = "+" * filled + "-" * (bar_len - filled)
        indicator = ""
        if rsi > 70:
            indicator = " [超买]"
        elif rsi < 30:
            indicator = " [超卖]"
        lines.append(f"  {name:<8} {bar} {emotion:>3}% | {indicator} | 状态:{status} | RSI:{rsi}")

    # 资金流向
    lines.append("")
    lines.append("[资金流向]")
    lines.append("-" * 40)
    for s in sorted(sectors, key=lambda x: x.get("fund_flow", 0), reverse=True):
        sign = "+" if s.get("fund_flow", 0) > 0 else ""
        lines.append(f"  {sign}{s['fund_flow']:.1f}亿  {s['name']}")

    # 轮动信号
    lines.append("")
    lines.append("[轮动信号]")
    lines.append("-" * 40)
    lines.append(f"  当前阶段: {signal.get('current_phase', '未知')}")
    lines.append(f"  目标切换: {signal.get('next_target', '未知')}")
    lines.append(f"  操作建议: {signal.get('recommendation', '')}")

    # 持仓关联
    lines.append("")
    lines.append("[持仓关联]")
    lines.append("-" * 40)
    for s in sectors:
        name = s["name"]
        status = s.get("status", "")
        emotion = s.get("emotion", 0)
        action = "维持现状"
        if status == "满仓" and emotion < 40:
            action = "考虑减仓"
        elif status == "建仓" and s.get("momentum", 0) > 0.5:
            action = "符合建仓条件"
        elif status == "半仓" and emotion < 50:
            action = "考虑补仓"
        elif status == "持有":
            action = "继续持有观察"
        elif status == "定投中":
            action = "按原计划定投"
        lines.append(f"  {name}: {action}")

    lines.append("")
    lines.append("=" * 50)
    report_text = "\n".join(lines)
    print(report_text)
    return report_text


def make_rotation_cover_text():
    """生成轮动信号封面文字，供 make_cover() 调用"""
    data = load_rotation_data()
    if not data:
        return None
    sectors = data.get("sectors", [])
    signal = data.get("rotation_signal", {})
    top_sector = max(sectors, key=lambda s: s.get("emotion", 0))
    bottom_sector = min(sectors, key=lambda s: s.get("emotion", 0))
    lines = [
        f"情绪Top: {top_sector['name']}({top_sector.get('emotion',0)})" ,
        f"情绪Bottom: {bottom_sector['name']}({bottom_sector.get('emotion',0)})",
        f"当前轮动: {signal.get('current_phase', '')}",
        f"建议: {signal.get('recommendation', '')}",
    ]
    return " | ".join(lines)


def make_cover():
    """生成封面图，包含轮动信号文字"""
    from PIL import Image, ImageDraw, ImageFont
    import os

    cover_data = make_rotation_cover_text()
    if not cover_data:
        cover_data = "市场数据加载中..."

    lines = cover_data.split("| ")

    W, H = 1200, 630
    img = Image.new("RGB", (W, H), (20, 20, 40))
    draw = ImageDraw.Draw(img)

    # 字体
    font_paths = [
        r"C:/Windows/Fonts/msyh.ttc",
        r"/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/System/Library/Fonts/PingFang.ttc",
    ]
    font = None
    font_large = None
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, 28)
                font_large = ImageFont.truetype(fp, 42)
                break
            except:
                pass
    if not font:
        font = ImageFont.load_default()
        font_large = font

    title = "SpaceNetX 每日轮动信号"
    if font_large:
        bbox = draw.textbbox((0, 0), title, font=font_large)
        tw = bbox[2] - bbox[0]
        draw.text(((W - tw) // 2, 50), title, fill=(255, 255, 255), font=font_large)

    y = 160
    default_font = font if font else ImageFont.load_default()
    for line in lines:
        if not line.strip():
            continue
        bbox = draw.textbbox((0, 0), line, font=default_font)
        lw = bbox[2] - bbox[0]
        draw.text(((W - lw) // 2, y), line, fill=(200, 220, 255), font=default_font)
        y += 45

    date_str = datetime.now().strftime("%Y.%m.%d")
    footer = f"SpaceNetX | {date_str} | Marquee Rotation Engine"
    bbox = draw.textbbox((0, 0), footer, font=default_font)
    fw = bbox[2] - bbox[0]
    draw.text(((W - fw) // 2, 540), footer, fill=(120, 140, 180), font=default_font)

    out_dir = os.path.join(SITE_DIR, "static")
    os.makedirs(out_dir, exist_ok=True)
    cover_path = os.path.join(out_dir, "cover_rotation.png")
    img.save(cover_path, quality=90)
    print(f"[OK] 轮动封面已生成: {cover_path}")
    return cover_path



