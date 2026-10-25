"""
One-off: copy the live forecast log and risk history from the local SQLite file to the hosted Postgres
database, so the forward test continues unbroken after moving to hosting. User accounts are NOT copied.

Run once, from the project folder, after creating the Postgres database:
    DATABASE_URL="postgresql://…?sslmode=require" python3 research/migrate_to_postgres.py
Safe to re-run: rows that already exist are skipped.
"""
import os
import sqlite3
import sys

import psycopg

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQLITE = os.path.join(ROOT, "chainintel.db")
URL = os.environ.get("DATABASE_URL", "")
if not URL.startswith(("postgres://", "postgresql://")):
    sys.exit("Set DATABASE_URL to the Postgres connection string first.")

src = sqlite3.connect(SQLITE)
with psycopg.connect(URL, connect_timeout=15) as dst:
    dst.execute("""CREATE TABLE IF NOT EXISTS forecast_log (
                       date TEXT NOT NULL, ticker TEXT NOT NULL, probability REAL, price REAL,
                       level TEXT, outcome INTEGER, max_dev REAL, resolved_at TEXT, model_version TEXT,
                       PRIMARY KEY (date, ticker))""")
    dst.execute("ALTER TABLE forecast_log ADD COLUMN IF NOT EXISTS model_version TEXT")
    dst.execute("""CREATE TABLE IF NOT EXISTS risk_history (
                       timestamp TEXT, ticker TEXT, price REAL, liquidity REAL,
                       sentiment_score REAL, total_risk REAL)""")
    dst.execute("CREATE INDEX IF NOT EXISTS idx_risk_ticker_ts ON risk_history (ticker, timestamp)")

    cols = [r[1] for r in src.execute("PRAGMA table_info(forecast_log)")]
    want = ["date", "ticker", "probability", "price", "level", "outcome", "max_dev", "resolved_at", "model_version"]
    sel = ", ".join(c if c in cols else "NULL" for c in want)
    rows = src.execute(f"SELECT {sel} FROM forecast_log").fetchall()
    n_f = 0
    for r in rows:
        cur = dst.execute(f"INSERT INTO forecast_log ({', '.join(want)}) VALUES ({', '.join(['%s'] * len(want))}) "
                          "ON CONFLICT (date, ticker) DO NOTHING", r)
        n_f += cur.rowcount
    have = dst.execute("SELECT COUNT(*) FROM risk_history").fetchone()[0]
    n_r = 0
    if have == 0:                                   # history has no key, so only copy into an empty table
        hist = src.execute("SELECT timestamp, ticker, price, liquidity, sentiment_score, total_risk FROM risk_history").fetchall()
        with dst.cursor() as c:
            c.executemany("INSERT INTO risk_history VALUES (%s,%s,%s,%s,%s,%s)", hist)
        n_r = len(hist)
print(f"Copied {n_f} forecast-log rows (of {len(rows)}) and {n_r} risk-history rows to Postgres.")
