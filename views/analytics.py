import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from chainintel_core import ASSETS
from styles import PLOT_LAYOUT, empty_state, risk_hex, section
from ui import get_engine, auto_refresh, header

engine = get_engine()
auto_refresh(300)
header("Analytics", "Risk over time, and how tightly the stablecoins move together")

days = st.segmented_control("Window", [1, 7, 30, 90], default=7, format_func=lambda d: f"Last {d}d",
                            label_visibility="collapsed", key="analytics_window") or 7

# ── Recorded risk history (hourly averages so assets line up) ──────────────────
hourly = {}
for t in ASSETS:
    df = engine.get_history(t, days=days)
    if not df.empty:
        hourly[t] = df["total_risk"].resample("1h").mean().dropna()
risk = pd.DataFrame(hourly)

st.markdown(section("Risk heatmap"), unsafe_allow_html=True)
if len(risk) < 3:
    st.markdown(empty_state("📊", "Not enough recorded history in this window yet",
                            f"{len(risk)} hourly reading(s) so far. ChainIntel saves a reading for every asset every "
                            "5 minutes while the app is open — check back in a few hours, or pick a longer window."),
                unsafe_allow_html=True)
else:
    bucket = "1h" if days <= 1 else "6h" if days <= 7 else "1D"
    heat = risk.resample(bucket).mean()
    with st.container(border=True):
        fig = go.Figure(go.Heatmap(
            z=heat.T.values, x=heat.index, y=list(heat.columns), zmin=0, zmax=100,
            colorscale=[[0, "#0d2818"], [0.3, "#166534"], [0.45, "#a16207"], [0.6, "#b45309"], [0.8, "#b91c1c"], [1, "#ef4444"]],
            hovertemplate="%{y} · %{x}<br>Risk %{z:.1f}<extra></extra>", hoverongaps=False,
            colorbar=dict(title=dict(text="Risk", font=dict(color="#94a3b8")), tickfont=dict(color="#94a3b8")),
        ))
        fig.update_layout(**PLOT_LAYOUT, height=320)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown(section("Risk trend"), unsafe_allow_html=True)
    with st.container(border=True):
        fig2 = go.Figure()
        for t in risk.columns:
            s = risk[t].dropna()
            fig2.add_trace(go.Scatter(x=s.index, y=s.values, name=t, mode="lines+markers" if len(s) < 30 else "lines",
                                      line=dict(color=ASSETS[t]["color"], width=2)))
        for y0, y1, c in [(0, 30, "rgba(34,197,94,.04)"), (30, 60, "rgba(245,158,11,.05)"), (60, 100, "rgba(239,68,68,.05)")]:
            fig2.add_hrect(y0=y0, y1=y1, fillcolor=c, line_width=0)
        fig2.update_layout(**PLOT_LAYOUT, height=320, legend=dict(orientation="h", y=1.1, bgcolor="rgba(0,0,0,0)"))
        fig2.update_yaxes(range=[0, 100])
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    st.markdown(section("Summary"), unsafe_allow_html=True)
    cols = st.columns(min(len(risk.columns), 9))
    for col, t in zip(cols, risk.columns):
        s = risk[t].dropna()
        change = s.iloc[-1] - s.iloc[0]
        with col:
            st.markdown(f"""
            <div class="card" style="padding:16px;text-align:center;">
              <div style="font-size:15px;font-weight:800;color:#f1f5f9;margin-bottom:10px;">{t}</div>
              <div class="note">Now</div><div style="font-size:18px;font-weight:800;color:{risk_hex(s.iloc[-1])};">{s.iloc[-1]:.1f}</div>
              <div class="note" style="margin-top:6px;">Avg · Peak</div>
              <div style="font-size:13px;font-weight:700;color:#94a3b8;">{s.mean():.1f} · {s.max():.1f}</div>
              <div style="font-size:12px;font-weight:700;margin-top:6px;color:{'#ef4444' if change > 0 else '#22c55e'};">{change:+.1f}</div>
            </div>""", unsafe_allow_html=True)

# ── Peg deviation history + co-movement (DefiLlama daily, 1 year) ──────────────
st.markdown(section("Distance from $1 · last 12 months (daily)"), unsafe_allow_html=True)
with st.spinner("Loading daily price history…"):
    daily = {t: engine.get_daily_prices(t) for t in ASSETS}
dev = pd.DataFrame({t: (s - 1) * 100 for t, s in daily.items() if s is not None}).sort_index()
if dev.empty:
    st.markdown(empty_state("🌐", "Daily history unavailable", "DefiLlama could not be reached."), unsafe_allow_html=True)
    st.stop()
dev = dev[dev.index >= dev.index.max() - pd.Timedelta(days=365)]

with st.container(border=True):
    fig3 = go.Figure()
    for t in dev.columns:
        fig3.add_trace(go.Scatter(x=dev.index, y=dev[t], name=t, mode="lines", line=dict(color=ASSETS[t]["color"], width=1.4)))
    fig3.add_hrect(y0=-0.5, y1=0.5, fillcolor="rgba(34,197,94,.05)", line_width=0)
    fig3.update_layout(**PLOT_LAYOUT, height=320, legend=dict(orientation="h", y=1.1, bgcolor="rgba(0,0,0,0)"))
    fig3.update_yaxes(ticksuffix="%", title="Deviation from peg")
    st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

left, right = st.columns([1.1, 1])
with left:
    st.markdown(section("Peg co-movement (correlation of daily deviations)"), unsafe_allow_html=True)
    corr = dev.corr(min_periods=60)
    with st.container(border=True):
        fig4 = go.Figure(go.Heatmap(
            z=corr.values, x=list(corr.columns), y=list(corr.index), zmin=-1, zmax=1,
            colorscale=[[0, "#3b82f6"], [0.5, "#12151c"], [1, "#ef4444"]],
            text=corr.round(2).values, texttemplate="%{text}", textfont=dict(size=11, color="#f1f5f9"),
            hovertemplate="%{y} vs %{x}: %{z:.2f}<extra></extra>",
        ))
        fig4.update_layout(**PLOT_LAYOUT, height=380)
        st.plotly_chart(fig4, use_container_width=True, config={"displayModeBar": False})

with right:
    st.markdown(section("How to read it"), unsafe_allow_html=True)
    st.markdown("""
    <div class="card">
      <div style="color:#ef4444;font-weight:700;font-size:13px;">Red (toward +1) — drift off peg together</div>
      <div class="note" style="margin-bottom:12px;">Shared collateral or shared market makers. Holding both gives less protection than it looks.</div>
      <div style="color:#94a3b8;font-weight:700;font-size:13px;">Dark (≈0) — independent</div>
      <div class="note" style="margin-bottom:12px;">Good for diversification.</div>
      <div style="color:#3b82f6;font-weight:700;font-size:13px;">Blue (toward −1) — opposite moves</div>
      <div class="note" style="margin-bottom:12px;">Common when traders swap from one into the other.</div>
      <div class="note" style="border-top:1px solid rgba(255,255,255,.06);padding-top:12px;">
        In March 2023 USDC, DAI and FRAX all fell together because DAI and FRAX were backed by USDC — exactly the
        pattern this chart is designed to reveal. Pairs need 60+ overlapping days to be shown.</div>
    </div>""", unsafe_allow_html=True)
