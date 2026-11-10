"""Raw parameterized SQL CRUD for every table. No string-built values anywhere."""
from app.db.connection import execute, fetch_all, fetch_one, get_connection

# ---------- users ----------

def create_user(username, email, password_hash, role="user") -> int:
    return execute(
        "INSERT INTO users (username, email, password_hash, role) VALUES (%s, %s, %s, %s)",
        (username, email, password_hash, role),
    )


def get_user(user_id):
    return fetch_one("SELECT * FROM users WHERE user_id = %s", (user_id,))


def get_user_by_username(username):
    return fetch_one("SELECT * FROM users WHERE username = %s", (username,))


def update_user_last_login(user_id) -> int:
    return execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = %s", (user_id,))


def update_user_role(user_id, role) -> int:
    return execute("UPDATE users SET role = %s WHERE user_id = %s", (role, user_id))


def delete_user(user_id) -> int:
    return execute("DELETE FROM users WHERE user_id = %s", (user_id,))


# ---------- repositories ----------

def create_repository(owner_id, name, git_url, description=None, default_branch=None, primary_language=None) -> int:
    return execute(
        "INSERT INTO repositories (owner_id, name, description, git_url, default_branch, primary_language) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (owner_id, name, description, git_url, default_branch, primary_language),
    )


def get_repository(repo_id):
    return fetch_one("SELECT * FROM repositories WHERE repo_id = %s", (repo_id,))


def list_repositories():
    return fetch_all(
        "SELECT repo_id, name, primary_language, status, last_synced_at FROM repositories ORDER BY created_at DESC"
    )


def update_repository_status(repo_id, status, error_message=None) -> int:
    return execute(
        "UPDATE repositories SET status = %s, error_message = %s WHERE repo_id = %s",
        (status, error_message, repo_id),
    )


def mark_repository_synced(repo_id, primary_language=None, default_branch=None) -> int:
    return execute(
        "UPDATE repositories SET last_synced_at = CURRENT_TIMESTAMP, primary_language = COALESCE(%s, primary_language), "
        "default_branch = COALESCE(%s, default_branch) WHERE repo_id = %s",
        (primary_language, default_branch, repo_id),
    )


def delete_repository(repo_id) -> int:
    return execute("DELETE FROM repositories WHERE repo_id = %s", (repo_id,))


# ---------- repository_members ----------

def add_member(user_id, repo_id, role="viewer") -> int:
    return execute(
        "INSERT INTO repository_members (user_id, repo_id, role) VALUES (%s, %s, %s)",
        (user_id, repo_id, role),
    )


def list_members(repo_id):
    return fetch_all(
        "SELECT m.user_id, u.username, m.role, m.joined_at FROM repository_members m "
        "JOIN users u ON u.user_id = m.user_id WHERE m.repo_id = %s",
        (repo_id,),
    )


def update_member_role(user_id, repo_id, role) -> int:
    return execute(
        "UPDATE repository_members SET role = %s WHERE user_id = %s AND repo_id = %s",
        (role, user_id, repo_id),
    )


def remove_member(user_id, repo_id) -> int:
    return execute("DELETE FROM repository_members WHERE user_id = %s AND repo_id = %s", (user_id, repo_id))


# ---------- branches ----------

def create_branch(repo_id, name, head_commit_hash=None, is_default=False) -> int:
    return execute(
        "INSERT INTO branches (repo_id, name, head_commit_hash, is_default) VALUES (%s, %s, %s, %s)",
        (repo_id, name, head_commit_hash, is_default),
    )


def list_branches(repo_id):
    return fetch_all("SELECT * FROM branches WHERE repo_id = %s ORDER BY name", (repo_id,))


def update_branch_head(branch_id, head_commit_hash) -> int:
    return execute("UPDATE branches SET head_commit_hash = %s WHERE branch_id = %s", (head_commit_hash, branch_id))


def delete_branch(branch_id) -> int:
    return execute("DELETE FROM branches WHERE branch_id = %s", (branch_id,))


# ---------- commits ----------

