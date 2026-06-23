import json, os

# 读取服务器上的articles.json
articles_file = '/home/ubuntu/wechat-publisher/site/data/articles.json'
with open(articles_file, 'r', encoding='utf-8') as f:
    articles = json.load(f)

# 找到最新文章的URL
art = articles[0]
title = art['title']
url = art['url']
if url.startswith('/'):
    url = url[1:]
full_path = os.path.join('/home/ubuntu/wechat-publisher/site', url)

print(f'Title: {title}')
print(f'URL: {url}')
print(f'Full path: {full_path}')
print(f'Exists: {os.path.exists(full_path)}')
