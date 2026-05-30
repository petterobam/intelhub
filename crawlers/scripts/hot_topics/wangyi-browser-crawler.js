/**
 * 网易新闻爬虫 — JSONP API 方案
 * API: https://3g.163.com/touch/reconstruct/article/list/BBM54PGAwangning/0-20.html
 */
const fs = require('fs');
const path = require('path');
const { fetchHTML } = require('../utils/fetch_helper');

const DATA_DIR = process.env.INTELHUB_DATA_DIR || path.join(__dirname, '../data/wangyi');
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

async function main() {
  console.log('📡 正在采集网易新闻...');

  try {
    const data = await fetchHTML('https://3g.163.com/touch/reconstruct/article/list/BBM54PGAwangning/0-20.html');

    // 解析 JSONP 响应
    const jsonMatch = data.match(/artiList\((.*)\)$/);
    if (!jsonMatch) {
      console.log('❌ 无法解析 JSONP 数据');
      process.exit(1);
    }

    const jsonData = JSON.parse(jsonMatch[1]);
    const articles = jsonData['BBM54PGAwangning'] || [];

    const items = articles
      .map((item) => ({
        title: item.title || '',
        url: item.url || '',
        timestamp: item.ptime || '',
        source_name: item.source || '网易新闻',
        commentCount: item.commentCount || 0
      }))
      .filter(item => item.title.length > 0)
      .slice(0, 30);

    if (items.length === 0) {
      console.log('❌ 未找到有效新闻');
      process.exit(1);
    }

    const output = {
      platform: '网易新闻',
      timestamp: new Date().toISOString(),
      count: items.length,
      items: items
    };

    // 保存 JSON
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const jsonPath = path.join(DATA_DIR, `wangyi-${ts}.json`);
    fs.writeFileSync(jsonPath, JSON.stringify(output, null, 2));

    // latest.json for plaza API
    fs.writeFileSync(path.join(DATA_DIR, 'wangyi-latest.json'), JSON.stringify(output, null, 2));

    console.log(`✅ 网易新闻采集成功: ${items.length} 条数据`);
    console.log('\n📊 TOP5 新闻:');
    items.slice(0, 5).forEach((item, i) => {
      console.log(`   ${i+1}. ${item.title}`);
    });

  } catch (e) {
    console.error('❌ 错误:', e.message);
    process.exit(1);
  }
}

main();
