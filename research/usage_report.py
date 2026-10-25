"""
Usage report for the petition record: daily visits, page views and feedback.

Run:  python3 research/usage_report.py
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import db   # noqa: E402


def main():
    with db.connect() as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()} \
            if not db.IS_POSTGRES else {"page_views", "usage_feedback"}
        if "page_views" not in tables:
            print("No visits recorded yet (the app creates the table on its first page view).")
            return
        days = conn.execute("SELECT day, COUNT(DISTINCT visitor), COUNT(*) FROM page_views GROUP BY day ORDER BY day").fetchall()
        pages = conn.execute("SELECT page, COUNT(*) FROM page_views GROUP BY page ORDER BY COUNT(*) DESC").fetchall()
        total = conn.execute("SELECT COUNT(DISTINCT visitor), COUNT(*), MIN(day), MAX(day) FROM page_views").fetchone()
        fb = conn.execute("SELECT created, role, use_case, contact FROM usage_feedback ORDER BY created").fetchall() \
            if "usage_feedback" in tables else []
    print(f"Visits (browser sessions): {total[0]} · page views: {total[1]} · {total[2]} to {total[3]}")
    print("\nBy day (sessions, page views):")
    for d, v, n in days:
        print(f"  {d}  {v:4d}  {n:5d}")
    print("\nBy page:")
    for p, n in pages:
        print(f"  {p:12s} {n}")
    print(f"\nFeedback responses: {len(fb)}")
    for created, role, use, contact in fb:
        print(f"  [{created}] {role or 'role not given'}: {use}" + (f"  (contact: {contact})" if contact else ""))
    print("\nNote: your own visits are included. Count them out before quoting numbers.")


if __name__ == "__main__":
    main()
