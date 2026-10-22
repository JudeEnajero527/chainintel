from datetime import datetime, timezone

import streamlit as st

import config
import db
import mailer
import notify
from alerts import render_alert_settings
from auth import (change_password, delete_account, get_current_user, get_user, load_notify_prefs, logout,
                  save_notify_prefs, send_verification_email, set_digest_opt_in)
from styles import esc, section
from ui import get_engine, header

engine = get_engine()
user = get_current_user()
user.update({k: v for k, v in (get_user(user["id"]) or {}).items() if k in ("email_verified", "digest_opt_in")})
header("Settings", f"Account, alerts and data sources for {esc(user['username'])}")

# ── Alerts ─────────────────────────────────────────────────────────────────────
st.markdown(section("Risk alerts"), unsafe_allow_html=True)
with st.container(border=True):
    st.caption(f"A banner appears at the top of the Overview, Monitor{' and Portfolio' if config.show_signals() else ''} pages when a coin's composite "
               "risk score reaches your threshold. Saved to your account.")
    render_alert_settings()

# ── Email + push notifications ─────────────────────────────────────────────────
st.markdown(section("Notifications"), unsafe_allow_html=True)
if not user.get("email_verified"):
    with st.container(border=True):
        st.markdown(f"**Confirm your email address** — digests and email alerts only go to confirmed addresses "
                    f"({esc(user['email'])}).")
        if st.button("Send confirmation link", icon=":material/mark_email_read:"):
            ok, err = send_verification_email(user)
            (st.success if ok else st.error)("Sent — check your inbox." if ok else err)

prefs = load_notify_prefs(user["id"])
with st.container(border=True):
    digest = st.toggle(f"Daily risk digest to {user['email']}", value=user.get("digest_opt_in", True))
    if digest != user.get("digest_opt_in", True):
        set_digest_opt_in(user["id"], digest)
        user["digest_opt_in"] = digest
        st.toast("Digest " + ("on" if digest else "off"))
    st.caption("Push alerts fire when a coin crosses your threshold above, when it recovers, and whenever a coin breaks "
               "its peg. They're sent by the background collector, so they arrive even when the app is closed.")
    with st.form("notify_form"):
        email_on = st.checkbox("Email alerts", value=prefs.get("email", False))
        discord = st.text_input("Discord webhook URL", value=prefs.get("discord_webhook", ""),
                                placeholder="https://discord.com/api/webhooks/…",
                                help="Discord channel → Edit channel → Integrations → Webhooks → New webhook → Copy URL")
        telegram = st.text_input("Telegram chat ID", value=prefs.get("telegram_chat_id", ""), placeholder="e.g. 123456789",
                                 help="Start a chat with this server's ChainIntel bot, then message @userinfobot to get your chat ID.",
                                 disabled=not notify.telegram_configured())
        saved = st.form_submit_button("Save notification settings")
    if saved:
        if discord and not notify.valid_discord_webhook(discord):
            st.error("That doesn't look like a Discord webhook URL.")
        else:
            prefs = {"email": email_on, "discord_webhook": discord.strip(), "telegram_chat_id": telegram.strip()}
            save_notify_prefs(user["id"], prefs)
            st.success("Saved.")
    channels = {"email": user["email"] if prefs.get("email") and user.get("email_verified") else "",
                "discord": prefs.get("discord_webhook", ""), "telegram": prefs.get("telegram_chat_id", "")}
    if any(channels.values()) and st.button("Send a test alert", icon=":material/notifications_active:"):
        results = notify.deliver(channels, "ChainIntel test alert", "If you can read this, alerts will reach you here.")
        for ch, (ok, err) in results.items():
            (st.success if ok else st.error)(f"{ch.title()}: {'delivered' if ok else err}")
    notes = []
    if prefs.get("email") and not user.get("email_verified"):
        notes.append("email alerts start once your address is confirmed")
    if not mailer.is_configured():
        notes.append("the server can't send email yet (CHAININTEL_EMAIL / CHAININTEL_APP_PASS)")
    if not notify.telegram_configured():
        notes.append("Telegram needs TELEGRAM_BOT_TOKEN on the server")
    if notes:
        st.caption("Note: " + "; ".join(notes) + ".")

# ── Security ───────────────────────────────────────────────────────────────────
st.markdown(section("Security"), unsafe_allow_html=True)
left, right = st.columns([1.4, 1])
with left, st.container(border=True):
    with st.form("change_password", clear_on_submit=True):
        current = st.text_input("Current password", type="password")
        new = st.text_input("New password", type="password")
        confirm = st.text_input("Confirm new password", type="password")
        if st.form_submit_button("Change password"):
            if new != confirm:
                st.error("The new passwords don't match.")
            else:
                ok, msg = change_password(user["id"], current, new, keep_token=st.session_state.get("_session_token"))
                (st.success if ok else st.error)(msg)
