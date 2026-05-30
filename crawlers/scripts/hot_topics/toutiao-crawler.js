/**
 * 今日头条热榜采集脚本
 * API: https://www.toutiao.com/hot-event/hot-board/
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

const DATA_DIR = process.env.INTELHUB_DATA_DIR || path.join(__dirname, '../data/toutiao');
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

function fetchToutiaoHot() {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'www.toutiao.com',
      path: '/hot-event/hot-board/?origin=hot_board&widen=1',
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': 'https://www.toutiao.com/',
        'Accept': 'application/json',
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          if (json.data && Array.isArray(json.data)) {
            resolve(json.data);
          } else {
            reject(new Error('Invalid data format'));
          }
        } catch (e) {
          reject(new Error(`Parse error: ${e.message}`));
        }
      });
    });

    req.on('error', reject);
    req.end();
  });
}

async function main() {
  console.log('📡 正在采集今日头条热榜...');

  try {
    const rawItems = await fetchToutiaoHot();

    const items = rawItems.map(item => ({
      title: item.Title || '',
      url: item.ClusterIdStr ? `https://www.toutiao.com/trending/${item.ClusterIdStr}/` : '',
      hotValue: item.HotValue || 0,
      timestamp: new Date().toISOString(),
      source_name: '今日头条'
    }));

    const output = {
      platform: '今日头条',
      timestamp: new Date().toISOString(),
      count: items.length,
      items: items
    };

    // 保存 JSON
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const jsonPath = path.join(DATA_DIR, `toutiao-${ts}.json`);
    fs.writeFileSync(jsonPath, JSON.stringify(output, null, 2), 'utf8');

    // latest.json for plaza API
    fs.writeFileSync(path.join(DATA_DIR, 'toutiao-latest.json'), JSON.stringify(output, null, 2), 'utf8');

    console.log(`✅ 今日头条热榜采集成功: ${items.length} 条数据`);
    console.log('\n📊 TOP5 热榜:');
    items.slice(0, 5).forEach((item, i) => {
      console.log(`   ${i + 1}. ${item.title}`);
    });

  } catch (error) {
    console.error('❌ 采集失败:', error.message);
    process.exit(1);
  }
}

main();
