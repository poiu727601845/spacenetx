#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复公众号文章封面图自动生成
自动在 publish_ds.py 中添加封面图生成和上传逻辑
"""
import shutil
import re
import os

FILE_PATH = "/home/ubuntu/wechat-publisher/publish_ds.py"
BACKUP_PATH = "/home/ubuntu/wechat-publisher/publish_ds.py.bak.cover_fix"

def main():
    if not os.path.exists(FILE_PATH):
        print(f"[ERROR] 找不到文件: {FILE_PATH}")
        return
    
    # 1. 备份
    shutil.copy2(FILE_PATH, BACKUP_PATH)
    print(f"[OK] 已备份: {BACKUP_PATH}")
    
    # 2. 读取
    with open(FILE_PATH, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 3. 检查是否已有封面图逻辑
    if "generate_cover_image" in content:
        print("[WARN] 文件中已存在封面图逻辑，跳过")
        return
    
    # 4. 添加 Pillow 导入
    if "from PIL import" not in content:
        lines = content.split('\n')
        import_idx = 0
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                import_idx = i
        lines.insert(import_idx + 1, "from PIL import Image, ImageDraw, ImageFont")
        content = '\n'.join(lines)
        print("[OK] 已添加 Pillow 导入")
    
    # 5. 添加封面图生成和上传函数
    cover_code = '''

# ==================== 封面图生成与上传 ====================

def generate_cover_image(title, date_str, output_path="/tmp/cover.jpg"):
    """生成公众号封面图 (900x500)，深色主题"""
    width, height = 900, 500
    img = Image.new('RGB', (width, height), color=(10, 10, 15))
    draw = ImageDraw.Draw(img)
    
    # 装饰线条
    draw.line([(50, 250), (850, 250)], fill=(225, 29, 72), width=3)
    draw.line([(50, 260), (850, 260)], fill=(245, 158, 11), width=1)
    
    # 尝试加载字体
    font_large = ImageFont.load_default()
    font_medium = ImageFont.load_default()
    font_small = ImageFont.load_default()
    
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font_large = ImageFont.truetype(fp, 48)
                font_medium = ImageFont.truetype(fp, 32)
                font_small = ImageFont.truetype(fp, 24)
                break
            except:
                continue
    
    # 绘制标题（截断）
    display_title = title[:14] + "..." if len(title) > 14 else title
    draw.text((50, 120), display_title, fill=(255, 255, 255), font=font_large)
    draw.text((50, 200), "A股投研工具箱 | 深度分析", fill=(136, 136, 168), font=font_medium)
    draw.text((50, 380), date_str, fill=(85, 85, 104), font=font_small)
    draw.text((700, 420), "spacenetx.com", fill=(85, 85, 104), font=font_small)
    
    img.save(output_path, quality=95)
    print(f"[OK] 封面图已生成: {output_path}")
    return output_path

def upload_cover_to_wechat(access_token, image_path):
    """上传封面图到微信素材库，返回 thumb_media_id"""
    boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
    
    with open(image_path, 'rb') as f:
        file_data = f.read()
    
    body = (
        f'--{boundary}\r\n'
        f'Content-Disposition: form-data; name="media"; filename="cover.jpg"\r\n'
        f'Content-Type: image/jpeg\r\n\r\n'
    ).encode('utf-8') + file_data + f'\r\n--{boundary}--\r\n'.encode('utf-8')
    
    url = f"https://api.weixin.qq.com/cgi-bin/media/upload?access_token={access_token}&type=thumb"
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
    
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            if 'media_id' in result:
                print(f"[OK] 封面上传成功")
                return result['media_id']
            else:
                print(f"[WARN] 封面上传失败: {result}")
                return None
    except Exception as e:
        print(f"[ERROR] 封面上传异常: {e}")
        return None

# ==================== 封面图生成与上传结束 ====================
'''
    
    content = content + cover_code
    print("[OK] 已添加封面图生成和上传函数")
    
    # 6. 写回
    with open(FILE_PATH, "w", encoding="utf-8") as f:
        f.write(content)
    
    print("\n" + "="*60)
    print("[OK] 封面图修复完成！")
    print("="*60)
    print("""
【重要】脚本已添加封面图生成函数，但还需手动修改一行代码：

1. 打开 publish_ds.py：
   nano /home/ubuntu/wechat-publisher/publish_ds.py

2. 找到创建微信草稿的地方（搜索 "articles" 或 "add_news"）

3. 在创建草稿之前，添加这两行：

   cover_path = generate_cover_image(title, "2026-06-12")
   thumb_media_id = upload_cover_to_wechat(access_token, cover_path)

4. 在草稿数据中确保有 thumb_media_id：

   "articles": [{
       "title": title,
       "thumb_media_id": thumb_media_id,   # ← 加上这行
       "content": html_content,
       ...
   }]

5. 保存退出：Ctrl+O → Enter → Ctrl+X

【关于字体】
如果生成的封面图文字显示为方块，说明服务器缺少中文字体。
安装中文字体命令：
   sudo apt-get update
   sudo apt-get install -y fonts-wqy-zenhei
""")

if __name__ == "__main__":
    main()
