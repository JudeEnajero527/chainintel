from datetime import datetime

import plotly.graph_objects as go
import streamlit as st

from alerts import check_and_show_alerts
from styles import (LEVEL_HEX, PLOT_LAYOUT, card, esc, fmt_price, fmt_usd, risk_hex, risk_level, section,
                    status_pill)
from ui import page

engine, _ = page("Home", "⬡", refresh_seconds=60)

st.markdown("""
<style>
.hero { position:relative; padding:36px 0 32px; overflow:hidden; margin-bottom:8px; }
.hero-orb { position:absolute; border-radius:50%; filter:blur(100px); opacity:.13; pointer-events:none; }
.hero-orb-1 { width:520px;height:520px;background:#3b82f6;top:-260px;left:-120px; }
.hero-orb-2 { width:400px;height:400px;background:#a78bfa;top:-180px;right:-80px; }
.hero-inner { position:relative; z-index:1; }
.hero-eyebrow { font-size:11px; font-weight:700; letter-spacing:.14em; text-transform:uppercase; color:#3b82f6; margin-bottom:14px; }
.hero-title { font-size:46px; font-weight:900; color:#f1f5f9; letter-spacing:-2px; line-height:1.06; margin-bottom:14px; }
.hero-title .grad { background:linear-gradient(90deg,#60a5fa,#a78bfa 60%,#f472b6); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }
.hero-stats { display:flex; flex-wrap:wrap; border:1px solid rgba(255,255,255,.06); border-radius:14px; overflow:hidden; background:rgba(255,255,255,.02); }
.hero-stat { flex:1 1 120px; padding:14px 18px; border-right:1px solid rgba(255,255,255,.06); }
.hero-stat:last-child { border-right:none; }
.hero-stat-val { font-size:22px; font-weight:800; color:#f1f5f9; letter-spacing:-.8px; margin-bottom:3px; }
.hero-stat-label { font-size:11px; color:#64748b; font-weight:600; letter-spacing:.04em; text-transform:uppercase; }
.asset-card-v2 { background:rgba(255,255,255,.02); border:1px solid rgba(255,255,255,.07); border-radius:14px; padding:16px; margin-bottom:12px; }
.ac-row { display:flex; justify-content:space-between; align-items:flex-start; gap:8px; }
.ac-ticker { font-size:15px; font-weight:800; color:#f1f5f9; }
.ac-issuer { font-size:10px; color:#64748b; font-weight:600; text-transform:uppercase; letter-spacing:.05em; margin-top:1px; }
.ac-price { font-size:22px; font-weight:900; letter-spacing:-1px; margin:10px 0 0; }
.ac-meta { font-size:11px; color:#64748b; margin:2px 0 10px; }
.ac-bar-wrap { height:4px; background:rgba(255,255,255,.06); border-radius:999px; margin-bottom:8px; }
.ac-bar { height:4px; border-radius:999px; }
.ac-foot { display:flex; justify-content:space-between; font-size:11px; font-weight:600; }
.depeg-row { display:flex; align-items:center; gap:16px; padding:12px 18px; background:rgba(239,68,68,.03);
             border:1px solid rgba(239,68,68,.12); border-radius:12px; margin-bottom:8px; flex-wrap:wrap; }
</style>
""", unsafe_allow_html=True)

with st.spinner("Assessing all stablecoins — the first load takes ~20 seconds while the sentiment model warms up…"):
    data = engine.assess_all()
    fg = engine.get_fear_greed()
    gas = engine.get_gas_price()

risks = {t: d["risk"]["total"] for t, d in data.items()}
scored = {t: r for t, r in risks.items() if r is not None}
avg_risk = sum(scored.values()) / len(scored) if scored else None
highest = max(scored, key=scored.get) if scored else None
counts = {lvl: sum(1 for d in data.values() if d["level"] == lvl) for lvl in ("stable", "elevated", "critical")}
off_peg = [t for t, d in data.items() if d["ml"]["label"] == "Off peg now"]
ml_watch = [t for t, d in data.items() if d["ml"]["level"] in ("elevated", "critical") and d["ml"]["probability"] is not None]

check_and_show_alerts(risks)

# ── Ticker ───────────────────────────────────────────────────────────────────────
items = ""
for t, d in data.items():
    rc = risk_hex(risks[t])
    score = f"{risks[t]:.0f}" if risks[t] is not None else "—"
    items += (f'<span style="margin:0 28px;display:inline-flex;align-items:center;gap:10px;">'
              f'<span style="color:#94a3b8;font-size:11px;font-weight:700;letter-spacing:.06em;">{t}</span>'
              f'<span style="color:#f1f5f9;font-weight:700;font-size:13px;">{fmt_price(d["price"])}</span>'
              f'<span style="color:{rc};font-size:10px;background:{rc}18;border:1px solid {rc}33;border-radius:4px;padding:1px 6px;font-weight:700;">{score}</span></span>')
st.markdown(f'<div class="ticker-wrap"><div class="ticker-inner">{items * 3}</div></div>', unsafe_allow_html=True)

