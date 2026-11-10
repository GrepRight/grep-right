"""Semantic search: query -> embedding -> Qdrant top-k -> MySQL join -> ranked results."""
from app.db import repository as r
from app.services import embedder, vector_store

SNIPPET_LINES = 12


def search(query: str, repo_id=None, language=None, limit=10) -> list[dict]:
    hits = vector_store.search(embedder.embed_query(query), limit=limit, repo_id=repo_id, language=language)
    rows = r.get_chunks_with_context([cid for cid, _ in hits])
    results = []
    for cid, score in hits:
        row = rows.get(cid)
        if not row:                      # vector without a MySQL row (stale) -> skip
            continue
        lines = row["content"].split("\n")
        results.append({
            "chunk_id": cid,
            "repo_id": row["repo_id"],
            "repo_name": row["repo_name"],
            "file_id": row["file_id"],
            "name": row["name"],
            "chunk_type": row["chunk_type"],
            "file_path": row["file_path"],
            "language": row["language"],
            "start_line": row["start_line"],
            "end_line": row["end_line"],
            "snippet": "\n".join(lines[:SNIPPET_LINES]) + ("\n..." if len(lines) > SNIPPET_LINES else ""),
            "score": round(score, 4),
        })
    return results
