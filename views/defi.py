import plotly.graph_objects as go
import streamlit as st

from styles import PLOT_LAYOUT, card, empty_state, esc, fmt_pct, fmt_usd, section
from ui import get_engine, auto_refresh, header

engine = get_engine()
auto_refresh(600)
header("DeFi protocols", "Total value locked in the protocols stablecoins depend on")

with st.spinner("Loading protocol data…"):
    protocols = engine.get_defi_protocols()

if not protocols:
    st.markdown(empty_state("🏦", "Protocol data unavailable", "DefiLlama could not be reached. Retrying shortly."),
                unsafe_allow_html=True)
    st.stop()

DESC = {
    "MakerDAO":    "Issuer of DAI. Collateralised debt positions back the largest decentralised stablecoin.",
    "Sky":         "MakerDAO's successor brand, issuer of USDS and DAI.",
    "Aave V3":     "The largest lending market. Sharp TVL drops mean users pulling collateral — often a precursor to stress.",
    "Compound V3": "Money market. High utilisation means heavy borrowing demand and more liquidation risk in a sell-off.",
    "Curve":       "The main DEX for stablecoin swaps. Imbalanced Curve pools are one of the earliest on-chain depeg signals.",
    "Uniswap V3":  "Largest DEX by volume; stablecoin pool depth is a key liquidity signal.",
    "Convex":      "Yield optimiser on Curve. TVL reflects confidence in the Curve ecosystem.",
    "Lido":        "Liquid ETH staking. stETH is collateral everywhere in DeFi — a stETH discount signals contagion risk.",
    "Spark":       "Sky/MakerDAO's lending arm; manages DAI liquidity.",
    "Ethena":      "Issuer of USDe, a synthetic dollar backed by hedged crypto positions.",
    "Frax":        "Issuer of FRAX and frxUSD.",
    "Liquity":     "Issuer of LUSD, a fully ETH-collateralised stablecoin.",
}

total = sum(p["tvl"] for p in protocols)
with_1d = [p for p in protocols if p["change_1d"] is not None]
best = max(with_1d, key=lambda p: p["change_1d"]) if with_1d else None
worst = min(with_1d, key=lambda p: p["change_1d"]) if with_1d else None

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(card("Total TVL tracked", fmt_usd(total), f"{len(protocols)} protocols"), unsafe_allow_html=True)
with c2:
    st.markdown(card("Best 24h", fmt_pct(best["change_1d"]) if best else "—", esc(best["name"]) if best else "",
                     color="#22c55e" if best and best["change_1d"] >= 0 else "#ef4444"), unsafe_allow_html=True)
with c3:
    st.markdown(card("Worst 24h", fmt_pct(worst["change_1d"]) if worst else "—", esc(worst["name"]) if worst else "",
                     color="#ef4444" if worst and worst["change_1d"] < 0 else "#22c55e"), unsafe_allow_html=True)

st.markdown(section("TVL and 7-day change"), unsafe_allow_html=True)
with st.container(border=True):
    fig = go.Figure(go.Bar(
        x=[p["name"] for p in protocols], y=[p["tvl"] for p in protocols],
        marker_color=["#22c55e" if (p["change_7d"] or 0) >= 0 else "#ef4444" for p in protocols],
        text=[fmt_pct(p["change_7d"]) for p in protocols], textposition="outside", textfont=dict(color="#94a3b8"),
        hovertemplate="<b>%{x}</b><br>TVL $%{y:,.0f}<extra></extra>",
    ))
    fig.update_layout(**PLOT_LAYOUT, height=300)
    fig.update_yaxes(tickprefix="$")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
st.markdown('<div class="note">Bar colour and label = 7-day TVL change (green up, red down).</div>', unsafe_allow_html=True)

st.markdown(section("Protocol detail"), unsafe_allow_html=True)
for p in protocols:
    chains = ", ".join(p["chains"][:5]) + ("…" if len(p["chains"]) > 5 else "")
    col1d = "#22c55e" if (p["change_1d"] or 0) >= 0 else "#ef4444"
    col7d = "#22c55e" if (p["change_7d"] or 0) >= 0 else "#ef4444"
    st.markdown(f"""
    <div class="card" style="padding:18px 22px;">
      <div style="display:flex;justify-content:space-between;gap:20px;flex-wrap:wrap;">
        <div style="flex:1;min-width:240px;">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
            <div style="font-size:17px;font-weight:800;color:#f1f5f9;">{esc(p['name'])}</div>
            <span class="note" style="border:1px solid rgba(255,255,255,.08);border-radius:5px;padding:1px 7px;">{esc(p['category'])}</span>
          </div>
          <div class="note" style="max-width:520px;color:#94a3b8;">{esc(DESC.get(p['name'], ''))}</div>
          <div class="note" style="margin-top:6px;">Chains: {esc(chains)}</div>
        </div>
        <div style="display:flex;gap:28px;align-items:center;">
          <div style="text-align:center;"><div class="note">TVL</div>
            <div style="font-size:22px;font-weight:800;color:#f1f5f9;">{fmt_usd(p['tvl'], 2)}</div>
            <div class="note">{p['tvl']/total*100:.1f}% of tracked</div></div>
          <div style="text-align:center;"><div class="note">24h</div>
            <div style="font-size:18px;font-weight:800;color:{col1d};">{fmt_pct(p['change_1d'])}</div></div>
          <div style="text-align:center;"><div class="note">7d</div>
            <div style="font-size:18px;font-weight:800;color:{col7d};">{fmt_pct(p['change_7d'])}</div></div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

st.markdown('<div class="footer-note">Data: DefiLlama · refreshes every 10 minutes</div>', unsafe_allow_html=True)
