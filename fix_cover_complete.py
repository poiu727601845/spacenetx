#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
完整修复封面图：同时修改 publish_ds.py 和 wxchat_publish.py
"""

import re
from pathlib import Path

BASE_DIR = Path("/home/ubuntu/wechat-publisher")
PUB_FILE = BASE_DIR / "publish_ds.py"
WXPUB_FILE = BASE_DIR / "wxchat_publish.py"

print("=" * 60)
print("修复封面图上传 - 完整版")
print("=" * 60)

# ==================== 1. 备份原文件 ====================
for f in [PUB_FILE, WXPUB_FILE]:
    if f.exists():
        bak = f.with_suffix(f".bak.cover_{__import__('datetime').datetime.now().strftime('%Y%m%d')}")
        bak.write_text(f.read_text(), encoding='utf-8')
        print(f"[OK] 已备份: {bak.name}")

# ==================== 2. 修改 wxchat_publish.py ====================
if WXPUB_FILE.exists():
    wx_content = WXPUB_FILE.read_text(encoding='utf-8')
    
    # 检查 push_draft 函数是否存在
    if "def push_draft" in wx_content:
        # 方案A：如果 push_draft 有 thumb_media_id 参数，跳过
        if "thumb_media_id" in wx_content:
            print("[OK] wxchat_publish.py 已支持 thumb_media_id，跳过")
        else:
            # 修改 push_draft 函数签名，增加 thumb_media_id=None
            wx_content = re.sub(
                r'def push_draft$([^)]*)$:',
                r'def push_draft(\1, thumb_media_id=None):',
                wx_content
            )
            
            # 在构造 data 的地方插入 thumb_media_id
            # 微信草稿接口需要 thumb_media_id 在 articles 列表里
            patterns = [
                (r'("content":\s*content[^}]*})', r'\1,\n                    "thumb_media_id": thumb_media_id'),
                (r'("title":\s*title[^}]*})', r'\1,\n                    "thumb_media_id": thumb_media_id'),
                (r'"articles":\s*\[\s*\{', r'"articles": [{\n                    "thumb_media_id": thumb_media_id,'),
            ]
            
            modified = False
            for pattern, repl in patterns:
                new_content, count = re.subn(pattern, repl, wx_content)
                if count > 0:
                    wx_content = new_content
                    modified = True
                    break
            
            if not modified:
                # 兜底：在 articles 列表开始后插入
                wx_content = re.sub(
                    r'("articles"\s*:\s*\[\s*\{)',
                    r'\1\n                    "thumb_media_id": thumb_media_id,',
                    wx_content
                )
            
            WXPUB_FILE.write_text(wx_content, encoding='utf-8')
            print("[OK] 已修改 wxchat_publish.py: 支持 thumb_media_id 参数")
    else:
        print("[WARN] wxchat_publish.py 中未找到 push_draft 函数")
else:
    print("[ERR] wxchat_publish.py 不存在")

# ==================== 3. 修改 publish_ds.py 调用位置 ====================
if PUB_FILE.exists():
    pub_content = PUB_FILE.read_text(encoding='utf-8')
    
    # 检查是否已经修改过
    if "thumb_media_id" in pub_content and "generate_cover_image" in pub_content:
        # 找到 push_draft 调用，确保传递了 thumb_media_id
        old_call = 'wxpub.push_draft(str(article_file))'
        new_call = 'wxpub.push_draft(str(article_file), thumb_media_id=thumb_media_id)'
        
        if old_call in pub_content:
            pub_content = pub_content.replace(old_call, new_call)
            PUB_FILE.write_text(pub_content, encoding='utf-8')
            print("[OK] 已修改 publish_ds.py: push_draft 调用增加 thumb_media_id 参数")
        elif new_call in pub_content:
            print("[OK] publish_ds.py 已正确传递 thumb_media_id")
        else:
            print("[WARN] 未找到 push_draft 调用，请手动检查")
    else:
        print("[ERR] publish_ds.py 缺少封面图函数，请先运行 fix_cover_image.py")
else:
    print("[ERR] publish_ds.py 不存在")

print("=" * 60)
print("[OK] 封面图修复完成！")
print("=" * 60)
print("\n验证方法：")
print("1. 检查 wxchat_publish.py 中 push_draft 函数签名")
print("2. 检查 publish_ds.py 中 push_draft 调用是否带了 thumb_media_id")
