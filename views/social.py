from datetime import datetime, timezone

import plotly.graph_objects as go
import streamlit as st

from styles import PLOT_LAYOUT, card, empty_state, esc, fmt_age, fmt_usd, risk_bar_html, risk_hex, section
from ui import get_engine, auto_refresh, asset_selector, header

engine = get_engine()
auto_refresh(600)
header("Social signals", "Search interest, Reddit chatter and on-chain trading pressure")
ticker = asset_selector()

with st.spinner("Gathering social and on-chain signals…"):
    trends = engine.get_google_trends(ticker)
    reddit = engine.get_reddit_mentions(ticker)
    dex = engine.get_dex_stats(ticker)
dex_ok = not dex.get("error")

# ── Signal scores (0–100, higher = more worrying; None = unavailable) ──────────
trend_score = min(trends["score"] * 1.5, 100) if trends else None
buzz_score = reddit["buzz"] if reddit else None
turnover_score = min(dex["turnover"] * 100, 100) if dex_ok and dex["turnover"] is not None else None
sell_score = max(0.0, min(100.0, (dex["sell_pressure"] - 50) * 4)) if dex_ok and dex["sell_pressure"] is not None else None

c1, c2, c3, c4 = st.columns(4)
with c1:
    st.markdown(card("Google search interest",
                     f"{trends['score']}<span style='font-size:14px;color:#64748b;'>/100</span>" if trends else "—",
                     f"{esc(trends['trend'])} · 7d avg {trends['week_avg']}" if trends else "Google Trends rate-limited — try later",
                     color=risk_hex(trend_score) if trends else None), unsafe_allow_html=True)
with c2:
    st.markdown(card("Reddit posts · 24h", str(reddit["count_24h"]) if reddit else "—",
                     f"{reddit['count_7d']} this week" if reddit else "Reddit unavailable (rate-limited)",
                     color=risk_hex(buzz_score) if reddit else None), unsafe_allow_html=True)
with c3:
    st.markdown(card("24h DEX volume", fmt_usd(dex["volume24h"]) if dex_ok else "—",
                     f"{dex['turnover']:.2f}× liquidity turned over" if dex_ok and dex["turnover"] is not None else "DexScreener unavailable"),
                unsafe_allow_html=True)
with c4:
    sp = dex.get("sell_pressure") if dex_ok else None
    st.markdown(card("Sell pressure", f"{sp:.0f}%" if sp is not None else "—",
                     f"{dex['sells']:,} sells · {dex['buys']:,} buys (24h)" if dex_ok else "DexScreener unavailable",
                     color="#ef4444" if sp and sp > 65 else "#f59e0b" if sp and sp > 55 else "#22c55e" if sp else None),
                unsafe_allow_html=True)

left, right = st.columns([1, 1])
with left:
    st.markdown(section("Buy vs sell transactions · 24h"), unsafe_allow_html=True)
    if dex_ok and dex["buys"] + dex["sells"] > 0:
        with st.container(border=True):
            fig = go.Figure(go.Pie(labels=["Buys", "Sells"], values=[dex["buys"], dex["sells"]], hole=0.62,
                                   marker=dict(colors=["#22c55e", "#ef4444"], line=dict(color="#080910", width=3)),
                                   textinfo="label+percent", textfont=dict(color="#f1f5f9", size=13)))
            fig.update_layout(**PLOT_LAYOUT, height=260, showlegend=False)
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown(f'<div class="note">Across {dex["pools"]} Ethereum pools · largest: {esc(dex["top_pool"])}</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown(empty_state("🔄", "No DEX trade data"), unsafe_allow_html=True)

with right:
    st.markdown(section("Google Trends · 7 days"), unsafe_allow_html=True)
    if trends:
        with st.container(border=True):
            s = trends["series"]
            fig2 = go.Figure(go.Scatter(x=s.index, y=s.values, mode="lines", fill="tozeroy",
                                        line=dict(color="#a78bfa", width=2), fillcolor="rgba(167,139,250,0.08)"))
            fig2.add_hline(y=trends["week_avg"], line_dash="dot", line_color="#64748b",
                           annotation_text="7d avg", annotation_font_color="#64748b")
            fig2.update_layout(**PLOT_LAYOUT, height=260)
            fig2.update_yaxes(range=[0, 100])
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
        st.markdown(f'<div class="note">Search term: “{esc(trends["query"])}”</div>', unsafe_allow_html=True)
    else:
        st.markdown(empty_state("📉", "Google Trends unavailable", "Google heavily rate-limits this data. ChainIntel retries in 10 minutes."),
                    unsafe_allow_html=True)

# ── Reddit posts ───────────────────────────────────────────────────────────────
st.markdown(section("Recent Reddit posts"), unsafe_allow_html=True)
if reddit is None:
    st.markdown(empty_state("🤐", "Reddit unavailable",
                            "Reddit rate-limits anonymous access. A reliable feed needs Reddit API credentials."),
                unsafe_allow_html=True)
elif not reddit["posts"]:
    st.markdown(empty_state("🤐", "No posts this week", f"Nobody in the tracked subreddits mentioned {ticker} in the last 7 days."),
                unsafe_allow_html=True)
else:
    for p in reddit["posts"]:
        age = fmt_age((datetime.now(timezone.utc) - p["time"]).total_seconds()) if p["time"] else ""
        st.markdown(f"""
        <a class="row-link" href="{esc(p['url'])}" target="_blank" rel="noopener">
          <div class="data-row"><div style="flex:1;">
            <div style="font-size:14px;font-weight:500;color:#f1f5f9;line-height:1.4;">{esc(p['title'])}</div>
            <div class="note">r/{esc(p['sub'])} · {age}</div>
          </div></div>
        </a>""", unsafe_allow_html=True)

# ── Signal summary ─────────────────────────────────────────────────────────────
st.markdown(section("Signal summary"), unsafe_allow_html=True)
signals = [
    ("Search interest", trend_score, "Spikes in searches like “USDC depeg” mean people are worried."),
    ("Reddit buzz", buzz_score, "50 = a normal day of posts, 100 = twice the weekly average."),
    ("DEX turnover", turnover_score, "Volume relative to liquidity. Heavy churn can mean holders are leaving."),
    ("Sell pressure", sell_score, "0 = balanced buys and sells, 100 = 75%+ of trades are sells."),
]
for col, (name, score, desc) in zip(st.columns(4), signals):
    with col:
        st.markdown(f'<div class="card">{risk_bar_html(score, name)}<div class="note" style="margin-top:10px;">{desc}</div></div>',
                    unsafe_allow_html=True)

st.markdown('<div class="footer-note">Google Trends · Reddit RSS · DexScreener · refreshes every 10 minutes</div>',
            unsafe_allow_html=True)
