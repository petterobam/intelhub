/**
 * 微博热搜采集脚本
 * API: https://weibo.com/ajax/side/hotSearch
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

const DATA_DIR = process.env.INTELHUB_DATA_DIR || path.join(__dirname, '../data/weibo');
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

function fetchWeiboHot() {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'weibo.com',
      path: '/ajax/side/hotSearch',
      method: 'GET',
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://weibo.com/'
      }
    };

    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => {
        try {
          // 处理可能的编码问题
          const json = JSON.parse(data);
          resolve(json);
        } catch (e) {
          // 尝试解码
          try {
            const decoded = new TextDecoder('utf-8', { fatal: true }).decode(Buffer.from(data));
            const json = JSON.parse(decoded);
            resolve(json);
          } catch (e2) {
            resolve({ raw: data.slice(0, 500) });
          }
        }
      });
    });

    req.on('error', reject);
    req.end();
  });
}

async function main() {
  console.log('📡 正在采集微博热搜...');
  
  try {
    const data = await fetchWeiboHot();
    
    // 生成时间戳
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const filename = `weibo-${timestamp.replace(/-/g, '').replace('T', '_')}.json`;
    const mdFilename = `weibo-${timestamp.replace(/-/g, '').replace('T', '_')}.md`;
    
    // 解析并格式化数据
    let items = [];
    if (data.data && data.data.realtime) {
      items = data.data.realtime.map(item => ({
        word: item.word || item.note || '无标题',
        hot: item.raw_hot || item.num || 0,
        label: item.label_name || '',
        url: `https://s.weibo.com/weibo?q=${encodeURIComponent(item.word || item.note)}`
      }));
    }
    
    // 保存JSON
    const jsonPath = path.join(DATA_DIR, filename);
    const output = {
      platform: '微博',
      timestamp: new Date().toISOString(),
      count: items.length,
      items: items
    };
    fs.writeFileSync(jsonPath, JSON.stringify(output, null, 2));
    // latest.json for plaza API
    fs.writeFileSync(path.join(DATA_DIR, 'weibo-latest.json'), JSON.stringify(output, null, 2));
    
    // 保存Markdown
    let mdContent = `# 微博热搜 - ${new Date().toLocaleString('zh-CN')}\n\n`;
    mdContent += `| 排名 | 标题 | 热度 |\n|------|------|------|\n`;
    items.slice(0, 10).forEach((item, i) => {
      mdContent += `| ${i + 1} | ${item.word} ${item.label ? '[' + item.label + ']' : ''} | ${item.hot} |\n`;
    });
    
    const mdPath = path.join(DATA_DIR, mdFilename);
    fs.writeFileSync(mdPath, mdContent);
    
    console.log(`✅ 微博热搜采集成功: ${items.length} 条数据`);
    console.log(`   JSON: ${filename}`);
    console.log(`   Markdown: ${mdFilename}`);
    
    if (items.length > 0) {
      console.log('\n📊 TOP5 热搜:');
      items.slice(0, 5).forEach((item, i) => {
        const label = item.label ? ` [${item.label}]` : '';
        console.log(`   ${i + 1}. ${item.word}${label} (${item.hot})`);
      });
    }
    
    return { success: true, count: items.length };
  } catch (error) {
    console.error('❌ 微博热搜采集失败:', error.message);
    return { success: false, error: error.message };
  }
}

main().then(result => {
  process.exit(result.success ? 0 : 1);
});
