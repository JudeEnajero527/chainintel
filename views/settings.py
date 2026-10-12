import streamlit as st

import config
from alerts import render_alert_settings
from auth import change_password, get_current_user, logout, set_digest_opt_in
from styles import esc, section
from ui import get_engine, header

engine = get_engine()
user = get_current_user()
header("Settings", f"Account, alerts and data sources for {esc(user['username'])}")

# ── Alerts ─────────────────────────────────────────────────────────────────────
st.markdown(section("Risk alerts"), unsafe_allow_html=True)
with st.container(border=True):
    st.caption("A banner appears at the top of the Overview, Monitor and Portfolio pages when a coin's composite "
               "risk score reaches your threshold. Saved to your account.")
    render_alert_settings()

# ── Email ──────────────────────────────────────────────────────────────────────
st.markdown(section("Email"), unsafe_allow_html=True)
with st.container(border=True):
    digest = st.toggle(f"Send the daily risk digest to {user['email']}", value=user.get("digest_opt_in", True))
    if digest != user.get("digest_opt_in", True):
        set_digest_opt_in(user["id"], digest)
        user["digest_opt_in"] = digest
        st.toast("Digest " + ("on" if digest else "off"))
    if not (config.get("CHAININTEL_EMAIL") and config.get("CHAININTEL_APP_PASS")):
        st.caption("Note: the server hasn't been configured to send email yet (CHAININTEL_EMAIL / CHAININTEL_APP_PASS).")

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
    ("Prices, liquidity, news, DeFi, yields", None, "CoinGecko · DefiLlama · DexScreener · Google News — no key needed"),
    ("Whale alerts + gas", "ETHERSCAN_API_KEY", "Free key at etherscan.io/apis"),
    ("Reddit (official API)", "REDDIT_CLIENT_ID", "Without it, Reddit's rate-limited public feed is used. Create a 'script' app at reddit.com/prefs/apps"),
    ("Daily digest email", "CHAININTEL_APP_PASS", "Gmail address + App Password (myaccount.google.com/apppasswords)"),
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

# ── Model ──────────────────────────────────────────────────────────────────────
meta = engine.model_meta
st.markdown(section("Depeg model"), unsafe_allow_html=True)
st.markdown(
    f'<div class="note">{esc(engine.ml_status)}'
    + (f' · trained {esc(meta.get("trained_at", "?"))} on data through {esc(meta.get("data_end", "?"))}. ' if meta else ". ")
    + 'Retrain with <code>python3 train_model.py</code> (about a minute) to pick up the latest market history.</div>',
    unsafe_allow_html=True,
)
