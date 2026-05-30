/**
 * 抖音热搜采集脚本
 * 使用 HTTP API 直采（无需 Playwright）
 * API: /aweme/v1/web/hot/search/list/
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

const DATA_DIR = process.env.INTELHUB_DATA_DIR || path.join(__dirname, '../data/douyin');
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

function fetchDouyinHot() {
  console.log('📡 正在采集抖音热搜...');

  const options = {
    hostname: 'www.douyin.com',
    port: 443,
    path: '/aweme/v1/web/hot/search/list/',
    method: 'GET',
    headers: {
      'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
      'Referer': 'https://www.douyin.com/',
      'Accept': 'application/json, text/plain, */*',
      'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'
    }
  };

  return new Promise((resolve, reject) => {
    const req = https.request(options, (res) => {
      let data = '';
      res.on('data', (chunk) => { data += chunk; });
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          // 关键修复：使用 word_list 而不是 trending_list
          // word_list 包含真实热度值 hot_value
          if (json.status_code === 0 && json.data && json.data.word_list) {
            resolve(json.data.word_list);
          } else if (json.status_code === 0 && json.data && json.data.trending_list) {
            // 降级方案：如果没有 word_list，使用 trending_list
            console.log('⚠️ word_list 为空，使用 trending_list (热度值可能为0)');
            resolve(json.data.trending_list);
          } else {
            reject(new Error(`API error: ${json.status_msg || 'Unknown error'}`));
          }
        } catch (e) {
          reject(new Error(`Parse error: ${e.message}`));
        }
      });
    });

    req.on('error', reject);
    req.setTimeout(10000, () => {
      req.destroy();
      reject(new Error('Request timeout'));
    });
    req.end();
  });
}

function formatHotValue(value) {
  if (value >= 100000000) return (value / 100000000).toFixed(1) + '亿';
  if (value >= 10000) return (value / 10000).toFixed(1) + '万';
  return value.toString();
}

function saveData(data) {
  // 使用固定文件名，覆盖旧数据，避免历史数据积累
  const jsonFile = path.join(DATA_DIR, 'douyin-latest.json');
  const mdFile = path.join(DATA_DIR, 'douyin-latest.md');

  // 保存 JSON
  fs.writeFileSync(jsonFile, JSON.stringify(data, null, 2), 'utf8');

  // 保存 Markdown
  let md = `# 抖音热搜榜\n\n`;
  md += `> 采集时间: ${new Date().toLocaleString('zh-CN')}\n`;
  md += `> 数据来源: 抖音热搜 API\n`;
  md += `> 总计: ${data.length} 条\n\n`;

  md += `## TOP ${Math.min(20, data.length)} 热搜\n\n`;
  data.slice(0, 20).forEach((item, i) => {
    const hotValue = formatHotValue(item.hot_value);
    md += `${i + 1}. **${item.word}**\n`;
    md += `   - 热度: ${hotValue}\n`;
    if (item.video_count > 0) md += `   - 视频数: ${item.video_count}\n`;
    if (item.discuss_video_count > 0) md += `   - 讨论数: ${item.discuss_video_count}\n`;
    md += `\n`;
  });

  fs.writeFileSync(mdFile, md, 'utf8');

  return { jsonFile, mdFile };
}

async function main() {
  try {
    const data = await fetchDouyinHot();
    const { jsonFile, mdFile } = saveData(data);

    console.log(`✅ 抖音热搜采集成功: ${data.length} 条数据`);
    console.log(`   JSON: ${path.basename(jsonFile)}`);
    console.log(`   Markdown: ${path.basename(mdFile)}`);
    console.log(`\n📊 TOP5 热搜:`);
    data.slice(0, 5).forEach((item, i) => {
      console.log(`   ${i + 1}. ${item.word} (${formatHotValue(item.hot_value)})`);
    });

  } catch (error) {
    console.error('❌ 采集失败:', error.message);
    process.exit(1);
  }
}

main();
