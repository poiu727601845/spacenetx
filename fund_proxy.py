#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金实时数据代理脚本
解决HTTPS网站访问HTTP API的混合内容问题
用法: /api/fund?code=001410,007300,...
"""

import sys
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ssl

# 基金数据API地址
FUND_API_BASE = "http://fundgz.1234567.com.cn/js"

class FundProxyHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # 静默日志输出
        pass
    
    def do_GET(self):
        if self.path.startswith('/api/fund'):
            # 解析参数
            query = self.path.split('?', 1)
            params = {}
            if len(query) > 1:
                for param in query[1].split('&'):
                    key, value = param.split('=', 1) if '=' in param else (param, '')
                    params[key] = value
            
            codes = params.get('code', '').split(',')
            
            results = []
            for code in codes:
                code = code.strip()
                if not code:
                    continue
                
                try:
                    url = f"{FUND_API_BASE}/{code}.js"
                    req = urllib.request.Request(url, headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Referer': 'http://fund.eastmoney.com/'
                    })
                    
                    with urllib.request.urlopen(req, timeout=3) as response:
                        data = response.read().decode('utf-8')
                        # 解析JSONP格式: jsonpgz({...})
                        json_str = data.replace('jsonpgz(', '').rstrip(');').strip()
                        fund_data = json.loads(json_str)
                        results.append(fund_data)
                        
                except Exception as e:
                    results.append({
                        'fundcode': code,
                        'error': str(e),
                        'name': f'基金{code}'
                    })
            
            # 返回JSON响应
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-store, no-cache')
            self.end_headers()
            self.wfile.write(json.dumps(results, ensure_ascii=False).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

def main():
    port = 8199  # 使用非标准端口避免冲突
    server = ThreadingHTTPServer(('127.0.0.1', port), FundProxyHandler)
    print(f"基金数据代理服务启动于端口 {port}")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n服务停止")
        server.shutdown()

if __name__ == '__main__':
    main()
