// 港交所公告采集脚本（基于 Hermes Browser Tool）
// 使用浏览器工具访问披露易并抓取最新公告

const fs = require('fs');
const path = require('path');

async function collectHKEXAnnouncements(outputDir) {
  // 注意：此脚本需通过 Hermes Browser Tool 执行或提供浏览器 CLI 入口
  // 以下为适配 Hermes Browser Tool 的 JS 脚本模板，执行方式示例：
  // node -e "$(cat exchange-hkex.js)" <在浏览器上下文中运行>

  function extractAnnouncementsFromPage() {
    const announcements = [];
    const listItems = document.querySelectorAll('li');

    for (let li of listItems) {
      const textContent = li.textContent.trim();
      const timeMatch = textContent.match(/(\d{1,2}:\d{2})/);
      const dateMatch = textContent.match(/(\d{1,2})\s+(五月|四月|六月|七月|八月|九月|十月|十一月|十二月)/);
      const codeMatch = textContent.match(/\b0\d{4}\b/);
      const catMatch = textContent.match(/公告及通告\s*-\s*\[([^\]]+)\]/);
      const titleMatch = textContent.match(/\]\s*([^\d]+)/);

      if (!timeMatch || !dateMatch || !codeMatch) continue;

      const time = timeMatch[1];
      const day = dateMatch[1];
      const month = dateMatch[2];
      const stockCode = codeMatch[0];
      const titleCat = catMatch ? catMatch[1] : '';
      const title = titleMatch ? titleMatch[1].trim() : '';

      let companyName = '';
      const nameMatch = textContent.match(new RegExp(stockCode + '\\s+([^\u4e00-\u9fa5]{2,4}|[\u4e00-\u9fa5]{2,4})'));
      if (nameMatch) companyName = nameMatch[1].trim();

      let url = '';
      const linkEl = li.querySelector('a[href^="javascript:openDoc"]');
      if (linkEl) {
        url = linkEl.href;
      }

      if (!time || !day || !month || !stockCode) continue;
      if (!titleCat && !title) continue;

      let category = '其他';
      let importance = 'low';

      if (titleCat.includes('停牌') || titleCat.includes('復牌') || titleCat.includes('暫停') || title.includes('停牌') || title.includes('復牌') || title.includes('暫停')) {
        category = '停复牌信息';
        importance = 'high';
      } else if (titleCat.includes('業績') || titleCat.includes('財務報表') || title.includes('業績') || title.includes('財務報表') || title.includes('中期') || title.includes('末期')) {
        category = '财务报告';
        importance = 'high';
      } else if (titleCat.includes('股東大會') || titleCat.includes('股東週年大會') || title.includes('股東大會') || title.includes('股東週年大會')) {
        category = '股东大会';
        importance = 'medium';
      } else if (titleCat.includes('通函') || title.includes('通函')) {
        category = '通函';
        importance = 'medium';
      } else if (titleCat.includes('收購') || titleCat.includes('併購') || titleCat.includes('配股') || titleCat.includes('供股') || title.includes('收購') || title.includes('併購') || title.includes('配股') || title.includes('供股')) {
        category = '重大事项';
        importance = 'high';
      } else if (titleCat.includes('重組') || title.includes('重組') || title.includes('破產')) {
        category = '重组';
        importance = 'high';
      }

      announcements.push({
        stockCode,
        company: companyName,
        title: title.substring(0, 200),
        titleCategory: titleCat,
        url,
        time: `${month} ${day}日 ${time}`,
        category,
        importance,
        timestamp: new Date().toISOString()
      });
    }

    const uniqueItems = [];
    const seenKeys = new Set();
    for (const item of announcements) {
      const key = `${item.stockCode}-${item.company}-${item.title.substring(0,30)}`;
      if (!seenKeys.has(key)) {
        seenKeys.add(key);
        uniqueItems.push(item);
      }
    }

    uniqueItems.sort((a, b) => {
      const order = { 'high': 0, 'medium': 1, 'low': 2 };
      return order[a.importance] - order[b.importance];
    });

    return uniqueItems.slice(0, 30);
  }

  // 若在浏览器上下文中，直接提取并返回
  if (typeof document !== 'undefined') {
    return extractAnnouncementsFromPage();
  }

  // 若在 Node.js 环境中，输出占位说明（实际采集由 Hermes Browser Tool 完成）
  const placeholder = [{
    title: "港交所公告由 Hermes Browser Tool 实时采集",
    url: "https://www.hkexnews.hk/index_c.htm",
    category: "公告采集说明",
    importance: "low",
    timestamp: new Date().toISOString()
  }];

  if (outputDir) {
    fs.mkdirSync(outputDir, { recursive: true });
    const outputFile = path.join(outputDir, 'hkex-extracted.json');
    fs.writeFileSync(outputFile, JSON.stringify(placeholder, null, 2));
    console.error(`已写入占位文件: ${outputFile}`);
  }

  return placeholder;
}

// Node.js 环境入口
if (require.main === module) {
  const outputDir = process.argv[2];
  collectHKEXAnnouncements(outputDir)
    .then(data => {
      if (typeof document === 'undefined') {
        console.log(JSON.stringify(data, null, 2));
      } else {
        return data;
      }
    })
    .catch(err => {
      console.error('采集失败:', err);
      process.exit(1);
    });
}

module.exports = collectHKEXAnnouncements;