def create_commit(repo_id, commit_hash, branch_id=None, author_id=None, message=None,
                  committed_at=None, additions=0, deletions=0) -> int:
    return execute(
        "INSERT INTO commits (commit_hash, repo_id, branch_id, author_id, message, committed_at, additions, deletions) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
        (commit_hash, repo_id, branch_id, author_id, message, committed_at, additions, deletions),
    )


def get_commit(commit_id):
    return fetch_one("SELECT * FROM commits WHERE commit_id = %s", (commit_id,))


def list_commits(repo_id, limit=50):
    return fetch_all(
        "SELECT * FROM commits WHERE repo_id = %s ORDER BY committed_at DESC LIMIT %s", (repo_id, int(limit))
    )


def delete_commit(commit_id) -> int:
    return execute("DELETE FROM commits WHERE commit_id = %s", (commit_id,))


# ---------- files ----------

def create_file(repo_id, file_path, language=None, size_bytes=0, line_count=0, last_modified=None) -> int:
    return execute(
        "INSERT INTO files (repo_id, file_path, language, size_bytes, line_count, last_modified) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (repo_id, file_path, language, size_bytes, line_count, last_modified),
    )


def get_file(file_id):
    return fetch_one("SELECT * FROM files WHERE file_id = %s", (file_id,))


def list_files(repo_id):
    return fetch_all(
        "SELECT file_id, file_path, language, line_count FROM files WHERE repo_id = %s ORDER BY file_path", (repo_id,)
    )


def update_file(file_id, language, size_bytes, line_count) -> int:
    return execute(
        "UPDATE files SET language = %s, size_bytes = %s, line_count = %s WHERE file_id = %s",
        (language, size_bytes, line_count, file_id),
    )


def delete_file(file_id) -> int:
    return execute("DELETE FROM files WHERE file_id = %s", (file_id,))


# ---------- commit_files ----------

def add_commit_file(commit_id, file_id, change_type, additions=0, deletions=0) -> int:
    return execute(
        "INSERT INTO commit_files (commit_id, file_id, change_type, additions, deletions) VALUES (%s, %s, %s, %s, %s)",
        (commit_id, file_id, change_type, additions, deletions),
    )


def list_commit_files(commit_id):
    return fetch_all(
        "SELECT cf.*, f.file_path FROM commit_files cf JOIN files f ON f.file_id = cf.file_id WHERE cf.commit_id = %s",
        (commit_id,),
    )


def remove_commit_file(commit_id, file_id) -> int:
    return execute("DELETE FROM commit_files WHERE commit_id = %s AND file_id = %s", (commit_id, file_id))


# ---------- functions ----------

def create_function(file_id, name, start_line, end_line, signature=None, docstring=None) -> int:
    return execute(
        "INSERT INTO functions (file_id, name, signature, start_line, end_line, docstring) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (file_id, name, signature, start_line, end_line, docstring),
    )


def list_functions(file_id):
    return fetch_all("SELECT * FROM functions WHERE file_id = %s ORDER BY start_line", (file_id,))


def update_function_docstring(func_id, docstring) -> int:
    return execute("UPDATE functions SET docstring = %s WHERE func_id = %s", (docstring, func_id))


def delete_function(func_id) -> int:
    return execute("DELETE FROM functions WHERE func_id = %s", (func_id,))


# ---------- classes ----------

def create_class(file_id, name, start_line, end_line, docstring=None) -> int:
    return execute(
        "INSERT INTO classes (file_id, name, start_line, end_line, docstring) VALUES (%s, %s, %s, %s, %s)",
        (file_id, name, start_line, end_line, docstring),
    )


def list_classes(file_id):
    return fetch_all("SELECT * FROM classes WHERE file_id = %s ORDER BY start_line", (file_id,))


def update_class_docstring(class_id, docstring) -> int:
    return execute("UPDATE classes SET docstring = %s WHERE class_id = %s", (docstring, class_id))


def delete_class(class_id) -> int:
    return execute("DELETE FROM classes WHERE class_id = %s", (class_id,))


# ---------- code_chunks ----------

def create_chunk(file_id, chunk_type, content, start_line, end_line) -> int:
    return execute(
        "INSERT INTO code_chunks (file_id, chunk_type, content, start_line, end_line) VALUES (%s, %s, %s, %s, %s)",
        (file_id, chunk_type, content, start_line, end_line),
    )


