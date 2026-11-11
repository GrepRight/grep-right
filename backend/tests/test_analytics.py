"""Phase 5: views, stored procedures, triggers, validation and the analytics endpoint."""
import pytest
from fastapi.testclient import TestClient
from mysql.connector import errors

from app.db import repository as r
from app.main import app


def _audit(table, record_id):
    return [x["details"] for x in r.fetch_all(
        "SELECT details FROM audit_log WHERE table_name = %s AND record_id = %s ORDER BY log_id", (table, record_id))]


def test_repository_triggers_write_audit_log(repo):
    r.update_repository_status(repo, "indexing")
    r.update_repository_status(repo, "indexing")          # no change -> no new row
    r.update_repository_status(repo, "ready")
    log = _audit("repositories", repo)
    assert log[0].startswith("imported ")
    assert log[1:] == ["status pending -> indexing", "status indexing -> ready"]
    r.delete_repository(repo)
    assert _audit("repositories", repo)[-1].startswith("deleted ")


def test_user_role_change_is_audited(user):
    r.update_user_role(user, "admin")
    assert _audit("users", user) == ["role user -> admin"]


def test_future_commit_rejected_by_trigger(repo):
    with pytest.raises(errors.DatabaseError):
        r.execute("INSERT INTO commits (commit_hash, repo_id, committed_at) VALUES (%s, %s, NOW() + INTERVAL 30 DAY)",
                  ("a" * 40, repo))


def _seed(repo):
    f1 = r.create_file(repo, "a.py", "python", 100, 10)
    f2 = r.create_file(repo, "b.py", "python", 300, 30)
    f3 = r.create_file(repo, "c.js", "javascript", 50, 5)
    r.create_function(f2, "f", 1, 5)
    r.create_function(f2, "g", 6, 9)
    r.create_class(f1, "C", 1, 4)
    r.create_chunk(f2, "function", "def f(): pass", 1, 5)
    c1 = r.create_commit(repo, "1" * 40, additions=10, deletions=2, committed_at="2024-01-01 10:00:00")
    c2 = r.create_commit(repo, "2" * 40, additions=5, deletions=1, committed_at="2024-01-02 10:00:00")
    r.add_commit_file(c1, f2, "added", 10, 2)
    r.add_commit_file(c2, f2, "modified", 5, 1)
    r.add_commit_file(c2, f1, "modified", 1, 0)
    return f1, f2, f3


def test_analytics_endpoint(repo):
    f1, f2, f3 = _seed(repo)
    with TestClient(app) as c:
        data = c.get(f"/api/repositories/{repo}/analytics").json()
        assert c.get("/api/repositories/999999/analytics").status_code == 404
    o = data["overview"]
    assert (o["files"], o["functions"], o["classes"], o["chunks"], o["commits"]) == (3, 2, 1, 1, 2)
    assert (o["additions"], o["deletions"]) == (15, 3)
    langs = {x["language"]: x for x in data["languages"]}
    assert langs["python"]["file_count"] == 2 and langs["python"]["total_lines"] == 40
    assert sum(x["pct_lines"] for x in data["languages"]) == pytest.approx(100, abs=0.2)
    assert [x["file_path"] for x in data["largest_files"]] == ["b.py", "a.py", "c.js"]
    assert data["files_by_functions"][0]["file_path"] == "b.py"
    assert data["hot_files"][0]["file_path"] == "b.py" and data["hot_files"][0]["change_count"] == 2
    assert [x["running_total"] for x in data["commit_activity"]] == [1, 2]
    assert data["chunk_types"] == [{"chunk_type": "function", "n": 1}]


def test_root_home_page_lists_routes():
    with TestClient(app) as c:
        resp = c.get("/")
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/html")
    for route in ("/health", "/api/repositories", "/api/search", "/api/repositories/{repo_id}/analytics"):
        assert route in resp.text
