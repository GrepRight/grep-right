import pytest

from app.errors import ImportFailure
from app.parsers import build_chunks, parse_file
from app.parsers.discovery import iter_source_files
from app.services.importer import normalize_git_url

PY = '''"""mod doc"""
import os

X = 1


def top(a, b=2) -> int:
    """Add things."""
    return a + b


@decorator
class Foo(Base):
    """Foo doc."""
    attr = 1

    def method(self):
        return 1

    async def amethod(self):
        pass


if X:
    def conditional():
        pass
'''

JS = '''/** Adds. */
export function add(a, b) {
  return a + b;
}

const mul = (a, b) => a * b;

class Calc {
  total() { return 1; }
}
'''


def test_python_symbols():
    p = parse_file(PY, "python")
    by = {s.name: s for s in p.symbols}
    assert set(by) == {"top", "Foo", "Foo.method", "Foo.amethod", "conditional"}
    assert by["top"].docstring == "Add things."
    assert by["top"].signature == "def top(a, b=2) -> int"
    assert by["Foo"].start_line == 12          # includes the decorator line
    assert by["Foo"].signature == "class Foo(Base)"
    assert by["Foo.amethod"].signature.startswith("async def amethod")


def test_python_syntax_error_flagged():
    assert parse_file("def broken(:\n", "python").parse_error


def test_chunks_cover_symbols_and_remainder():
    p = parse_file(PY, "python")
    chunks = build_chunks(PY, p)
    types = [(c.chunk_type, c.start_line) for c in chunks]
    assert ("function", 7) in types and ("class", 12) in types
    assert any(c.chunk_type == "module" and "import os" in c.content for c in chunks)
    class_chunk = next(c for c in chunks if c.chunk_type == "class")
    assert "def method" not in class_chunk.content and "attr = 1" in class_chunk.content
    assert all(c.end_line >= c.start_line >= 1 for c in chunks)


def test_long_function_is_windowed():
    src = "def big():\n" + "    x = 1\n" * 200
    chunks = build_chunks(src, parse_file(src, "python"))
    assert len(chunks) == 3 and all(c.chunk_type == "function" for c in chunks)


def test_js_symbols():
    p = parse_file(JS, "javascript", "a.js")
    by = {s.name: s for s in p.symbols}
    assert set(by) == {"add", "mul", "Calc", "Calc.total"}
    assert by["add"].docstring == "Adds."
    assert by["add"].start_line == 2 or by["add"].start_line == 1
    assert by["mul"].signature.startswith("mul = ")


def test_ts_and_tsx_parse():
    ts = "export interface A { x: number }\nexport function f(a: number): number { return a; }\n"
    assert [s.name for s in parse_file(ts, "typescript", "a.ts").symbols] == ["f"]
    tsx = "export const C = () => <div/>;\n"
    assert [s.name for s in parse_file(tsx, "typescript", "a.tsx").symbols] == ["C"]


@pytest.mark.parametrize("url,expected", [
    ("https://github.com/acme/widgets", "widgets"),
    ("https://github.com/acme/widgets.git", "widgets"),
    ("  https://github.com/acme/widgets/  ", "widgets"),
])
def test_url_accepted(url, expected):
    canonical, name = normalize_git_url(url)
    assert name == expected and canonical == "https://github.com/acme/widgets"


@pytest.mark.parametrize("url", [
    "http://github.com/a/b", "https://gitlab.com/a/b", "git@github.com:a/b.git", "file:///etc/passwd",
    "https://github.com/a", "https://github.com/a/b/c", "https://github.com/../b", "https://github.com/a/..",
    "https://github.com/a/b?x=1", "https://evil.com/https://github.com/a/b", "--upload-pack=x", "",
])
def test_url_rejected(url):
    with pytest.raises(ImportFailure):
        normalize_git_url(url)


def test_discovery_filters(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "b.js").write_text("x")
    (tmp_path / "big.py").write_text("x" * 5000)
    (tmp_path / "bin.py").write_bytes(b"\x00\x01")
    (tmp_path / "app.min.js").write_text("x")
    (tmp_path / "notes.xyz").write_text("x")
    found = {f.rel_path for f in iter_source_files(tmp_path, max_file_bytes=1000)}
    assert found == {"src/a.py"}
