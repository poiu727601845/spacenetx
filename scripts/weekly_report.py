#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SpaceNetX.com 周报生成器
读取持仓配置和轮动数据，生成周报HTML文件到 site/reports/
"""

import json
import os
import sys
from datetime import datetime, timedelta

# 路径
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_DIR = os.path.join(BASE_DIR, "site")
DATA_DIR = os.path.join(SITE_DIR, "data")
REPORTS_DIR = os.path.join(SITE_DIR, "reports")

PORTFOLIO_PATH = os.path.join(DATA_DIR, "portfolio.json")
ROTATION_PATH = os.path.join(DATA_DIR, "marquee_rotations.json")


def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[WARN] 文件未找到: {path}")
        return None
    except Exception as e:
        print(f"[ERROR] 读取失败: {e}")
        return None


def get_emotion_color(e):
    if e >= 70: return "#ff6b6b"
    if e >= 55: return "#ffa94d"
    if e >= 40: return "#69db7c"
    return "#74c0fc"


def get_momentum_txt(m):
    if m >= 0.7: return "Strong"
    if m >= 0.5: return "Rising"
    if m >= 0.3: return "Cooling"
    return "Low"


def generate_weekly_report():
    portfolio = load_json(PORTFOLIO_PATH)
    rotation = load_json(ROTATION_PATH)

    now = datetime.now()
    week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
    week_end = (now + timedelta(days=6 - now.weekday())).strftime("%Y-%m-%d")

    # 生成持仓HTML
    holdings_html = ""
    holdings = portfolio.get("holdings", []) if portfolio else []
    total_val = 0.0
    total_cost = 0.0

    for h in holdings:
        nm = h.get("name", "?")
        code = h.get("fund_code", h.get("code", ""))
        shares = h.get("shares", h.get("amount", 0))
        cost = h.get("avg_cost", h.get("cost", 0))
        price = h.get("current_price", 0)
        weight = h.get("weight", 0)
        val = price * shares if price else shares * cost
        profit = (price - cost) * shares if price else 0
        pct = ((price / cost) - 1) * 100 if cost > 0 else 0
        total_val += val
        total_cost += shares * cost
        clr = "#ff6b6b" if profit < 0 else "#51cf66"
        icon = "-" if profit < 0 else "+"
        holdings_html += f"""<tr>
<td>{nm}<br><small style="color:#888">{code}</small></td>
<td>{shares:,.0f}</td>
<td>¥{cost:.3f}</td>
<td>¥{price:.3f}</td>
<td>¥{val:,.0f}</td>
<td style="color:{clr}">{icon}¥{profit:,.2f} ({pct:+.1f}%)</td>
<td>{weight:.1f}%</td></tr>\n"""

    total_profit = total_val - total_cost
    total_pct = ((total_val / total_cost) - 1) * 100 if total_cost > 0 else 0

    # 轮动部分
    sectors_html = ""
    signal_html = ""
    if rotation:
        sectors = rotation.get("sectors", [])
        signal = rotation.get("rotation_signal", {})

        for s in sorted(sectors, key=lambda x: x.get("emotion", 0), reverse=True):
            nm = s["name"]
            em = s.get("emotion", 0)
            mo = s.get("momentum", 0)
            rsi = s.get("rsi", 50)
            flow = s.get("fund_flow", 0)
            status = s.get("status", "")
            clr = get_emotion_color(em)
            sign = "+" if flow > 0 else ""
            fc = "#ff6b6b" if flow > 0 else "#74c0fc"
            fill_w = max(em, 5)
            sectors_html += f"""<tr>
<td>{nm}</td>
<td><div style="display:inline-block;width:80px;height:10px;background:#333;border-radius:5px;vertical-align:middle"><div style="width:{fill_w}%;height:100%;background:{clr};border-radius:5px"></div></div> {em}%</td>
<td>{get_momentum_txt(mo)}<br><small>{mo:.2f}</small></td>
<td>{rsi}</td>
<td style="color:{fc}">{sign}¥{flow:.1f}亿</td>
<td>{status}</td></tr>\n"""

        cp = signal.get("current_phase", "-")
        nt = signal.get("next_target", "-")
        rec = signal.get("recommendation", "")
        signal_html = f"""<div class="signal">
