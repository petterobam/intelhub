/**
 * 虎嗅网热榜采集脚本
 * 通过解析 HTML 页面获取文章列表（无 cheerio 依赖）
 */
const https = require('https');
const fs = require('fs');
const path = require('path');

const DATA_DIR = process.env.INTELHUB_DATA_DIR || path.join(__dirname, '../data/huxiu');
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

function fetchHuxiuArticles() {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'www.huxiu.com',
      path: '/article/',
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          const articles = [];
          const seen = new Set();

          // Extract article links with titles
          const linkRegex = /<a[^>]+href="(\/article\/\d+\.html)"[^>]*>([^<]{6,100})<\/a>/g;
          let match;
          while ((match = linkRegex.exec(data)) !== null && articles.length < 30) {
            const url = match[1];
            const title = match[2].trim();
            if (!seen.has(url) && title.length > 5) {
              seen.add(url);
              articles.push({
                title: title,
                url: 'https://www.huxiu.com' + url,
                source_name: '虎嗅',
                timestamp: new Date().toISOString()
              });
            }
          }

          resolve(articles);
        } catch (e) {
          reject(new Error(`Parse error: ${e.message}`));
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

async function main() {
  console.log('📡 正在采集虎嗅网热榜...');

  try {
    const items = await fetchHuxiuArticles();

    const output = {
      platform: '虎嗅',
      timestamp: new Date().toISOString(),
      count: items.length,
      items: items
    };

    // 保存 JSON
    const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const jsonPath = path.join(DATA_DIR, `huxiu-${ts}.json`);
    fs.writeFileSync(jsonPath, JSON.stringify(output, null, 2), 'utf8');
    fs.writeFileSync(path.join(DATA_DIR, 'huxiu-latest.json'), JSON.stringify(output, null, 2), 'utf8');

    console.log(`✅ 虎嗅网热榜采集成功: ${items.length} 条数据`);

    if (items.length > 0) {
      console.log('\n📊 TOP5:');
      items.slice(0, 5).forEach((item, i) => {
        console.log(`   ${i + 1}. ${item.title}`);
      });
    }

  } catch (error) {
    console.error('❌ 采集失败:', error.message);
    process.exit(1);
  }
}

main();
