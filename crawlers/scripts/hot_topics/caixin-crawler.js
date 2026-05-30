/**
 * 财新网 (Caixin) 爬虫
 * API: https://gateway.caixin.com/api/extapi/homeInterface.jsp
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

const DATA_DIR = process.env.INTELHUB_DATA_DIR || path.join(__dirname, '../data/caixin');
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

function fetchCaixinAPI() {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'gateway.caixin.com',
      path: '/api/extapi/homeInterface.jsp?subject=100589266&start=1&count=30&type=2',
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
        'Referer': 'https://www.caixin.com/'
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(data));
        } catch (e) {
          reject(new Error('Failed to parse JSON: ' + e.message));
        }
      });
    });

    req.on('error', reject);
    req.setTimeout(15000, () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });
    req.end();
  });
}

function parseCaixinData(apiData) {
  const articles = [];
  if (!apiData || !apiData.datas || !Array.isArray(apiData.datas)) {
    return articles;
  }

  for (const item of apiData.datas) {
    if (!item.desc) continue;

    articles.push({
      title: item.desc.trim(),
      url: item.link || '',
      summary: item.summ || '',
      source_name: '财新网',
      timestamp: item.time || new Date().toISOString(),
      category: item.channelDesc || '财经'
    });
  }
  return articles;
}

async function main() {
  console.log('📡 正在采集财新网数据...');

  try {
    const apiData = await fetchCaixinAPI();
    const items = parseCaixinData(apiData);

    if (items.length === 0) {
      console.log('⚠️ 未采集到文章');
      process.exit(1);
    }

    const output = {
      platform: '财新网',
      timestamp: new Date().toISOString(),
      count: items.length,
      items: items
    };

    // 保存 JSON
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const jsonPath = path.join(DATA_DIR, `caixin-${ts}.json`);
    fs.writeFileSync(jsonPath, JSON.stringify(output, null, 2), 'utf8');

    // latest.json for plaza API
    fs.writeFileSync(path.join(DATA_DIR, 'caixin-latest.json'), JSON.stringify(output, null, 2), 'utf8');

    console.log(`✅ 财新网采集成功: ${items.length} 条数据`);
    console.log('\n📊 TOP5:');
    items.slice(0, 5).forEach((item, i) => {
      console.log(`   ${i + 1}. ${item.title}`);
    });

  } catch (error) {
    console.error('❌ 采集失败:', error.message);
    process.exit(1);
  }
}

main();
