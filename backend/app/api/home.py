"""HTML landing page for the API root (GET /): lists every route, generated from the app itself."""
from html import escape

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(include_in_schema=False)

_STYLE = """
body{font-family:system-ui,sans-serif;max-width:900px;margin:40px auto;padding:0 16px;color:#1f2430}
h1{margin-bottom:4px}.sub{color:#667;margin-top:0}
table{width:100%;border-collapse:collapse;margin-top:16px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #e3e6ec;font-size:14px}
code{background:#f1f3f7;padding:2px 6px;border-radius:4px}
.m{font-weight:600;font-size:12px;padding:2px 8px;border-radius:4px;color:#fff}
.GET{background:#2b8a3e}.POST{background:#1c6dd0}.DELETE{background:#c92a2a}
a{color:#1c6dd0}
"""


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    rows = []
    for path, ops in request.app.openapi().get("paths", {}).items():
        for m, op in ops.items():
            m = m.upper()
            if m not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                continue
            link = f'<a href="{escape(path)}">{escape(path)}</a>' if m == "GET" and "{" not in path else f"<code>{escape(path)}</code>"
            doc = escape(op.get("summary") or "")
            rows.append((path, m, f'<tr><td><span class="m {m}">{m}</span></td><td>{link}</td><td>{doc}</td></tr>'))
    rows.sort(key=lambda x: (x[0], x[1]))
    body = "".join(r[2] for r in rows)
    return (
        f"<!doctype html><html><head><meta charset='utf-8'><title>GrepRight API</title><style>{_STYLE}</style></head>"
        "<body><h1>GrepRight API</h1><p class='sub'>Semantic code search backend · "
        "<a href='/docs'>Interactive docs (Swagger)</a> · <a href='/redoc'>ReDoc</a> · "
        "<a href='http://localhost:3000'>Web app</a></p>"
        f"<table><thead><tr><th>Method</th><th>Route</th><th>Description</th></tr></thead><tbody>{body}</tbody></table>"
        "</body></html>"
    )
