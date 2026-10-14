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
        for i, (section, pages) in enumerate(SECTIONS.items()):
            with st.container(key=f"nav_group_{i}"):          # keeps each heading attached to its links
                if section:
                    st.markdown(f'<div class="nav-section">{section}</div>', unsafe_allow_html=True)
                for page in pages:
                    st.page_link(page, icon=page.icon)

    with st.container(key="sidebar_account"):
        who, out = st.columns([3, 2], vertical_alignment="center", gap="small")
        who.markdown(
            f'<div class="account"><span class="avatar">{esc(user["username"][:1].upper())}</span>'
            f'<span class="account-name">{esc(user["username"])}</span></div>',
            unsafe_allow_html=True,
        )
        if out.button("Sign out", icon=":material/logout:", type="tertiary", key="sidebar_logout"):
            logout()
            st.rerun()
    status_slot = st.empty()


def model_status():
    healthy = engine.model is not None and engine.sentiment_status != "Offline"
    missing = [k for k, ok in config.status().items() if not ok and k in ("ETHERSCAN_API_KEY", "REDDIT_CLIENT_ID")]
    line = "Models online" if healthy else f"Forecast model: {esc(engine.ml_status)}"
    extra = f'<div>{len(missing)} data source{"s" if len(missing) != 1 else ""} not set up</div>' if missing else ""
    status_slot.markdown(
        f'<div class="sidebar-meta"><div><span class="status-dot {"ok" if healthy else "warn"}"></span>{line}</div>{extra}</div>',
        unsafe_allow_html=True,
    )


model_status()
with st.sidebar.container(key="legal_links"):
    terms_col, privacy_col, note_col = st.columns(3, gap="small", vertical_alignment="center")
    terms_col.page_link(TERMS, label="Terms")
    privacy_col.page_link(PRIVACY, label="Privacy")
    note_col.markdown('<span class="legal-note">Not financial advice</span>', unsafe_allow_html=True)
apply_cookie_action()
nav.run()
model_status()      # refresh once the page has run, so it reflects models the page just loaded
