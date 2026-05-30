/**
 * 知乎热榜采集脚本
 * API: https://www.zhihu.com/api/v4/feed/topstory/hot-lists/total
 */

const https = require('https');
const zlib = require('zlib');
const fs = require('fs');
const path = require('path');

const DATA_DIR = process.env.INTELHUB_DATA_DIR || path.join(__dirname, '../data/zhihu');
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

// 通用请求头 - 适配 v3 API
const DEFAULT_HEADERS = {
  'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
  'Accept': 'application/json, text/plain, */*',
  'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
  'Accept-Encoding': 'gzip, deflate, br',
  'Connection': 'keep-alive',
  'Referer': 'https://www.zhihu.com/hot',
  'x-requested-with': 'fetch',
  'sec-ch-ua': '"Chromium";v="120", "Not_A Brand";v="24", "Google Chrome";v="120"',
  'sec-ch-ua-mobile': '?0',
  'sec-ch-ua-platform': '"macOS"',
  'Sec-Fetch-Dest': 'empty',
  'Sec-Fetch-Mode': 'cors',
  'Sec-Fetch-Site': 'same-origin'
};

function fetchZhihuHotList() {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'www.zhihu.com',
      path: '/api/v3/feed/topstory/hot-list-web?limit=50',
      method: 'GET',
      headers: DEFAULT_HEADERS
    };

    const req = https.request(options, (res) => {
      const chunks = [];
      
      res.on('data', chunk => {
        chunks.push(chunk);
      });
      
      res.on('end', () => {
        const buffer = Buffer.concat(chunks);
        const encoding = res.headers['content-encoding'];
        
        const parseData = (data) => {
          try {
            const json = JSON.parse(data);
            resolve(json);
          } catch (e) {
            console.log('解析失败，原始数据:', String(data).slice(0, 500));
            reject(new Error(`JSON解析失败: ${e.message}`));
          }
        };
        
        if (encoding === 'gzip') {
          zlib.gunzip(buffer, (err, decoded) => {
            if (err) return reject(err);
            parseData(decoded.toString());
          });
        } else if (encoding === 'br') {
          zlib.brotliDecompress(buffer, (err, decoded) => {
            if (err) return reject(err);
            parseData(decoded.toString());
          });
        } else if (encoding === 'deflate') {
          zlib.inflate(buffer, (err, decoded) => {
            if (err) return reject(err);
            parseData(decoded.toString());
          });
        } else {
          parseData(buffer.toString());
        }
      });
    });

    req.on('error', reject);
    req.setTimeout(15000, () => {
      req.destroy();
      reject(new Error('请求超时'));
    });

    req.end();
  });
}

// 获取问题详情
function fetchQuestionDetail(questionId) {
  return new Promise((resolve, reject) => {
    const options = {
      hostname: 'www.zhihu.com',
      path: `/api/v4/questions/${questionId}`,
      method: 'GET',
      headers: DEFAULT_HEADERS
    };

    const req = https.request(options, (res) => {
      let data = '';
      
      res.on('data', chunk => {
        data += chunk;
      });
      
      res.on('end', () => {
        try {
          const json = JSON.parse(data);
          resolve(json);
        } catch (e) {
          reject(e);
        }
      });
    });

    req.on('error', reject);
    req.setTimeout(5000, () => {
      req.destroy();
      reject(new Error('问题详情请求超时'));
    });

    req.end();
  });
}

