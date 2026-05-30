/**
 * 1905电影网爬虫 - 影视资讯采集
 * HTML: https://www.1905.com/news/
 */

const fs = require('fs');
const path = require('path');
const { fetchHTML } = require('../utils/fetch_helper');

const DATA_DIR = process.env.INTELHUB_DATA_DIR || path.join(__dirname, '../data/1905');
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

async function main() {
  console.log('📡 正在采集1905电影网影视资讯...');

  try {
    const html = await fetchHTML('https://www.1905.com/news/');

    const items = [];
    const seen = new Set();
    const titleRegex = /href="(https:\/\/www\.1905\.com\/news\/\d{8}\/\d+\.shtml)"[^>]*title="([^"]+)"/g;
    let match;

    while ((match = titleRegex.exec(html)) !== null && items.length < 20) {
      const url = match[1];
      const title = match[2].trim();
      if (!seen.has(url) && title) {
        seen.add(url);
        items.push({
          title: title,
          url: url,
          source_name: '1905电影网',
          timestamp: new Date().toISOString()
        });
      }
    }

    const output = {
      platform: '1905电影网',
      timestamp: new Date().toISOString(),
      count: items.length,
      items: items
    };

    // 保存 JSON
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const jsonPath = path.join(DATA_DIR, `1905-${ts}.json`);
    fs.writeFileSync(jsonPath, JSON.stringify(output, null, 2));

    // latest.json for plaza API
    fs.writeFileSync(path.join(DATA_DIR, '1905-latest.json'), JSON.stringify(output, null, 2));

    console.log(`✅ 1905电影网采集成功: ${items.length} 条数据`);
    console.log('\n📊 TOP5 资讯:');
    items.slice(0, 5).forEach((item, i) => {
      console.log(`   ${i + 1}. ${item.title}`);
    });

  } catch (error) {
    console.error(`❌ 采集失败: ${error.message}`);
    process.exit(1);
  }
}

main();
