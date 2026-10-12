"""
Daily risk digest mailer for ChainIntel.

Usage:
    python3 send_digest.py            # send to every opted-in user
    python3 send_digest.py --dry-run  # build the email and write it to digest_preview.html instead of sending

Settings (environment variables, or put them in .env — see .env.example):
    CHAININTEL_EMAIL      Gmail address you send from
    CHAININTEL_APP_PASS   Gmail App Password (myaccount.google.com/apppasswords) — not your normal password
    CHAININTEL_URL        Public URL of the dashboard (default http://localhost:8501), used for links + unsubscribe
    ETHERSCAN_API_KEY     optional, enables gas data

Run once daily via cron (settings are read from .env, so the crontab line stays short):
    0 8 * * * cd /Users/jaysonenajero/chainintel2 && /usr/bin/python3 send_digest.py >> digest.log 2>&1
"""
import argparse
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr, make_msgid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
from auth import get_digest_recipients, init_user_db
from chainintel_core import RiskEngine
from styles import LEVEL_HEX, LEVEL_TEXT, esc, fmt_price

SENDER_EMAIL = config.get("CHAININTEL_EMAIL")
SENDER_PASS  = config.get("CHAININTEL_APP_PASS")
APP_URL      = config.get("CHAININTEL_URL", "http://localhost:8501").rstrip("/")
SMTP_HOST, SMTP_PORT = "smtp.gmail.com", 587


def build_snapshot():
    data = RiskEngine().assess_all()
    rows = []
    for t, d in data.items():
        rows.append({"ticker": t, "issuer": d["cfg"]["issuer"], "price": d["price"],
                     "risk": d["risk"]["total"], "level": d["level"], "ml": d["ml"]})
    alerts = [r for r in rows if r["level"] == "critical" or r["ml"]["level"] == "critical"]
    return rows, alerts


def build_html(rows, alerts, username, unsubscribe_url):
    date_str = datetime.now(timezone.utc).strftime("%B %d, %Y")
    alert_html = ""
    if alerts:
        items = "".join(
            f'<li style="margin-bottom:4px;"><strong>{r["ticker"]}</strong> — '
            f'{"risk score " + format(r["risk"], ".0f") if r["risk"] is not None else "risk n/a"}'
            f'{" · " + esc(r["ml"]["label"]) if r["ml"]["level"] == "critical" else ""}</li>'
            for r in alerts)
        alert_html = f"""
        <div style="background:#1f0808;border:1px solid #7f1d1d;border-radius:10px;padding:16px 20px;margin:20px 0;color:#fca5a5;">
          <div style="font-size:13px;font-weight:700;color:#ef4444;margin-bottom:8px;">⚠️ {len(alerts)} asset(s) need attention</div>
          <ul style="margin:0;padding-left:16px;font-size:13px;">{items}</ul>
        </div>"""

    td = 'style="padding:10px 12px;border-top:1px solid #1e2130;"'
    body_rows = ""
    for r in rows:
        color = LEVEL_HEX[r["level"]]
        risk = f'{r["risk"]:.0f}' if r["risk"] is not None else "—"
        ml = r["ml"]
        fc = f'{ml["probability"]:.1f}%' if ml["probability"] is not None else esc(ml["label"])
        body_rows += f"""
        <tr>
          <td {td}><strong style="color:#f9fafb;">{r['ticker']}</strong><br><span style="color:#64748b;font-size:11px;">{esc(r['issuer'])}</span></td>
          <td {td}><span style="color:#f9fafb;">{fmt_price(r['price'])}</span></td>
          <td {td}><span style="color:{color};font-weight:700;">{risk}</span> <span style="color:{color};font-size:11px;">{LEVEL_TEXT[r['level']]}</span></td>
          <td {td}><span style="color:{LEVEL_HEX[ml['level']]};">{fc}</span></td>
        </tr>"""

    th = 'style="padding:10px 12px;text-align:left;font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.06em;"'
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width"></head>
<body style="margin:0;padding:0;background:#080a10;font-family:'Helvetica Neue',Arial,sans-serif;color:#f9fafb;">
<div style="max-width:580px;margin:0 auto;padding:32px 20px;">
  <div style="text-align:center;margin-bottom:28px;">
    <div style="font-size:28px;font-weight:900;letter-spacing:-1px;">⬡ Chain<span style="color:#3b82f6;">Intel</span></div>
    <div style="font-size:13px;color:#64748b;margin-top:4px;">Daily Risk Digest · {date_str}</div>
  </div>
  <div style="background:#0f121c;border:1px solid #1e2130;border-radius:14px;padding:22px 26px;font-size:15px;color:#d1d5db;line-height:1.6;">
    Hi <strong style="color:#f9fafb;">{esc(username)}</strong>, here's today's stablecoin risk snapshot.
  </div>
  {alert_html}
  <div style="background:#0f121c;border:1px solid #1e2130;border-radius:14px;overflow:hidden;margin:20px 0;">
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
      <thead><tr style="background:#0b0d15;"><th {th}>Asset</th><th {th}>Price</th><th {th}>Risk</th><th {th}>7-day depeg</th></tr></thead>
      <tbody>{body_rows}</tbody>
    </table>
  </div>
  <div style="font-size:12px;color:#64748b;line-height:1.6;margin-bottom:24px;">
    Risk (0–100) combines peg deviation, on-chain liquidity and news sentiment.
    "7-day depeg" is the model's probability of the coin trading ≥1% off peg within a week.
  </div>
  <div style="text-align:center;margin-bottom:28px;">
    <a href="{esc(APP_URL)}" style="display:inline-block;background:#3b82f6;color:#fff;font-weight:700;font-size:14px;
       border-radius:10px;padding:12px 28px;text-decoration:none;">Open the dashboard →</a>
  </div>
  <div style="text-align:center;font-size:11px;color:#64748b;line-height:1.7;">
    You're receiving this because you opted in to ChainIntel daily digests.<br>
    <a href="{esc(unsubscribe_url)}" style="color:#94a3b8;">Unsubscribe</a> · Not financial advice
  </div>