// 处理热榜数据 (v3 API格式)
function processHotListData(data) {
  if (!data.data || !Array.isArray(data.data)) {
    throw new Error('API返回的数据格式不正确');
  }

  const hotItems = data.data.map((item, index) => {
    const target = item.target || {};
    const titleArea = target.title_area || {};
    const excerptArea = target.excerpt_area || {};
    const metricsArea = target.metrics_area || {};
    const linkArea = target.link || {};
    
    // Extract question ID from link or card_id
    const linkUrl = linkArea.url || '';
    const questionIdMatch = linkUrl.match(/question\/(\d+)/) || 
                           (item.card_id || '').match(/Q_(\d+)/);
    const questionId = questionIdMatch ? questionIdMatch[1] : '';
    
    return {
      rank: index + 1,
      id: questionId,
      title: titleArea.text || '无标题',
      excerpt: excerptArea.text || '',
      url: linkUrl || `https://www.zhihu.com/question/${questionId}`,
      heat_text: metricsArea.text || '',
      answer_count: item.feed_specific ? item.feed_specific.answer_count : 0,
      card_id: item.card_id || '',
      thumbnail: (target.image_area || {}).url || ''
    };
  });

  return hotItems;
}

async function main() {
  console.log('🔍 开始采集知乎热榜数据...');
  
  try {
    // 1. 获取热榜列表
    const rawData = await fetchZhihuHotList();
    console.log('📡 API响应状态:', rawData.status || '未知');
    
    // 2. 处理数据
    const processedData = processHotListData(rawData);
    
    // 3. 生成时间戳
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const filename = `zhihu-${timestamp.replace(/-/g, '').replace('T', '_')}.json`;
    const mdFilename = `zhihu-${timestamp.replace(/-/g, '').replace('T', '_')}.md`;
    
    // 4. 保存JSON
    const jsonPath = path.join(DATA_DIR, filename);
    const outputData = {
      platform: '知乎',
      timestamp: new Date().toISOString(),
      total: processedData.length,
      hotlist: processedData
    };
    
    fs.writeFileSync(jsonPath, JSON.stringify(outputData, null, 2));
    
    // Update latest file
    const latestPath = path.join(DATA_DIR, 'zhihu-latest.json');
    fs.writeFileSync(latestPath, JSON.stringify(outputData, null, 2));
    
    // 5. 生成Markdown报告
    let mdContent = `# 知乎热榜 - ${new Date().toLocaleString('zh-CN')}\n\n`;
    mdContent += `| 排名 | 标题 | 热度 | 回答数 |\n`;
    mdContent += `|------|------|------|--------|\n`;
    
    processedData.slice(0, 20).forEach((item) => {
      const heat = item.heat_text || '-';
      const answers = item.answer_count || 0;
      
      mdContent += `| ${item.rank} | ${item.title} | ${heat} | ${answers} |\n`;
    });
    
    const mdPath = path.join(DATA_DIR, mdFilename);
    fs.writeFileSync(mdPath, mdContent);
    
    // 6. 输出结果
    console.log(`✅ 知乎热榜采集成功: ${processedData.length} 条数据`);
    console.log(`   JSON: ${filename}`);
    console.log(`   Markdown: ${mdFilename}`);
    
    if (processedData.length > 0) {
      console.log('\n📊 TOP5 热榜:');
      processedData.slice(0, 5).forEach((item, i) => {
        const heat = item.heat_text ? ` [${item.heat_text}]` : '';
        console.log(`   ${i + 1}. ${item.title}${heat}`);
      });
    }
    
    return { success: true, count: processedData.length };
    
  } catch (error) {
    console.error('❌ 知乎热榜采集失败:', error.message);
    
    // 生成错误日志
    const errorData = {
      platform: '知乎',
      timestamp: new Date().toISOString(),
      error: {
        message: error.message,
        stack: error.stack,
        code: error.code
      }
    };
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
    const errorFilename = `zhihu-error-${timestamp.replace(/-/g, '').replace('T', '_')}.json`;
    const errorPath = path.join(DATA_DIR, errorFilename);
    fs.writeFileSync(errorPath, JSON.stringify(errorData, null, 2));
    
    return { success: false, error: error.message };
  }
}

main().then(result => {
  process.exit(result.success ? 0 : 1);
}).catch(error => {
  console.error('执行失败:', error);
  process.exit(1);
});