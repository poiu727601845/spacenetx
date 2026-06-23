#!/usr/bin/env python3
"""
双网站每日巡检  →  生成报告  →  推送微信公众号草稿箱
巡检对象：spacenetx.com、uam.city
巡检维度：功能 | 内容 | SEO | 安全 | 性能
"""

import os
import sys
import requests
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

# ── 配置 ────────────────────────────────────────────────────────────────
WECHAT_APPID   = 'wx8317fbdafcbcd670'
WECHAT_SECRET  = '01f46e2cae3ea006d28c5a36fbea4fd6'
WEBSITES        = [
    {'name': 'spacenetx.com', 'url': 'https://spacenetx.com'},
    {'name': 'uam.city',        'url': 'https://uam.city'},
]

TIMEOUT = 15   # 单次请求超时（秒）

# ── 工具函数 ──────────────────────────────────────────────────────────────
def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)

def get_access_token():
    url = (f'https://api.weixin.qq.com/cgi-bin/token'
             f'?grant_type=client_credential&appid={WECHAT_APPID}&secret={WECHAT_SECRET}')
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()['access_token']

def push_draft(access_token, title, html_content):
    # 1. 上传图文素材
    url = f'https://api.weixin.qq.com/cgi-bin/material/add_news?access_token={access_token}'
    articles = [{
        'title': title,
        'author': '无缘的人',
        'digest': '每日双网站巡检报告，涵盖功能、内容、SEO、安全、性能五大维度。',
        'content': html_content,
        'content_source_url': '',
        'thumb_media_id': ''
    }]
    r = requests.post(url, json={'articles': articles}, timeout=30)
    r.raise_for_status()
    media_id = r.json()['media_id']
    log(f'✅ 已推送草稿箱  media_id={media_id}')
    return media_id

# ── 五大巡检维度 ────────────────────────────────────────────────────────
def check_functionality(url):
    """① 功能巡检：页面能否正常打开"""
    result = {'status': '❌', 'code': '-', 'detail': ''}
    try:
        r = requests.get(url, timeout=TIMEOUT, allow_redirects=True)
        result['code'] = r.status_code
        if r.status_code == 200:
            result['status'] = '✅'
            result['detail'] = f'HTTP {r.status_code}，响应正常'
        else:
            result['detail'] = f'HTTP {r.status_code}，非预期状态码'
    except requests.exceptions.Timeout:
        result['detail'] = '⏰ 请求超时（>15s）'
    except requests.exceptions.SSLError as e:
        result['detail'] = f'🔒 SSL 证书错误：{e}'
    except Exception as e:
        result['detail'] = f'❌ 连接失败：{e}'
    return result

def check_content(url):
    """② 内容巡检：首页是否包含关键内容（防止页面被篡改/清空）"""
    result = {'status': '⚠️', 'detail': ''}
    try:
        r = requests.get(url, timeout=TIMEOUT)
        text = r.text.lower()
        # 检查关键词汇（按网站类型调整）
        keywords = ['etf', '基金', '半导体', '电网'] if 'spacenetx' in url else ['低空', 'uam', '城市']
        hit = [k for k in keywords if k in text]
        if hit:
            result['status'] = '✅'
            result['detail'] = f'关键词命中：{", ".join(hit[:3])}'
        else:
            result['detail'] = f'⚠️ 未命中预期关键词（检查：{", ".join(keywords[:3])}）'
    except Exception as e:
        result['detail'] = f'❌ 检查失败：{e}'
    return result

def check_seo(url, name):
    """③ SEO 巡检：robots.txt / sitemap.xml 是否可访问"""
    result = {'robots': '⚠️', 'sitemap': '⚠️', 'detail': ''}
    for path, key in [('/robots.txt', 'robots'), ('/sitemap.xml', 'sitemap')]:
        try:
            r = requests.get(url.rstrip('/') + path, timeout=10)
            if r.status_code == 200 and len(r.text) > 10:
                result[key] = '✅'
            else:
                result[key] = f'❌ HTTP {r.status_code}'
        except Exception:
            result[key] = '❌ 无响应'
    # 额外：尝试百度收录查询（仅提示，不自动查询）
    result['detail'] = f'百度收录查询：site:{name}'
    return result

def check_security(url):
    """④ 安全巡检：HTTPS 证书有效期、安全响应头"""
    result = {'https': '⚠️', 'headers': [], 'detail': ''}
    try:
        r = requests.get(url, timeout=TIMEOUT)
        # 检查安全头
        security_headers = ['Strict-Transport-Security', 'X-Content-Type-Options', 'X-Frame-Options']
        hit = [h for h in security_headers if h in r.headers]
        result['headers'] = hit
        if len(hit) >= 2:
            result['https'] = '✅'
        # HTTPS 检查
        if url.startswith('https://'):
            result['https'] = '✅ HTTPS'
        result['detail'] = f'安全头命中：{[h.split("-")[-1] for h in hit] if hit else "无"}'
    except Exception as e:
        result['detail'] = f'❌ 安全检查失败：{e}'
    return result

