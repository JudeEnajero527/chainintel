import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from depeg_model import FEATURE_LABELS
from styles import LEVEL_HEX, PLOT_LAYOUT, card, empty_state, esc, fmt_price, fmt_prob, risk_hex, section, status_pill
from ui import get_engine, auto_refresh, header

engine = get_engine()
auto_refresh(300)
header("Depeg forecasts", "7-day depeg forecasts, and exactly how good the model is")

meta = engine.model_meta
m = meta.get("metrics", {})
if engine.model is None:
    st.markdown(empty_state("🤖", "Depeg model not trained", "Run <code>python3 train_model.py</code> (takes about a minute)."),
                unsafe_allow_html=True)
    st.stop()

with st.spinner("Scoring all assets…"):
    data = engine.assess_all()

# ── Forecast cards ─────────────────────────────────────────────────────────────
st.markdown(section(f"Probability of a ≥{meta['depeg_threshold']:.0%} depeg in the next {meta['horizon_days']} days"),
            unsafe_allow_html=True)


def forecast_card(t, d):
    ml = d["ml"]
    color = LEVEL_HEX[ml["level"]]
    prob = fmt_prob(ml["probability"])
    f = ml.get("features") or {}
    drivers = ""
    if f:
        drivers = (f"30d volatility {f['vol_30d']*100:.3f}% · off-peg days (30d) {f['offpeg_days_30d']:.0f} · "
                   f"worst 7d deviation {f['max_abs_dev_7d']*100:.2f}%")
    return f"""
    <div class="card" style="border-color:{color}33;padding:18px;">
      <div style="display:flex;justify-content:space-between;align-items:center;">
        <div style="font-size:16px;font-weight:800;color:#f1f5f9;">{t}</div>
        {status_pill(level=ml['level'], text=ml['label'])}
      </div>
      <div style="font-size:34px;font-weight:900;color:{color};letter-spacing:-1.5px;margin:10px 0 2px;">{prob}</div>
      <div class="note">price {fmt_price(d['price'])}</div>
      <div class="note" style="margin-top:8px;">{drivers}</div>
    </div>"""


tickers = list(data)
for row in (tickers[:5], tickers[5:]):
    cols = st.columns(5)
    for col, t in zip(cols, row):
        with col:
            st.markdown(forecast_card(t, data[t]), unsafe_allow_html=True)

st.markdown('<div class="note" style="margin-top:4px;">Forecasts cover fiat-backed coins (USDC, USDT, PYUSD, TUSD) and '
            'crypto-backed or synthetic dollars (DAI, LUSD, crvUSD, USDe, FRAX), because all of them can lose their peg. '
            'The 9-coin composite risk score on this site is separate from the ChainIntel v1.0 methodology, which scores fiat-backed coins only.</div>',
            unsafe_allow_html=True)

