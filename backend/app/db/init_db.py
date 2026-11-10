"""Create the database (if missing) and apply database/schema.sql.

Usage (from repo root):  python -m app.db.init_db   (with PYTHONPATH=backend or --app-dir)
"""
import re
import sys

from app.config import ROOT_DIR, settings
from app.db.connection import get_server_connection

SCHEMA_FILE = ROOT_DIR / "database" / "schema.sql"


def split_statements(sql: str) -> list[str]:
    sql = re.sub(r"--[^\n]*", "", sql)  # strip line comments (none contain ';' or quotes)
    return [s.strip() for s in sql.split(";") if s.strip()]


def init_db() -> int:
    db = settings.mysql_database
    if not re.fullmatch(r"[A-Za-z0-9_]+", db):
        raise ValueError("MYSQL_DATABASE must be alphanumeric/underscore")
    conn = get_server_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        cur.execute(f"USE `{db}`")
        stmts = split_statements(SCHEMA_FILE.read_text(encoding="utf-8"))
        for stmt in stmts:
            cur.execute(stmt)
        conn.commit()
        return len(stmts)
    finally:
        conn.close()


if __name__ == "__main__":
    n = init_db()
    print(f"Applied {n} statements to database '{settings.mysql_database}'.")
    sys.exit(0)
