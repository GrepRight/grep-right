"""JavaScript / TypeScript symbol extraction with Tree-sitter (source is parsed, never executed)."""
import tree_sitter_javascript as ts_js
import tree_sitter_typescript as ts_ts
from tree_sitter import Language, Parser

from app.parsers.models import ParsedFile, Symbol

_LANGS = {
    "javascript": Language(ts_js.language()),
    "typescript": Language(ts_ts.language_typescript()),
    "tsx": Language(ts_ts.language_tsx()),
}
_FUNC_VALUES = {"arrow_function", "function_expression", "function", "generator_function"}
_FUNC_DECLS = {"function_declaration", "generator_function_declaration"}
_CLASS_DECLS = {"class_declaration", "abstract_class_declaration"}


def _text(node) -> str:
    return node.text.decode("utf-8", errors="replace")


def _jsdoc(node) -> str | None:
    """A `/** ... */` comment directly above `node` (must be on the adjacent line)."""
    prev = node.prev_sibling
    if prev is not None and prev.type == "comment" and prev.end_point[0] >= node.start_point[0] - 1:
        raw = _text(prev)
        if raw.startswith("/**"):
            lines = [ln.strip().lstrip("*").strip() for ln in raw[3:-2].splitlines()]
            return "\n".join(ln for ln in lines if ln) or None
    return None


def _header(node) -> str:
    """Source text of `node` up to (excluding) its body, collapsed to one line."""
    body = node.child_by_field_name("body")
    end = body.start_byte if body is not None else node.end_byte
    raw = node.text[: end - node.start_byte].decode("utf-8", errors="replace")
    return " ".join(raw.split())


def _add(out, kind, name, outer, signature, doc_anchor):
    out.append(Symbol(kind, name, outer.start_point[0] + 1, outer.end_point[0] + 1, signature, _jsdoc(doc_anchor)))


def _visit(node, out: list[Symbol], anchor=None) -> None:
    """`anchor` is the node whose preceding comment is the doc (the `export` wrapper if present)."""
    t = node.type
    anchor = anchor or node
    if t == "export_statement":
        for child in node.named_children:
            _visit(child, out, anchor=node)
    elif t in _FUNC_DECLS:
        name = node.child_by_field_name("name")
        if name is not None:
            _add(out, "function", _text(name), anchor, _header(node), anchor)
    elif t in _CLASS_DECLS:
        name = node.child_by_field_name("name")
        if name is not None:
            cname = _text(name)
            _add(out, "class", cname, anchor, _header(node), anchor)
            body = node.child_by_field_name("body")
            if body is not None:
                for member in body.named_children:
                    if member.type == "method_definition":
                        mname = member.child_by_field_name("name")
                        if mname is not None:
                            _add(out, "function", f"{cname}.{_text(mname)}", member, _header(member), member)
    elif t in ("lexical_declaration", "variable_declaration"):
        for decl in node.named_children:
            if decl.type != "variable_declarator":
                continue
            value, name = decl.child_by_field_name("value"), decl.child_by_field_name("name")
            if value is not None and name is not None and value.type in _FUNC_VALUES and name.type == "identifier":
                _add(out, "function", _text(name), anchor, f"{_text(name)} = " + _header(value), anchor)


def parse_js(source: str, language: str = "javascript", path: str = "") -> ParsedFile:
    lang_key = "tsx" if path.lower().endswith(".tsx") else language
    parser = Parser(_LANGS.get(lang_key, _LANGS["javascript"]))
    try:
        tree = parser.parse(source.encode("utf-8"))
    except Exception:
        return ParsedFile(parse_error=True)
    symbols: list[Symbol] = []
    for child in tree.root_node.named_children:
        _visit(child, symbols)
    # Tree-sitter recovers from syntax errors, so partial results are still useful; flag only if nothing parsed.
    return ParsedFile(symbols=symbols, parse_error=tree.root_node.has_error and not symbols)
