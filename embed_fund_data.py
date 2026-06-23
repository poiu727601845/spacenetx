#!/usr/bin/env python3
"""spacenetx.com - 内嵌基金估值数据到 index.html"""
import json, urllib.request, urllib.parse, re, os, sys, time

FUND_CODES = ['012733','007300','025832','001410','003095','163406','110020','001990']

def fetch(codes):
    results = []
    for code in codes:
        try:
            url = f'http://fundgz.1234567.com.cn/js/{code}.js'
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Referer': 'http://fund.eastmoney.com/'
            })
            with urllib.request.urlopen(req, timeout=8) as resp:
                text = resp.read().decode('utf-8')
            json_str = re.sub(r'^jsonpgz\(', '', text)
            json_str = re.sub(r'\);\s*$', '', json_str).strip()
            data = json.loads(json_str)
            results.append(data)
            print(f'  OK: {code} {data.get("name","")} {data.get("gszzl","--")}%')
        except Exception as e:
            print(f'  FAIL: {code} - {e}')
            results.append({'fundcode': code, 'name': '', 'gsz': '--', 'gszzl': '--'})
    return results

def embed(html_path, fund_data):
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    data_json = json.dumps(fund_data, ensure_ascii=False)
    marker = '<script>'
    if marker not in html:
        print('ERROR: 找不到 <script> 标签')
        return False

    inject = f'''<script>
// === 自动生成的内嵌数据（每次部署时更新）===
window.__EMBEDDED_DATA__ = {data_json};
// === 内嵌数据结束 ===
</script>
'''
    html = html.replace(marker, inject + '\n' + marker, 1)

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return True

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(base_dir, 'public', 'index.html')
    if not os.path.exists(html_path):
        print(f'ERROR: {html_path} 不存在')
        sys.exit(1)

    print('=== 获取基金估值数据 ===')
    fund_data = fetch(FUND_CODES)

    print(f'\n=== 嵌入数据到 index.html ===')
    if embed(html_path, fund_data):
        print('✅ 数据已内嵌')
    else:
        print('❌ 内嵌失败')
        sys.exit(1)

if __name__ == '__main__':
    main()
