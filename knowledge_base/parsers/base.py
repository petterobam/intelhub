# Parsers

import os


class BaseParser:
    def parse(self, path: str) -> dict:
        """Returns {text, title, char_count, metadata}."""
        raise NotImplementedError

