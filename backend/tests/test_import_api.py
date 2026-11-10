"""End-to-end import through the HTTP API with the network clone replaced by a local git repo."""
import time

import pytest
from fastapi.testclient import TestClient
from git import Actor, Repo

from app.db import repository as r
from app.main import app
from app.services import importer

URL = "https://github.com/acme/demo-project"


@pytest.fixture()
def client(monkeypatch):
    def fake_clone(git_url, repo_id):
        dest = importer.repo_dir(repo_id)
        dest.mkdir(parents=True, exist_ok=True)
        repo = Repo.init(dest, initial_branch="main")
        who = Actor("Dev", "dev@example.com")
        (dest / "app.py").write_text('def hello():\n    """Say hi."""\n    return "hi"\n')
        (dest / "README.md").write_text("# demo\n")
        repo.index.add(["app.py", "README.md"])
        repo.index.commit("first", author=who, committer=who)
        (dest / "app.py").write_text('def hello():\n    """Say hi."""\n    return "hi"\n\n\nclass A:\n    def m(self):\n        pass\n')
        (dest / "util.js").write_text("export const f = (x) => x;\n")
        repo.index.add(["app.py", "util.js"])
        repo.index.commit("second", author=who, committer=who)
        return repo

    monkeypatch.setattr(importer, "clone_repo", fake_clone)
    r.execute("DELETE FROM repositories WHERE git_url = %s", (URL,))
    with TestClient(app) as c:
        yield c
    r.execute("DELETE FROM repositories WHERE git_url = %s", (URL,))


def _wait_ready(client, repo_id):
    for _ in range(100):
        s = client.get(f"/api/repositories/{repo_id}/status").json()
        if s["status"] in ("ready", "failed"):
            return s
        time.sleep(0.1)
    raise AssertionError("import did not finish")


def test_health(client):
    assert client.get("/health").json()["mysql"] == "ok"


def test_full_import_flow(client):
    resp = client.post("/api/repositories", json={"git_url": URL})
    assert resp.status_code == 202
    repo_id = resp.json()["repo_id"]
    status = _wait_ready(client, repo_id)
    assert status["status"] == "ready", status

    repo = client.get(f"/api/repositories/{repo_id}").json()
    assert repo["primary_language"] == "python" and repo["default_branch"] == "main"
    counts = repo["counts"]
    assert counts["files"] == 3 and counts["commits"] == 2 and counts["branches"] == 1
    assert counts["functions"] == 3 and counts["classes"] == 1 and counts["chunks"] >= 3

    files = client.get(f"/api/repositories/{repo_id}/files").json()
    assert [f["file_path"] for f in files] == ["app.py", "README.md", "util.js"]   # case-insensitive collation
    assert client.get(f"/api/repositories/{repo_id}/files", params={"path": "nope"}).json() == []

    app_py = next(f for f in files if f["file_path"] == "app.py")
    detail = client.get(f"/api/files/{app_py['file_id']}").json()
    assert {f["name"] for f in detail["functions"]} == {"hello", "A.m"}
    assert detail["classes"][0]["name"] == "A"
    assert detail["chunks"]

    # commit_files recorded for the second commit (files still in the tree)
    rows = r.fetch_all(
        "SELECT cf.change_type FROM commit_files cf JOIN commits c ON c.commit_id = cf.commit_id "
        "WHERE c.repo_id = %s AND c.message = 'second'", (repo_id,))
    assert sorted(x["change_type"] for x in rows) == ["added", "modified"]

    assert not importer.repo_dir(repo_id).exists()           # workspace cleaned up

    assert client.post("/api/repositories", json={"git_url": URL}).status_code == 409

    assert client.delete(f"/api/repositories/{repo_id}").status_code == 204
    assert client.get(f"/api/repositories/{repo_id}").status_code == 404
    assert r.get_file_map(repo_id) == {}                      # cascade removed children


def test_invalid_url_and_errors(client):
    bad = client.post("/api/repositories", json={"git_url": "file:///etc/passwd"})
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid_url"
    assert client.post("/api/repositories", json={}).json()["error"]["code"] == "validation_error"
    assert client.get("/api/repositories/999999").json()["error"]["code"] == "repo_not_found"
    assert client.get("/api/files/999999").status_code == 404


def test_failed_import_can_be_retried(client, monkeypatch):
    from app.errors import ImportFailure
    real = importer.clone_repo
    monkeypatch.setattr(importer, "clone_repo", lambda *a: (_ for _ in ()).throw(ImportFailure("boom")))
    repo_id = client.post("/api/repositories", json={"git_url": URL}).json()["repo_id"]
    s = _wait_ready(client, repo_id)
    assert s["status"] == "failed" and s["error"] == "boom"

    monkeypatch.setattr(importer, "clone_repo", real)
    again = client.post("/api/repositories", json={"git_url": URL})
    assert again.status_code == 202 and again.json()["repo_id"] == repo_id


def test_path_filter_escapes_wildcards(client):
    repo_id = client.post("/api/repositories", json={"git_url": URL}).json()["repo_id"]
    _wait_ready(client, repo_id)
    # '%' and '_' must be treated literally, not as LIKE wildcards
    assert client.get(f"/api/repositories/{repo_id}/files", params={"path": "%"}).json() == []
    assert client.get(f"/api/repositories/{repo_id}/files", params={"path": "_"}).json() == []
