// Vercel Serverless Function - 基金/指数数据代理
// 代理天天基金API，解决HTTPS网站访问HTTP API的混合内容问题

module.exports = async function handler(req, res) {
  // 设置CORS头
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Cache-Control', 'no-store, must-revalidate');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  try {
    const urlObj = new URL(req.url, 'http://localhost');
    const codes = urlObj.searchParams.get('code')?.split(',') || [];
    
    if (codes.length === 0) {
      return res.status(400).json({ error: 'Missing code parameter' });
    }

    const results = [];

    for (const code of codes) {
      const trimmedCode = code.trim();
      if (!trimmedCode) continue;

      try {
        // 天天基金估值接口
        const fundUrl = 'https://fundgz.1234567.com.cn/js/' + trimmedCode + '.js';

        const response = await fetch(fundUrl, {
          headers: {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Referer': 'https://fund.eastmoney.com/',
            'Accept': '*/*'
          },
          // 使用no-cache避免CDN缓存
          cache: 'no-store'
        });

        if (!response.ok) {
          results.push({ fundcode: trimmedCode, error: 'HTTP ' + response.status });
          continue;
        }

        const text = await response.text();

        // 解析JSONP格式: jsonpgz({...});
        const jsonStr = text.replace(/^jsonpgz\(/, '').replace(/\);\s*$/, '').trim();

        try {
          const data = JSON.parse(jsonStr);
          results.push(data);
        } catch (parseErr) {
          results.push({ fundcode: trimmedCode, error: 'parse_failed', raw: text.substring(0, 100) });
        }
      } catch (err) {
        results.push({ fundcode: trimmedCode, error: err.message });
      }
    }

    res.status(200).json(results);

  } catch (e) {
    console.error('Fund API Error:', e.message);
    res.status(500).json({ error: e.message });
  }
};
