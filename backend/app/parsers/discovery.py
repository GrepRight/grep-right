"""Walk a cloned working tree and decide which files get recorded / parsed.

Nothing here executes or imports repository code: files are only read as bytes/text.
"""
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

SKIP_DIRS = {
    ".git", "node_modules", "venv", ".venv", "env", "__pycache__", "dist", "build", "out",
    "target", "vendor", "site-packages", ".next", ".nuxt", "coverage", ".idea", ".vscode",
    ".tox", ".mypy_cache", ".pytest_cache", "bower_components",
}
SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Pipfile.lock",
    "composer.lock", "Cargo.lock", "go.sum",
}
SKIP_SUFFIXES = (".min.js", ".min.css", ".map", ".bundle.js")

# Extensions recorded in `files`. Only PARSED_LANGUAGES are chunked / embedded.
LANGUAGES = {
    ".py": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".java": "java", ".go": "go", ".rs": "rust", ".c": "c", ".h": "c", ".cpp": "cpp",
    ".cs": "csharp", ".rb": "ruby", ".php": "php", ".kt": "kotlin", ".swift": "swift",
    ".sql": "sql", ".sh": "shell", ".html": "html", ".css": "css", ".scss": "css",
    ".md": "markdown", ".json": "json", ".yml": "yaml", ".yaml": "yaml", ".toml": "toml",
}
PARSED_LANGUAGES = {"python", "javascript", "typescript"}
MAX_PATH_LEN = 500


@dataclass
class SourceFile:
    rel_path: str             # posix-style, relative to the repo root
    abs_path: Path
    language: str | None
    size_bytes: int
    last_modified: datetime | None


def _is_inside(root: Path, path: Path) -> bool:
    try:
        path.resolve().relative_to(root)
        return True
    except ValueError:
        return False


def _looks_binary(path: Path) -> bool:
    try:
        with open(path, "rb") as fh:
            return b"\x00" in fh.read(8192)
    except OSError:
        return True


def iter_source_files(root: Path, max_file_bytes: int):
    """Yield SourceFile for every recordable file under `root` (symlinks and escapes are skipped)."""
    root = Path(root).resolve()
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in SKIP_DIRS and not os.path.islink(os.path.join(dirpath, d))
        )
        for fname in sorted(filenames):
            if fname in SKIP_FILES or fname.lower().endswith(SKIP_SUFFIXES):
                continue
            ext = os.path.splitext(fname)[1].lower()
            if ext not in LANGUAGES:
                continue
            path = Path(dirpath) / fname
            if path.is_symlink() or not _is_inside(root, path):
                continue
            try:
                st = path.stat()
            except OSError:
                continue
            if st.st_size > max_file_bytes or _looks_binary(path):
                continue
            rel = path.relative_to(root).as_posix()
            if len(rel) > MAX_PATH_LEN:
                continue
            yield SourceFile(
                rel_path=rel,
                abs_path=path,
                language=LANGUAGES[ext],
                size_bytes=st.st_size,
                last_modified=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).replace(tzinfo=None),
            )


def read_source(path: Path) -> str:
    """Read as UTF-8 (undecodable bytes replaced) with line endings normalised to LF.

    Normalising here keeps `ast` and tree-sitter line numbers identical to our own line splitting.
    """
    text = Path(path).read_bytes().decode("utf-8", errors="replace")
    if text.startswith("﻿"):
        text = text[1:]
    return text.replace("\r\n", "\n").replace("\r", "\n")
