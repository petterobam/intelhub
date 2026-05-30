"""URL content parser — fetch and extract text from web pages."""

import requests

from knowledge_base.parsers.base import BaseParser


class UrlParser(BaseParser):
    def fetch_and_parse(self, url: str) -> dict:
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; IntelHub/1.0)'}
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = resp.apparent_encoding or 'utf-8'

        # Try BeautifulSoup for better extraction
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(resp.text, 'html.parser')
            for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
                tag.decompose()
            text = soup.get_text(separator='\n', strip=True)
            title_el = soup.find('title')
            title = title_el.get_text(strip=True) if title_el else url
        except ImportError:
            # Fallback: basic HTML stripping
            import re
            text = re.sub(r'<[^>]+>', '\n', resp.text)
            text = re.sub(r'\n{3,}', '\n\n', text).strip()
            title = url

        return {'text': text, 'title': title, 'char_count': len(text),
                'metadata': {'source': 'url', 'url': url}}

    def parse(self, path: str) -> dict:
        raise NotImplementedError("Use fetch_and_parse(url) for URL parser")
