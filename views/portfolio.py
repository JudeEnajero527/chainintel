import plotly.graph_objects as go
import streamlit as st

from alerts import check_and_show_alerts
from auth import get_current_user, load_portfolio, save_portfolio
from chainintel_core import ASSETS, WORST_CASE
from styles import PLOT_LAYOUT, card, empty_state, fmt_price, fmt_usd, risk_hex, section, status_pill
from ui import get_engine, header

engine = get_engine()
header("Portfolio", "Enter your stablecoin holdings to see expected loss and how you'd fare in a repeat of past crises")

SCENARIOS = {
    "SVB replay (Mar 2023)": {"USDC": 0.877, "DAI": 0.897, "FRAX": 0.874},
    "UST contagion (May 2022)": {"USDT": 0.948, "FRAX": 0.97},
    "Every coin at its worst-ever price": WORST_CASE,
}

# ── Holdings ───────────────────────────────────────────────────────────────────
st.markdown(section("Your holdings (USD face value)"), unsafe_allow_html=True)
user = get_current_user()
if "saved_holdings" not in st.session_state:
    st.session_state.saved_holdings = load_portfolio(user["id"])
saved = st.session_state.saved_holdings

holdings = {}
tickers = list(ASSETS)
for row in (tickers[:5], tickers[5:]):
    cols = st.columns(5)
    for col, t in zip(cols, row):
        with col:
            holdings[t] = float(st.number_input(t, min_value=0, value=int(saved.get(t, 0)), step=1000, format="%d", key=f"hold_{t}"))
if holdings != {t: float(saved.get(t, 0)) for t in tickers}:
    save_portfolio(user["id"], holdings)
    st.session_state.saved_holdings = holdings
st.caption("Saved to your account automatically.")

total = sum(holdings.values())
if total == 0:
    st.markdown(empty_state("💼", "Enter your holdings above", "Add a dollar amount for each stablecoin you hold."),
                unsafe_allow_html=True)
    st.stop()

with st.spinner("Scoring your holdings…"):
    data = engine.assess_all()
check_and_show_alerts({t: data[t]["risk"]["total"] for t in holdings if holdings[t] > 0})

rows = []
for t, amount in holdings.items():
    if amount <= 0:
        continue
    d = data[t]
    price, ml = d["price"], d["ml"]
    severity = 1 - WORST_CASE[t]
    if ml["label"] == "Off peg now" and price is not None:
        expected = amount * max(0.0, 1 - price)          # already depegged: the loss is real today
    elif ml["probability"] is not None:
        expected = amount * ml["probability"] / 100 * severity
    else:
        expected = None
    rows.append({
        "ticker": t, "amount": amount, "price": price, "value": amount * price if price is not None else None,
        "risk": d["risk"]["total"], "ml": ml, "expected": expected, "worst": amount * severity,
    })

known_value = [r["value"] for r in rows if r["value"] is not None]
expected_known = [r["expected"] for r in rows if r["expected"] is not None]
scored = [r for r in rows if r["risk"] is not None]
weighted = sum(r["risk"] * r["amount"] for r in scored) / sum(r["amount"] for r in scored) if scored else None
top_share = max(r["amount"] for r in rows) / total
top_coin = max(rows, key=lambda r: r["amount"])["ticker"]

m1, m2, m3, m4 = st.columns(4)
with m1:
    mtm = sum(known_value)
    st.markdown(card("Market value today", fmt_usd(mtm, 2),
                     f"{fmt_usd(mtm - sum(r['amount'] for r in rows if r['value'] is not None), 2)} vs. face value"),
                unsafe_allow_html=True)
with m2:
    st.markdown(card("Weighted risk score", f"{weighted:.1f}" if weighted is not None else "—", status_pill(weighted),
                     color=risk_hex(weighted), border=risk_hex(weighted)), unsafe_allow_html=True)
with m3:
    exp = sum(expected_known)
    st.markdown(card("Expected loss · next 7 days", fmt_usd(exp, 2),
                     f"{exp / total * 100:.3f}% · forecast × historical severity", color="#f59e0b"), unsafe_allow_html=True)
with m4:
    st.markdown(card("Largest position", f"{top_share*100:.0f}%", f"in {top_coin}" + (" — concentrated" if top_share > 0.6 and len(rows) > 0 else ""),
                     color="#ef4444" if top_share > 0.8 else None), unsafe_allow_html=True)

