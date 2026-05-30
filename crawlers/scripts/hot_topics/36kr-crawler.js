// 36kr 热榜爬虫 - HTML 解析方案 v3
// 方案：解析页面中的 window.initialState JSON 数据
// 更新：支持定时采集任务，创建专门的目录结构

const fs = require('fs');
const path = require('path');
const { fetchHTML } = require('../utils/fetch_helper');

const OUTPUT_DIR = process.env.INTELHUB_DATA_DIR || path.join(__dirname, '../data/36kr');

// 确保目录存在
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

async function fetch36kr() {
  const data = await fetchHTML('https://www.36kr.com/newsflashes');

  // 使用更精确的提取方式
  const startMarker = 'window.initialState=';
  const startIdx = data.indexOf(startMarker);

  if (startIdx === -1) {
    throw new Error('无法找到 initialState 数据');
  }

  // 从 startMarker 之后开始解析 JSON
  const jsonStart = startIdx + startMarker.length;

  // 找到 JSON 对象的结束位置
  let depth = 0;
  let inString = false;
  let escape = false;
  let endIdx = jsonStart;

  for (let i = jsonStart; i < data.length; i++) {
    const char = data[i];

    if (escape) {
      escape = false;
      continue;
    }

    if (char === '\\') {
      escape = true;
      continue;
    }

    if (char === '"' && !escape) {
      inString = !inString;
      continue;
    }

    if (inString) continue;

    if (char === '{') depth++;
    else if (char === '}') {
      depth--;
      if (depth === 0) {
        endIdx = i + 1;
        break;
      }
    }
  }

  const jsonStr = data.substring(jsonStart, endIdx);
  const initialState = JSON.parse(jsonStr);

  // 提取快讯数据
  const newsflashData = initialState.newsflashCatalogData?.data?.newsflashList?.data?.itemList || [];
  const hotlistData = initialState.newsflashCatalogData?.data?.hotlist?.data || [];

  return {
    newsflash: newsflashData.map(item => ({
      id: item.itemId,
      title: item.templateMaterial?.widgetTitle,
      content: item.templateMaterial?.widgetContent,
      publishTime: item.templateMaterial?.publishTime,
      time: new Date(item.templateMaterial?.publishTime).toISOString()
    })),
    hotlist: hotlistData.map(item => ({
      id: item.itemId,
      title: item.templateMaterial?.widgetTitle,
      image: item.templateMaterial?.widgetImage,
      publishTime: item.templateMaterial?.publishTime,
      time: new Date(item.templateMaterial?.publishTime).toISOString()
    })),
    fetchTime: new Date().toISOString()
  };
}

async function main() {
  console.log('🔍 开始采集 36kr 热榜数据...');
  
  try {
    const data = await fetch36kr();
    
    const timestamp = new Date().toISOString().replace(/[:.]/g, '').slice(0, 15);
    const jsonFile = path.join(OUTPUT_DIR, `36kr-${timestamp}.json`);
    const mdFile = path.join(OUTPUT_DIR, `36kr-${timestamp}.md`);
    
    // 保存 JSON 文件
    fs.writeFileSync(jsonFile, JSON.stringify({
      platform: '36kr',
      timestamp: new Date().toISOString(),
      newsflash: data.newsflash,
      hotlist: data.hotlist
    }, null, 2), 'utf8');
    
    // 保存 Markdown 文件
    let md = `# 36kr 热榜\n\n`;
    md += `> 采集时间: ${new Date().toLocaleString('zh-CN')}\n`;
    md += `> 数据来源: 36kr 新闻快讯\n`;
    md += `> 快讯: ${data.newsflash.length} 条 | 热榜: ${data.hotlist.length} 条\n\n`;
    
    md += `## 🔥 热榜 TOP ${Math.min(10, data.hotlist.length)}\n\n`;
    data.hotlist.slice(0, 10).forEach((item, i) => {
      const title = item.title || '';
      md += `${i + 1}. **${title}**\n`;
      if (item.publishTime) {
        md += `   - 发布时间: ${new Date(item.publishTime).toLocaleString('zh-CN')}\n`;
      }
      md += `\n`;
    });
    
    md += `## 📰 最新快讯 TOP ${Math.min(10, data.newsflash.length)}\n\n`;
    data.newsflash.slice(0, 10).forEach((item, i) => {
      const title = item.title || '';
      md += `${i + 1}. ${title}\n`;
      if (item.publishTime) {
        md += `   - ${new Date(item.publishTime).toLocaleString('zh-CN')}\n`;
      }
      md += `\n`;
    });
    
    fs.writeFileSync(mdFile, md, 'utf8');
    
    // 同时更新 latest.json（兼容旧版）
    const latestFile = path.join(OUTPUT_DIR, '36kr-latest.json');
    fs.writeFileSync(latestFile, JSON.stringify(data, null, 2));
    
    console.log(`✅ 36kr 数据采集成功！`);
    console.log(`   快讯数量: ${data.newsflash.length}`);
    console.log(`   热榜数量: ${data.hotlist.length}`);
    console.log(`   JSON: ${path.basename(jsonFile)}`);
    console.log(`   Markdown: ${path.basename(mdFile)}`);
    
    console.log('\n📊 前5条热榜:');
    data.hotlist.slice(0, 5).forEach((item, i) => {
      const title = item.title || '';
      console.log(`   ${i+1}. ${title.substring(0, 60)}${title.length > 60 ? '...' : ''}`);
    });
    
    return data;
  } catch (error) {
    console.error(`❌ 36kr 数据采集失败:`, error.message);
    throw error;
  }
}

main();