# ── Model report card ──────────────────────────────────────────────────────────
st.markdown(section("Model report card"), unsafe_allow_html=True)
st.markdown(f"""
<div class="banner">
  <strong style="color:#f1f5f9;">The question:</strong> {esc(meta['question'])}<br>
  <strong style="color:#f1f5f9;">Trained on:</strong> {meta['coins']} USD stablecoins, {meta['data_start']} → {meta['data_end']}
  ({meta['training_rows']:,} coin-days), including every coin DefiLlama tracks — not only the nine above — so the model has seen
  hundreds of real depeg episodes.<br>
  <strong style="color:#f1f5f9;">Tested on:</strong> {m['test_start']} → {m['test_end']} — data the model never saw during training
  ({m['test_rows']:,} coin-days, {m['test_positives']:,} of which were followed by a depeg).
</div>""", unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
with k1:
    st.markdown(card("PR-AUC (main score)", f"{m['pr_auc']:.2f}",
                     f"Naive rule: {m['pr_auc_baseline']:.2f} · random guess: {m['prevalence']:.2f}", color="#a78bfa"),
                unsafe_allow_html=True)
with k2:
    st.markdown(card("Depegs caught", f"{m['recall_at_alert']*100:.0f}%",
                     f"of real depegs got a ≥{m['alert_threshold']*100:.0f}% warning beforehand", color="#22c55e"),
                unsafe_allow_html=True)
with k3:
    st.markdown(card("Warnings that were right", f"{m['precision_at_alert']*100:.0f}%",
                     f"of ≥{m['alert_threshold']*100:.0f}% warnings were followed by a depeg", color="#f59e0b"),
                unsafe_allow_html=True)
with k4:
    st.markdown(card("ROC-AUC", f"{m['roc_auc']:.2f}", f"Brier score {m['brier']:.3f} (probabilities are calibrated)"),
                unsafe_allow_html=True)

variants = m.get("variants")
if variants:
    st.markdown('<div class="note" style="margin-bottom:8px;">Inputs tested: ' + " · ".join(
        f"{esc(k)} → PR-AUC {v:.3f}" for k, v in variants.items()) + f'. The live model uses <strong>{esc(meta.get("feature_set", "price"))}</strong> '
        "(chosen on the validation period, before looking at the test period). Supply flows turned out to add little: "
        "price behaviour carries almost all the signal.</div>", unsafe_allow_html=True)
large = m.get("large_coins")
if large and large.get("scored"):
    st.markdown(
        f'<div class="note" style="margin-bottom:8px;"><strong>Large coins only</strong> (≥${large["min_supply_usd"]/1e9:.0f}B in '
        f'circulation, {large["coins"]} coins, {large["rows"]:,} coin-days, {large["positives"]:,} followed by a depeg): '
        f'PR-AUC {large["pr_auc"]:.2f} (naive rule {large["pr_auc_baseline"]:.2f}, random guess {large["prevalence"]:.2f}) · '
        f'depegs caught {large["recall_at_alert"]*100:.0f}% · warnings right {large["precision_at_alert"]*100:.0f}%. '
        'Depegs are much rarer among large coins, so these numbers are the stricter test.</div>',
        unsafe_allow_html=True)
elif large:
    eps = large.get("episodes", [])
    counts = {}
    for e in eps:
        counts[e["coin"]] = counts.get(e["coin"], 0) + 1
    which = ", ".join(f"{esc(c)} ×{n}" if n > 1 else esc(c) for c, n in counts.items())
    warned = sum(e["warned"] for e in eps)
    detail = (f" ({which}). The model gave a ≥{m['alert_threshold']*100:.0f}% warning before {warned} of them"
              if eps else "")
    st.markdown(
        f'<div class="note" style="margin-bottom:8px;"><strong>Large coins only</strong> (≥${large["min_supply_usd"]/1e9:.0f}B in '
        f'circulation, {large["coins"]} coins): {len(eps)} separate depeg episode{"s" if len(eps) != 1 else ""} in the test '
        f'period{detail}. That\'s too few to score the model fairly on large coins (at least {large.get("min_episodes", 10)} '
        'are needed), so no accuracy figure is shown for this group.</div>',
        unsafe_allow_html=True)
st.markdown('<div class="note">PR-AUC is the honest headline number for rare events: it measures how well the model ranks '
            'coins that will depeg above those that won\'t, and doesn\'t get inflated by the many calm days. '
            f'Retrain any time with <code>python3 train_model.py</code> (last trained {esc(meta["trained_at"])}).</div>',
            unsafe_allow_html=True)

left, right = st.columns([1, 1])
with left:
    st.markdown(section("What the model pays attention to"), unsafe_allow_html=True)
    imp = meta.get("importance", {})
    names = [FEATURE_LABELS.get(k, k) for k in imp][::-1]
    vals = list(imp.values())[::-1]
    with st.container(border=True):
        fig = go.Figure(go.Bar(x=vals, y=names, orientation="h",
                               marker=dict(color=["#3b82f6" if v > 0.02 else "#1e3a5f" for v in vals])))
        fig.update_layout(**PLOT_LAYOUT, height=340)
        fig.update_xaxes(title="Importance (PR-AUC drop when shuffled)")
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

with right:
    st.markdown(section("Composite risk vs. ML forecast"), unsafe_allow_html=True)
    pts = [(t, d["risk"]["total"], d["ml"]["probability"]) for t, d in data.items()
           if d["risk"]["total"] is not None and d["ml"]["probability"] is not None]
    with st.container(border=True):
        if pts:
            fig = go.Figure(go.Scatter(
                x=[p[1] for p in pts], y=[p[2] for p in pts], mode="markers+text",
                text=[p[0] if p[1] >= 30 or p[2] >= 10 else "" for p in pts], customdata=[p[0] for p in pts],
                textposition="top center", textfont=dict(color="#f1f5f9", size=12),
                marker=dict(size=16, color=[risk_hex(p[1]) for p in pts], line=dict(color="#0d0f14", width=2)),
                hovertemplate="%{customdata}<br>Risk %{x:.1f}<br>Depeg prob %{y:.1f}%<extra></extra>",
            ))
            fig.update_layout(**PLOT_LAYOUT, height=340)
            fig.update_xaxes(title="Composite risk score (today)", range=[0, 100])
            fig.update_yaxes(title="7-day depeg probability (%)", rangemode="tozero")
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown(empty_state("📉", "Nothing to plot", "No asset has both a risk score and a forecast."),
                        unsafe_allow_html=True)
    st.markdown('<div class="note">Hover a dot for its name; only coins with notable risk are labelled. The composite score describes <em>today</em>; the forecast estimates the <em>next week</em>. '
                'A coin can look calm today and still carry forecast risk if its recent history has been shaky.</div>',
                unsafe_allow_html=True)

# ── Live track record ──────────────────────────────────────────────────────────
st.markdown(section("Live track record"), unsafe_allow_html=True)
record = engine.forecast_record()
done = record[record["outcome"].notna()]
if done.empty:
    pending = len(record)
    st.markdown(empty_state("🗓️", "No forecasts have been scored yet",
                            f"ChainIntel saves each coin's forecast once a day ({pending} saved so far) and scores it after its "
                            "7-day window closes. Results appear here from then on. Keep the background collector running "
                            "so a forecast is saved every day."), unsafe_allow_html=True)
else:
    y, p = done["outcome"].astype(int), done["probability"] / 100
    alerts = p >= m["alert_threshold"]
    t1, t2, t3, t4 = st.columns(4)
    with t1:
        st.markdown(card("Forecasts scored", f"{len(done):,}", f"{int(y.sum())} were followed by a depeg"), unsafe_allow_html=True)
    with t2:
        brier = float(((p - y) ** 2).mean())
        st.markdown(card("Brier score", f"{brier:.3f}", f"lower is better · test period: {m['brier']:.3f}"), unsafe_allow_html=True)
    with t3:
        caught = f"{(alerts & (y == 1)).sum()}/{int(y.sum())}" if y.sum() else "—"
        st.markdown(card("Depegs warned about", caught, f"forecast ≥{m['alert_threshold']*100:.0f}% beforehand"), unsafe_allow_html=True)
    with t4:
        false_alarms = int((alerts & (y == 0)).sum())
        st.markdown(card("False alarms", str(false_alarms), f"of {int(alerts.sum())} warnings"), unsafe_allow_html=True)
    show = done.head(40).assign(
        Forecast=lambda d: d["probability"].map(fmt_prob),
        Outcome=lambda d: d["outcome"].map({1: "🔴 Depegged", 0: "🟢 Held peg"}),
        **{"Worst move": lambda d: (d["max_dev"] * 100).map(lambda v: f"{v:.2f}%")},
    )[["date", "ticker", "Forecast", "Outcome", "Worst move"]].rename(columns={"date": "Forecast date", "ticker": "Coin"})
    st.dataframe(show, hide_index=True, use_container_width=True)
    st.caption("Each forecast is scored on whether the coin traded ≥1% off peg in the 7 days after it was made (DefiLlama daily prices).")

# ── Scenario simulator ─────────────────────────────────────────────────────────
st.markdown(section("Scenario simulator"), unsafe_allow_html=True)
st.markdown('<div class="note" style="margin-bottom:12px;">Build a made-up 90-day price history and see what the model '
            'predicts. Useful for building intuition about which patterns it treats as warning signs.</div>',
            unsafe_allow_html=True)

s1, s2, s3 = st.columns(3)
with s1:
    sim_price = st.slider("Price today ($)", 0.9950, 1.0050, 0.9990, 0.0005, format="%.4f")
with s2:
    sim_vol = st.slider("Daily price noise over the last 30 days (%)", 0.00, 0.50, 0.05, 0.01, format="%.2f")
with s3:
    sim_wobbles = st.slider("Days ≥0.5% off peg in the last 30", 0, 10, 0)

rng = np.random.default_rng(7)
idx = pd.date_range(end=pd.Timestamp.today().normalize(), periods=90, freq="D")
series = 1 + rng.normal(0, 0.0003, 90)                              # calm first 60 days
series[-30:] = 1 + rng.normal(0, sim_vol / 100, 30)
for k in rng.choice(np.arange(60, 88), size=sim_wobbles, replace=False):
    series[k] = 1 - 0.006 - rng.uniform(0, 0.004)                   # brief dips below the 0.5% band
series[-1] = sim_price
sim = engine.predict_from_prices(pd.Series(series, index=idx))

o1, o2 = st.columns([1, 2])
with o1:
    prob = sim["probability"]
    st.markdown(card("Model output", fmt_prob(prob), esc(sim["label"]),
                     color=LEVEL_HEX[sim["level"]], border=LEVEL_HEX[sim["level"]]), unsafe_allow_html=True)
with o2, st.container(border=True):
    fig = go.Figure(go.Scatter(x=idx, y=series, mode="lines", line=dict(color="#a78bfa", width=1.5)))
    fig.add_hrect(y0=0.995, y1=1.005, fillcolor="rgba(34,197,94,.06)", line_width=0)
    fig.update_layout(**PLOT_LAYOUT, height=170)
    fig.update_yaxes(tickformat="$.3f")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
