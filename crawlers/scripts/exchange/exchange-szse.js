// 深交所公告采集脚本
// 使用 Hermes Browser Tool 采集深交所最新公告

const szseAnnouncements = [];
const allLinks = document.querySelectorAll('a');

for (let link of allLinks) {
  const text = link.textContent.trim();
  const href = link.href;

  // 过滤公告链接
  if (text.length > 10 && text.length < 200 &&
      !text.includes('首页') &&
      !text.includes('更多') &&
      !text.includes('网站地图') &&
      !text.includes('关于我们') &&
      !text.includes('联系我们') &&
      !text.includes('登录') &&
      !text.includes('搜索') &&
      !href.includes('javascript') &&
      href && href.length > 20 &&
      (href.includes('szse.cn') || href.includes('/disclosure/'))) {

    let category = '其他';
    let importance = 'low';

    // 深交所特定关键词匹配
    if (text.includes('公告') || text.includes('通知') || text.includes('披露')) {
      category = '上市公司公告';
      importance = 'high';
    } else if (text.includes('停牌') || text.includes('复牌') || text.includes('停复牌')) {
      category = '停复牌信息';
      importance = 'high';
    } else if (text.includes('年报') || text.includes('季报') || text.includes('报告')) {
      category = '财务报告';
      importance = 'high';
    } else if (text.includes('股东大会') || text.includes('董事会')) {
      category = '股东大会';
      importance = 'medium';
    } else if (text.includes('增发') || text.includes('配股') || text.includes('重组')) {
      category = '重大事项';
      importance = 'high';
    } else if (text.includes('处罚') || text.includes('决定书') || text.includes('问询函')) {
      category = '监管处罚';
      importance = 'high';
    } else if (text.includes('并购') || text.includes('收购') || text.includes('要约')) {
      category = '并购重组';
      importance = 'high';
    }

    szseAnnouncements.push({
      title: text,
      url: href,
      category: category,
      importance: importance
    });
  }
}

// 去重
const uniqueItems = [];
const seenUrls = new Set();

for (let item of szseAnnouncements) {
  if (!seenUrls.has(item.url)) {
    seenUrls.add(item.url);
    uniqueItems.push(item);
  }
}

// 按重要性排序
uniqueItems.sort((a, b) => {
  const order = { 'high': 0, 'medium': 1, 'low': 2 };
  return order[a.importance] - order[b.importance];
});

const results = uniqueItems.slice(0, 15);

// Node.js 环境写入 JSON（若提供了输出目录）
if (typeof document === 'undefined' && typeof module !== 'undefined' && module.exports !== undefined) {
  const fs = require('fs');
  const path = require('path');
  const outputDir = process.argv[2];
  if (outputDir) {
    fs.mkdirSync(outputDir, { recursive: true });
    const timestamp = Date.now();
    const outputFile = path.join(outputDir, `szse-${timestamp}.json`);
    fs.writeFileSync(outputFile, JSON.stringify(results, null, 2));
  }
  console.log(JSON.stringify(results, null, 2));
}

return results;
