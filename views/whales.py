import streamlit as st

from styles import card, empty_state, esc, fmt_age, fmt_usd, short_addr
from ui import get_engine, auto_refresh, asset_selector, header

engine = get_engine()
auto_refresh(120)

header("Whale alerts", "Large on-chain stablecoin transfers on Ethereum")
pick, size = st.columns([3, 1.3])
with pick:
    ticker = asset_selector()
with size:
    threshold = st.select_slider("Minimum transfer", options=[250_000, 500_000, 1_000_000, 5_000_000, 10_000_000, 50_000_000],
                                 value=1_000_000, format_func=fmt_usd, label_visibility="collapsed")

st.markdown("""
<div class="banner"><strong>Why this matters:</strong> very large stablecoin transfers — especially
into exchanges or redemption addresses — can signal holders heading for the exit. Most big transfers are routine
(market makers, treasury moves), so treat these as context rather than a signal on their own.</div>
""", unsafe_allow_html=True)

with st.spinner(f"Scanning recent {ticker} transfers…"):
    res = engine.get_whale_alerts(ticker, min_usd=threshold)

if res["error"]:
    st.markdown(empty_state("🔑", "Whale tracking is unavailable", esc(res["error"]) +
                            "<br><br>Add it to the <code>.env</code> file in the project folder (see Settings → Data sources) and restart the app."),
                unsafe_allow_html=True)
    st.stop()

whales = res["transfers"]
window = fmt_age(res["window_secs"]).removesuffix(" ago")
c1, c2, c3 = st.columns([1, 1.4, 1])
with c1:
    st.markdown(card("Large transfers", str(len(whales)), f"≥ {fmt_usd(threshold, 0)}"), unsafe_allow_html=True)
with c2:
    st.markdown(card("Volume in large transfers", fmt_usd(sum(w["amount"] for w in whales)), ticker, color="#f59e0b"),
                unsafe_allow_html=True)
with c3:
    st.markdown(card("Window scanned", window, f"latest {res['scanned']:,} transfers"), unsafe_allow_html=True)

if not whales:
    st.markdown(empty_state("🐋", "No large transfers in this window",
                            f"None of the latest {res['scanned']:,} {ticker} transfers (the last {window}) were above {fmt_usd(threshold, 0)}."),
                unsafe_allow_html=True)
    st.stop()

for w in whales:
    amt = w["amount"]
    color = "#ef4444" if amt >= 50e6 else "#f59e0b" if amt >= 10e6 else "#3b82f6"
    label = "MEGA" if amt >= 50e6 else "LARGE" if amt >= 10e6 else "NOTABLE"
    st.markdown(f"""
    <div class="whale-card">
      <div style="display:flex;align-items:center;gap:16px;">
        <div style="font-size:11px;font-weight:700;color:{color};background:{color}18;border:1px solid {color}44;border-radius:6px;padding:3px 8px;">{label}</div>
        <div>
          <div class="whale-amount" style="color:{color};">{fmt_usd(amt, 2)} {ticker}</div>
          <div class="whale-addr">
            <a href="https://etherscan.io/address/{esc(w['from'])}" target="_blank" rel="noopener" style="color:#94a3b8;">{short_addr(w['from'])}</a>
            → <a href="https://etherscan.io/address/{esc(w['to'])}" target="_blank" rel="noopener" style="color:#94a3b8;">{short_addr(w['to'])}</a>
          </div>
        </div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:13px;color:#94a3b8;margin-bottom:6px;">{fmt_age(w['age_secs'])}</div>
        <a href="https://etherscan.io/tx/{esc(w['hash'])}" target="_blank" rel="noopener"
           style="font-size:12px;color:#3b82f6;text-decoration:none;background:#0f1929;border:1px solid #1e3a5f;border-radius:6px;padding:4px 10px;">
          View transaction ↗</a>
      </div>
    </div>""", unsafe_allow_html=True)

st.markdown('<div class="footer-note">Etherscan API V2 · Ethereum mainnet only · refreshes every 2 minutes</div>',
            unsafe_allow_html=True)