</div></body></html>"""


def build_text(rows, alerts, username, unsubscribe_url):
    lines = [f"ChainIntel daily risk digest — {datetime.now(timezone.utc):%B %d, %Y}", "", f"Hi {username},", ""]
    if alerts:
        lines += [f"! {len(alerts)} asset(s) need attention: " + ", ".join(r["ticker"] for r in alerts), ""]
    for r in rows:
        risk = f'{r["risk"]:.0f}' if r["risk"] is not None else "n/a"
        ml = f'{r["ml"]["probability"]:.1f}%' if r["ml"]["probability"] is not None else r["ml"]["label"]
        lines.append(f"{r['ticker']:7s} {fmt_price(r['price']):>9s}  risk {risk:>3s} ({LEVEL_TEXT[r['level']]})  7d depeg {ml}")
    lines += ["", f"Dashboard: {APP_URL}", f"Unsubscribe: {unsubscribe_url}"]
    return "\n".join(lines)


def make_message(to_email, username, token, rows, alerts):
    unsubscribe_url = f"{APP_URL}/?unsubscribe={token}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"ChainIntel daily digest — {datetime.now(timezone.utc):%b %d}" + (f" · ⚠️ {len(alerts)} alert(s)" if alerts else "")
    msg["From"] = formataddr(("ChainIntel", SENDER_EMAIL))
    msg["To"] = to_email
    msg["Message-ID"] = make_msgid(domain="chainintel.local")
    msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
    msg.attach(MIMEText(build_text(rows, alerts, username, unsubscribe_url), "plain", "utf-8"))
    msg.attach(MIMEText(build_html(rows, alerts, username, unsubscribe_url), "html", "utf-8"))
    return msg


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="write digest_preview.html instead of sending")
    args = ap.parse_args()

    init_user_db()
    print("Fetching live risk data…")
    rows, alerts = build_snapshot()

    if args.dry_run:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "digest_preview.html")
        with open(path, "w") as fh:
            fh.write(build_html(rows, alerts, "preview", f"{APP_URL}/?unsubscribe=preview"))
        print(f"Wrote {path}")
        return

    if not SENDER_EMAIL or not SENDER_PASS:
        sys.exit("ERROR: set CHAININTEL_EMAIL and CHAININTEL_APP_PASS in .env (see .env.example).")
    users = get_digest_recipients()
    if not users:
        print("No opted-in users.")
        return

    sent = 0
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_PASS)
        for u in users:
            try:
                msg = make_message(u["email"], u["username"], u["unsubscribe_token"], rows, alerts)
                server.sendmail(SENDER_EMAIL, [u["email"]], msg.as_string())
                print(f"  ✓ {u['email']}")
                sent += 1
            except smtplib.SMTPException as e:
                print(f"  ✗ {u['email']}: {e}")
    print(f"\nDone. {sent}/{len(users)} emails delivered.")


if __name__ == "__main__":
    main()