<h3>轮动信号</h3>
<p><strong>当前阶段:</strong> {cp}</p>
<p><strong>目标切换:</strong> {nt}</p>
<p><strong>建议:</strong> {rec}</p>
</div>"""

    # 情绪分析
    sent_html = ""
    if rotation:
        sectors = rotation.get("sectors", [])
        hot = max(sectors, key=lambda s: s.get("emotion", 0))
        cold = min(sectors, key=lambda s: s.get("emotion", 0))
        avg = sum(s.get("emotion", 0) for s in sectors) / len(sectors)
        label = "Overheated" if avg >= 65 else "Warm" if avg >= 50 else "Cool" if avg >= 35 else "Cold"

    # 汇总HTML
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>SpaceNetX 周报 - 第{now.isocalendar()[1]}周</title>
<style>
body {{ font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; background: #0d1117; color: #c9d1d9; margin: 0; padding: 20px; }}
.container {{ max-width: 1100px; margin: 0 auto; }}
h1 {{ color: #58a6ff; text-align: center; border-bottom: 1px solid #30363d; padding-bottom: 15px; }}
.subtitle {{ text-align: center; color: #8b949e; margin-bottom: 30px; }}
.section {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; margin-bottom: 20px; }}
.section h2 {{ color: #58a6ff; margin-top: 0; border-bottom: 1px solid #21262d; padding-bottom: 10px; }}
table {{ width: 100%; border-collapse: collapse; }}
th {{ background: #21262d; color: #c9d1d9; padding: 10px; text-align: left; font-size: 14px; }}
td {{ padding: 8px 10px; border-top: 1px solid #21262d; font-size: 14px; }}
.signal {{ background: #1c2333; border-left: 4px solid #58a6ff; padding: 15px; border-radius: 4px; margin: 10px 0; }}
.badge {{ background: #238636; color: white; padding: 2px 8px; border-radius: 10px; font-size: 12px; }}
footer {{ text-align: center; color: #484f58; margin-top: 30px; padding-top: 15px; border-top: 1px solid #21262d; }}
</style>
</head>
<body>
<div class="container">
<h1>SpaceNetX 投资周报</h1>
<p class="subtitle">Week {now.isocalendar()[1]} | {week_start} ~ {week_end} | Generated: {now.strftime('%Y-%m-%d %H:%M')}</p>

<div class="section">
<h2>持仓周报</h2>
<table>
<thead><tr><th>基金</th><th>份额</th><th>成本价</th><th>现价</th><th>市值</th><th>盈亏</th><th>权重</th></tr></thead>
<tbody>{holdings_html}</tbody>
<tfoot><tr style="font-weight:bold;border-top:2px solid #4a90d9">
<td colspan="4">合计</td>
<td>¥{total_val:,.0f}</td>
<td style="color={'#ff6b6b' if total_profit < 0 else '#51cf66'}">{'-' if total_profit < 0 else '+'}¥{abs(total_profit):,.2f} ({total_pct:+.1f}%)</td>
<td>100%</td></tr></tfoot>
</table>
</div>

<div class="section">
<h2>轮动回顾</h2>
<table>
<thead><tr><th>板块</th><th>情绪</th><th>动量</th><th>RSI</th><th>资金流向</th><th>状态</th></tr></thead>
<tbody>{sectors_html}</tbody>
</table>
{signal_html}
</div>

<div class="section">
<h2>情绪分析</h2>
<p>市场整体情绪: <strong>{avg:.0f}/100 ({label})</strong></p>
<p>最热板块: {hot.get('name', '-') if rotation else '-'} ({hot.get('emotion', '-') if rotation else '-'})</p>
<p>最冷板块: {cold.get('name', '-') if rotation else '-'} ({cold.get('emotion', '-') if rotation else '-'})</p>
</div>

<div class="section">
<h2>下周展望</h2>
<p>根据轮动信号，下一阶段目标切换至 <strong>{nt}</strong>。</p>
<p>建议关注: {rec}</p>
<p>当前持仓中建议:</p>
<ul>
{"<li>" + hot.get('name', '') + ": 情绪偏高，注意追高风险</li>" if rotation else ""}
{"<li>" + cold.get('name', '') + ": 情绪低迷，可考虑逢低布局</li>" if rotation else ""}
</ul>
</div>

<footer>SpaceNetX.com | Weekly Report Generator v1.0</footer>
</div>
</body>
</html>"""

    # 保存
    os.makedirs(REPORTS_DIR, exist_ok=True)
    week_num = now.isocalendar()[1]
    filename = f"weekly_report_w{week_num:02d}_{now.strftime('%Y-%m-%d')}.html"
    filepath = os.path.join(REPORTS_DIR, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"[OK] 周报已生成: {filepath}")
    return filepath


if __name__ == "__main__":
    generate_weekly_report()
