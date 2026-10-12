"""
Database access for SQLite (local default) and Postgres (hosting).

    DATABASE_URL=postgresql://user:pass@host/db   → Postgres (e.g. Neon, Supabase)
    unset                                          → SQLite file (CHAININTEL_DB or chainintel.db)

Write SQL with `?` placeholders and portable types (TEXT, REAL, INTEGER); `connect()` translates
placeholders for Postgres. Use AUTO_ID for auto-increment primary keys and `columns()` instead of
SQLite's PRAGMA.
"""
import os
import sqlite3
from contextlib import contextmanager

import config

HERE = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = config.get("DATABASE_URL")
IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))
SQLITE_PATH = config.get("CHAININTEL_DB") or os.path.join(HERE, "chainintel.db")

AUTO_ID = "SERIAL PRIMARY KEY" if IS_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"

if IS_POSTGRES:
    import psycopg
    IntegrityError = (sqlite3.IntegrityError, psycopg.IntegrityError)
else:
    IntegrityError = (sqlite3.IntegrityError,)


class _Conn:
    def __init__(self, raw):
        self.raw = raw

    def execute(self, sql: str, params=()):
        cur = self.raw.cursor()
        cur.execute(sql.replace("?", "%s") if IS_POSTGRES else sql, tuple(params))
        return cur


@contextmanager
def connect():
    """Yields a connection; commits on success, rolls back on error, always closes."""
    if IS_POSTGRES:
        raw = psycopg.connect(DATABASE_URL, connect_timeout=10)
    else:
        raw = sqlite3.connect(SQLITE_PATH, timeout=15)
    try:
        yield _Conn(raw)
        raw.commit()
    except BaseException:
        raw.rollback()
        raise
    finally:
        raw.close()


def columns(conn: _Conn, table: str) -> set[str]:
    if IS_POSTGRES:
        rows = conn.execute("SELECT column_name FROM information_schema.columns WHERE table_name = ?", (table,)).fetchall()
        return {r[0] for r in rows}
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def describe() -> str:
    """Human-readable location, without credentials."""
    if IS_POSTGRES:
        return "Postgres @ " + DATABASE_URL.split("@")[-1].split("?")[0]
    return f"SQLite ({os.path.basename(SQLITE_PATH)})"
