"""Python symbol extraction using the standard-library `ast` (source is parsed, never executed)."""
import ast

from app.parsers.models import ParsedFile, Symbol


def _signature(node) -> str:
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    sig = f"{prefix} {node.name}({ast.unparse(node.args)})"
    if node.returns is not None:
        sig += f" -> {ast.unparse(node.returns)}"
    return sig


def _class_signature(node: ast.ClassDef) -> str:
    parts = [ast.unparse(b) for b in node.bases] + [ast.unparse(k) for k in node.keywords]
    return f"class {node.name}({', '.join(parts)})" if parts else f"class {node.name}"


def _start_line(node) -> int:
    return min([node.lineno] + [d.lineno for d in node.decorator_list])


def _nested_bodies(stmt):
    """Statement lists inside compound statements (if/try/with/...) that may hold definitions."""
    for attr in ("body", "orelse", "finalbody"):
        body = getattr(stmt, attr, None)
        if isinstance(body, list):
            yield body
    for handler in getattr(stmt, "handlers", []):
        yield handler.body
    for case in getattr(stmt, "cases", []):
        yield case.body


def _visit(body, prefix: str, out: list[Symbol]) -> None:
    for stmt in body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # nested functions are intentionally not extracted; they stay inside the parent's chunk
            out.append(Symbol("function", prefix + stmt.name, _start_line(stmt), stmt.end_lineno,
                              _signature(stmt), ast.get_docstring(stmt)))
        elif isinstance(stmt, ast.ClassDef):
            out.append(Symbol("class", prefix + stmt.name, _start_line(stmt), stmt.end_lineno,
                              _class_signature(stmt), ast.get_docstring(stmt)))
            _visit(stmt.body, prefix + stmt.name + ".", out)
        else:
            for inner in _nested_bodies(stmt):
                _visit(inner, prefix, out)


def parse_python(source: str) -> ParsedFile:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError, MemoryError):
        return ParsedFile(parse_error=True)
    symbols: list[Symbol] = []
    _visit(tree.body, "", symbols)
    return ParsedFile(symbols=symbols)
