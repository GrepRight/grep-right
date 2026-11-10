"""Turn a parsed file into code chunks (one per function / class header, plus a module remainder).

Rules (see docs/ARCHITECTURE.md, key decision 3):
- every function/method -> a 'function' chunk
- every class -> a 'class' chunk holding the class text up to its first method (header, docstring, fields)
- lines not covered by any of the above -> one 'module' chunk
- chunks longer than WINDOW_LINES are split into consecutive windows of that size
"""
from app.parsers.models import Chunk, ParsedFile, Symbol

WINDOW_LINES = 80
MAX_CHUNKS_PER_FILE = 500


def _split(chunk_type: str, lines: list[str], first_line: int) -> list[Chunk]:
    out = []
    for i in range(0, len(lines), WINDOW_LINES):
        part = lines[i:i + WINDOW_LINES]
        if "".join(part).strip():
            out.append(Chunk(chunk_type, "\n".join(part), first_line + i, first_line + i + len(part) - 1))
    return out


def _class_end(cls: Symbol, symbols: list[Symbol]) -> int:
    """Last line of the class's own text: one line before its first nested definition (if any)."""
    inner = [s.start_line for s in symbols if s is not cls
             and s.start_line >= cls.start_line and s.end_line <= cls.end_line and s.name.startswith(cls.name + ".")]
    return min(inner) - 1 if inner else cls.end_line


def build_chunks(source: str, parsed: ParsedFile) -> list[Chunk]:
    lines = source.split("\n")
    total = len(lines)
    covered = [False] * (total + 2)
    chunks: list[Chunk] = []

    for sym in sorted(parsed.symbols, key=lambda s: (s.start_line, s.kind)):
        start = sym.start_line
        end = min(_class_end(sym, parsed.symbols) if sym.kind == "class" else sym.end_line, total)
        if end < start:
            continue
        chunks.extend(_split(sym.kind, lines[start - 1:end], start))
        for n in range(start, end + 1):
            covered[n] = True

    rest = [(n, lines[n - 1]) for n in range(1, total + 1) if not covered[n]]
    # keep the remainder as contiguous runs so line ranges stay truthful
    run: list[tuple[int, str]] = []
    for item in rest + [(None, "")]:
        if run and (item[0] is None or item[0] != run[-1][0] + 1):
            text = [ln for _, ln in run]
            chunks.extend(_split("module", text, run[0][0]))
            run = []
        if item[0] is not None:
            run.append(item)

    # whitespace-only runs were dropped by _split; cap pathological files
    chunks.sort(key=lambda c: (c.start_line, c.end_line))
    return chunks[:MAX_CHUNKS_PER_FILE]
