"""Embedding + Qdrant + search, with the in-memory Qdrant and the fake embedder from conftest."""
import time

import pytest
from fastapi.testclient import TestClient
from git import Actor, Repo

from app.db import repository as r
from app.main import app
from app.services import importer, vector_store

URL = "https://github.com/acme/search-demo"

PY = '''import hashlib


def hash_password(password):
    """Hash a password with sha256."""
    return hashlib.sha256(password.encode()).hexdigest()


def read_csv_rows(path):
    """Read every row of a csv file."""
    with open(path) as fh:
        return [line.split(",") for line in fh]
'''
JS = "export function formatDate(d) {\n  return d.toISOString();\n}\n"


@pytest.fixture()
def client(monkeypatch):
    def fake_clone(git_url, repo_id):
        dest = importer.repo_dir(repo_id)
        dest.mkdir(parents=True, exist_ok=True)
        repo = Repo.init(dest, initial_branch="main")
        who = Actor("Dev", "dev@example.com")
        (dest / "auth.py").write_text(PY)
        (dest / "dates.js").write_text(JS)
        repo.index.add(["auth.py", "dates.js"])
        repo.index.commit("init", author=who, committer=who)
        return repo

    monkeypatch.setattr(importer, "clone_repo", fake_clone)
    vector_store.reset_client()
    r.execute("DELETE FROM repositories WHERE git_url = %s", (URL,))
    with TestClient(app) as c:
        yield c
    r.execute("DELETE FROM repositories WHERE git_url = %s", (URL,))
    vector_store.reset_client()


def _import(client):
    repo_id = client.post("/api/repositories", json={"git_url": URL}).json()["repo_id"]
    for _ in range(100):
        s = client.get(f"/api/repositories/{repo_id}/status").json()
        if s["status"] in ("ready", "failed"):
            assert s["status"] == "ready", s
            return repo_id
        time.sleep(0.1)
    raise AssertionError("import did not finish")


def test_import_embeds_every_chunk(client):
    repo_id = _import(client)
    assert r.count_chunks_to_embed(repo_id) == 0
    row = r.fetch_one(
        "SELECT COUNT(*) AS n, SUM(embedding_ref = chunk_id) AS ok FROM code_chunks c "
        "JOIN files f ON f.file_id = c.file_id WHERE f.repo_id = %s", (repo_id,))
    assert row["n"] > 0 and int(row["ok"]) == row["n"]
    assert vector_store.get_client().count(vector_store.settings.qdrant_collection).count == row["n"]


def test_search_ranks_relevant_chunk_first(client):
    repo_id = _import(client)
    res = client.post("/api/search", json={"query": "hash a password with sha256", "repo_id": repo_id}).json()
    assert res and res[0]["name"] == "hash_password" and res[0]["file_path"] == "auth.py"
    assert {"chunk_id", "chunk_type", "start_line", "end_line", "snippet", "score"} <= res[0].keys()
    assert res == sorted(res, key=lambda x: -x["score"])


def test_search_language_filter_and_limit(client):
    repo_id = _import(client)
    js = client.post("/api/search", json={"query": "date", "language": "javascript", "repo_id": repo_id}).json()
    assert js and all(x["language"] == "javascript" for x in js)
    assert len(client.post("/api/search", json={"query": "file", "limit": 1}).json()) == 1


def test_search_validation_and_unknown_repo(client):
    assert client.post("/api/search", json={"query": "   "}).status_code == 422
    assert client.post("/api/search", json={"query": "x", "limit": 0}).status_code == 422
    resp = client.post("/api/search", json={"query": "x", "repo_id": 999999})
    assert resp.status_code == 404 and resp.json()["error"]["code"] == "repo_not_found"


def test_delete_repository_removes_vectors(client):
    repo_id = _import(client)
    coll = vector_store.settings.qdrant_collection
    assert vector_store.get_client().count(coll).count > 0
    assert client.delete(f"/api/repositories/{repo_id}").status_code == 204
    assert vector_store.get_client().count(coll).count == 0


def test_health_reports_qdrant(client):
    assert client.get("/health").json()["qdrant"] == "ok"


def test_qdrant_url_typo_is_normalised():
    from app.config import Settings
    assert Settings(qdrant_url="https:https://x.cloud.qdrant.io/").qdrant_url == "https://x.cloud.qdrant.io"