def get_chunk(chunk_id):
    return fetch_one("SELECT * FROM code_chunks WHERE chunk_id = %s", (chunk_id,))


def list_chunks(file_id):
    return fetch_all("SELECT * FROM code_chunks WHERE file_id = %s ORDER BY start_line", (file_id,))


def list_unembedded_chunks(limit=500):
    return fetch_all("SELECT * FROM code_chunks WHERE embedding_ref IS NULL LIMIT %s", (int(limit),))


def set_chunk_embedding_ref(chunk_id, embedding_ref) -> int:
    return execute("UPDATE code_chunks SET embedding_ref = %s WHERE chunk_id = %s", (embedding_ref, chunk_id))


def delete_chunk(chunk_id) -> int:
    return execute("DELETE FROM code_chunks WHERE chunk_id = %s", (chunk_id,))


# ---------- Phase 2: import / indexing helpers ----------

SYSTEM_USERNAME = "system"


def get_or_create_system_user() -> int:
    """Placeholder owner for imported repos until authentication exists (non-loginable hash)."""
    row = get_user_by_username(SYSTEM_USERNAME)
    if row:
        return row["user_id"]
    return create_user(SYSTEM_USERNAME, "system@grepright.local", "!", role="admin")


def get_repository_by_url(git_url):
    return fetch_one("SELECT * FROM repositories WHERE git_url = %s", (git_url,))


