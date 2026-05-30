/**
 * 东方财富财经爬虫
 * 采集财经新闻、股票资讯等数据
 */

const fs = require('fs');
const path = require('path');

// 东方财富财经新闻 API
const NEWS_API = 'https://news.eastmoney.com/kuaixun/cankao.html';
const STOCK_NEWS_API = 'https://np-anotice-stock.eastmoney.com/api/publicity/zhangdieNotice';

// 数据保存目录
const DATA_DIR = process.env.INTELHUB_DATA_DIR || path.join(__dirname, '..', 'data', 'eastmoney');
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}
const OUTPUT_FILE = path.join(DATA_DIR, `eastmoney-${getTimestamp()}.json`);

// 辅助函数
function getTimestamp() {
  const now = new Date();
  return now.toISOString().replace(/[:.]/g, '-').slice(0, 19);
}

function formatTime(date) {
  const d = new Date(date);
  return d.toISOString().slice(0, 19).replace('T', ' ');
}

// 采集东方财富财经新闻
async function fetchEastMoneyNews() {
  const newsList = [];
  
  try {
    // 尝试获取股市新闻
    console.log('📈 采集东方财富股市新闻...');
    
    // 尝试东方财富股市新闻API
    const today = new Date().toISOString().slice(0, 10);
    const stockApiUrl = `https://np-anotice-stock.eastmoney.com/api/publicity/zhangdieNotice?page=1&pageSize=20&plate=&date=${today}`;
    
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    
    const response = await fetch(stockApiUrl, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://stock.eastmoney.com/',
      },
      signal: controller.signal
    });
    
    clearTimeout(timeout);
    
    if (response.ok) {
      const data = await response.json();
      
      if (data.data && data.data.notices) {
        data.data.notices.forEach((item, index) => {
          newsList.push({
            rank: index + 1,
            title: item.title || '',
            content: item.summary || '',
            url: item.url || '',
            stockCode: item.sInfo || '',
            change: item.change || '',
            time: item.ajaxTime || '',
            source: '东方财富-股市新闻'
          });
        });
      }
    }
  } catch (error) {
    console.log('⚠️ 股市新闻API失败，尝试其他数据源...');
  }
  
  // 如果没有获取到数据，尝试财经新闻
  if (newsList.length === 0) {
    try {
      console.log('📊 尝试财经新闻数据...');
      
      // 尝试财经新闻列表API
      const financeApiUrl = 'https://newsapi.eastmoney.com/kuaixun/v1/getlist_102_ajaxResult_50_1_.html';
      
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 10000);
      
      const response = await fetch(financeApiUrl, {
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          'Referer': 'https://www.eastmoney.com/',
        },
        signal: controller.signal
      });
      
      clearTimeout(timeout);
      
      if (response.ok) {
        const text = await response.text();
        // 尝试解析JSONP格式
        const jsonMatch = text.match(/\{.*\}/);
        if (jsonMatch) {
          const data = JSON.parse(jsonMatch[0]);
          if (data.LivesList) {
            data.LivesList.forEach((item, index) => {
              newsList.push({
                rank: index + 1,
                title: item.title || item.content || '',
                content: item.content || '',
                url: item.url || '',
                time: item.showtime || '',
                source: '东方财富-财经新闻'
              });
            });
          }
        }
      }
    } catch (error) {
      console.log('⚠️ 财经新闻API失败:', error.message);
    }
  }
  
  if (newsList.length === 0) {
    console.log('⚠️ 所有API均未获取到数据');
  }

  return newsList;
}

// 主函数
async function main() {
  console.log('🕷️ 东方财富爬虫启动...');
  console.log('='.repeat(50));
  
  const startTime = Date.now();
  
  // 采集数据
  const newsList = await fetchEastMoneyNews();
  
  console.log(`\n✅ 采集完成: ${newsList.length} 条财经资讯`);
  
  // 保存原始数据
  const rawData = {
    platform: '东方财富',
    category: '财经',
    timestamp: new Date().toISOString(),
    count: newsList.length,
    items: newsList
  };

  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(rawData, null, 2));
  // latest.json for plaza API
  const latestFile = path.join(DATA_DIR, 'eastmoney-latest.json');
  fs.writeFileSync(latestFile, JSON.stringify(rawData, null, 2));
  console.log(`💾 数据已保存: ${OUTPUT_FILE}`);
  
  // 输出TOP10
  console.log('\n📊 东方财富 TOP10 财经新闻:');
  console.log('-'.repeat(50));
  
  newsList.slice(0, 10).forEach((item, index) => {
    console.log(`${index + 1}. ${item.title}`);
    if (item.content) console.log(`   ${item.content}`);
  });
  
  console.log('\n' + '='.repeat(50));
  console.log(`🕷️ 采集耗时: ${(Date.now() - startTime) / 1000}s`);
  
  return newsList;
}

main().catch(console.error);
