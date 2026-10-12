from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from alerts import check_and_show_alerts
from chainintel_core import RISK_WEIGHTS
from styles import LEVEL_HEX, card, esc, fmt_price, fmt_usd, risk_hex, section
from ui import auto_refresh, get_engine, header

engine = get_engine()
auto_refresh(60)

header("Overview", "Live risk across the nine largest stablecoins",
       f'<div class="note"><span class="live-dot"></span>Updated {datetime.now():%I:%M %p} · refreshes every minute</div>')

with st.spinner("Assessing all stablecoins — the first load takes ~20 seconds while the sentiment model warms up…"):
    data = engine.assess_all()
    fg = engine.get_fear_greed()
    market = engine.get_stablecoin_market_caps()

risks = {t: d["risk"]["total"] for t, d in data.items()}
check_and_show_alerts(risks)

# ── Status banner ──────────────────────────────────────────────────────────────
off_peg  = [t for t, d in data.items() if d["ml"]["label"] == "Off peg now"]
critical = [t for t, d in data.items() if d["level"] == "critical"]
elevated = [t for t, d in data.items() if d["level"] == "elevated"]
ml_watch = [t for t, d in data.items() if d["ml"]["probability"] is not None and d["ml"]["level"] != "stable"]
scored   = [r for r in risks.values() if r is not None]

if not scored:
    level, title, sub = "unknown", "Live data is unavailable", "Price sources couldn't be reached. Retrying every minute."
elif off_peg or critical:
    level = "critical"
    title = (f"{', '.join(off_peg)} {'is' if len(off_peg) == 1 else 'are'} off peg" if off_peg
             else f"{', '.join(critical)} in the critical zone")
    sub = " · ".join(f"{t} {fmt_price(data[t]['price'])}" for t in (off_peg or critical))
elif elevated or ml_watch:
    level = "elevated"
    watch = sorted(set(elevated) | set(ml_watch))
    title = f"{len(watch)} coin{'s' if len(watch) != 1 else ''} to watch"
    sub = ", ".join(watch) + " — elevated risk score or 7-day depeg forecast"
else:
    level, title, sub = "stable", f"All {len(data)} stablecoins look stable", "Every coin is on peg with low composite risk and low forecast risk."

st.markdown(f"""
<div class="status status-{level}">
  <div><div class="status-title" style="color:{LEVEL_HEX[level]};">{esc(title)}</div><div class="status-sub">{esc(sub)}</div></div>
</div>""", unsafe_allow_html=True)

# ── KPIs ───────────────────────────────────────────────────────────────────────
avg = sum(scored) / len(scored) if scored else None
on_peg = sum(1 for d in data.values() if d["price"] is not None and abs(d["price"] - 1) < 0.005)
k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.markdown(card("Average risk", f"{avg:.1f}" if avg is not None else "—", "composite, 0–100", color=risk_hex(avg)),
                unsafe_allow_html=True)
with k2:
    st.markdown(card("On peg", f"{on_peg}<span style='font-size:15px;color:var(--muted);'>/{len(data)}</span>",
                     "within 0.5% of $1", color=LEVEL_HEX["stable" if on_peg == len(data) else "elevated"]),
                unsafe_allow_html=True)
with k3:
    st.markdown(card("Forecast watchlist", str(len(ml_watch)), ", ".join(ml_watch) or "no elevated 7-day forecasts",
                     color=LEVEL_HEX["elevated" if ml_watch else "stable"]), unsafe_allow_html=True)
with k4:
    if fg:
        fg_color = "#22c55e" if fg["value"] >= 55 else "#f59e0b" if fg["value"] >= 35 else "#ef4444"
        st.markdown(card("Fear & Greed", str(fg["value"]), esc(fg["label"]), color=fg_color), unsafe_allow_html=True)
    else:
        st.markdown(card("Fear & Greed", "—", "unavailable"), unsafe_allow_html=True)
with k5:
    supply = sum(c["market_cap"] for c in market) if market else None
    st.markdown(card("Stablecoin supply", fmt_usd(supply), "top 25, all chains"), unsafe_allow_html=True)

