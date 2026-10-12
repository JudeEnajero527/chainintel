"""
Push alerts (email, Discord, Telegram), sent by the background collector.

Each user's alert state is remembered per coin, so a coin that stays above its threshold produces one
"crossed" message and, later, one "recovered" message — not a message every five minutes.
"""
import logging
import re
from datetime import datetime, timezone

import requests

import auth
import config
import db
import mailer
from styles import fmt_price

log = logging.getLogger("chainintel.notify")

RECOVERY_MARGIN = 5          # must fall this far below the threshold to count as recovered
DISCORD_RE = re.compile(r"^https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[\w-]+$")


def init_db():
    with db.connect() as conn:
        conn.execute(auth.ALERT_STATE_DDL)

# ── Channels ────────────────────────────────────────────────────────────────────

def valid_discord_webhook(url: str) -> bool:
    return bool(DISCORD_RE.match(url.strip()))


def telegram_configured() -> bool:
    return bool(config.get("TELEGRAM_BOT_TOKEN"))


def send_discord(url: str, text: str) -> tuple[bool, str]:
    if not valid_discord_webhook(url):
        return False, "That isn't a Discord webhook URL."
    try:
        r = requests.post(url, json={"content": text[:1900], "username": "ChainIntel"}, timeout=10)
        return (r.status_code < 300), ("" if r.status_code < 300 else f"Discord returned {r.status_code}")
    except requests.RequestException as e:
        return False, str(e)


def send_telegram(chat_id: str, text: str) -> tuple[bool, str]:
    token = config.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return False, "Telegram isn't set up on this server (TELEGRAM_BOT_TOKEN)."
    try:
        r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                          json={"chat_id": chat_id.strip(), "text": text, "disable_web_page_preview": True}, timeout=10)
        body = r.json()
        return bool(body.get("ok")), body.get("description", "")
    except (requests.RequestException, ValueError) as e:
        return False, str(e)


def deliver(channels: dict, subject: str, text: str) -> dict:
    """Sends to every configured channel. Returns {channel: (ok, error)}."""
    results = {}
    if channels.get("email"):
        results["email"] = mailer.send(channels["email"], subject, text + f"\n\n{mailer.app_url()}")
    if channels.get("discord"):
        results["discord"] = send_discord(channels["discord"], f"**{subject}**\n{text}")
    if channels.get("telegram"):
        results["telegram"] = send_telegram(channels["telegram"], f"{subject}\n\n{text}")
    for ch, (ok, err) in results.items():
        if not ok:
            log.warning("Alert via %s failed: %s", ch, err)
    return results

# ── Alert logic ─────────────────────────────────────────────────────────────────

def _set_state(user_id, key, active):
    now = datetime.now(timezone.utc).isoformat()
    with db.connect() as conn:
        if conn.execute("SELECT 1 FROM alert_state WHERE user_id=? AND key=?", (user_id, key)).fetchone():
            conn.execute("UPDATE alert_state SET active=?, changed=? WHERE user_id=? AND key=?", (int(active), now, user_id, key))
        else:
            conn.execute("INSERT INTO alert_state (user_id, key, active, changed) VALUES (?,?,?,?)", (user_id, key, int(active), now))


def _states(user_id) -> dict:
    with db.connect() as conn:
        return {k: bool(a) for k, a in conn.execute("SELECT key, active FROM alert_state WHERE user_id=?", (user_id,)).fetchall()}


def events_for(thresholds: dict, states: dict, data: dict) -> list[tuple[str, bool, str, str]]:
    """
    Pure decision logic: (state_key, new_active, subject, message) for every change worth a notification.
    Two kinds of state per coin: composite risk vs. the user's threshold, and the coin trading off peg.
    """
    events = []
    for t, d in data.items():
        risk = d["risk"]["total"]
        threshold = thresholds.get(t, 50)
        key = f"risk:{t}"
        if risk is not None:
            if risk >= threshold and not states.get(key):
                events.append((key, True, f"⚠ {t} risk {risk:.0f} crossed your threshold of {threshold}",
                                f"{t} is at {fmt_price(d['price'])}. Composite risk {risk:.1f}/100 "
                                f"(peg {d['risk']['peg'] or 0:.0f}, liquidity {d['risk']['liquidity'] or 0:.0f}, "
                                f"sentiment {d['risk']['sentiment'] or 0:.0f})."))
            elif risk < threshold - RECOVERY_MARGIN and states.get(key):
                events.append((key, False, f"✅ {t} risk back to {risk:.0f}",
                                f"{t} composite risk fell to {risk:.1f}, below your threshold of {threshold}."))
        key = f"peg:{t}"
        off = d["ml"].get("label") == "Off peg now"
        if d["price"] is not None:
            if off and not states.get(key):
                events.append((key, True, f"🔴 {t} is off peg at {fmt_price(d['price'])}",
                                f"{t} is trading {abs(d['price'] - 1) * 100:.2f}% away from $1."))
            elif not off and states.get(key) and abs(d["price"] - 1) < 0.003:
                events.append((key, False, f"✅ {t} is back on peg",
                                f"{t} is trading at {fmt_price(d['price'])} again."))
    return events


def process_alerts(data: dict) -> int:
    """Checks every subscriber against the latest assessment and sends what changed. Returns messages sent."""
    init_db()
    sent = 0
    for sub in auth.alert_subscribers():
        for key, active, subject, message in events_for(sub["thresholds"], _states(sub["id"]), data):
            results = deliver(sub["channels"], subject, message)
            if any(ok for ok, _ in results.values()):
                _set_state(sub["id"], key, active)       # only remember it once someone was actually told
                sent += 1
    return sent
