import os, re, json

SITE_ROOT = '/home/ubuntu/wechat-publisher/site'

# 读取 articles.json
articles_file = os.path.join(SITE_ROOT, 'data', 'articles.json')
with open(articles_file, 'r', encoding='utf-8') as f:
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
    
    # 检查是否已经有 article-content 标签
    if 'article-content' in html:
        print(f'[{i}] SKIP (already has article-content): {filename[:40]}')
        continue
    
    # 找到 </body> 的位置
    body_end_match = re.search(r'</body\s*>', html, re.IGNORECASE | re.DOTALL)
    if not body_end_match:
        errors += 1
        print(f'[{i}] ERROR: no </body> in {filename[:30]}')
        continue
    
    # 提取 body 内容
    body_start_match = re.search(r'<body[^>]*>', html, re.IGNORECASE)
    if not body_start_match:
        errors += 1
        continue
    
    body_start = body_start_match.end()
    body_content = html[body_start:body_end_match.start()]
    
    # 提取 head 和 rest
    head_end_match = re.search(r'</head\s*>', html, re.IGNORECASE | re.DOTALL)
    rest = html[body_end_match.end():]
    
    # 在 body 内容前后加上 article-content 标签
    new_body = '<div class="article-content">\n' + body_content + '\n</div>'
    
    # 重构 HTML
    new_html = html[:head_end_match.end()] + '\n<body>\n' + new_body + rest
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(new_html)
    
    fixed_count += 1
    print(f'[{i}] FIXED: {filename[:40]}...')

print(f'\nDone! Fixed: {fixed_count}, Errors: {errors}')