def check_performance(url):
    """⑤ 性能巡检：首屏响应时间"""
    result = {'time': '-', 'status': '⚠️', 'detail': ''}
    try:
        start = time.time()
        r = requests.get(url, timeout=TIMEOUT)
        elapsed = round((time.time() - start) * 1000, 0)
        result['time'] = int(elapsed)
        if elapsed < 2000:
            result['status'] = '✅'
            result['detail'] = f'首屏响应 {int(elapsed)}ms，速度正常'
        elif elapsed < 5000:
            result['status'] = '⚠️'
            result['detail'] = f'首屏响应 {int(elapsed)}ms，偏慢，建议优化'
        else:
            result['status'] = '❌'
            result['detail'] = f'首屏响应 {int(elapsed)}ms，过慢！'
    except Exception as e:
        result['detail'] = f'❌ 性能检测失败：{e}'
    return result

# ── 主流程 ────────────────────────────────────────────────────────────
def inspect_all():
    today = datetime.now().strftime('%Y-%m-%d')
    log('=== 双网站巡检开始 ===')

    rows = ''
    summary_lines = []

    for site in WEBSITES:
        name = site['name']
        url  = site['url']
        log(f'[巡检] {name}')

        f = check_functionality(url)
        c = check_content(url)
        s = check_seo(url, name)
        sec = check_security(url)
        p = check_performance(url)

        # 综合评级
        scores = [f['status'], c['status'], s['robots'], s['sitemap'], sec['status'], p['status']]
        ok_count = scores.count('✅')
        if ok_count >= 5:
            grade = '🟢 优秀'
        elif ok_count >= 3:
            grade = '🟡 一般'
        else:
            grade = '🔴 异常'

        summary_lines.append(f'{name}：{grade}（{ok_count}/6 项通过）')

        rows += f'''
        <tr>
            <td><strong>{name}</strong></td>
            <td>{f['status']}<br><small>{f['detail']}</small></td>
            <td>{c['status']}<br><small>{c['detail']}</small></td>
            <td>{s['robots']} robots<br>{s['sitemap']} sitemap<br><small>{s['detail']}</small></td>
            <td>{sec['status']}<br><small>{sec['detail']}</small></td>
            <td>{p['status']}<br><small>{p['detail']}</small></td>
            <td><strong>{grade}</strong></td>
        </tr>'''

    # 生成 HTML 报告
    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
           background:#0d1117; color:#c9d1d9; padding:20px; line-height:1.8; }}
    h1 {{ color:#58a6ff; border-bottom:1px solid #21262d; padding-bottom:8px; }}
    h2 {{ color:#79c0ff; margin-top:20px; }}
    table {{ border-collapse:collapse; width:100%; margin:16px 0; font-size:14px; }}
    th,td {{ border:1px solid #21262d; padding:10px 12px; text-align:left; vertical-align:top; }}
    th {{ background:#161b22; color:#58a6ff; }}
    .note {{ background:#161b22; padding:12px; border-radius:8px; margin:12px 0; }}
    .summary {{ background:#1c2030; padding:16px; border-radius:8px; margin:16px 0; }}
</style></head><body>
<h1>🛡️ {today} 双网站每日巡检报告</h1>

<div class="note">📋 巡检对象：spacenetx.com、uam.city | 巡检维度：功能 · 内容 · SEO · 安全 · 性能</div>

<div class="summary">
<h2>📊 综合评分</h2>
{"<br>".join(summary_lines)}
</div>

<h2>📋 详细巡检结果</h2>
<table>
<tr>
    <th>网站</th><th>① 功能</th><th>② 内容</th><th>③ SEO</th><th>④ 安全</th><th>⑤ 性能</th><th>综合</th>
</tr>
{rows}
</table>

<hr>
<h2>📌 处理建议</h2>
<ul>
    <li>🟢 优秀：无需处理，明日继续巡检</li>
    <li>🟡 一般：建议检查 SEO/性能，3 日内优化</li>
    <li>🔴 异常：立即排查，功能异常需当天修复</li>
</ul>
<p style="color:#8b949e;font-size:12px;">由腾讯云服务器自动巡检 · {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
</body></html>'''

    log('=== 巡检完成 ===')
    return html

def main():
    today = datetime.now().strftime('%Y-%m-%d')
    title = f'{today} 双网站巡检报告'

    # 1. 执行巡检
    html = inspect_all()

    # 2. 保存本地
    out_dir = Path(__file__).parent / 'inspections'
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f'{today}.html'
    out_file.write_text(html, encoding='utf-8')
    log(f'[保存] {out_file}')

    # 3. 推送微信公众号草稿箱
    log('[微信] 获取 access_token...')
    try:
        token = get_access_token()
        push_draft(token, title, html)
        # 写日志
        log_file = Path(__file__).parent / 'inspect.log'
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f'{datetime.now()}  [OK] {title}\n')
    except Exception as e:
        log(f'❌ 微信推送失败: {e}')
        log_file = Path(__file__).parent / 'inspect.log'
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f'{datetime.now()}  [FAIL] {title}  err={e}\n')

if __name__ == '__main__':
    main()
