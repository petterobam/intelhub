/**
 * Fetch helper with proper encoding detection for Chinese websites.
 * Many Chinese sites (1905, huanqiu, etc.) serve GBK/GB2312 content,
 * which Node.js https.get would misinterpret as UTF-8 by default.
 */

const https = require('https');
const http = require('http');
const iconv = require('iconv-lite');

/**
 * Fetch URL with automatic encoding detection.
 * Collects raw Buffer chunks, detects charset from Content-Type header
 * or HTML meta tag, then decodes properly.
 */
function fetchHTML(url, options = {}) {
  return new Promise((resolve, reject) => {
    const client = url.startsWith('https') ? https : http;
    const req = client.get(url, {
      headers: {
        'User-Agent': options.userAgent || 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
      }
    }, (res) => {
      const chunks = [];
      res.on('data', chunk => chunks.push(chunk));
      res.on('end', () => {
        const buf = Buffer.concat(chunks);

        // Detect encoding from Content-Type header
        let charset = 'utf-8';
        const contentType = res.headers['content-type'] || '';
        const ctMatch = contentType.match(/charset=([^\s;]+)/i);
        if (ctMatch) {
          charset = ctMatch[1].replace(/['"]/g, '').trim().toLowerCase();
        }

        // If not specified or ambiguous, check HTML meta tag
        if (!ctMatch || charset === 'utf-8' || charset === 'utf8') {
          const headSample = buf.slice(0, 2048).toString('ascii');
          const metaMatch = headSample.match(/charset=["']?([^"'\s>]+)/i);
          if (metaMatch) {
            const detected = metaMatch[1].toLowerCase();
            if (detected.includes('gb') || detected.includes('big5') || detected.includes('euc')) {
              charset = detected;
            }
          }
        }

        // Normalize charset names
        if (charset === 'gb2312') charset = 'gbk';

        // Decode
        let html;
        if (iconv.encodingExists(charset) && charset !== 'utf-8' && charset !== 'utf8') {
          html = iconv.decode(buf, charset);
        } else {
          html = buf.toString('utf-8');
        }

        resolve(html);
      });
    });
    req.on('error', reject);
    const timeout = options.timeout || 15000;
    req.setTimeout(timeout, () => {
      req.destroy();
      reject(new Error(`Request timeout (${timeout}ms)`));
    });
  });
}

module.exports = { fetchHTML };
