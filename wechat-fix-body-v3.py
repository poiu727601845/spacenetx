import os, re

SITE_ROOT = '/home/ubuntu/wechat-publisher/site'

# 读取 articles.json
articles_file = os.path.join(SITE_ROOT, 'data', 'articles.json')
with open(articles_file, 'r', encoding='utf-8') as f:
    import json
    articles = json.load(f)

fixed_count = 0
errors = 0

print(f'Total articles in JSON: {len(articles)}')

for i, art in enumerate(articles):
    url = art.get('url', '')
    if not url:
        continue
    
    if url.startswith('/'):
        filename = url.lstrip('/')
    else:
        filename = url
    
    full_path = os.path.join(SITE_ROOT, filename)
    
    if not os.path.exists(full_path):
        continue
    
    with open(full_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 检查是否已经有 <body>
    if '<body' in html.lower():
        print(f'[{i}] SKIP (already has body): {filename[:50]}')
        continue
    
    # 找到 <head> 结束位置
    head_end_match = re.search(r'</head\s*>', html, re.IGNORECASE | re.DOTALL)
    if not head_end_match:
        errors += 1
        print(f'[{i}] ERROR: no </head> in {filename[:30]}')
        continue
    
    head_end = head_end_match.end()
    rest = html[head_end:]
    
    # 在 </head> 后插入 <body>
    new_html = html[:head_end] + '\n<body>' + rest
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(new_html)
    
    fixed_count += 1
    print(f'[{i}] FIXED: {filename[:50]}')

print(f'\nDone! Fixed: {fixed_count}, Errors: {errors}')
