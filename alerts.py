"""Per-user risk alerts. Thresholds are saved to the user's account, so they survive sign-out."""
import streamlit as st

from auth import get_current_user, load_alert_prefs, save_alert_prefs
from chainintel_core import ASSETS
from styles import esc

DEFAULT_THRESHOLD = 50


def init_alerts():
    if "alert_thresholds" in st.session_state:
        return
    user = get_current_user()
    prefs = (load_alert_prefs(user["id"]) if user else None) or {}
    saved = prefs.get("thresholds", {})
    st.session_state.alert_thresholds = {t: int(saved.get(t, DEFAULT_THRESHOLD)) for t in ASSETS}
    st.session_state.alerts_enabled = bool(prefs.get("enabled", True))


def _persist():
    user = get_current_user()
    if user:
        save_alert_prefs(user["id"], {"enabled": st.session_state.alerts_enabled,
                                      "thresholds": st.session_state.alert_thresholds})


def render_alert_settings():
    """Alert controls (Settings page). Saved to the account as soon as anything changes."""
    init_alerts()
    enabled = st.toggle("Show alerts when a coin crosses its threshold", value=st.session_state.alerts_enabled, key="alert_toggle")
    changed = enabled != st.session_state.alerts_enabled
    st.session_state.alerts_enabled = enabled
    if enabled:
        cols = st.columns(3)
        for i, ticker in enumerate(ASSETS):
            with cols[i % 3]:
                val = st.slider(ticker, 0, 100, st.session_state.alert_thresholds[ticker], step=5, key=f"thresh_{ticker}")
            if val != st.session_state.alert_thresholds[ticker]:
                st.session_state.alert_thresholds[ticker] = val
                changed = True
    if changed:
        _persist()


def check_and_show_alerts(current_risks: dict):
    """current_risks = {"USDC": 13.5, "USDT": None, ...} — None (no data) never triggers."""
    init_alerts()
    if not st.session_state.alerts_enabled:
        return
    for ticker, risk in current_risks.items():
        threshold = st.session_state.alert_thresholds.get(ticker, DEFAULT_THRESHOLD)
        if risk is None or risk < threshold:
            continue
        color = "#ef4444" if risk >= 70 else "#f59e0b"
        why = (f"risk score crossed your threshold of {threshold}" if get_current_user()
               else f"risk score is above {threshold} (default alert level)")
        st.markdown(f"""
        <div style="background:{color}14;border:1px solid {color}66;border-radius:12px;padding:12px 18px;
                    margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;gap:12px;">
          <div>
            <span style="font-size:15px;font-weight:800;color:{color};">⚠ {esc(ticker)}</span>
            <span style="font-size:13px;color:#94a3b8;margin-left:10px;">{why}</span>
          </div>
          <span style="font-size:20px;font-weight:800;color:{color};">{risk:.1f}</span>
        </div>""", unsafe_allow_html=True)