# ── Charts ─────────────────────────────────────────────────────────────────────
left, right = st.columns([1, 1])
with left:
    st.markdown(section("Composition"), unsafe_allow_html=True)
    with st.container(border=True):
        fig = go.Figure(go.Pie(
            labels=[r["ticker"] for r in rows], values=[r["amount"] for r in rows], hole=0.6, sort=False,
            marker=dict(colors=[ASSETS[r["ticker"]]["color"] for r in rows], line=dict(color="#080910", width=3)),
            textinfo="label+percent", textfont=dict(color="#f9fafb", size=13),
        ))
        fig.update_layout(**PLOT_LAYOUT, height=300, showlegend=False,
                          annotations=[dict(text=fmt_usd(total, 1), x=0.5, y=0.5, showarrow=False,
                                            font=dict(size=22, color="#f9fafb"))])
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with right:
    st.markdown(section("Expected vs. worst-case loss"), unsafe_allow_html=True)
    with st.container(border=True):
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(name="Expected (7d)", x=[r["ticker"] for r in rows], y=[r["expected"] or 0 for r in rows],
                              marker_color=[risk_hex(r["risk"]) for r in rows]))
        fig2.add_trace(go.Bar(name="Worst case (history)", x=[r["ticker"] for r in rows], y=[r["worst"] for r in rows],
                              marker_color="rgba(239,68,68,.35)"))
        fig2.update_layout(**PLOT_LAYOUT, height=300, barmode="group",
                           legend=dict(orientation="h", y=1.08, bgcolor="rgba(0,0,0,0)"))
        fig2.update_yaxes(tickprefix="$", type="log")
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
    st.markdown('<div class="note">Log scale — expected losses are usually orders of magnitude smaller than worst cases.</div>',
                unsafe_allow_html=True)

# ── Per-asset table ────────────────────────────────────────────────────────────
st.markdown(section("By asset"), unsafe_allow_html=True)
for r in rows:
    ml = r["ml"]
    prob = f"{ml['probability']:.1f}%" if ml["probability"] is not None else ml["label"]
    st.markdown(f"""
    <div class="data-row" style="flex-wrap:wrap;gap:16px;">
      <div style="font-size:17px;font-weight:800;color:#f1f5f9;width:70px;">{r['ticker']}</div>
      <div style="flex:1;min-width:110px;"><div class="note">Holding</div><div style="font-weight:700;color:#f1f5f9;">{fmt_usd(r['amount'], 2)}</div></div>
      <div style="flex:1;min-width:110px;"><div class="note">Price</div><div style="font-weight:700;color:#f1f5f9;">{fmt_price(r['price'])}</div></div>
      <div style="flex:1;min-width:110px;"><div class="note">7d depeg prob.</div><div style="font-weight:700;color:#a78bfa;">{prob}</div></div>
      <div style="flex:1;min-width:110px;"><div class="note">Expected loss</div><div style="font-weight:700;color:#f59e0b;">{fmt_usd(r['expected'], 2)}</div></div>
      <div style="flex:1;min-width:110px;"><div class="note">Worst case</div><div style="font-weight:700;color:#ef4444;">{fmt_usd(r['worst'], 1)}</div>
        <div class="note">at ${WORST_CASE[r['ticker']]}</div></div>
      <div style="min-width:120px;text-align:right;">{status_pill(r['risk'])}</div>
    </div>""", unsafe_allow_html=True)

# ── Stress tests ───────────────────────────────────────────────────────────────
st.markdown(section("Stress test: what if history repeats?"), unsafe_allow_html=True)
cols = st.columns(len(SCENARIOS) + 1)
for col, (name, shocks) in zip(cols, SCENARIOS.items()):
    loss = sum(r["amount"] * (1 - shocks[r["ticker"]]) for r in rows if r["ticker"] in shocks)
    hit = [r["ticker"] for r in rows if r["ticker"] in shocks]
    with col:
        st.markdown(card(name, f"-{fmt_usd(loss, 1)}", f"{loss/total*100:.1f}% of portfolio · hits {', '.join(hit) or 'none of your coins'}",
                         color="#ef4444" if loss else "#22c55e"), unsafe_allow_html=True)
with cols[-1]:
    with st.container(border=True):
        shock_coin = st.selectbox("Custom: shock one coin", [r["ticker"] for r in rows])
        shock_price = st.slider("…to price", 0.50, 1.00, 0.90, 0.01, format="$%.2f")
        loss = holdings[shock_coin] * (1 - shock_price)
        st.markdown(f'<div style="font-size:24px;font-weight:800;color:#ef4444;">-{fmt_usd(loss, 1)}</div>'
                    f'<div class="note">{loss/total*100:.1f}% of portfolio</div>', unsafe_allow_html=True)

st.markdown('<div class="footer-note">Expected loss = 7-day depeg probability × the coin\'s worst historical drawdown. '
            'Coins already off peg use today\'s actual discount. Not financial advice.</div>', unsafe_allow_html=True)
