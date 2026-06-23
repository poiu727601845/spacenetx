import json, os, re

SITE_ROOT = '/home/ubuntu/wechat-publisher/site'

# 读取 articles.json
articles_file = os.path.join(SITE_ROOT, 'data', 'articles.json')
with open(articles_file, 'r', encoding='utf-8') as f:
    articles = json.load(f)

fixed_count = 0
skipped_count = 0
errors = 0

print(f'Total articles in JSON: {len(articles)}')

for i, art in enumerate(articles):
    url = art.get('url', '')
    if not url:
        skipped_count += 1
        continue
    
    if url.startswith('/'):
        filename = url.lstrip('/')
    elif url.startswith('articles/'):
        filename = url
    else:
        filename = url
    
    full_path = os.path.join(SITE_ROOT, filename)
    
    if not os.path.exists(full_path):
        skipped_count += 1
        print(f'  [{i}] SKIP (file not exists): {filename[:50]}...')
        continue
    
    with open(full_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 如果已经有 article-content 标签，跳过
    if 'article-content' in html:
        skipped_count += 1
        continue
    
    # 提取正文
    body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
    if not body_match:
        errors += 1
        print(f'  [{i}] ERROR: no <body> in {filename}')
        continue
    
    body = body_match.group(1)
    
    # 提取 <div class="content">...</div> 内的所有 HTML
    content_match = re.search(r'<div[^>]*class=["\']content["\'][^>]*>(.*)', body, re.DOTALL)
    if content_match:
        # 找到对应的 </div>
        end_pos = body.rindex('</div>')
        inner_html = body[content_match.start(1):end_pos]
    else:
        # 没有 content 标签，使用所有非导航元素
        # 排除 <p><a href="/">
        inner_html = re.sub(r'<p><a href="/">.*?</a></p>', '', body)
        inner_html = re.sub(r'<hr>', '', inner_html)
    
    # 替换 body 的内容
    new_html = html.replace(body, inner_html.strip())
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(new_html)
    
    fixed_count += 1
    print(f'  [{i}] FIXED: {filename[:50]}...')

print(f'\nTotal fixed: {fixed_count}')
print(f'Total skipped: {skipped_count}')
print(f'Total errors: {errors}')
