#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
spacenetx.com 每日内容自动生成脚本（V2）
CSS模板已按用户定的「浅色主题+口语化唠嗑风」更新
"""

import os
import re
import json
import markdown
from datetime import datetime

BASE_DIR = "C:/Users/Administrator/WorkBuddy/2026-05-29-08-46-48/auto-site/site"
ARTICLES_JSON = "C:/Users/Administrator/WorkBuddy/2026-05-29-08-46-48/auto-site/site/data/articles.json"

LIGHT_CSS = """
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { 
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: #f8fafc; color: #1a1a1a; line-height: 1.9; font-size: 16px;
    max-width: 760px; margin: 0 auto; padding: 24px 20px;
  }
  h1 { font-size: 1.6em; color: #0f172a; margin: 0.3em 0 0.6em; line-height: 1.4; }
  h2 { font-size: 1.2em; color: #1e40af; margin: 1.4em 0 0.5em; padding-bottom: 0.4em; border-bottom: 2px solid #dbeafe; }
  h3 { font-size: 1.05em; color: #334155; margin: 1em 0 0.3em; }
  p { margin: 0.7em 0; }
  a { color: #2563eb; text-decoration: none; } a:hover { text-decoration: underline; }
  table { width: 100%; border-collapse: collapse; margin: 1.2em 0; font-size: 0.93em; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
  thead { background: #1e40af; color: #fff; }
  th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }
  tbody tr:hover { background: #f1f5f9; }
  tbody tr:last-child td { border-bottom: none; }
  blockquote { border-left: 4px solid #2563eb; margin: 1em 0; padding: 12px 18px; background: linear-gradient(135deg, #eff6ff 0%, #dbeafe 100%); border-radius: 0 8px 8px 0; color: #334155; }
  code { background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; color: #dc2626; }
  pre { background: #1e293b; color: #e2e8f0; padding: 16px; border-radius: 8px; overflow-x: auto; margin: 1em 0; }
  pre code { background: transparent; color: inherit; padding: 0; }
  ul, ol { margin: 0.6em 0; padding-left: 1.8em; }
  li { margin: 0.3em 0; }
  strong { color: #0f172a; }
  hr { border: none; border-top: 2px solid #e2e8f0; margin: 1.5em 0; }
  .article-meta { color: #64748b; font-size: 0.9em; margin: 0.8em 0 1.2em; }
  .tag { display: inline-block; background: #dbeafe; color: #1e40af; padding: 2px 10px; border-radius: 12px; font-size: 0.85em; margin-right: 6px; }
  .back-link { display: inline-block; margin-top: 2em; color: #2563eb; font-size: 0.95em; }
  .back-link:hover { text-decoration: underline; }
  img { max-width: 100%; height: auto; border-radius: 8px; margin: 1em 0; }
</style>
"""

def generate_article(title, category, excerpt, content_md):
    """生成文章 HTML 文件（浅色主题+口语化风格）"""
    today = datetime.now().strftime("%Y-%m-%d")
    slug = re.sub(r'[^a-zA-Z0-9\u4e00-\u9fff]+', '-', title)[:50]
    filename = f"{today}-{slug}.html"
    filepath = os.path.join(BASE_DIR, "articles", filename)
    
    content_html = markdown.markdown(content_md, extensions=['tables', 'fenced_code', 'nl2br', 'sane_lists'])
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} | A股投研工具箱</title>
    <meta name="description" content="{excerpt}">
    {LIGHT_CSS}
</head>
<body>
    <p class="back-link"><a href="/" style="color:#8888a8;text-decoration:none;">← 返回首页</a> · {today}</p>
    
    <h1>{title}</h1>
    <p style="color:#8888a8;font-size:0.88rem;margin-bottom:20px;">⏱️ 5分钟 · 标签：<span class="tag">{category}</span></p>
    
    <div class="content">
        {content_html}
    </div>
    
    <p style="color:#8888a8;font-size:0.85em;margin-top:2em;">免责声明：本文仅为个人研究记录，不构成投资建议。投资有风险，入市需谨慎。😊</p>
    
    <p><a href="/" class="back-link">← 返回首页</a></p>
</body>
</html>"""
    
    os.makedirs(os.path.join(BASE_DIR, "articles"), exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    
    articles_path = ARTICLES_JSON
    if os.path.exists(articles_path):
        with open(articles_path, "r", encoding="utf-8") as f:
            articles = json.load(f)
    else:
        articles = []
    
    articles.insert(0, {
        "title": title,
        "file": f"articles/{filename}",
        "date": today,
        "category": category,
        "excerpt": excerpt
    })
    
    with open(articles_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 文章已生成: {filename}")
    return filepath

if __name__ == "__main__":
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"SpacenetX 每日内容生成 — {today}")
    print("⚠️ 请在自动化任务中调用此脚本，并传入真实文章数据")
