from app.parsers.chunker import build_chunks
from app.parsers.js_parser import parse_js
from app.parsers.models import Chunk, ParsedFile, Symbol
from app.parsers.python_parser import parse_python


def parse_file(source: str, language: str, path: str = "") -> ParsedFile:
    """Dispatch to the right parser; unsupported languages yield an empty result."""
    if language == "python":
        return parse_python(source)
    if language in ("javascript", "typescript"):
        return parse_js(source, language, path)
    return ParsedFile()


__all__ = ["parse_file", "build_chunks", "Chunk", "ParsedFile", "Symbol"]
