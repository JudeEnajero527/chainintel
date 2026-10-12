"""Helpers shared by the views: cached engine, page header, asset picker, auto-refresh."""
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from chainintel_core import ASSETS, RiskEngine


@st.cache_resource(show_spinner=False)
def get_engine() -> RiskEngine:
    return RiskEngine()


def header(title: str, subtitle: str = "", right_html: str = ""):
    sub = f'<div class="page-sub">{subtitle}</div>' if subtitle else ""
    st.markdown(f"""
    <div style="display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;margin-bottom:18px;">
      <div><div class="page-title">{title}</div>{sub}</div>
      <div style="text-align:right;">{right_html}</div>
    </div>""", unsafe_allow_html=True)


def asset_selector() -> str:
    """Horizontal coin picker. The choice follows the user from page to page."""
    tickers = list(ASSETS)
    current = st.session_state.get("selected_asset", tickers[0])
    choice = st.segmented_control("Asset", tickers, default=current if current in tickers else tickers[0],
                                  key="asset_picker", label_visibility="collapsed")
    choice = choice or current                      # clicking the active option deselects it — keep the old one
    st.session_state["selected_asset"] = choice
    return choice


def auto_refresh(seconds: int):
    st_autorefresh(interval=seconds * 1000, key=f"refresh_{st.session_state.get('_page', 'page')}_{seconds}")
