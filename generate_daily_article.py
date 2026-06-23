#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spacenetx.com 每日内容自动生成脚本
每天自动生成一篇A股投研文章，保持网站持续更新
"""

import os
import re
import json
import markdown
from datetime import datetime

BASE_DIR = "C:/Users/Administrator/WorkBuddy/2026-05-29-08-46-48/auto-site/site"
ARTICLES_JSON = "C:/Users/Administrator/WorkBuddy/2026-05-29-08-46-48/auto-site/site/data/articles.json"

def generate_article(title, category, excerpt, content_md):
    """生成文章 HTML 文件"""
    today = datetime.now().strftime("%Y-%m-%d")
    slug = title.replace(" ", "-").replace("/", "-")[:50]
    filename = f"{today}-{slug}.html"
    filepath = os.path.join(BASE_DIR, filename)
    
    html = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} — SpacenetX A股投研</title>
    <meta name="description" content="{excerpt}">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
               max-width: 720px; margin: 40px auto; padding: 0 20px; line-height: 1.8; color: #1a1a1a; }}
        h1 {{ font-size: 1.8em; margin: 1.2em 0 0.6em; }}
        h2 {{ font-size: 1.3em; margin: 1em 0 0.5em; color: #2563eb; }}
        .meta {{ color: #888; font-size: 0.9em; margin-bottom: 2em; }}
        .tag {{ background: #f0f4ff; color: #2563eb; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; }}
        pre {{ background: #f5f5f5; padding: 12px; overflow-x: auto; border-radius: 6px; }}
        blockquote {{ border-left: 3px solid #2563eb; margin: 1em 0; padding: 0.5em 1em; background: #f0f4ff; }}
    </style>
</head>
<body>
    <p><a href="/">← 返回首页</a></p>
    <h1>{title}</h1>
    <div class="meta">📅 {date} · <span class="tag">{category}</span></div>
    <div class="content">
        {content}
    </div>
    <hr>
    <p><a href="/">← 返回 SpacenetX A股投研</a></p>
</body>
</html>""".format(
        title=title,
        excerpt=excerpt,
        category=category,
        date=today,
        content=markdown.markdown(content_md, extensions=['tables', 'fenced_code', 'nl2br', 'sane_lists'])
    )
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    
    # 更新 articles.json
    if os.path.exists(ARTICLES_JSON):
        with open(ARTICLES_JSON, "r", encoding="utf-8") as f:
            articles = json.load(f)
    else:
        articles = []
    
    articles.insert(0, {
        "title": title,
        "url": "/" + filename,
        "date": today,
        "category": category,
        "excerpt": excerpt
    })
    
    with open(ARTICLES_JSON, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 文章已生成: {filename}")
    return filepath

if __name__ == "__main__":
    # 示例：生成一篇今日文章
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"SpacenetX 每日内容生成 — {today}")
    print("⚠️ 请在自动化任务中调用此脚本，并传入真实文章数据")
