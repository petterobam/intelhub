"""PDF parser using pdfminer."""

import os

from knowledge_base.parsers.base import BaseParser


class PdfParser(BaseParser):
    def parse(self, path: str) -> dict:
        try:
            from pdfminer.high_level import extract_text
            text = extract_text(path)
        except ImportError:
            # Fallback: try PyPDF2
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(path)
                text = '\n'.join(page.extract_text() or '' for page in reader.pages)
            except ImportError:
                return {'text': '', 'title': os.path.basename(path), 'char_count': 0,
                        'metadata': {'source': 'pdf', 'error': 'No PDF parser available'}}

        lines = [l.strip() for l in text.split('\n') if l.strip()]
        title = lines[0][:100] if lines else os.path.basename(path)
        return {'text': text, 'title': title, 'char_count': len(text),
                'metadata': {'source': 'pdf'}}
