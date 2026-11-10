"""FastEmbed wrapper (BAAI/bge-small-en-v1.5, 384-d). The model is loaded lazily on first use."""
import threading

from app.config import settings

# bge models are trained with this instruction prefix on the *query* side only.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    with _lock:
        if _model is None:
            from fastembed import TextEmbedding
            _model = TextEmbedding(model_name=settings.embedding_model)
        return _model


def chunk_text(row: dict) -> str:
    """Embedding text = path + name + signature + docstring + code, truncated."""
    parts = [row["file_path"]]
    for key in ("name", "signature", "docstring"):
        if row.get(key):
            parts.append(row[key])
    parts.append(row["content"])
    return "\n".join(parts)[:settings.max_embed_chars]


def embed_documents(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in _get_model().embed(texts, batch_size=settings.embed_batch_size)]


def embed_query(query: str) -> list[float]:
    return next(iter(_get_model().embed([QUERY_PREFIX + query]))).tolist()
