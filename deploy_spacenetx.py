#!/usr/bin/env python3
"""
Vercel 自动部署脚本 - spacenetx.com
每次更新网站内容后运行此脚本，自动部署到 Vercel 并刷新 CDN 缓存

用法:
  python3 deploy_spacenetx.py              # 部署 site/ 下所有文件
  python3 deploy_spacenetx.py index.html  # 部署指定文件
"""

import sys
import os
import json
import paramiko
import subprocess
import time

# =========== 配置区 ===========
VERCEL_TOKEN = "os.environ.get("VERCEL_TOKEN", "")"
SSH_HOST = "140.143.210.199"
SSH_USER = "ubuntu"
SSH_PASS = "123654poiuMNBV"
REMOTE_DIR = "/home/ubuntu/wechat-publisher"
# ==================================


def ssh_connect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(SSH_HOST, username=SSH_USER, password=SSH_PASS, timeout=15)
    return client


def purge_vercel_cache(client):
    """用 Vercel CLI 清除 CDN 缓存（通过重新部署实现）"""
    print("📡 步骤1: 检查 Vercel 项目关联...")
    stdin, stdout, stderr = client.exec_command(
        f"cat {REMOTE_DIR}/.vercel/project.json 2>/dev/null", timeout=10
    )
    out = stdout.read().decode("utf-8").strip()
    if not out:
        print("   ⚠️  项目未关联，先执行 vercel link...")
        stdin2, stdout2, stderr2 = client.exec_command(
            f"cd {REMOTE_DIR} && vercel link --yes --token '{VERCEL_TOKEN}' --project spacenetx 2>&1",
            timeout=60,
        )
        result = stdout2.read().decode("utf-8").strip()
        print(f"   {result[-200:]}")
    else:
        print(f"   ✅ 项目已关联: {json.loads(out).get('projectName', 'spacenetx')}")

    return True


def deploy_to_vercel(client):
    """执行 Vercel 生产环境部署"""
    print("🚀 步骤2: 部署到 Vercel 生产环境...")
    print("   （这会自动刷新 CDN 缓存，约30秒）")

    stdin, stdout, stderr = client.exec_command(
        f"cd {REMOTE_DIR} && "
        f"vercel --prod --yes --token '{VERCEL_TOKEN}' 2>&1",
        timeout=180,
    )
    out = stdout.read().decode("utf-8")
    err = stderr.read().decode("utf-8")

    if "Ready" in out or "✓" in out:
        import re
        urls = re.findall(r"https://[^\s]+\.vercel\.app", out)
        alias = re.findall(r"https://(?:www\.)?spacenetx\.com", out)
        print(f"   ✅ 部署成功! (耗时 ~{out.count('...')}s)")
        if urls:
            print(f"   预览: {urls[0]}")
        if alias:
            print(f"   生产: https://spacenetx.com")
        return True, out
    else:
        print(f"   ❌ 部署失败:")
        print(f"   {out[-400:]}")
        if err:
            print(f"   {err[-200:]}")
        return False, out


def verify_deployment():
    """验证 spacenetx.com 是否已更新（最多等60秒）"""
    print("🔍 步骤3: 验证部署结果...")
    for i in range(12):  # 最多等60秒
        try:
            import urllib.request
            req = urllib.request.Request(
                "https://spacenetx.com",
                headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                html = r.read().decode("utf-8", errors="ignore")
                cache = r.headers.get("x-vercel-cache", "unknown")

                has_market = "market-overview" in html
                has_mid = "mid-section" in html
                has_sidebar = "sidebar" in html

                print(f"   第{i+1}次检查: cache={cache}")
                print(f"   market-overview={has_market}, mid-section={has_mid}, sidebar={has_sidebar}")

                if has_market and has_mid:
                    print("   ✅ 新版已上线!")
                    return True

                time.sleep(5)
        except Exception as e:
            print(f"   第{i+1}次检查: 错误 {e}")
            time.sleep(5)

    print("   ⚠️  验证超时，请手动检查 https://spacenetx.com")
    return False


def update_local_file(local_path):
    """如果需要，同步本地文件到服务器"""
    if not os.path.exists(local_path):
        print(f"⚠️  本地文件不存在: {local_path}")
        return False

    client = ssh_connect()
    sftp = client.open_sftp()
    remote_path = f"{REMOTE_DIR}/site/{os.path.basename(local_path)}"
    with open(local_path, "r", encoding="utf-8") as f:
        content = f.read()
    with sftp.open(remote_path, "w") as f:
        f.write(content)
    sftp.close()
    client.close()
    print(f"✅ 已上传 {local_path} → {remote_path}")
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("  Vercel 自动部署脚本 - spacenetx.com")
    print("=" * 50)

    # 如果命令行传了文件，先上传
    if len(sys.argv) > 1:
        for filepath in sys.argv[1:]:
            update_local_file(filepath)

    # 连接服务器并部署
    client = ssh_connect()
    print("\n✅ SSH 连接成功")

    # 步骤1: 确保项目已关联
    purge_vercel_cache(client)

    # 步骤2: 部署
    success, output = deploy_to_vercel(client)

    client.close()

    # 步骤3: 验证
    if success:
        verify_deployment()
        print("\n🎉 部署完成! 请访问 https://spacenetx.com 查看")
        print("   （如仍显示旧版，请 Ctrl+Shift+R 强制刷新）")
    else:
        print("\n❌ 部署失败，请检查上面的错误信息")
        sys.exit(1)
