"""Plain data containers shared by the parsers, chunker and indexer."""
from dataclasses import dataclass, field


@dataclass
class Symbol:
    kind: str                 # 'function' | 'class'
    name: str                 # methods are qualified: "Class.method"
    start_line: int           # 1-based, inclusive
    end_line: int
    signature: str | None = None
    docstring: str | None = None


@dataclass
class ParsedFile:
    symbols: list[Symbol] = field(default_factory=list)
    parse_error: bool = False   # syntax error / parser failure -> chunker falls back to module windows


@dataclass
class Chunk:
    chunk_type: str           # 'function' | 'class' | 'module'
    content: str
    start_line: int
    end_line: int
