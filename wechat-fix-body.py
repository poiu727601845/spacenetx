import json, os, re

SITE_ROOT = '/home/ubuntu/wechat-publisher/site'

# 读取 articles.json
articles_file = os.path.join(SITE_ROOT, 'data', 'articles.json')
with open(articles_file, 'r', encoding='utf-8') as f:
    articles = json.load(f)

# 需要修复的文章列表（URL不以articles/开头的是旧格式）
fixed_count = 0
skipped_count = 0

for i, art in enumerate(articles):
    url = art.get('url', '')
    if not url or url.startswith('/'):
        filename = url.lstrip('/')
        full_path = os.path.join(SITE_ROOT, filename)
    elif url.startswith('articles/'):
        full_path = os.path.join(SITE_ROOT, url)
    else:
        skipped_count += 1
        continue
    
    if not os.path.exists(full_path):
        print(f'Skipped (file not exists): {filename[:50]}...')
        skipped_count += 1
        continue
    
    with open(full_path, 'r', encoding='utf-8') as f:
        html = f.read()
    
    # 如果已经有 article-content 标签，跳过
    if 'article-content' in html or '<main' in html or '<article' in html:
        skipped_count += 1
        continue
    
    # 提取正文内容（在 <div class="article-body"> 和 </div> 之间）
    m = re.search(r'<div[^>]*class=["\']article-body["\'][^>]*>(.*?)</div>', html, re.DOTALL)
    if m:
        body = m.group(1)
    else:
        # 如果没有 article-body 标签，尝试从 </head> 之后找第一个非<style>内容
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html, re.DOTALL)
        if body_match:
            body = body_match.group(1)
            # 找到第一个真正的正文 <div>
            div_match = re.search(r'<div[^>]*class=["\']content[^"\']*["\'][^>]*>(.*)', body, re.DOTALL)
            if div_match:
                body = div_match.group(1)
            else:
                # 提取所有 <p><h2><ul><table> 等非导航元素
                body = re.sub(r'<[^>]+>', '', body)[:2000]  # 太粗暴了
        else:
            print(f'No body tag in: {filename}')
            skipped_count += 1
            continue
    
    # 重构 HTML
    head_match = re.search(r'(<head>.*?</head>)', html, re.DOTALL)
    if head_match:
        head = head_match.group(1)
        rest = html[head_match.end():]
        
        # 在 <body> 前插入 article-content 包装
        new_body = f'{head}\n<div class="article-content">\n{body}\n</div>\n{rest}'
        
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(new_body)
        fixed_count += 1
        print(f'Fixed: {filename}')

print(f'\nDone! Fixed: {fixed_count}, Skipped: {skipped_count}')
