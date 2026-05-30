/**
 * B站热门视频采集脚本
 * API: https://api.bilibili.com/x/web-interface/popular
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

const DATA_DIR = process.env.INTELHUB_DATA_DIR || path.join(__dirname, '../data/bilibili');
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

function fetchBilibiliPopular() {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'api.bilibili.com',
      path: '/x/web-interface/popular?ps=50',
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.bilibili.com/'
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve(json);
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
  console.log('📡 正在采集 B 站热门视频...');

  try {
    const data = await fetchBilibiliPopular();

    let items = [];
    if (data.data && data.data.list) {
      items = data.data.list.map(item => ({
        title: item.title || '无标题',
        url: `https://www.bilibili.com/video/${item.bvid || ''}`,
        author: item.owner?.name || '未知',
        play: item.stat?.view || 0,
        timestamp: new Date().toISOString(),
        source_name: 'B站'
      }));
    }

    const output = {
      platform: 'B站',
      timestamp: new Date().toISOString(),
      count: items.length,
      items: items
    };

    // 保存 JSON
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const jsonPath = path.join(DATA_DIR, `bilibili-${ts}.json`);
    fs.writeFileSync(jsonPath, JSON.stringify(output, null, 2));

    // latest.json for plaza API
    fs.writeFileSync(path.join(DATA_DIR, 'bilibili-latest.json'), JSON.stringify(output, null, 2));

    console.log(`✅ B站热门视频采集成功: ${items.length} 条数据`);

    if (items.length > 0) {
      console.log('\n📊 TOP5 热门:');
      items.slice(0, 5).forEach((item, i) => {
        console.log(`   ${i + 1}. ${item.title} - ${item.author} (${item.play} 播放)`);
      });
    }

    return { success: true, count: items.length };
  } catch (error) {
    console.error('❌ B站热门视频采集失败:', error.message);
    return { success: false, error: error.message };
  }
}

main().then(result => {
  process.exit(result.success ? 0 : 1);
});
