#!/usr/bin/env node
// 第一财经 — 新闻列表
const https = require('https');
const fs = require('fs');
const path = require('path');

const API_URL = 'https://www.yicai.com/api/ajax/getlatest?page=1&pagesize=30';

function fetch(url) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try { resolve(JSON.parse(data)); }
        catch (e) { reject(e); }
      });
    }).on('error', reject);
  });
}

async function main() {
  try {
    const resp = await fetch(API_URL);
    const items = (resp || []).map(a => ({
      title: a.title || a.NewsTitle || '',
      url: a.url || a.filename ? `https://www.yicai.com/news/${a.filename || a.NewsID}.html` : '',
      summary: (a.summary || a.description || '').substring(0, 300),
      timestamp: a.CreateDate || a.pubDate || new Date().toISOString(),
      category: 'finance',
    }));

    const output = {
      platform: 'yicai',
      name: '第一财经',
      collected_at: new Date().toISOString(),
      items,
    };

    const outDir = process.env.INTELHUB_DATA_DIR || path.join(__dirname, '..', '..', '..', 'data', 'raw', 'hot_topics', 'yicai');
    fs.mkdirSync(outDir, { recursive: true });
    const outFile = path.join(outDir, `${new Date().toISOString().replace(/[:.]/g, '-')}.json`);
    fs.writeFileSync(outFile, JSON.stringify(output, null, 2), 'utf-8');
    fs.writeFileSync(path.join(outDir, 'yicai-latest.json'), JSON.stringify(output, null, 2), 'utf-8');
    console.log(`OK: ${items.length} items saved to ${outFile}`);
  } catch (e) {
    console.error('FAIL:', e.message);
    process.exit(1);
  }
}

main();
