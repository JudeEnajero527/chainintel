"""Page shell shared by every page: config, theme, login wall, sidebar, cached engine."""
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from alerts import render_alert_settings
from auth import get_current_user, logout, render_auth_wall, set_digest_opt_in, signed_in_badge
from chainintel_core import ASSETS, RiskEngine
from styles import BASE_CSS, esc

NAV = [
    ("Home.py",                 "⬡  Home"),
    ("pages/1_Monitor.py",      "📡  Monitor"),
    ("pages/2_Intelligence.py", "🤖  Intelligence"),
    ("pages/3_Whales.py",       "🐋  Whale Alerts"),
    ("pages/4_Portfolio.py",    "💼  Portfolio"),
    ("pages/5_Analytics.py",    "📈  Analytics"),
    ("pages/6_Social.py",       "🌐  Social Intel"),
    ("pages/7_Markets.py",      "🌍  Markets"),
    ("pages/8_DeFi.py",         "🏦  DeFi Protocols"),
    ("pages/9_Yields.py",       "💰  Yields"),
]


@st.cache_resource(show_spinner=False)
def get_engine() -> RiskEngine:
    return RiskEngine()


def page(title: str, icon: str, refresh_seconds: int | None = None, asset_picker: bool = False):
    """
    Sets up a page and returns (engine, selected_ticker). Call first on every page.
    The selected asset is shared across pages via session state.
    """
    st.set_page_config(page_title=f"{title} · ChainIntel" if title != "Home" else "ChainIntel",
                       page_icon=icon, layout="wide", initial_sidebar_state="expanded")
    st.markdown(BASE_CSS, unsafe_allow_html=True)
    if not render_auth_wall():
        st.stop()
    if refresh_seconds:
        st_autorefresh(interval=refresh_seconds * 1000, key=f"refresh_{title}")

    engine = get_engine()
    selected = None
    with st.sidebar:
        st.markdown("""
        <div style="padding:16px 0 16px;border-bottom:1px solid rgba(255,255,255,.06);margin-bottom:14px;">
          <div style="font-size:22px;font-weight:900;letter-spacing:-1px;background:linear-gradient(135deg,#60a5fa,#a78bfa);
                      -webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;">⬡ ChainIntel</div>
          <div style="font-size:11px;color:#64748b;margin-top:3px;font-weight:600;letter-spacing:.06em;">STABLECOIN RISK INTELLIGENCE</div>
        </div>""", unsafe_allow_html=True)
        for path, label in NAV:
            st.page_link(path, label=label)

        if asset_picker:
            st.markdown('<div class="section-title" style="margin:20px 0 8px;">Asset</div>', unsafe_allow_html=True)
            tickers = list(ASSETS)
            current = st.session_state.get("selected_asset", tickers[0])
            selected = st.radio("Asset", tickers, index=tickers.index(current) if current in tickers else 0,
                                label_visibility="collapsed", key=f"asset_{title}")
            st.session_state["selected_asset"] = selected

        st.markdown('<div style="height:12px;"></div>', unsafe_allow_html=True)
        render_alert_settings()

        user = get_current_user()
        st.markdown(signed_in_badge(user), unsafe_allow_html=True)
        digest = st.toggle("Daily email digest", value=user.get("digest_opt_in", True), key="digest_toggle")
        if digest != user.get("digest_opt_in", True):
            set_digest_opt_in(user["id"], digest)
            user["digest_opt_in"] = digest
        if st.button("Sign out", key="sidebar_logout", use_container_width=True):
            logout()
            st.rerun()

        st.markdown(
            f'<div class="note" style="margin-top:18px;">Sentiment AI: {esc(engine.sentiment_status)}<br>'
            f'Depeg model: {esc(engine.ml_status)}</div>',
            unsafe_allow_html=True,
        )
    return engine, selected


def header(title: str, subtitle: str = "", right_html: str = ""):
    sub = f'<div class="page-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(f"""
    <div style="display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;padding:4px 0 24px;">
      <div><div class="page-title">{title}</div>{sub}</div>
      <div style="text-align:right;">{right_html}</div>
    </div>""", unsafe_allow_html=True)
