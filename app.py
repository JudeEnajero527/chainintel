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


SECTIONS = {
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
}
# Reachable pages that don't belong in the menu — linked from the sidebar footer instead.
TERMS = view("terms.py", "Terms of Use", "gavel", url_path="terms")
PRIVACY = view("privacy.py", "Privacy Policy", "shield", url_path="privacy")

# Streamlit's built-in menu can't hide individual pages, so it's turned off and drawn below.
nav = st.navigation([p for pages in SECTIONS.values() for p in pages] + [TERMS, PRIVACY], position="hidden")
st.session_state["_page"] = nav.url_path or "home"

engine = get_engine()
user = get_current_user()
with st.sidebar:
    with st.container(key="main_nav"):
        for section, pages in SECTIONS.items():
            if section:
                st.markdown(f'<div class="nav-section">{section}</div>', unsafe_allow_html=True)
            for page in pages:
                st.page_link(page, icon=page.icon)
    st.markdown('<hr class="nav-rule">', unsafe_allow_html=True)
    st.markdown(
        f'<div class="note">Signed in as <strong style="color:var(--text);">{esc(user["username"])}</strong></div>',
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
with st.sidebar.container(key="legal_links"):
    terms_col, privacy_col = st.columns(2, gap="small")
    terms_col.page_link(TERMS, label="Terms")
    privacy_col.page_link(PRIVACY, label="Privacy")
    st.markdown('<div class="note">Not financial advice</div>', unsafe_allow_html=True)
apply_cookie_action()
nav.run()
model_status()      # refresh once the page has run, so it reflects models the page just loaded
