"""
Background collector — keeps ChainIntel's data fresh whether or not anyone has the app open.

Each pass:
  1. assesses every coin (price, liquidity, sentiment, forecast) and saves a snapshot the app reuses,
     so pages load instantly and risk history is recorded around the clock
  2. logs today's 7-day forecasts and scores the ones whose week has passed (Forecasts → track record)
  3. sends push alerts (email / Discord / Telegram) to users whose thresholds were crossed
  4. emails the daily digest once a day, at --digest-hour local time (default 8)
  5. retrains the depeg model when it's older than --retrain-days (default 30; use 0 to keep the
     model frozen, e.g. during a live forward test), and reloads it if train_model.py was run by hand

Usage:
    python3 collector.py                # one pass (for cron, launchd, or GitHub Actions)
    python3 collector.py --loop 300     # keep running, one pass every 5 minutes
"""
import argparse
import fcntl
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import auth          # noqa: E402
import db            # noqa: E402
import mailer        # noqa: E402
import notify        # noqa: E402
import send_digest   # noqa: E402
from chainintel_core import META_PATH, RiskEngine   # noqa: E402

log = logging.getLogger("chainintel.collector")


def model_age_days() -> float | None:
    try:
        with open(META_PATH) as fh:
            trained = datetime.strptime(json.load(fh)["trained_at"], "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - trained).total_seconds() / 86400
    except (OSError, KeyError, ValueError):
        return None


def retrain_if_stale(max_age_days: float) -> bool:
    age = model_age_days()
    if age is not None and age < max_age_days:
        return False
    log.info("Model is %s days old — retraining", "unknown" if age is None else f"{age:.0f}")
    result = subprocess.run([sys.executable, os.path.join(HERE, "train_model.py")], cwd=HERE,
                            capture_output=True, text=True, timeout=3600)
    if result.returncode != 0:
        log.error("Retraining failed:\n%s", result.stderr[-2000:])
        return False
    log.info("Retrained:\n%s", "\n".join(result.stdout.strip().splitlines()[-25:]))
    return True


def _state(key: str, value: str | None = None) -> str | None:
    """Tiny key/value store for the collector (e.g. the date the last digest went out)."""
    with db.connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS collector_state (key TEXT PRIMARY KEY, value TEXT)")
        if value is None:
            row = conn.execute("SELECT value FROM collector_state WHERE key = ?", (key,)).fetchone()
            return row[0] if row else None
        conn.execute("DELETE FROM collector_state WHERE key = ?", (key,))
        conn.execute("INSERT INTO collector_state (key, value) VALUES (?, ?)", (key, value))
        return value


def maybe_send_digest(data: dict, hour: int) -> str:
    now = datetime.now()                      # local time: "8am" means 8am where the collector runs
    today = now.strftime("%Y-%m-%d")
    if hour < 0 or now.hour < hour or _state("last_digest") == today:
        return "not due"
    if not mailer.is_configured():
        return "skipped (email not configured)"
    rows, alerts = send_digest.build_snapshot(data)
    sent, total = send_digest.send_all(rows, alerts)
    _state("last_digest", today)
    return f"sent to {sent}/{total}"


def run_once(engine: RiskEngine, retrain_days: float, digest_hour: int = 8) -> RiskEngine:
    started = time.time()
    data = engine.assess_all(fresh=True)
    scored = sum(1 for d in data.values() if d["risk"]["total"] is not None)
    logged = engine.log_forecasts(data)
    resolved = engine.resolve_forecasts()
    sent = notify.process_alerts(data)
    digest = maybe_send_digest(data, digest_hour)
    summary = ", ".join(f"{t} {d['risk']['total']:.0f}" for t, d in data.items() if d["risk"]["total"] is not None)
    log.info("Pass done in %.1fs · %d/%d coins scored · %d forecasts logged · %d resolved · %d alerts sent · digest %s · %s",
             time.time() - started, scored, len(data), logged, resolved, sent, digest, summary)
    if retrain_days and retrain_if_stale(retrain_days):
        engine = RiskEngine()        # pick up the new model
    elif _meta_trained_at() != engine.model_meta.get("trained_at"):
        log.info("Model file changed on disk (retrained elsewhere) — reloading")
        engine = RiskEngine()
    return engine


def _meta_trained_at() -> str | None:
    try:
        with open(META_PATH) as fh:
            return json.load(fh).get("trained_at")
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--loop", type=int, metavar="SECONDS", help="keep running, one pass every SECONDS")
    ap.add_argument("--retrain-days", type=float, default=30, help="retrain when the model is older than this (0 = never)")
    ap.add_argument("--digest-hour", type=int, default=8, help="local hour to send the daily digest (-1 = never)")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("transformers").setLevel(logging.ERROR)

    # Only one collector at a time (cron can overlap a slow pass).
    lock = open(os.path.join(HERE, ".collector.lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.info("Another collector is already running — exiting")
        return

    auth.init_user_db()
    notify.init_db()
    engine = RiskEngine()
    while True:
        try:
            engine = run_once(engine, args.retrain_days, args.digest_hour)
        except Exception:                       # keep the loop alive; the next pass may succeed
            log.exception("Collector pass failed")
            if not args.loop:
                sys.exit(1)
        if not args.loop:
            break
        # The engine caches API calls for a few minutes; clear the per-pass ones so each pass is fresh.
        RiskEngine.assess_all.cache_clear()
        RiskEngine.get_all_prices.cache_clear()
        time.sleep(args.loop)


if __name__ == "__main__":
    main()
