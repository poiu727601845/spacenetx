#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
公众号推送巡检器 v2
每天自动运行，检查推送状态并告警
"""
import json
import os
import re
import subprocess
import sys
import traceback
from pathlib import Path
from datetime import datetime

PUB_DIR = Path('/home/ubuntu/wechat-publisher')
SITE_DIR = PUB_DIR / 'site'
ARTICLES_DIR = SITE_DIR / 'articles'
DATA_DIR = SITE_DIR / 'data'
ARTICLES_JSON = DATA_DIR / 'articles.json'
RUN_LOG = PUB_DIR / 'run.log'
PUBLISH_DS = PUB_DIR / 'publish_ds.py'
ALERT_LOG = DATA_DIR / 'push_alert.log'

def check_run_log():
    """检查 run.log 中最近的推送状态"""
    if not RUN_LOG.exists():
        return False, "run.log 不存在"
    
    content = RUN_LOG.read_text(encoding='utf-8')
    lines = content.strip().split('\n')
    
    for i, line in enumerate(lines[::-1]):
        if '全部完成' in line:
            # 找到最近的成功记录
            for j in range(i-1, max(-1, i-10), -1):
                if j >= 0 and '草稿创建成功' in lines[-1-j]:
                    return True, "最近一次推送成功"
            return True, "最近一次推送成功"
        elif 'FAIL' in line or '失败' in line:
            return False, f"推送失败: {line.strip()}"
        elif 'KeyError' in line or 'SyntaxError' in line:
            return False, f"脚本错误: {line.strip()}"
    
    return False, "未找到推送记录"

def check_pending_articles():
    """检查有没有文章已生成但未推送"""
    if not ARTICLES_DIR.exists():
        return [], []
    
    html_files = [f for f in os.listdir(ARTICLES_DIR) if f.endswith('.html')]
    log_drafts = set()
    
    if RUN_LOG.exists():
        content = RUN_LOG.read_text(encoding='utf-8')
        pattern = r'已写入:.*?/articles/([^"\']+)'
        for m in re.finditer(pattern, content):
            log_drafts.add(m.group(1).replace('.html', ''))
    
    published = []
    pending = []
    for fn in html_files:
        article_id = fn.replace('.html', '')
        if article_id in log_drafts:
            published.append(article_id)
        else:
            pending.append(article_id)
    
    return pending, published

def main():
    print(f"===== 公众号推送巡检 {datetime.now().strftime('%Y-%m-%d %H:%M')} =====")
    
    try:
        ok, msg = check_run_log()
        print(f"[推送状态] {msg}")
        
        pending, published = check_pending_articles()
        if pending:
            print(f"[待推送文章] {len(pending)} 篇: {', '.join(pending[:3])}")
        else:
            print("[待推送文章] 无")
        
        if ok:
            print("[状态] ✅ 今日推送正常")
            return 0
        else:
            print(f"[状态] ⚠️ 推送异常: {msg}")
            print("[建议]")
            print("  1. 手动运行: cd /home/ubuntu/wechat-publisher && python3 publish_ds.py")
            print("  2. 检查微信后台草稿箱: https://mp.weixin.qq.com")
            return 1
    except Exception as e:
        print(f"[ERROR] 巡检程序异常: {e}")
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    main()
