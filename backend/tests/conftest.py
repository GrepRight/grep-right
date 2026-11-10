import os
import sys
from pathlib import Path

# Tests run against a throwaway database, never the real one.
os.environ["MYSQL_DATABASE"] = "grepright_test"
os.environ["QDRANT_URL"] = ":memory:"        # in-process Qdrant, never the cloud cluster
os.environ["QDRANT_COLLECTION"] = "test_chunks"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app.db.connection import get_server_connection  # noqa: E402
from app.db.init_db import init_db  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def test_database():
    conn = get_server_connection()
    conn.cursor().execute("DROP DATABASE IF EXISTS grepright_test")
    conn.close()
    init_db()
    yield
    conn = get_server_connection()
    conn.cursor().execute("DROP DATABASE IF EXISTS grepright_test")
    conn.close()


@pytest.fixture()
def user():
    from app.db import repository as r
    import uuid
    name = "u" + uuid.uuid4().hex[:10]
    uid = r.create_user(name, f"{name}@example.com", "hash")
    yield uid
    r.execute("DELETE FROM repositories WHERE owner_id = %s", (uid,))
    r.delete_user(uid)


@pytest.fixture()
def repo(user):
    from app.db import repository as r
    import uuid
    slug = uuid.uuid4().hex[:10]
    return r.create_repository(user, slug, f"https://github.com/acme/{slug}")


@pytest.fixture(autouse=True)
def fake_embedder(monkeypatch):
    """Deterministic bag-of-words hash vectors: fast, offline, and similar texts score higher."""
    import hashlib
    import math
    import re

    from app.config import settings
    from app.services import embedder

    def vec(text):
        v = [0.0] * settings.embedding_dim
        for tok in re.findall(r"[a-z0-9]+", text.lower()):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % settings.embedding_dim] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / n for x in v]

    monkeypatch.setattr(embedder, "embed_documents", lambda texts: [vec(t) for t in texts])
    monkeypatch.setattr(embedder, "embed_query", lambda q: vec(q))