# ── Hero ─────────────────────────────────────────────────────────────────────────
lvl = risk_level(avg_risk)
status = {"stable": "All systems stable", "elevated": "Elevated risk detected",
          "critical": "Critical risk", "unknown": "Data unavailable"}[lvl]
fg_html = (f'<div class="hero-stat-val" style="color:{"#22c55e" if fg["value"] >= 55 else "#f59e0b" if fg["value"] >= 35 else "#ef4444"};">{fg["value"]}</div>'
           f'<div class="hero-stat-label">Fear &amp; Greed · {esc(fg["label"])}</div>') if fg else \
          '<div class="hero-stat-val" style="color:#64748b;">—</div><div class="hero-stat-label">Fear &amp; Greed</div>'
gas_html = (f'<div class="hero-stat-val">{gas["propose"]:.1f}</div><div class="hero-stat-label">Gas · Gwei</div>') if gas else \
           '<div class="hero-stat-val" style="color:#64748b;">—</div><div class="hero-stat-label">Gas · needs Etherscan key</div>'

st.markdown(f"""
<div class="hero">
  <div class="hero-orb hero-orb-1"></div><div class="hero-orb hero-orb-2"></div>
  <div class="hero-inner">
    <div class="hero-eyebrow"><span class="live-dot"></span>Live · {datetime.now():%b %d, %Y · %I:%M %p}</div>
    <div class="hero-title">The early warning system<br>for <span class="grad">stablecoin depegs</span></div>
    <div class="hero-stats">
      <div class="hero-stat"><div class="hero-stat-val" style="color:{LEVEL_HEX[lvl]};">{f'{avg_risk:.1f}' if avg_risk is not None else '—'}</div><div class="hero-stat-label">Avg risk score</div></div>
      <div class="hero-stat"><div class="hero-stat-val" style="color:#22c55e;">{counts['stable']}</div><div class="hero-stat-label">Stable</div></div>
      <div class="hero-stat"><div class="hero-stat-val" style="color:#f59e0b;">{counts['elevated']}</div><div class="hero-stat-label">Elevated</div></div>
      <div class="hero-stat"><div class="hero-stat-val" style="color:#ef4444;">{counts['critical']}</div><div class="hero-stat-label">Critical</div></div>
      <div class="hero-stat"><div class="hero-stat-val" style="color:{LEVEL_HEX[lvl]};font-size:15px;padding-top:5px;">{status}</div><div class="hero-stat-label">Market status</div></div>
      <div class="hero-stat">{fg_html}</div>
      <div class="hero-stat">{gas_html}</div>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

if off_peg:
    off_txt = ", ".join(f"{t} ({fmt_price(data[t]['price'])})" for t in off_peg)
    st.markdown(f'<div class="banner banner-bad">🔴 <strong style="color:#f1f5f9;">Off peg right now:</strong> '
                f'{off_txt} — trading more than 0.5% from $1.</div>', unsafe_allow_html=True)

# ── Overview row ─────────────────────────────────────────────────────────────────
st.markdown(section("Market overview"), unsafe_allow_html=True)
g_col, h_col, m_col = st.columns([1.2, 1.3, 1.3])

with g_col, st.container(border=True):
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=avg_risk or 0,
        number={"font": {"size": 34, "color": LEVEL_HEX[lvl]}, "valueformat": ".1f"},
        title={"text": "Average risk score", "font": {"size": 12, "color": "#64748b"}},
        gauge={"axis": {"range": [0, 100], "tickwidth": 0, "tickfont": {"color": "#475569", "size": 9}},
               "bar": {"color": LEVEL_HEX[lvl], "thickness": 0.22}, "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
               "steps": [{"range": [0, 30], "color": "rgba(34,197,94,.08)"},
                         {"range": [30, 60], "color": "rgba(245,158,11,.08)"},
                         {"range": [60, 100], "color": "rgba(239,68,68,.08)"}]},
    ))
    fig.update_layout(**{**PLOT_LAYOUT, "margin": dict(t=36, b=4, l=18, r=18)}, height=190)
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False}, key="global_gauge")

with h_col:
    if highest:
        d = data[highest]
        wc = risk_hex(risks[highest])
        st.markdown(f"""
        <div class="card" style="border-color:{wc}33;min-height:222px;">
          <div class="card-label">Highest composite risk</div>
          <div style="display:flex;justify-content:space-between;align-items:flex-end;margin-top:12px;">
            <div>
              <div style="font-size:32px;font-weight:900;color:#f1f5f9;letter-spacing:-1.5px;">{highest}</div>
              <div style="font-size:12px;color:#64748b;margin-top:4px;">{esc(d['cfg']['issuer'])} · {fmt_price(d['price'])}</div>
              <div style="font-size:12px;color:#94a3b8;margin-top:10px;">Liquidity {fmt_usd(d['liquidity'])}</div>
            </div>
            <div style="text-align:right;">
              <div style="font-size:42px;font-weight:900;color:{wc};letter-spacing:-2px;line-height:1;">{risks[highest]:.0f}</div>
              <div style="margin-top:8px;">{status_pill(risks[highest])}</div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown(card("Highest composite risk", "—", "Price data unavailable"), unsafe_allow_html=True)

with m_col:
    meta = engine.model_meta.get("metrics", {})
    watch = ", ".join(ml_watch) if ml_watch else "None"
    pr_auc = f'{meta["pr_auc"]:.2f}' if meta else "—"
    st.markdown(f"""
    <div class="card" style="min-height:222px;">
      <div class="card-label">7-day depeg forecast</div>
      <div style="font-size:13px;color:#94a3b8;margin-top:10px;">Model flags</div>
      <div style="font-size:24px;font-weight:800;color:{'#f59e0b' if ml_watch else '#22c55e'};margin:2px 0 14px;">{esc(watch)}</div>
      <div class="note">Out-of-sample PR-AUC <strong style="color:#a78bfa;">{pr_auc}</strong>
        (vs {meta.get('pr_auc_baseline', '—')} for a naive rule). Details on the Intelligence page.</div>
    </div>""", unsafe_allow_html=True)

# ── Asset grid ───────────────────────────────────────────────────────────────────
st.markdown(section("Live asset risk"), unsafe_allow_html=True)


def asset_card(t, d):
    r = risks[t]
    p = d["price"]
    dev = abs(1 - p) * 100 if p is not None else None
    dev_color = "#64748b" if dev is None else "#22c55e" if dev < 0.1 else "#f59e0b" if dev < 0.5 else "#ef4444"
    ml = d["ml"]
    ml_txt = f'{ml["probability"]:.0f}% 7d' if ml["probability"] is not None else ml["label"]
    return f"""
    <div class="asset-card-v2">
      <div class="ac-row">
        <div><div class="ac-ticker">{t}</div><div class="ac-issuer">{esc(d['cfg']['issuer'])}</div></div>
        {status_pill(r)}
      </div>
      <div class="ac-price" style="color:{dev_color};">{fmt_price(p)}</div>
      <div class="ac-meta">{f'Δ {dev:.3f}% from peg' if dev is not None else 'price unavailable'} · liq {fmt_usd(d['liquidity'], 0)}</div>
      <div class="ac-bar-wrap"><div class="ac-bar" style="width:{min(r or 0, 100)}%;background:{risk_hex(r)};"></div></div>
      <div class="ac-foot"><span style="color:{risk_hex(r)};">Risk {f'{r:.1f}' if r is not None else '—'}</span>
        <span style="color:{LEVEL_HEX[ml['level']]};">ML {esc(ml_txt)}</span></div>
    </div>"""


tickers = list(data)
for row in (tickers[:5], tickers[5:]):
    cols = st.columns(5)
    for col, t in zip(cols, row):
        with col:
            st.markdown(asset_card(t, data[t]), unsafe_allow_html=True)

st.markdown('<div class="note">Risk score = 50% peg deviation · 30% on-chain DEX liquidity · 20% news sentiment. '
            'Components that can\'t be fetched are left out rather than guessed. '
            'ML = probability of trading ≥1% off peg within 7 days.</div>', unsafe_allow_html=True)

# ── Depeg history ────────────────────────────────────────────────────────────────
st.markdown(section("Notable depeg events"), unsafe_allow_html=True)
EVENTS = [
    ("Mar 2023", "USDC", "#2775ca", "$0.877", "Silicon Valley Bank collapse — $3.3B of reserves stuck at the failed bank"),
    ("Mar 2023", "FRAX", "#9ca3af", "$0.874", "USDC contagion — FRAX was partly backed by USDC"),
    ("Mar 2023", "DAI",  "#f5ac37", "$0.897", "Over half of DAI's collateral was USDC"),
    ("May 2022", "USDT", "#26a17b", "$0.948", "UST/LUNA's $40B collapse triggered a stablecoin-wide run"),
    ("Oct 2018", "USDT", "#26a17b", "$0.850", "Reserve transparency fears — USDT's worst depeg on record"),
]
for date, coin, color, low, cause in EVENTS:
    st.markdown(f"""
    <div class="depeg-row">
      <div style="width:8px;height:8px;border-radius:50%;background:{color};box-shadow:0 0 6px {color}88;"></div>
      <div style="font-size:15px;font-weight:800;color:#f1f5f9;width:56px;">{coin}</div>
      <div style="font-size:17px;font-weight:800;color:#ef4444;width:72px;">{low}</div>
      <div style="font-size:13px;color:#94a3b8;flex:1;min-width:200px;">{cause}</div>
      <div style="font-size:11px;color:#64748b;font-weight:600;">{date}</div>
    </div>""", unsafe_allow_html=True)

st.markdown('<div class="footer-note">Data: CoinGecko · DefiLlama · DexScreener · Google News · Etherscan · '
            'FinBERT sentiment · Not financial advice</div>', unsafe_allow_html=True)
