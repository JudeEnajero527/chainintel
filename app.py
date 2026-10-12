"""
ChainIntel — entry point.

    streamlit run app.py        (or just: python3 app.py)

This file runs on every page load: theme, sign-in, navigation and the sidebar live here, and each
view in views/ only renders its own content.
"""
import os
import sys

import streamlit as st

# Started with plain `python app.py` (e.g. the editor's Run button)? Relaunch it as a Streamlit server.
if __name__ == "__main__" and not st.runtime.exists():
    from streamlit.web import cli as stcli
    sys.argv = ["streamlit", "run", os.path.abspath(__file__), *sys.argv[1:]]
    sys.exit(stcli.main())

import config
from auth import apply_cookie_action, get_current_user, logout, render_auth_wall
from styles import BASE_CSS, esc
from ui import get_engine

HERE = os.path.dirname(os.path.abspath(__file__))

st.set_page_config(page_title="ChainIntel", page_icon=os.path.join(HERE, "assets", "icon.svg"),
                   layout="wide", initial_sidebar_state="auto")
st.markdown(BASE_CSS, unsafe_allow_html=True)

if not render_auth_wall():
    st.stop()

st.logo(os.path.join(HERE, "assets", "logo.svg"), icon_image=os.path.join(HERE, "assets", "icon.svg"), size="large")


def view(file, title, icon, **kw):
    return st.Page(os.path.join("views", file), title=title, icon=f":material/{icon}:", **kw)


nav = st.navigation({
    "": [view("home.py", "Overview", "space_dashboard", default=True)],
    "Risk": [
        view("monitor.py", "Monitor", "monitor_heart", url_path="monitor"),
        view("intelligence.py", "Forecasts", "psychology", url_path="forecasts"),
        view("analytics.py", "Analytics", "insights", url_path="analytics"),
    ],
    "Markets": [
        view("markets.py", "Stablecoins", "public", url_path="markets"),
        view("defi.py", "DeFi protocols", "account_balance", url_path="defi"),
        view("yields.py", "Yields", "savings", url_path="yields"),
    ],
    "Signals": [
        view("whales.py", "Whale alerts", "waves", url_path="whales"),
        view("social.py", "Social", "forum", url_path="social"),
    ],
    "You": [
        view("portfolio.py", "Portfolio", "account_balance_wallet", url_path="portfolio"),
        view("settings.py", "Settings", "settings", url_path="settings"),
    ],
})
st.session_state["_page"] = nav.url_path or "home"

engine = get_engine()
user = get_current_user()
with st.sidebar:
    st.markdown(
        f'<div class="note" style="margin-top:14px;">Signed in as <strong style="color:var(--text);">{esc(user["username"])}</strong></div>',
        unsafe_allow_html=True,
    )
    if st.button("Sign out", icon=":material/logout:", key="sidebar_logout", use_container_width=True):
        logout()
        st.rerun()



def model_status():
    missing = [k for k, ok in config.status().items() if not ok and k in ("ETHERSCAN_API_KEY", "REDDIT_CLIENT_ID")]
    status_slot.markdown(
        f'<div class="note" style="margin-top:16px;">'
        f'<span class="live-dot"></span>Depeg model: {esc(engine.ml_status)}<br>'
        f'Sentiment model: {esc(engine.sentiment_status)}'
        + (f'<br>{len(missing)} optional data source(s) need a key — see Settings' if missing else "")
        + '</div>',
        unsafe_allow_html=True,
    )


status_slot = st.sidebar.empty()
model_status()
apply_cookie_action()
nav.run()
model_status()      # refresh once the page has run, so it reflects models the page just loaded
