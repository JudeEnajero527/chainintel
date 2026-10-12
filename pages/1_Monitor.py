from datetime import datetime

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from alerts import check_and_show_alerts
from chainintel_core import DEPEG_EVENTS
from styles import (LEVEL_HEX, PLOT_LAYOUT, card, empty_state, esc, fmt_price, fmt_usd, risk_bar_html, risk_hex,
                    section, status_pill)
from ui import header, page

engine, ticker = page("Monitor", "📡", refresh_seconds=60, asset_picker=True)

with st.spinner(f"Assessing {ticker}…"):
    a = engine.assess(ticker)
cfg, price, risk, ml, dex, sent = a["cfg"], a["price"], a["risk"], a["ml"], a["dex"], a["sentiment"]

check_and_show_alerts({ticker: risk["total"]})

header(
    f'{ticker} <span style="color:#475569;font-weight:400;font-size:22px;">/ USD</span>',
    f"Issued by {esc(cfg['issuer'])}",
    f'{status_pill(risk["total"])}<div class="note" style="margin-top:6px;">Updated {datetime.now():%I:%M:%S %p} · refreshes every 60s</div>',
)

# ── Top metrics ────────────────────────────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
dev = abs(1 - price) if price is not None else None
price_color = "#64748b" if dev is None else "#22c55e" if dev < 0.001 else "#f59e0b" if dev < 0.005 else "#ef4444"
with c1:
    st.markdown(card("Price", fmt_price(price), f"Deviation {dev*100:.3f}%" if dev is not None else "CoinGecko unavailable",
                     color=price_color), unsafe_allow_html=True)
with c2:
    sub = (f"{dex['pools']} Ethereum pools · top: {esc(dex['top_pool'])}" if not dex.get("error")
           else f"Unavailable: {esc(dex['error'])}")
    st.markdown(card("DEX liquidity", fmt_usd(a["liquidity"]), sub), unsafe_allow_html=True)
with c3:
    s = sent["score"]
    st.markdown(card("News sentiment risk", f"{s:.0f}<span style='font-size:15px;color:#64748b;'>/100</span>" if s is not None else "—",
                     f"{len(sent['items'])} headlines · FinBERT" if s is not None else esc(sent["error"]),
                     color=risk_hex(s) if s is not None else None), unsafe_allow_html=True)
with c4:
    t = risk["total"]
    st.markdown(card("Composite risk", f"{t:.1f}<span style='font-size:15px;color:#64748b;'>/100</span>" if t is not None else "—",
                     f"from {', '.join(risk['used'])}" if risk["used"] else "no data", color=risk_hex(t), border=risk_hex(t)),
                unsafe_allow_html=True)
with c5:
    prob = ml["probability"]
    st.markdown(card("7-day depeg forecast", f"{prob:.1f}%" if prob is not None else "—", esc(ml["label"]),
                     color=LEVEL_HEX[ml["level"]], border=LEVEL_HEX[ml["level"]]), unsafe_allow_html=True)

# ── Risk breakdown ─────────────────────────────────────────────────────────────
st.markdown(section("Risk breakdown"), unsafe_allow_html=True)
r1, r2, r3 = st.columns(3)
for col, key, label, why in [
    (r1, "peg",       "Peg risk · 50%",       "0 at $1.00, 100 at ≥1% off peg"),
    (r2, "liquidity", "Liquidity risk · 30%", "0 with ≥$500M on-chain DEX depth, 100 at ≤$5M (log scale)"),
    (r3, "sentiment", "Sentiment risk · 20%", "Share of recent headlines FinBERT reads as negative"),
]:
    with col:
        st.markdown(f'<div class="card">{risk_bar_html(risk[key], label)}<div class="note" style="margin-top:10px;">{why}</div></div>',
                    unsafe_allow_html=True)

# ── News + history ─────────────────────────────────────────────────────────────
left, right = st.columns([1, 1])

with left:
    st.markdown(section("Latest headlines"), unsafe_allow_html=True)
    if not sent["items"]:
        st.markdown(empty_state("📰", "No headlines", esc(sent["error"] or "")), unsafe_allow_html=True)
    badge = {"positive": ("news-dot-green", "news-badge-pos", "Positive"),
             "negative": ("news-dot-red", "news-badge-neg", "Negative"),
             "neutral":  ("news-dot-yellow", "news-badge-neu", "Neutral")}
    for item in sent["items"]:
        dot, cls, txt = badge.get(item.get("label"), ("news-dot-yellow", "news-badge-neu", "Unscored"))
        st.markdown(f"""
        <a class="row-link" href="{esc(item['link'])}" target="_blank" rel="noopener">
        <div class="news-card"><div class="{dot}"></div>
          <div><span class="{cls}">{txt}</span>
            <div class="news-text">{esc(item['title'])}</div>
            <div class="note">{esc(item['source'])}</div></div>
        </div></a>""", unsafe_allow_html=True)

with right:
    st.markdown(section("Risk & price history"), unsafe_allow_html=True)
    days = st.segmented_control("Window", [1, 7, 30, 90], default=7, format_func=lambda d: f"{d}d",
                                label_visibility="collapsed", key="monitor_window") or 7
    hist = engine.get_history(ticker, days=days)
    if hist.empty:
        st.markdown(empty_state("📊", "No history yet",
                                "ChainIntel records a reading every 5 minutes while the app is open."), unsafe_allow_html=True)
    else:
        with st.container(border=True):
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_trace(go.Scatter(x=hist.index, y=hist["total_risk"], name="Risk score", mode="lines+markers" if len(hist) < 30 else "lines",
                                     fill="tozeroy", line=dict(color="#3b82f6", width=2), fillcolor="rgba(59,130,246,0.08)"))
            fig.add_trace(go.Scatter(x=hist.index, y=hist["price"], name="Price", mode="lines",
                                     line=dict(color="#a78bfa", width=1.5, dash="dot")), secondary_y=True)
            fig.update_layout(**PLOT_LAYOUT, height=260, showlegend=True,
                              legend=dict(orientation="h", y=1.1, bgcolor="rgba(0,0,0,0)"))
            fig.update_yaxes(range=[0, 100], gridcolor="rgba(255,255,255,0.05)", secondary_y=False)
            lo, hi = hist["price"].min(), hist["price"].max()
            pad = max((hi - lo) * 0.2, 0.0005)
            fig.update_yaxes(tickformat="$.4f", showgrid=False, range=[lo - pad, hi + pad], nticks=5, secondary_y=True)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    events = DEPEG_EVENTS.get(ticker, [])
    if events:
        st.markdown(section("Historical depeg events"), unsafe_allow_html=True)
        for ev in events:
            st.markdown(f"""
            <div class="card-sm" style="border-left:3px solid #ef4444;display:flex;justify-content:space-between;align-items:center;">
              <span style="color:#f87171;font-weight:600;">{esc(ev['label'])}</span>
              <span class="note">{ev['date']} · low ${ev['price']}</span>
            </div>""", unsafe_allow_html=True)
