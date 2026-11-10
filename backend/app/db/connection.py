from contextlib import contextmanager

import mysql.connector
from mysql.connector import pooling

from app.config import settings

_pool: pooling.MySQLConnectionPool | None = None


def _conn_args(with_database: bool = True) -> dict:
    args = {
        "host": settings.mysql_host,
        "port": settings.mysql_port,
        "user": settings.mysql_user,
        "password": settings.mysql_password,
        "charset": "utf8mb4",
        "autocommit": False,
    }
    if with_database:
        args["database"] = settings.mysql_database
    return args


def get_server_connection():
    """Connection without a selected database (used to CREATE DATABASE)."""
    return mysql.connector.connect(**_conn_args(with_database=False))


def _get_pool() -> pooling.MySQLConnectionPool:
    global _pool
    if _pool is None:
        _pool = pooling.MySQLConnectionPool(pool_name="grepright", pool_size=5, **_conn_args())
    return _pool


@contextmanager
def get_connection():
    """Pooled connection; commits on success, rolls back on error."""
    conn = _get_pool().get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def execute(sql: str, params: tuple | dict = ()) -> int:
    """Run a write statement; returns lastrowid (or rowcount if no autoincrement id)."""
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        result = cur.lastrowid or cur.rowcount
        cur.close()
        return result


def fetch_all(sql: str, params: tuple | dict = ()) -> list[dict]:
    with get_connection() as conn:
        cur = conn.cursor(dictionary=True)
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows


def fetch_one(sql: str, params: tuple | dict = ()) -> dict | None:
    rows = fetch_all(sql, params)
    return rows[0] if rows else None
