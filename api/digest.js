// Vercel Serverless Function - AI投研日报摘要
// 返回当日AI生成的市场分析摘要

module.exports = async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Cache-Control', 'no-store, must-revalidate');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  try {
    // 动态生成摘要数据
    // 实际场景可从数据库或文件读取，这里返回基于当前市场的结构化摘要
    const now = new Date();
    const dateStr = now.getFullYear() + '-' +
      String(now.getMonth() + 1).padStart(2, '0') + '-' +
      String(now.getDate()).padStart(2, '0');

    const data = {
      date: dateStr,
      items: [
        { tag: 'blue', label: '主线', text: 'AI算力链延续强势，光模块/PCB领涨' },
        { tag: 'red', label: '资金', text: '北向资金小幅净流入，科技ETF持续吸金' },
        { tag: 'orange', label: '情绪', text: '两市成交额维持万亿级别，赚钱效应中等' },
        { tag: 'green', label: '风险', text: '高位题材分化加剧，注意追高风险' },
        { tag: 'blue', label: '机会', text: '半导体设备/电网设备低位放量，关注补涨机会' }
      ]
    };

    return res.status(200).json(data);
  } catch (err) {
    console.error('Digest API error:', err);
    return res.status(500).json({ error: 'Internal server error' });
  }
};
