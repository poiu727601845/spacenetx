module.exports = async function handler(req, res) {
  // CORS headers - 必须，否则浏览器会阻止跨域请求
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  try {
    const urlObj = new URL(req.url, 'http://localhost');
    const codes = urlObj.searchParams.get('code')?.split(',') || [];
    const results = [];

    for (const code of codes) {
      const fundUrl = 'http://fundgz.1234567.com.cn/js/' + code.trim() + '.js';

      const response = await fetch(fundUrl, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
          'Referer': 'http://fund.eastmoney.com/'
        },
        redirect: 'follow'
      });

      const text = await response.text();
      const jsonStr = text.replace(/^jsonpgz\(/, '').replace(/\);\s*$/,'').trim();

      try {
        const data = JSON.parse(jsonStr);
        results.push(data);
      } catch(e) {
        results.push({ fundcode: code.trim(), error: 'parse failed' });
      }
    }

    return res.status(200).json(results);
  } catch(e) {
    return res.status(500).json({error: e.message});
  }
}