# ── Watchlist ──────────────────────────────────────────────────────────────────
st.markdown(section("Watchlist"), unsafe_allow_html=True)
STATUS = {"stable": "🟢 Stable", "elevated": "🟡 Elevated", "critical": "🔴 Critical", "unknown": "⚪ No data"}
rows = []
for t, d in data.items():
    daily = engine.get_daily_prices(t)
    spark = daily.sort_index().tail(30).tolist() if daily is not None else []
    if spark and d["price"] is not None:
        spark[-1] = d["price"]
    if spark:                                   # scale each row to its own range so calm coins still show their shape
        lo, hi = min(spark), max(spark)
        spark = [round((v - lo) / (hi - lo), 4) if hi > lo else 0.5 for v in spark]
    ml = d["ml"]
    rows.append({
        "Coin": t, "Issuer": d["cfg"]["issuer"], "Price": d["price"],
        "Off peg (bps)": abs(d["price"] - 1) * 10_000 if d["price"] is not None else None,
        "Liquidity": d["liquidity"], "Risk": risks[t],
        "7d depeg": ml["probability"] if ml["probability"] is not None else (100.0 if ml["label"] == "Off peg now" else None),
        "Status": STATUS[d["level"]], "30-day price": spark,
    })
df = pd.DataFrame(rows)
event = st.dataframe(
    df, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row", key="watchlist",
    height=35 * (len(df) + 1) + 3,
    column_config={
        "Price": st.column_config.NumberColumn(format="$%.4f"),
        "Off peg (bps)": st.column_config.NumberColumn(format="%.1f", help="Basis points from $1.00 (100 bps = 1%)"),
        "Liquidity": st.column_config.NumberColumn(format="compact", help="On-chain DEX liquidity on Ethereum (DexScreener)"),
        "Risk": st.column_config.ProgressColumn(format="%.1f", min_value=0, max_value=100,
                                                help="Composite: 50% peg · 30% liquidity · 20% news sentiment"),
        "7d depeg": st.column_config.NumberColumn(format="%.1f%%", help="Model probability of trading ≥1% off peg within 7 days. 100% = already off peg."),
        "30-day price": st.column_config.LineChartColumn(width="medium", y_min=0, y_max=1,
                                                        help="Daily price shape over 30 days, scaled per coin"),
    },
)
st.caption("Click a row to open that coin in Monitor.")
if event.selection.rows:
    st.session_state["selected_asset"] = df.iloc[event.selection.rows[0]]["Coin"]
    st.switch_page("views/monitor.py")

# ── What drives each score + history ───────────────────────────────────────────
left, right = st.columns([1.35, 1])
with left:
    st.markdown(section("What drives each risk score"), unsafe_allow_html=True)
    with st.container(border=True):
        tickers = [t for t in data if risks[t] is not None]
        fig = go.Figure()
        for comp, color, name in [("peg", "#4f8cff", "Peg"), ("liquidity", "#a78bfa", "Liquidity"), ("sentiment", "#f59e0b", "Sentiment")]:
            vals = []
            for t in tickers:
                r = data[t]["risk"]
                weight = sum(RISK_WEIGHTS[k] for k in r["used"])
                vals.append(r[comp] * RISK_WEIGHTS[comp] / weight if r[comp] is not None else 0)
            fig.add_trace(go.Bar(name=name, y=tickers, x=vals, orientation="h", marker_color=color,
                                 hovertemplate="%{y} · " + name + ": %{x:.1f} pts<extra></extra>"))
        fig.update_layout(barmode="stack", height=320, legend=dict(orientation="h", y=1.08))
        fig.update_xaxes(range=[0, 100], title="Points contributed to the composite score")
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with right:
    st.markdown(section("Notable depeg events"), unsafe_allow_html=True)
    EVENTS = [
        ("Mar 2023", "USDC", "$0.877", "Silicon Valley Bank failure — $3.3B of reserves stuck at the bank"),
        ("Mar 2023", "FRAX", "$0.874", "USDC contagion — FRAX was partly backed by USDC"),
        ("Mar 2023", "DAI",  "$0.897", "Over half of DAI's collateral was USDC"),
        ("May 2022", "USDT", "$0.948", "UST/LUNA's $40B collapse sparked a stablecoin-wide run"),
        ("Oct 2018", "USDT", "$0.850", "Reserve transparency fears — USDT's worst depeg on record"),
    ]
    for date, coin, low, cause in EVENTS:
        st.markdown(f"""
        <div class="card-sm" style="display:flex;gap:14px;align-items:baseline;">
          <div style="width:44px;font-weight:800;color:var(--text);">{coin}</div>
          <div style="width:58px;font-weight:800;color:var(--red);">{low}</div>
          <div style="flex:1;font-size:12.5px;color:var(--text-2);line-height:1.45;">{cause}
            <div class="note">{date}</div></div>
        </div>""", unsafe_allow_html=True)

st.markdown('<div class="footer-note">Data: CoinGecko · DefiLlama · DexScreener · Google News · Etherscan · '
            'FinBERT sentiment · Not financial advice</div>', unsafe_allow_html=True)
