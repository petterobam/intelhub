/**
 * 澎湃新闻热榜爬虫
 * 分类: 社会动态
 */
const fs = require('fs');
const path = require('path');
const { fetchHTML } = require('../utils/fetch_helper');

const DATA_DIR = process.env.INTELHUB_DATA_DIR || path.join(__dirname, '../data/paper');
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

async function main() {
  console.log('📡 正在采集澎湃新闻热榜...');

  try {
    const data = await fetchHTML('https://m.thepaper.cn/', {
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 MicroMessenger/8.0.0',
    });

    // 从 HTML 中提取 __NEXT_DATA__
    const nextDataMatch = data.match(/<script id="__NEXT_DATA__" type="application\/json">([\s\S]*?)<\/script>/);

    if (!nextDataMatch) {
      console.log('❌ 无法解析澎湃新闻数据');
      process.exit(1);
    }

    const jsonData = JSON.parse(nextDataMatch[1]);
    const newsList = jsonData.props.pageProps.data.list || [];

    const items = newsList.slice(0, 30).map((item, index) => ({
      title: item.name || '',
      url: `https://m.thepaper.cn/newsDetail_forward_${item.contId}`,
      category: item.nodeInfo?.name || '',
      timestamp: item.pubTime || '',
      source_name: '澎湃新闻'
    }));

    const output = {
      platform: '澎湃新闻',
      timestamp: new Date().toISOString(),
      count: items.length,
      items: items
    };

    // 保存 JSON
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const jsonPath = path.join(DATA_DIR, `paper-${timestamp}.json`);
    fs.writeFileSync(jsonPath, JSON.stringify(output, null, 2));

    // latest.json for plaza API
    fs.writeFileSync(path.join(DATA_DIR, 'paper-latest.json'), JSON.stringify(output, null, 2));

    console.log(`✅ 澎湃新闻采集成功: ${items.length} 条数据`);

    if (items.length > 0) {
      console.log('\n📊 TOP5 新闻:');
      items.slice(0, 5).forEach((item, i) => {
        console.log(`   ${i+1}. ${item.title} (${item.category})`);
      });
    }

  } catch (e) {
    console.error('❌ 错误:', e.message);
    process.exit(1);
  }
}

main();
