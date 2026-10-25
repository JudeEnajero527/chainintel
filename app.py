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
import usage
from auth import apply_cookie_action, get_current_user, logout, render_auth_wall, show_sign_in
from styles import BASE_CSS, esc
from ui import get_engine

HERE = os.path.dirname(os.path.abspath(__file__))

st.set_page_config(page_title="ChainIntel", page_icon=os.path.join(HERE, "assets", "icon.svg"),
                   layout="wide", initial_sidebar_state="auto")
st.markdown(BASE_CSS, unsafe_allow_html=True)

if not render_auth_wall(optional=True):     # accounts are optional; the site is open
    st.stop()

st.logo(os.path.join(HERE, "assets", "logo.svg"), icon_image=os.path.join(HERE, "assets", "icon.svg"), size="large")


def view(file, title, icon, **kw):
    return st.Page(os.path.join("views", file), title=title, icon=f":material/{icon}:", **kw)


SIGNALS = config.show_signals()     # trading-style pages; off by default so ChainIntel reads as a risk tool
SECTIONS = {
    "": [view("home.py", "Overview", "space_dashboard", default=True)],
    "Risk": [
        view("monitor.py", "Monitor", "monitor_heart", url_path="monitor"),
        view("forecasts.py", "Forecasts", "psychology", url_path="forecasts"),
        view("analytics.py", "Analytics", "insights", url_path="analytics"),
    ],
    "Markets": [
        view("markets.py", "Stablecoins", "public", url_path="markets"),
        view("defi.py", "DeFi protocols", "account_balance", url_path="defi"),
        *([view("yields.py", "Yields", "savings", url_path="yields")] if SIGNALS else []),
    ],
    "Signals": [
        view("whales.py", "Whale alerts", "waves", url_path="whales"),
        view("social.py", "Social", "forum", url_path="social"),
    ] if SIGNALS else [],
    "You": [
        *([view("portfolio.py", "Portfolio", "account_balance_wallet", url_path="portfolio")] if SIGNALS else []),
        view("settings.py", "Settings", "settings", url_path="settings"),
    ],
}
SECTIONS = {name: pages for name, pages in SECTIONS.items() if pages}
# Reachable pages that don't belong in the menu — linked from the sidebar footer instead.
TERMS = view("terms.py", "Terms of Use", "gavel", url_path="terms")
PRIVACY = view("privacy.py", "Privacy Policy", "shield", url_path="privacy")

# Streamlit's built-in menu can't hide individual pages, so it's turned off and drawn below.
nav = st.navigation([p for pages in SECTIONS.values() for p in pages] + [TERMS, PRIVACY], position="hidden")
st.session_state["_page"] = nav.url_path or "home"
usage.record_view(st.session_state["_page"])      # anonymous visit count (no cookies, no IP)

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
        if user:
            who, out = st.columns([3, 2], vertical_alignment="center", gap="small")
            who.markdown(
                f'<div class="account"><span class="avatar">{esc(user["username"][:1].upper())}</span>'
                f'<span class="account-name">{esc(user["username"])}</span></div>',
                unsafe_allow_html=True,
            )
            if out.button("Sign out", icon=":material/logout:", type="tertiary", key="sidebar_logout"):
                logout()
                st.rerun()
        else:
            if st.button("Sign in for alerts", icon=":material/login:", type="tertiary", key="sidebar_login"):
                show_sign_in()
                st.rerun()
    status_slot = st.empty()


def model_status():
    # Social sentiment only matters when the Social page is on
    healthy = engine.model is not None and (not SIGNALS or engine.sentiment_status != "Offline")
    line = "Models online" if healthy else f"Forecast model: {esc(engine.ml_status)}"
    status_slot.markdown(     # optional data sources are reported in Settings, not in every visitor's sidebar
        f'<div class="sidebar-meta"><div><span class="status-dot {"ok" if healthy else "warn"}"></span>{line}</div></div>',
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
