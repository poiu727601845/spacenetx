#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
每日自动维护脚本：
1. 从 articles/ 目录 HTML 文件重建 articles.json
2. 更新 ai_digest.json（基于当日文章 + DeepSeek API）
"""

import os
import json
import re
import urllib.request
import urllib.error
from datetime import datetime

SITE_DIR = "/home/ubuntu/wechat-publisher/site"
ARTICLES_DIR = os.path.join(SITE_DIR, "articles")
DATA_DIR = os.path.join(SITE_DIR, "data")
ARTICLES_JSON = os.path.join(DATA_DIR, "articles.json")
DIGEST_JSON = os.path.join(DATA_DIR, "ai_digest.json")

DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
# 如果没有环境变量，用fallback规则生成digest

def rebuild_articles_json():
    """从 HTML 文件重建 articles.json"""
    articles = []
    html_files = [f for f in os.listdir(ARTICLES_DIR) if f.endswith(".html")]

    for fname in sorted(html_files, reverse=True):
        fpath = os.path.join(ARTICLES_DIR, fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()

            date_match = re.search(r"(\d{4}-\d{2}-\d{2})", fname)
            date_str = date_match.group(1) if date_match else datetime.now().strftime("%Y-%m-%d")

            title_match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE)
            if not title_match:
                title_match = re.search(r"<h1>(.*?)</h1>", content, re.IGNORECASE)
            title = title_match.group(1).strip() if title_match else fname.replace(".html", "")
            title = re.sub(r" — SpacenetX A股投研$", "", title).strip()
            title = re.sub(r" \| SpacenetX$", "", title).strip()

            excerpt_match = re.search(r'<meta name="description" content="(.*?)"', content, re.IGNORECASE)
            excerpt = excerpt_match.group(1).strip() if excerpt_match else title[:100]

            cat_match = re.search(r'class="tag">(.*?)</span>', content, re.IGNORECASE)
            category = cat_match.group(1).strip() if cat_match else "ETF"

            articles.append({
                "id": fname.replace(".html", ""),
                "title": title,
                "excerpt": excerpt,
                "category": category,
                "date": date_str,
                "file": fname
            })
        except Exception as e:
            print(f"处理失败 {fname}: {e}")

    articles.sort(key=lambda x: x["date"], reverse=True)

    with open(ARTICLES_JSON, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

    print(f"[articles.json] 重建完成！共 {len(articles)} 篇文章")
    return articles


def generate_digest_with_ai(today_articles):
    """用 DeepSeek API 生成 AI 投研日报"""
    if not DEEPSEEK_API_KEY:
        return None

    titles = [a["title"] for a in today_articles[:5]]
    prompt = f"""今天是 {datetime.now().strftime("%Y-%m-%d")}，网站最新文章标题：
""" + "\n".join(f"- {t}" for t in titles) + """

请生成5条A股投研日报摘要，格式为JSON数组，每条包含：
- tag: red（主线）/ orange（机会）/ blue（策略）/ green（工具）/ purple（展望）
- label: 简短标签（2-4字）
- text: 50字以内的投研观点

只返回JSON数组，不要其他内容。"""

    try:
        data = json.dumps({
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }).encode()

        req = urllib.request.Request(
            "https://api.deepseek.com/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode())
            content = result["choices"][0]["message"]["content"]
            items = json.loads(content)
            return {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "generated": True,
                "items": items
            }
    except Exception as e:
        print(f"[digest] AI生成失败: {e}")
        return None


def generate_digest_fallback(articles):
    """规则fallback：基于最新文章生成digest"""
    today = datetime.now().strftime("%Y-%m-%d")
    latest = [a for a in articles if a["date"] == today][:5]

    # 默认digest
    items = [
        {"tag": "red", "label": "主线", "text": "资源板块（有色金属/小金属）持续强势，关注铜、铝、稀土细分方向"},
        {"tag": "orange", "label": "观察", "text": "科技板块处于调整期，半导体设备与材料逢低布局机会"},
        {"tag": "blue", "label": "回避", "text": "高位题材股回调风险加大，控制仓位等待企稳信号"},
        {"tag": "green", "label": "机会", "text": "电力电网设备受益于夏季用电高峰，关注特高压与配网改造"},
        {"tag": "purple", "label": "定投", "text": "医疗/新能源处于历史估值低位区间，适合左侧分批建仓"}
    ]

    # 如果当天有文章，动态生成
    if latest:
        keywords = " ".join(a["title"] + " " + a["excerpt"] for a in latest)
        # 通信/半导体关键词
        if "通信" in keywords or "半导体" in keywords or "芯片" in keywords:
            items[0] = {"tag": "red", "label": "主线", "text": "通信设备与半导体ETF获资金关注，板块轮动信号值得跟踪"}
        if "电网" in keywords or "设备" in keywords:
            items[3] = {"tag": "green", "label": "机会", "text": "电网设备板块出现回调买入机会，关注目标价区间逢低布局"}
        if "量化" in keywords or "ETF" in keywords:
            items[4] = {"tag": "purple", "label": "工具", "text": "量化工具ETF选择重视费率与跟踪误差，多策略分散配置"}

    return {
        "date": today,
        "generated": bool(DEEPSEEK_API_KEY),
        "items": items
    }


def update_digest_json(articles):
    """更新 ai_digest.json"""
    # 先尝试AI生成
    digest = generate_digest_with_ai([a for a in articles if a["date"] == datetime.now().strftime("%Y-%m-%d")])
    if not digest:
        digest = generate_digest_fallback(articles)

    with open(DIGEST_JSON, "w", encoding="utf-8") as f:
        json.dump(digest, f, ensure_ascii=False, indent=2)

    print(f"[ai_digest.json] 更新完成！date={digest['date']}, items={len(digest['items'])}")
    return digest


if __name__ == "__main__":
    print(f"===== spacenetx.com 每日维护 {datetime.now().strftime('%Y-%m-%d %H:%M')} =====")

    # 1. 重建 articles.json
    articles = rebuild_articles_json()

    # 2. 更新 ai_digest.json
    update_digest_json(articles)

    print("===== 完成 =====")
