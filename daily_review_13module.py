#!/usr/bin/env python3
"""
每日13模块A股复盘  →  生成HTML  →  推送微信公众号草稿箱
数据来源：westock-data API + neodata API（双源互补）
"""

import os
import sys
import requests
import json
from datetime import datetime, timedelta
from pathlib import Path
import subprocess
import time

# ── 配置 ──────────────────────────────────────────────────────────────
WECOM_API_ID   = 'wx8317fbdafcbcd670'
WECOM_SECRET   = '01f46e2cae3ea006d28c5a36fbea4fd6'
DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY', '')
WECOM_PUSH_SCRIPT = Path(__file__).parent / 'scripts' / 'wechat_publish.py'

# ── 工具函数 ────────────────────────────────────────────────────────────
def log(msg):
    print(f'[{(datetime.now().strftime("%H:%M:%S"))}] {msg}', flush=True)

def get_access_token():
    url = (f'https://api.weixin.qq.com/cgi-bin/token'
            f'?grant_type=client_credential&appid={WECOM_API_ID}&secret={WECOM_SECRET}')
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    return r.json()['access_token']

def upload_news(access_token, articles):
    url = f'https://api.weixin.qq.com/cgi-bin/material/add_news?access_token={access_token}'
    payload = {'articles': articles}
    r = requests.post(url, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()['media_id']

# ── 数据获取（双源）─────────────────────────────────────────────────────
def fetch_westock_data():
    """调用 westock-data 本地 API（假设在服务器 localhost:8000 运行）
       如果不存在则跳过，用 neodata 补充
    """
    try:
        # 大盘指数
        indices = {}
        for code, name in [('000001.SH','上证指数'),('399001.SZ','深证成指'),
                           ('000300.SH','沪深300'),('399006.SZ','创业板指'),('000688.SH','科创50')]:
            r = requests.get(f'http://localhost:8000/api/quote?code={code}', timeout=8)
            if r.status_code == 200:
                d = r.json()
                indices[name] = d
        return {'indices': indices, 'source': 'westock'}
    except Exception as e:
        log(f'[westock] 不可用: {e}')
        return {'indices': {}, 'source': 'none'}

def fetch_neodata_news():
    """调用 neodata 搜索政策/消息面"""
    try:
        r = requests.get('http://localhost:8001/api/search?q=A股+政策+今日&type=news&limit=10', timeout=10)
        if r.status_code == 200:
            return r.json().get('news', [])
    except Exception as e:
        log(f'[neodata] 不可用: {e}')
    return []

def fetch_market_data_fallback():
    """westock/neodata 都不可用时的免费 API 兜底方案"""
    log('[fallback] 使用新浪财经免费API获取行情...')
    result = {'indices': {}, 'limit_up': 0, 'limit_down': 0, 'source': 'fallback'}
    try:
        sina_codes = 's_sh000001,s_sz399001,s_sh000300,s_sz399006,s_sh000688'
        r = requests.get(f'https://hq.sinajs.cn/list={sina_codes}', timeout=10)
        if r.status_code == 200:
            for line in r.text.strip().split('\n'):
                if '=' not in line:
                    continue
                code = line.split('=')[0].split('_')[-1]
                fields = line.split('"')[1].split(',')
                if len(fields) > 3:
                    result['indices'][code] = {
                        'name': fields[0],
                        'price': float(fields[1]),
                        'change_pct': float(fields[2])
                    }
    except Exception as e:
        log(f'[fallback] 新浪API失败: {e}')
    return result

# ── DeepSeek 生成复盘 ───────────────────────────────────────────────────
def build_prompt(data):
    today = datetime.now().strftime('%Y年%m月%d日')
    prompt = f"""你是一位专业的A股独立投资人，请严格按照以下13个模块，为{today}生成完整的每日复盘报告。
报告将发布在微信公众号「无缘的人」，面向有一定经验的A股投资者。

## 数据背景
{json.dumps(data, ensure_ascii=False, indent=2)[:3000]}

## 13个模块要求

**模块1：大盘行情** ⭐
输出：上证/深证/沪深300/创业板/科创50的收盘点位、涨跌幅、成交额；沪深合计成交额（>3万亿=健康）；涨跌家数；涨停/跌停数（>70=强势）

**模块2：主力资金流向** 💰
输出：主力净流入TOP3板块（板块名+金额）；主力净流出TOP3；北向资金流向；宽基ETF流向

**模块3：主线轮动雷达** 🔄
对涨幅>3%的板块进行四维评分（持续性/风险/逻辑硬度/建仓价值，各0-10分）；判断主线是否切换；建仓板块必查（通信设备/元件/电网设备/玻璃玻纤）

**模块4：板块轮动速度** 🔁
判断轮动速度（慢/中/快），给出判断依据

**模块5：政策消息面** 📰
国内政策、国际动态、大宗商品、未来5日重要事件日历

**模块6：基金净值验证** 💼
6只持仓基金：025832（电网ETF）、007300（半导体ETF）、012733（AI主题）、163406（兴全合润）、001990（中欧数据挖掘）、110020（沪深300）。给出昨日净值、涨幅、今日影响分析

**模块7：基金影响判断** + **模块7.5：建仓板块扫描**
对6只基金逐一给出操作建议（持有/暂缓加仓/可补仓/减仓）；扫描建仓板块（元器件/医药/储能/玻璃/电力）是否满足建仓条件

**模块8：下期预判** 📈
预判明日上证/创业板/科创50点位区间；黄金/美元走势；持仓基金净值变动预判

**模块9：换手率情绪** 📊（可选）
全市场换手率、融资余额变化、龙虎榜机构买卖TOP

**模块10：风险提示** ⚠️
黑天鹅风险、持仓集中度、流动性风险、当前最大回撤

**模块11：自查清单**（AI内部检查，不输出）
不输出给用户

**模块12：社保持仓追踪** 🏦（可选）
社保基金Q1/Q2持仓变动

**模块13：大佬言论解码** 🎙️（可选）
高盛/中金/中信/知名投资人最新观点

## 输出格式要求
- 用HTML格式输出，包含完整CSS样式（暗色主题，适合微信公众号）
- 每个模块用 <h2> 标题
- 数据用表格或加粗显示
- 总长度控制在 3000-5000 字
- 语言简洁专业，有实操建议
"""
    return prompt

def generate_review_with_deepseek(prompt):
    if not DEEPSEEK_API_KEY:
        log('[DeepSeek] API Key 未配置，跳过AI生成')
        return None
    headers = {'Authorization': f'Bearer {DEEPSEEK_API_KEY}',
               'Content-Type': 'application/json'}
    payload = {
        'model': 'deepseek-chat',
        'messages': [{'role': 'user', 'content': prompt}],
        'temperature': 0.7,
        'max_tokens': 6000
    }
    r = requests.post('https://api.deepseek.com/v1/chat/completions',
                     headers=headers, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()['choices'][0]['message']['content']

def generate_fallback_review(data):
    """DeepSeek 不可用时的简单模板生成"""
    today = datetime.now().strftime('%Y年%m月%d日')
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background:#0d1117; color:#c9d1d9; padding:20px; line-height:1.8; }}
h1 {{ color:#58a6ff; border-bottom:1px solid #21262d; padding-bottom:8px; }}
h2 {{ color:#79c0ff; margin-top:24px; }}
table {{ border-collapse:collapse; width:100%; margin:12px 0; }}
th,td {{ border:1px solid #21262d; padding:8px 12px; text-align:left; }}
th {{ background:#161b22; color:#58a6ff; }}
.note {{ background:#161b22; padding:12px; border-radius:8px; margin:12px 0; }}
</style></head><body>
<h1>📅 {today} A股每日复盘（13模块）</h1>
<div class="note">⚠️ 今日为模板简版，AI生成服务暂不可用。请检查 DeepSeek API Key 配置。</div>
<h2>⭐ 模块1：大盘行情</h2><p>数据获取中，请稍后查看完整版...</p>
<h2>💰 模块2：主力资金流向</h2><p>数据获取中...</p>
<h2>🔄 模块3：主线轮动雷达</h2><p>数据获取中...</p>
<h2>🔁 模块4：板块轮动速度</h2><p>数据获取中...</p>
<h2>📰 模块5：政策消息面</h2><p>数据获取中...</p>
<h2>💼 模块6：基金净值验证</h2><p>数据获取中...</p>
<h2>📊 模块7/7.5：基金影响+建仓扫描</h2><p>数据获取中...</p>
<h2>📈 模块8：下期预判</h2><p>数据获取中...</p>
<h2>⚠️ 模块9/10/13：情绪+风险+大佬言论</h2><p>数据获取中...</p>
<hr><p style="color:#8b949e;font-size:12px;">由腾讯云服务器自动生成 · {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
</body></html>"""
    return html

# ── 主流程 ─────────────────────────────────────────────────────────────
def main():
    log('=== 13模块复盘开始 ===')
    today = datetime.now().strftime('%Y-%m-%d')
    title = f'{today} A股每日复盘（13模块）'

    # 1. 获取数据（双源）
    log('[数据] 获取 westock 数据...')
    ws_data = fetch_westock_data()
    log('[数据] 获取 neodata 消息...')
    news = fetch_neodata_news()
    if not ws_data.get('indices'):
        log('[数据] westock 无数据，使用 fallback...')
        ws_data = fetch_market_data_fallback()
    data = {'westock': ws_data, 'news': news, 'date': today}

    # 2. 生成复盘内容
    log('[生成] 调用 DeepSeek 生成复盘...')
    prompt = build_prompt(data)
    html = generate_review_with_deepseek(prompt)
    if not html:
        log('[生成] DeepSeek 失败，使用模板...')
        html = generate_fallback_review(data)

    # 3. 保存本地
    out_dir = Path(__file__).parent / 'reviews'
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f'{today}.html'
    out_file.write_text(html, encoding='utf-8')
    log(f'[保存] {out_file}')

    # 4. 推送微信公众号草稿箱
    log('[微信] 获取 access_token...')
    try:
        token = get_access_token()
        articles = [{
            'title': title,
            'author': '无缘的人',
            'digest': f'{today} A股每日13模块完整复盘，涵盖大盘、资金、主线、基金、风险全流程分析。',
            'content': html,
            'content_source_url': '',
            'thumb_media_id': ''   # 可选：先不传封面，用户自行添加
        }]
        media_id = upload_news(token, articles)
        log(f'✅ 推送成功！media_id={media_id}')
        # 写日志
        log_file = Path(__file__).parent / 'review.log'
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f'{datetime.now()}  [OK] {title}  media_id={media_id}\n')
    except Exception as e:
        log(f'❌ 微信推送失败: {e}')
        log_file = Path(__file__).parent / 'review.log'
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(f'{datetime.now()}  [FAIL] {title}  err={e}\n')

    # 推送 AI 摘要到前端 API
    try:
        digest_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "generated": True,
            "items": [
                {"tag": "red", "label": "主线", "text": html[:100]},
                {"tag": "orange", "label": "预判", "text": html[100:200] if len(html) > 200 else html[:100]},
                {"tag": "blue", "label": "回避", "text": html[200:300] if len(html) > 300 else html[:100]},
                {"tag": "green", "label": "机会", "text": html[300:400] if len(html) > 400 else html[:100]},
                {"tag": "purple", "label": "定投", "text": html[400:500] if len(html) > 500 else html[:100]},
            ],
            "source": "deepseek"
        }
        requests.post('http://127.0.0.1:8200/api/digest/update', json=digest_data, timeout=5)
        log('[摘要] AI摘要已推送到前端 API')
    except Exception as e:
        log(f'[摘要] 推送失败: {e}')

    log('=== 13模块复盘完成 ===')

if __name__ == '__main__':
    main()
