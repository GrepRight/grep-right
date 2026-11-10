import mysql.connector
import pytest

from app.db import repository as r


def test_user_crud(user):
    row = r.get_user(user)
    assert row["role"] == "user" and row["last_login"] is None
    r.update_user_last_login(user)
    assert r.get_user(user)["last_login"] is not None
    r.update_user_role(user, "admin")
    assert r.get_user_by_username(row["username"])["role"] == "admin"


def test_user_delete():
    uid = r.create_user("deleteme", "deleteme@example.com", "h")
    assert r.delete_user(uid) == 1
    assert r.get_user(uid) is None


def test_user_unique_and_checks(user):
    row = r.get_user(user)
    with pytest.raises(mysql.connector.IntegrityError):
        r.create_user(row["username"], "other@example.com", "h")
    with pytest.raises(mysql.connector.IntegrityError):
        r.create_user("other_name", row["email"], "h")
    with pytest.raises(mysql.connector.Error):
        r.create_user("ab", "short@example.com", "h")          # username CHECK
    with pytest.raises(mysql.connector.Error):
        r.create_user("bademail", "not-an-email", "h")         # email CHECK
    with pytest.raises(mysql.connector.Error):
        r.create_user("badrole", "badrole@example.com", "h", role="root")  # ENUM


def test_repository_crud_and_constraints(user, repo):
    row = r.get_repository(repo)
    assert row["status"] == "pending" and row["owner_id"] == user
    r.update_repository_status(repo, "failed", "clone error")
    assert r.get_repository(repo)["error_message"] == "clone error"
    r.mark_repository_synced(repo, primary_language="Python")
    assert r.get_repository(repo)["primary_language"] == "Python"
    with pytest.raises(mysql.connector.IntegrityError):         # unique git_url
        r.create_repository(user, "dup", row["git_url"])
    with pytest.raises(mysql.connector.Error):                  # git_url CHECK
        r.create_repository(user, "bad", "http://evil.example/x/y")
    with pytest.raises(mysql.connector.IntegrityError):         # FK owner
        r.create_repository(999999, "orphan", "https://github.com/a/orphan")
    with pytest.raises(mysql.connector.Error):                  # status ENUM
        r.update_repository_status(repo, "bogus")


def test_owner_delete_restricted(user, repo):
    with pytest.raises(mysql.connector.IntegrityError):
        r.delete_user(user)


def test_members(user, repo):
    r.add_member(user, repo, "owner")
    with pytest.raises(mysql.connector.IntegrityError):         # composite PK
        r.add_member(user, repo, "viewer")
    r.update_member_role(user, repo, "maintainer")
    assert r.list_members(repo)[0]["role"] == "maintainer"
    assert r.remove_member(user, repo) == 1


def test_branches_commits_files(user, repo):
    b = r.create_branch(repo, "main", "a" * 40, True)
    with pytest.raises(mysql.connector.IntegrityError):         # unique (repo, name)
        r.create_branch(repo, "main")
    c = r.create_commit(repo, "b" * 40, branch_id=b, author_id=user, message="init", additions=3)
    with pytest.raises(mysql.connector.IntegrityError):         # unique (repo, hash)
        r.create_commit(repo, "b" * 40)
    f = r.create_file(repo, "src/app.py", "Python", 100, 10)
    with pytest.raises(mysql.connector.IntegrityError):         # unique (repo, path)
        r.create_file(repo, "src/app.py")
    r.add_commit_file(c, f, "added", 3, 0)
    with pytest.raises(mysql.connector.IntegrityError):         # composite PK
        r.add_commit_file(c, f, "modified")
    assert r.list_commit_files(c)[0]["file_path"] == "src/app.py"
    r.update_file(f, "Python", 120, 12)
    assert r.get_file(f)["line_count"] == 12
    r.delete_branch(b)                                          # commits.branch_id -> SET NULL
    assert r.get_commit(c)["branch_id"] is None


def test_symbols_and_chunks(repo):
    f = r.create_file(repo, "m.py", "Python")
    fn = r.create_function(f, "foo", 1, 5, "def foo()", "doc")
    cl = r.create_class(f, "Bar", 6, 20)
    ch = r.create_chunk(f, "function", "def foo(): pass", 1, 5)
    assert r.list_functions(f)[0]["name"] == "foo"
    assert r.list_classes(f)[0]["name"] == "Bar"
    assert r.get_chunk(ch)["embedding_ref"] is None
    assert any(c["chunk_id"] == ch for c in r.list_unembedded_chunks())
    r.set_chunk_embedding_ref(ch, ch)
    assert r.get_chunk(ch)["embedding_ref"] == ch
    r.update_function_docstring(fn, "new")
    r.update_class_docstring(cl, "cdoc")
    with pytest.raises(mysql.connector.Error):                  # CHECK end >= start
        r.create_function(f, "bad", 10, 5)
    with pytest.raises(mysql.connector.Error):
        r.create_chunk(f, "function", "x", 10, 5)
    with pytest.raises(mysql.connector.Error):                  # chunk_type ENUM
        r.create_chunk(f, "banana", "x", 1, 2)
    with pytest.raises(mysql.connector.IntegrityError):         # FK file
        r.create_function(999999, "x", 1, 2)
    assert r.delete_function(fn) == 1 and r.delete_class(cl) == 1 and r.delete_chunk(ch) == 1


def test_cascade_delete_repository(user):
    rid = r.create_repository(user, "casc", "https://github.com/acme/casc")
    f = r.create_file(rid, "a.py")
    r.create_function(f, "foo", 1, 2)
    r.create_chunk(f, "module", "x", 1, 2)
    c = r.create_commit(rid, "c" * 40)
    r.add_commit_file(c, f, "added")
    r.delete_repository(rid)
    for table in ("files", "functions", "code_chunks", "commits", "commit_files"):
        assert r.fetch_one(f"SELECT COUNT(*) AS n FROM {table} WHERE 1=1 AND " + {
            "files": "repo_id = %s", "functions": "file_id = %s", "code_chunks": "file_id = %s",
            "commits": "repo_id = %s", "commit_files": "file_id = %s"}[table],
            (rid if table in ("files", "commits") else f,))["n"] == 0


def test_transaction_rollback(user):
    from app.db.connection import get_connection
    with pytest.raises(RuntimeError):
        with get_connection() as conn:
            conn.cursor().execute(
                "INSERT INTO audit_log (table_name, action) VALUES ('t', 'INSERT')")
            raise RuntimeError
    assert r.fetch_one("SELECT COUNT(*) AS n FROM audit_log WHERE table_name = 't'")["n"] == 0


def test_fulltext_index_exists():
    row = r.fetch_one(
        "SELECT COUNT(*) AS n FROM information_schema.statistics "
        "WHERE table_schema = DATABASE() AND table_name = 'code_chunks' AND index_type = 'FULLTEXT'")
    assert row["n"] == 1
