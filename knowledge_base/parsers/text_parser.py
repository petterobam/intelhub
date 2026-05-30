"""Text/Markdown parser."""

import os

from knowledge_base.parsers.base import BaseParser


class TextParser(BaseParser):
    def parse(self, path: str) -> dict:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()
        lines = text.split('\n')
        title = next((l.lstrip('#').strip() for l in lines if l.strip()), os.path.basename(path))
        return {'text': text, 'title': title, 'char_count': len(text),
                'metadata': {'source': 'text'}}
