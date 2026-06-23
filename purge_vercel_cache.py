#!/usr/bin/env python3
"""
Vercel CDN 缓存自动清除脚本
每次更新网站内容后调用，强制 Vercel 边缘节点拉取最新文件

用法:
  python3 purge_vercel_cache.py              # 清除所有缓存
  python3 purge_vercel_cache.py index.html # 清除指定文件缓存
"""

import sys
import json
import urllib.request
import urllib.error

# ============ 配置区 ============
VERCEL_TOKEN = "os.environ.get("VERCEL_TOKEN", "")"
PROJECT_ID  = "prj_cc4I9i5slfeQldQP9IeFxC3A1DSY"   # spacenetx
# ==================================


def purge_all():
    """清除项目所有 CDN 缓存"""
    url = f"https://api.vercel.com/v2/projects/{PROJECT_ID}/purge-cache"
    data = json.dumps({}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {VERCEL_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            print(f"✅ 全站缓存已清除")
            print(f"   状态: {result.get('status', 'ok')}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"❌ 清除失败: {e.code} {body}")
        return False


def purge_files(paths):
    """清除指定文件的 CDN 缓存"""
    url = f"https://api.vercel.com/v2/projects/{PROJECT_ID}/purge-cache"
    data = json.dumps({"paths": paths}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {VERCEL_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            print(f"✅ 指定文件缓存已清除: {paths}")
            return True
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"❌ 清除失败: {e.code} {body}")
        return False


def trigger_redeploy():
    """触发 Vercel 重新部署（最彻底的方式）"""
    import paramiko

    HOST = "140.143.210.199"
    USER = "ubuntu"
    PASSWORD = "123654poiuMNBV"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=10)

    print("🚀 触发 Vercel 重新部署...")
    stdin, stdout, stderr = client.exec_command(
        f"cd /home/ubuntu/wechat-publisher && "
        f"vercel --prod --yes --token '{VERCEL_TOKEN}' 2>&1",
        timeout=180,
    )
    out = stdout.read().decode("utf-8")
    err = stderr.read().decode("utf-8")
    client.close()

    if "Ready" in out:
        # 提取部署 URL
        import re
        m = re.search(r"https://[^\s]+\.vercel\.app", out)
        url = m.group(0) if m else ""
        print(f"✅ 部署成功! {url}")
        print(f"   www.spacenetx.com 将在数秒内更新")
        return True
    else:
        print(f"❌ 部署失败:\n{out}\n{err}")
        return False


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # 指定了文件 → 清除指定文件缓存
        paths = [f"/{p.lstrip('/')}" for p in sys.argv[1:]]
        print(f"🧹 清除指定文件缓存: {paths}")
        purge_files(paths)
    else:
        print("选择清除方式:")
        print("  1) 清除 CDN 缓存（快速，约5秒）")
        print("  2) 重新部署（最彻底，约30秒）")
        choice = input("请选择 [1/2]: ").strip()
        if choice == "1":
            print("🧹 清除全站 CDN 缓存...")
            purge_all()
        else:
            trigger_redeploy()
