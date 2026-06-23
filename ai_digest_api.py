#!/usr/bin/env python3
"""
ai_digest_api.py - 增加 POST /api/digest/update 支持
并优化 UPDATE 端点使用 PUT
"""
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from pathlib import Path

SITE_PATH = Path("/home/ubuntu/wechat-publisher/site")
DATA_PATH = SITE_PATH / "data"
DIGEST_FILE = DATA_PATH / "ai_digest.json"
REVIEW_DIR = Path("/home/ubuntu/wechat-publisher/reviews")

PORT = 8200

FALLBACK_ITEMS = [
    {"tag": "red", "label": "主线", "text": "资源板块（有色金属/小金属）持续强势，关注铜、铝、稀土细分方向龙头"},
    {"tag": "orange", "label": "观察", "text": "科技板块处于调整期，半导体设备与材料逢低布局机会"},
    {"tag": "blue", "label": "回避", "text": "高位题材股回调风险加大，控制仓位等待企稳信号"},
    {"tag": "green", "label": "机会", "text": "电力电网设备受益于夏季用电高峰，关注特高压与配网改造"},
    {"tag": "purple", "label": "定投", "text": "医疗/新能源处于历史估值低位区间，适合左侧分批建仓"},
]


def get_digest():
    if DIGEST_FILE.exists():
        try:
            with open(DIGEST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    now = datetime.now().strftime("%Y-%m-%d")
    return {
        "date": now,
        "generated": False,
        "items": FALLBACK_ITEMS,
        "source": "fallback"
    }


def update_digest(data=None):
    now = datetime.now().strftime("%Y-%m-%d")
    if data:
        data["date"] = now
    else:
        data = get_digest()
    DATA_PATH.mkdir(parents=True, exist_ok=True)
    with open(DIGEST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/digest" or self.path == "/digest":
            digest = get_digest()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "no-store, max-age=0")
            self.end_headers()
            self.wfile.write(json.dumps(digest, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/api/digest/update":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b"{}"
            try:
                data = json.loads(body)
            except:
                data = {}
            update_digest(data)
            digest = get_digest()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(digest, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass


def main():
    global PORT
    if "--port" in sys.argv:
        PORT = int(sys.argv[sys.argv.index("--port") + 1])

    if not DIGEST_FILE.exists():
        update_digest()

    print(f"[START] AI Digest API on :{PORT}")
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[STOP]")
        server.server_close()


if __name__ == "__main__":
    main()
