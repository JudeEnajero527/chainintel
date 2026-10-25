"""
Live forward test status — the numbers Section 9 of the paper needs.

Run:  python3 research/live_status.py
Reads the forecast log (forecast_log table) and prints: forecasts saved and scored, by model version,
depegs that occurred, alerts issued (forecast >= 20%), and the Brier score on scored forecasts.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import db                     # noqa: E402
import depeg_model as dm      # noqa: E402

ALERT = 0.20      # as a fraction; the log stores probabilities in percent (0–100)


def main():
    with db.connect() as conn:
        cols = db.columns(conn, "forecast_log")
        version = "model_version" if "model_version" in cols else "NULL"
        raw = conn.execute(f"SELECT date, ticker, probability, outcome, {version} FROM forecast_log ORDER BY date").fetchall()
    rows = [(d, t, None if p is None else p / 100, o, v) for d, t, p, o, v in raw]
    if not rows:
        print("No forecasts logged yet.")
        return
    today = datetime.now(timezone.utc).date()
    dates = sorted({r[0] for r in rows})
    first, last = dates[0], dates[-1]
    span = (datetime.strptime(last, "%Y-%m-%d").date() - datetime.strptime(first, "%Y-%m-%d").date()).days + 1
    scored = [r for r in rows if r[3] is not None]
    due = [r for r in rows if r[3] is None and
           datetime.strptime(r[0], "%Y-%m-%d").date() <= today - timedelta(days=dm.HORIZON_DAYS + 1)]

    print(f"Forecast log as of {today}  ({db.describe()})")
    print(f"  Saved forecasts:   {len(rows)}  ({len({r[1] for r in rows})} coins, {first} to {last})")
    print(f"  Days with a save:  {len(dates)} of {span} calendar days in that range"
          + ("" if len(dates) == span else "  ← gaps: the collector was not running every day"))
    print(f"  Scored:            {len(scored)}")
    print(f"  Window closed, not yet scored: {len(due)}" + ("  ← run the collector to score these" if due else ""))
    if last < str(today - timedelta(days=1)):
        print(f"  WARNING: nothing saved since {last}. Is the collector running?")

    if scored:
        depegs = sum(r[3] for r in scored)
        alerts = [r for r in scored if r[2] is not None and r[2] >= ALERT]
        hits = sum(r[3] for r in alerts)
        brier = sum((r[2] - r[3]) ** 2 for r in scored if r[2] is not None) / len(scored)
        caught = sum(1 for r in scored if r[3] == 1 and r[2] is not None and r[2] >= ALERT)
        print(f"  Depegs (>= {dm.DEPEG_THRESHOLD:.0%} within {dm.HORIZON_DAYS} days): {depegs} of {len(scored)} scored")
        print(f"  Alerts (forecast >= {ALERT:.0%}): {len(alerts)}, of which followed by a depeg: {hits}")
        print(f"  Depegs preceded by an alert: {caught} of {depegs}")
        print(f"  Brier score: {brier:.4f}  (lower is better)")

    print("  By model version:")
    by = {}
    for r in rows:
        k = r[4] or "not recorded (logged before versioning)"
        s = by.setdefault(k, [0, 0])
        s[0] += 1
        s[1] += r[3] is not None
    for k, (n, sc) in by.items():
        print(f"    {k}: {n} saved, {sc} scored")


if __name__ == "__main__":
    main()
