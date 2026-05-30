"""Parser dispatcher — routes file extensions to their parsers."""

from knowledge_base.parsers.text_parser import TextParser
from knowledge_base.parsers.pdf_parser import PdfParser
from knowledge_base.parsers.docx_parser import DocxParser
from knowledge_base.parsers.base import BaseParser

PARSERS = {
    'pdf': PdfParser,
    'txt': TextParser,
    'md': TextParser,
    'markdown': TextParser,
    'docx': DocxParser,
}


def get_parser(ext: str) -> BaseParser:
    cls = PARSERS.get(ext.lower())
    if not cls:
        raise ValueError(f'No parser for .{ext}')
    return cls()
