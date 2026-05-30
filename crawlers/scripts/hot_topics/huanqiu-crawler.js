/**
 * 环球网国际新闻爬虫
 * 分类: 国际时事
 */
const fs = require('fs');
const path = require('path');
const { fetchHTML } = require('../utils/fetch_helper');

const DATA_DIR = process.env.INTELHUB_DATA_DIR || path.join(__dirname, '../data/huanqiu');
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

async function main() {
  console.log('📡 正在采集环球网国际新闻...');

  try {
    const data = await fetchHTML('https://world.huanqiu.com/');

    // 从 HTML 中提取新闻标题
    const titleRegex = /<textarea class="item-title">([^<]+)<\/textarea>/g;

    let titles = [];
    let match;
    while ((match = titleRegex.exec(data)) !== null) {
      titles.push(match[1]);
    }

    // 去重并取前30条
    titles = [...new Set(titles)].slice(0, 30);

    const items = titles.map((title, index) => ({
      title: title,
      url: 'https://world.huanqiu.com/',
      category: '国际',
      source_name: '环球网'
    }));

    const output = {
      platform: '环球网',
      timestamp: new Date().toISOString(),
      count: items.length,
      items: items
    };

    // 保存 JSON
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const jsonPath = path.join(DATA_DIR, `huanqiu-${timestamp}.json`);
    fs.writeFileSync(jsonPath, JSON.stringify(output, null, 2));

    // latest.json for plaza API
    fs.writeFileSync(path.join(DATA_DIR, 'huanqiu-latest.json'), JSON.stringify(output, null, 2));

    console.log(`✅ 环球网采集成功: ${items.length} 条数据`);

    if (items.length > 0) {
      console.log('\n📊 TOP5 新闻:');
      items.slice(0, 5).forEach((item, i) => {
        console.log(`   ${i+1}. ${item.title}`);
      });
    }

  } catch (e) {
    console.error('❌ 错误:', e.message);
    process.exit(1);
  }
}

main();
