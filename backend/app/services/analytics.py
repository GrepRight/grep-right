"""SQL analytics for a repository: views, stored procedures and window functions (see database/*.sql)."""
from app.db.connection import get_connection, fetch_all, fetch_one


def _call(name: str, args: tuple) -> list[dict]:
    """Call a stored procedure and return its first result set as dicts."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.callproc(name, args)
        rows: list[dict] = []
        for res in cur.stored_results():
            cols = res.column_names
            rows = [dict(zip(cols, row)) for row in res.fetchall()]
            break
        cur.close()
        return rows


def get_analytics(repo_id: int) -> dict:
    overview = _call("sp_repo_overview", (repo_id,))[0]
    languages = fetch_all(
        "SELECT language, file_count, total_lines, "
        "ROUND(100 * total_lines / NULLIF(SUM(total_lines) OVER (), 0), 1) AS pct_lines "
        "FROM v_repo_language_stats WHERE repo_id = %s ORDER BY total_lines DESC",
        (repo_id,),
    )
    largest = _call("sp_largest_files", (repo_id, 10))
    top_functions = fetch_all(
        "SELECT file_id, file_path, function_count, class_count FROM v_file_summary "
        "WHERE repo_id = %s AND function_count > 0 ORDER BY function_count DESC, file_id LIMIT 10",
        (repo_id,),
    )
    hot = fetch_all(
        "SELECT file_id, file_path, change_count, total_additions, total_deletions FROM v_hot_files "
        "WHERE repo_id = %s ORDER BY change_count DESC, file_id LIMIT 10",
        (repo_id,),
    )
    activity = fetch_all(
        "SELECT commit_date, commit_count, SUM(commit_count) OVER (ORDER BY commit_date) AS running_total "
        "FROM v_commit_activity WHERE repo_id = %s ORDER BY commit_date",
        (repo_id,),
    )
    chunk_types = fetch_all(
        "SELECT ch.chunk_type, COUNT(*) AS n FROM code_chunks ch JOIN files f ON f.file_id = ch.file_id "
        "WHERE f.repo_id = %s GROUP BY ch.chunk_type",
        (repo_id,),
    )
    return _jsonable({
        "overview": overview,
        "languages": languages,
        "largest_files": largest,
        "files_by_functions": top_functions,
        "hot_files": hot,
        "commit_activity": activity,
        "chunk_types": chunk_types,
    })


def _jsonable(obj):
    from datetime import date, datetime
    from decimal import Decimal
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, Decimal):
        return float(obj) if obj % 1 else int(obj)
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    return obj


def recent_audit(limit: int = 20) -> list[dict]:
    return _jsonable(fetch_all("SELECT * FROM audit_log ORDER BY log_id DESC LIMIT %s", (limit,)))
