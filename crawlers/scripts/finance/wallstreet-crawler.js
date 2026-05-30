#!/usr/bin/env node
// 华尔街见闻 — 快讯
const https = require('https');
const fs = require('fs');
const path = require('path');

const API_URL = 'https://api-one-wscn.awtmt.com/apiv1/content/live-stream?channel=global-channel&limit=30';

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
    const items = (resp.data?.items || resp.data || []).map(a => ({
      title: a.title || a.content_text || '',
      url: a.uri || a.url || '',
      summary: (a.content_text || a.brief || '').substring(0, 300),
      timestamp: a.display_time || a.created_at || new Date().toISOString(),
      category: 'finance',
    }));

    const output = {
      platform: 'wallstreet',
      name: '华尔街见闻',
      collected_at: new Date().toISOString(),
      items,
    };

    const outDir = process.env.INTELHUB_DATA_DIR || path.join(__dirname, '..', '..', '..', 'data', 'raw', 'hot_topics', 'wallstreet');
    fs.mkdirSync(outDir, { recursive: true });
    const outFile = path.join(outDir, `${new Date().toISOString().replace(/[:.]/g, '-')}.json`);
    fs.writeFileSync(outFile, JSON.stringify(output, null, 2), 'utf-8');
    fs.writeFileSync(path.join(outDir, 'wallstreet-latest.json'), JSON.stringify(output, null, 2), 'utf-8');
    console.log(`OK: ${items.length} items saved to ${outFile}`);
  } catch (e) {
    console.error('FAIL:', e.message);
    process.exit(1);
  }
}

main();