with right, st.container(border=True):
    st.markdown("**Remembered devices**")
    st.caption("If you signed in on a shared computer, sign out everywhere. You'll need to sign in again on every device.")
    if st.button("Sign out of all devices", icon=":material/devices:", use_container_width=True):
        logout(everywhere=True)
        st.rerun()

# ── Data sources ───────────────────────────────────────────────────────────────
st.markdown(section("Data sources"), unsafe_allow_html=True)
st.caption("Optional keys unlock more data. Add them to a `.env` file in the project folder (copy `.env.example`), "
           "then restart the app. Keys are never shown here.")
status = config.status()
SOURCES = [
    ("Prices, liquidity, news, DeFi" + (", yields" if config.show_signals() else ""), None,
     "CoinGecko · DefiLlama · DexScreener · Google News — no key needed"),
    ("Whale alerts + gas" if config.show_signals() else "Ethereum gas prices", "ETHERSCAN_API_KEY", "Free key at etherscan.io/apis"),
    *([("Reddit (official API)", "REDDIT_CLIENT_ID",
        "Without it, Reddit's rate-limited public feed is used. Create a 'script' app at reddit.com/prefs/apps")]
      if config.show_signals() else []),
    ("Email (digest, alerts, password reset)", "CHAININTEL_APP_PASS", "Gmail address + App Password (myaccount.google.com/apppasswords)"),
    ("Telegram alerts", "TELEGRAM_BOT_TOKEN", "Create a bot with @BotFather and paste its token"),
    ("Public contact address", "CHAININTEL_CONTACT_EMAIL", "Shown in the Terms of Use and Privacy Policy — set this before hosting publicly"),
]
for name, key, how in SOURCES:
    ok = True if key is None else status[key] and (key != "REDDIT_CLIENT_ID" or status["REDDIT_CLIENT_SECRET"])
    badge = '<span class="pill-stable">● Connected</span>' if ok else '<span class="pill-unknown">○ Not set up</span>'
    st.markdown(f"""
    <div class="data-row" style="gap:16px;flex-wrap:wrap;">
      <div style="flex:1;min-width:220px;">
        <div style="font-weight:600;color:var(--text);">{esc(name)}</div>
        <div class="note">{esc(how)}{f' · <code>{key}</code>' if key and not ok else ''}</div>
      </div>
      {badge}
    </div>""", unsafe_allow_html=True)

# ── Background collector ───────────────────────────────────────────────────────
snap = engine.load_snapshot(max_age_seconds=10 ** 9)
st.markdown(section("Background collector"), unsafe_allow_html=True)
with st.container(border=True):
    newest = None
    if snap:
        newest = max(d.get("assessed_at", "") for d in snap.values())
    if newest:
        age = (datetime.now(timezone.utc) - datetime.fromisoformat(newest)).total_seconds() / 60
        state = "running" if age < 10 else "not running"
        st.markdown(f"Last assessment **{age:.0f} min ago** — collector looks **{state}**. Database: {esc(db.describe())}.")
    else:
        st.markdown("No assessments recorded yet.")
    st.caption("Start it with `python3 collector.py --loop 300`, or install it to run in the background on this Mac with "
               "`bash deploy/install_collector_macos.sh`.")

# ── Model ──────────────────────────────────────────────────────────────────────
meta = engine.model_meta
st.markdown(section("Depeg model"), unsafe_allow_html=True)
st.markdown(
    f'<div class="note">{esc(engine.ml_status)}'
    + (f' · trained {esc(meta.get("trained_at", "?"))} on data through {esc(meta.get("data_end", "?"))}. ' if meta else ". ")
    + 'Retrain with <code>python3 train_model.py</code> (about a minute) to pick up the latest market history.</div>',
    unsafe_allow_html=True,
)

# ── Delete account ─────────────────────────────────────────────────────────────
st.markdown(section("Delete account"), unsafe_allow_html=True)
with st.container(border=True):
    st.markdown("Permanently deletes your account, settings, portfolio, alert history and remembered devices. "
                "**This can't be undone.**")
    with st.form("delete_account", clear_on_submit=True):
        pw = st.text_input("Your password", type="password")
        confirm = st.text_input('Type DELETE to confirm')
        go = st.form_submit_button("Delete my account", type="primary")
    if go:
        if confirm.strip() != "DELETE":
            st.error('Type DELETE (in capitals) to confirm.')
        else:
            ok, msg = delete_account(user["id"], pw)
            if ok:
                logout()
                st.session_state["_flash"] = msg
                st.rerun()
            st.error(msg)
