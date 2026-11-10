"""Qdrant access. Point ID == code_chunks.chunk_id; payload carries filter fields only (text stays in MySQL)."""
import threading

from qdrant_client import QdrantClient, models

from app.config import settings

_client = None
_lock = threading.Lock()


def get_client() -> QdrantClient:
    global _client
    with _lock:
        if _client is None:
            if not settings.qdrant_url:
                raise RuntimeError("QDRANT_URL is not configured")
            if settings.qdrant_url == ":memory:":
                _client = QdrantClient(location=":memory:")
            else:
                _client = QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key or None, timeout=60)
        return _client


def reset_client() -> None:
    global _client
    with _lock:
        _client = None


def ensure_collection() -> None:
    c = get_client()
    name = settings.qdrant_collection
    if not c.collection_exists(name):
        c.create_collection(
            name, vectors_config=models.VectorParams(size=settings.embedding_dim, distance=models.Distance.COSINE))
    for field in ("repo_id", "file_id"):
        c.create_payload_index(name, field, models.PayloadSchemaType.INTEGER)
    for field in ("language", "chunk_type"):
        c.create_payload_index(name, field, models.PayloadSchemaType.KEYWORD)


def upsert(points: list[tuple[int, list[float], dict]]) -> None:
    get_client().upsert(
        settings.qdrant_collection,
        points=[models.PointStruct(id=pid, vector=vec, payload=payload) for pid, vec, payload in points],
        wait=True,
    )


def _filter(repo_id=None, language=None):
    must = []
    if repo_id is not None:
        must.append(models.FieldCondition(key="repo_id", match=models.MatchValue(value=repo_id)))
    if language:
        must.append(models.FieldCondition(key="language", match=models.MatchValue(value=language)))
    return models.Filter(must=must) if must else None


def search(vector, limit=10, repo_id=None, language=None) -> list[tuple[int, float]]:
    res = get_client().query_points(
        settings.qdrant_collection, query=vector, limit=limit,
        query_filter=_filter(repo_id, language), with_payload=False)
    return [(int(p.id), float(p.score)) for p in res.points]


def delete_repo(repo_id: int) -> None:
    c = get_client()
    if c.collection_exists(settings.qdrant_collection):
        c.delete(settings.qdrant_collection, points_selector=models.FilterSelector(filter=_filter(repo_id)), wait=True)


def ping() -> bool:
    get_client().get_collections()
    return True
