import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from styles import PLOT_LAYOUT, card, empty_state, esc, fmt_usd, section
from ui import get_engine, auto_refresh, header

engine = get_engine()
auto_refresh(600)
header("Stablecoin markets", "The 25 largest stablecoins by circulating supply")

with st.spinner("Loading market data…"):
    coins = engine.get_stablecoin_market_caps()
    fg = engine.get_fear_greed()
    gas = engine.get_gas_price()

if not coins:
    st.markdown(empty_state("🌐", "Market data unavailable", "DefiLlama could not be reached. Retrying shortly."),
                unsafe_allow_html=True)
    st.stop()

total = sum(c["market_cap"] for c in coins)
top = coins[0]
off_peg = [c for c in coins if c["price"] and c["peg_type"] == "USD" and abs(c["price"] - 1) >= 0.005]

m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.markdown(card("Top-25 supply", fmt_usd(total), "circulating, all chains"), unsafe_allow_html=True)
with m2:
    st.markdown(card("Largest", esc(top["symbol"]), f"{fmt_usd(top['market_cap'])} · {top['market_cap']/total*100:.1f}% share"),
                unsafe_allow_html=True)
with m3:
    top3 = sum(c["market_cap"] for c in coins[:3]) / total * 100
    st.markdown(card("Top-3 concentration", f"{top3:.1f}%", "of the top-25 supply"), unsafe_allow_html=True)
with m4:
    st.markdown(card("Off peg (≥0.5%)", str(len(off_peg)), ", ".join(esc(c["symbol"]) for c in off_peg[:4]) or "none of the top 25",
                     color="#ef4444" if off_peg else "#22c55e"), unsafe_allow_html=True)
with m5:
    if fg:
        fg_color = "#22c55e" if fg["value"] >= 55 else "#f59e0b" if fg["value"] >= 35 else "#ef4444"
        st.markdown(card("Crypto Fear & Greed", str(fg["value"]), esc(fg["label"]), color=fg_color), unsafe_allow_html=True)
    else:
        st.markdown(card("Crypto Fear & Greed", "—", "unavailable"), unsafe_allow_html=True)

left, right = st.columns([1.4, 1])
with left:
    st.markdown(section("Market share"), unsafe_allow_html=True)
    top_n = coins[:8]
    labels = [c["symbol"] for c in top_n] + ["Others"]
    values = [c["market_cap"] for c in top_n] + [total - sum(c["market_cap"] for c in top_n)]
    with st.container(border=True):
        fig = go.Figure(go.Pie(
            labels=labels, values=values, hole=0.55, sort=False,
            marker=dict(colors=["#26a17b", "#2775ca", "#f5ac37", "#a78bfa", "#f472b6", "#34d399", "#fb923c", "#60a5fa", "#334155"],
                        line=dict(color="#080910", width=2)),
            textinfo="label+percent", textfont=dict(color="#f9fafb", size=12),
            hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<br>%{percent}<extra></extra>",
        ))
        fig.update_layout(**PLOT_LAYOUT, height=320, showlegend=False,
                          annotations=[dict(text=fmt_usd(total, 0), x=0.5, y=0.5, showarrow=False, font=dict(size=20, color="#f9fafb"))])
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with right:
    st.markdown(section("Market mood · 30 days"), unsafe_allow_html=True)
    with st.container(border=True):
        if fg and fg["history"]:
            fig2 = go.Figure(go.Scatter(y=fg["history"], mode="lines+markers", line=dict(color="#a78bfa", width=2),
                                        marker=dict(size=4), fill="tozeroy", fillcolor="rgba(167,139,250,.08)"))
            fig2.add_hrect(y0=0, y1=25, fillcolor="rgba(239,68,68,.06)", line_width=0)
            fig2.add_hrect(y0=75, y1=100, fillcolor="rgba(34,197,94,.06)", line_width=0)
            fig2.update_layout(**PLOT_LAYOUT, height=200)
            fig2.update_yaxes(range=[0, 100])
            fig2.update_xaxes(visible=False)
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
            st.markdown('<div class="note">Fear &amp; Greed index (alternative.me). Stablecoin stress tends to cluster in "Extreme Fear".</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="note">Fear &amp; Greed history unavailable.</div>', unsafe_allow_html=True)
        gas_txt = f"{gas['propose']:.2f} gwei (safe {gas['safe']:.2f} · fast {gas['fast']:.2f})" if gas else "needs ETHERSCAN_API_KEY"
        st.markdown(f'<div class="note" style="margin-top:8px;">Ethereum gas: <strong style="color:#f1f5f9;">{gas_txt}</strong></div>',
                    unsafe_allow_html=True)

st.markdown(section("Leaderboard"), unsafe_allow_html=True)
df = pd.DataFrame([{
    "Symbol": c["symbol"], "Name": c["name"], "Market cap": c["market_cap"],
    "Share": c["market_cap"] / total * 100, "Price": c["price"],
    "Off peg %": abs(c["price"] - 1) * 100 if c["price"] and c["peg_type"] == "USD" else None,
    "Chains": c["chain_count"], "Peg": c["peg_type"], "Mechanism": c["peg_mech"],
} for c in coins])
df.index = range(1, len(df) + 1)
st.dataframe(
    df, use_container_width=True, height=min(38 * len(df) + 40, 720),
    column_config={
        "Market cap": st.column_config.NumberColumn(format="dollar"),
        "Share": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=100),
        "Price": st.column_config.NumberColumn(format="$%.4f"),
        "Off peg %": st.column_config.NumberColumn(format="%.3f%%"),
    },
)
st.markdown('<div class="footer-note">Data: DefiLlama · alternative.me · Etherscan · refreshes every 10 minutes</div>',
            unsafe_allow_html=True)
