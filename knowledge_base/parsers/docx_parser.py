"""DOCX parser using python-docx."""

import os

from knowledge_base.parsers.base import BaseParser


class DocxParser(BaseParser):
    def parse(self, path: str) -> dict:
        try:
            from docx import Document
            doc = Document(path)
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            text = '\n'.join(paragraphs)
            title = paragraphs[0][:100] if paragraphs else os.path.basename(path)
        except ImportError:
            return {'text': '', 'title': os.path.basename(path), 'char_count': 0,
                    'metadata': {'source': 'docx', 'error': 'python-docx not installed'}}
        return {'text': text, 'title': title, 'char_count': len(text),
                'metadata': {'source': 'docx'}}