def clear_repository_data(repo_id) -> None:
    """Remove everything derived from a clone (files + children cascade) so a failed import can be retried."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM commits WHERE repo_id = %s", (repo_id,))
        cur.execute("DELETE FROM files WHERE repo_id = %s", (repo_id,))
        cur.execute("DELETE FROM branches WHERE repo_id = %s", (repo_id,))
        cur.close()


def get_repository_counts(repo_id) -> dict:
    return fetch_one(
        "SELECT "
        "(SELECT COUNT(*) FROM files WHERE repo_id = %(r)s) AS files, "
        "(SELECT COUNT(*) FROM functions fn JOIN files f ON f.file_id = fn.file_id WHERE f.repo_id = %(r)s) AS `functions`, "
        "(SELECT COUNT(*) FROM classes c JOIN files f ON f.file_id = c.file_id WHERE f.repo_id = %(r)s) AS `classes`, "
        "(SELECT COUNT(*) FROM code_chunks ch JOIN files f ON f.file_id = ch.file_id WHERE f.repo_id = %(r)s) AS chunks, "
        "(SELECT COUNT(*) FROM commits WHERE repo_id = %(r)s) AS commits, "
        "(SELECT COUNT(*) FROM branches WHERE repo_id = %(r)s) AS branches",
        {"r": repo_id},
    )


def _like_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_files_under(repo_id, path_prefix=""):
    """Files whose path starts with `path_prefix` (wildcards escaped; MySQL's default LIKE escape is backslash)."""
    prefix = path_prefix.strip("/")
    if not prefix:
        return list_files(repo_id)
    return fetch_all(
        "SELECT file_id, file_path, language, line_count FROM files "
        "WHERE repo_id = %s AND file_path LIKE %s ORDER BY file_path",
        (repo_id, _like_escape(prefix) + "/%"),
    )


def insert_file_bundle(repo_id, sf, line_count, symbols, chunks) -> int:
    """Insert one file with its functions, classes and chunks in a single transaction. Returns file_id."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO files (repo_id, file_path, language, size_bytes, line_count, last_modified) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (repo_id, sf.rel_path, sf.language, sf.size_bytes, line_count, sf.last_modified),
        )
        file_id = cur.lastrowid
        funcs = [(file_id, s.name[:255], s.signature, s.start_line, s.end_line, s.docstring)
                 for s in symbols if s.kind == "function"]
        classes = [(file_id, s.name[:255], s.start_line, s.end_line, s.docstring)
                   for s in symbols if s.kind == "class"]
        if funcs:
            cur.executemany(
                "INSERT INTO functions (file_id, name, signature, start_line, end_line, docstring) "
                "VALUES (%s, %s, %s, %s, %s, %s)", funcs)
        if classes:
            cur.executemany(
                "INSERT INTO classes (file_id, name, start_line, end_line, docstring) "
                "VALUES (%s, %s, %s, %s, %s)", classes)
        if chunks:
            cur.executemany(
                "INSERT INTO code_chunks (file_id, chunk_type, content, start_line, end_line) "
                "VALUES (%s, %s, %s, %s, %s)",
                [(file_id, c.chunk_type, c.content, c.start_line, c.end_line) for c in chunks])
        cur.close()
        return file_id


def get_file_map(repo_id) -> dict:
    return {r["file_path"]: r["file_id"] for r in fetch_all(
        "SELECT file_id, file_path FROM files WHERE repo_id = %s", (repo_id,))}


def get_file_detail(file_id):
    f = fetch_one(
        "SELECT f.*, r.name AS repo_name FROM files f JOIN repositories r ON r.repo_id = f.repo_id WHERE f.file_id = %s",
        (file_id,))
    if not f:
        return None
    f["functions"] = list_functions(file_id)
    f["classes"] = list_classes(file_id)
    f["chunks"] = [{k: c[k] for k in ("chunk_id", "chunk_type", "start_line", "end_line", "content")}
                   for c in list_chunks(file_id)]
    return f


def fail_interrupted_repositories() -> int:
    """On startup: imports that were mid-flight when the server stopped can never finish."""
    return execute(
        "UPDATE repositories SET status = 'failed', error_message = 'Import interrupted by server restart' "
        "WHERE status IN ('pending','cloning','indexing')"
    )


# ---------- Phase 3: embedding / search helpers ----------

_CHUNK_SELECT = (
    "SELECT c.chunk_id, c.chunk_type, c.content, c.start_line, c.end_line, c.file_id, "
    "f.repo_id, f.file_path, f.language, "
    "COALESCE(fn.name, cl.name) AS name, fn.signature, COALESCE(fn.docstring, cl.docstring) AS docstring "
    "FROM code_chunks c JOIN files f ON f.file_id = c.file_id "
    "LEFT JOIN functions fn ON fn.file_id = c.file_id AND fn.start_line = c.start_line AND c.chunk_type = 'function' "
    "LEFT JOIN classes cl ON cl.file_id = c.file_id AND cl.start_line = c.start_line AND c.chunk_type = 'class' "
)


def list_chunks_to_embed(repo_id, after_chunk_id=0, limit=500):
    """Chunks of a repo without an embedding yet, keyset-paginated by chunk_id."""
    return fetch_all(
        _CHUNK_SELECT + "WHERE f.repo_id = %s AND c.embedding_ref IS NULL AND c.chunk_id > %s "
        "ORDER BY c.chunk_id LIMIT %s",
        (repo_id, after_chunk_id, int(limit)),
    )


def count_chunks_to_embed(repo_id) -> int:
    return fetch_one(
        "SELECT COUNT(*) AS n FROM code_chunks c JOIN files f ON f.file_id = c.file_id "
        "WHERE f.repo_id = %s AND c.embedding_ref IS NULL", (repo_id,))["n"]


def set_embedding_refs(chunk_ids) -> None:
    """Point ID in Qdrant == chunk_id, so embedding_ref = chunk_id."""
    ids = [(cid, cid) for cid in chunk_ids]
    if not ids:
        return
    with get_connection() as conn:
        cur = conn.cursor()
        cur.executemany("UPDATE code_chunks SET embedding_ref = %s WHERE chunk_id = %s", ids)
        cur.close()


def get_chunks_with_context(chunk_ids):
    """Chunk + file + repo rows for search results, keyed by chunk_id."""
    ids = [int(i) for i in chunk_ids]
    if not ids:
        return {}
    marks = ", ".join(["%s"] * len(ids))
    rows = fetch_all(
        _CHUNK_SELECT.replace("f.repo_id,", "f.repo_id, rp.name AS repo_name,")
        + "JOIN repositories rp ON rp.repo_id = f.repo_id "
        f"WHERE c.chunk_id IN ({marks})", tuple(ids))
    return {row["chunk_id"]: row for row in rows}
