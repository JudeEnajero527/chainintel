import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from styles import PLOT_LAYOUT, card, empty_state, esc, fmt_usd, section
from ui import header, page

engine, _ = page("Yields", "💰", refresh_seconds=900)
header("💰 Stablecoin Yields", "Every DefiLlama pool made up only of stablecoins — filter, sort, and sanity-check the APY")

with st.spinner("Loading yield data…"):
    all_pools = engine.get_stablecoin_yields()
if not all_pools:
    st.markdown(empty_state("💰", "Yield data unavailable", "DefiLlama could not be reached. Retrying shortly."),
                unsafe_allow_html=True)
    st.stop()

df = pd.DataFrame(all_pools)
df["reward_share"] = (df["apy_reward"] / df["apy"]).clip(0, 1).fillna(0)

with st.sidebar:
    st.markdown('<div class="section-title" style="margin:20px 0 8px;">Filters</div>', unsafe_allow_html=True)
    min_tvl = st.select_slider("Min pool TVL", options=[100_000, 1_000_000, 5_000_000, 10_000_000, 50_000_000, 100_000_000],
                               value=5_000_000, format_func=lambda x: fmt_usd(x, 0))
    min_apy, max_apy = st.slider("APY range (%)", 0.0, 50.0, (2.0, 30.0), 0.5)
    chains = st.multiselect("Chains", sorted(df["chain"].unique(), key=lambda c: -df[df["chain"] == c]["tvl"].sum()))
    query = st.text_input("Search symbol or protocol", placeholder="e.g. USDC, aave")
    base_only = st.toggle("Base yield only (ignore token rewards)", value=False)

apy_col = "apy_base" if base_only else "apy"
pools = df[(df["tvl"] >= min_tvl) & (df[apy_col] >= min_apy) & (df[apy_col] <= max_apy)]
if chains:
    pools = pools[pools["chain"].isin(chains)]
if query:
    q = query.strip().lower()
    pools = pools[pools["symbol"].str.lower().str.contains(q, regex=False) | pools["protocol"].str.lower().str.contains(q, regex=False)]
pools = pools.sort_values(apy_col, ascending=False)

if pools.empty:
    st.markdown(empty_state("💰", "No pools match your filters", "Try a lower minimum TVL or a wider APY range."),
                unsafe_allow_html=True)
    st.stop()

best = pools.iloc[0]
tvl_weighted = (pools[apy_col] * pools["tvl"]).sum() / pools["tvl"].sum()
m1, m2, m3, m4 = st.columns(4)
with m1:
    st.markdown(card("Highest APY", f"{best[apy_col]:.2f}%", f"{esc(best['protocol'])} · {esc(best['symbol'])} · {esc(best['chain'])}",
                     color="#22c55e"), unsafe_allow_html=True)
with m2:
    st.markdown(card("TVL-weighted APY", f"{tvl_weighted:.2f}%", "what the money actually earns"), unsafe_allow_html=True)
with m3:
    st.markdown(card("Pools", f"{len(pools):,}", f"of {len(df):,} stablecoin pools"), unsafe_allow_html=True)
with m4:
    st.markdown(card("TVL in these pools", fmt_usd(pools["tvl"].sum()), f"{pools['protocol'].nunique()} protocols"),
                unsafe_allow_html=True)

st.markdown(section("APY vs pool size"), unsafe_allow_html=True)
top = pools.head(60)
with st.container(border=True):
    fig = go.Figure(go.Scatter(
        x=top["tvl"], y=top[apy_col], mode="markers",
        marker=dict(size=10, color=top["reward_share"], colorscale=[[0, "#22c55e"], [0.5, "#f59e0b"], [1, "#ef4444"]],
                    cmin=0, cmax=1, line=dict(color="#0d0f14", width=1),
                    colorbar=dict(title=dict(text="Reward share", font=dict(color="#94a3b8")), tickformat=".0%",
                                  tickfont=dict(color="#94a3b8"))),
        customdata=top[["protocol", "symbol", "chain"]].values,
        hovertemplate="<b>%{customdata[0]}</b> · %{customdata[1]}<br>%{customdata[2]}<br>APY %{y:.2f}%<br>TVL $%{x:,.0f}<extra></extra>",
    ))
    fig.update_layout(**PLOT_LAYOUT, height=340)
    fig.update_xaxes(type="log", title="Pool TVL (log)", tickprefix="$")
    fig.update_yaxes(title="APY", ticksuffix="%")
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

st.markdown("""
<div class="banner banner-warn"><strong style="color:#f1f5f9;">Reading the numbers:</strong>
red dots earn most of their yield in reward tokens, which can fall in value or stop at any time — base APY (from real
borrowing demand or fees) is the durable part. Large, long-lived pools have had more time to be battle-tested.
"vs 30d avg" shows whether today's APY is a temporary spike.</div>
""", unsafe_allow_html=True)

table = pd.DataFrame({
    "Protocol": pools["protocol"], "Pool": pools["symbol"], "Chain": pools["chain"],
    "APY": pools["apy"], "Base": pools["apy_base"], "Rewards": pools["apy_reward"],
    "30d avg": pools["apy_mean_30d"], "TVL": pools["tvl"],
    "Reward share": pools["reward_share"] * 100, "IL risk": pools["il_risk"],
    "Link": "https://defillama.com/yields/pool/" + pools["pool_id"],
})
st.dataframe(
    table, hide_index=True, use_container_width=True, height=560,
    column_config={
        "APY": st.column_config.NumberColumn(format="%.2f%%"),
        "Base": st.column_config.NumberColumn(format="%.2f%%"),
        "Rewards": st.column_config.NumberColumn(format="%.2f%%"),
        "30d avg": st.column_config.NumberColumn(format="%.2f%%"),
        "TVL": st.column_config.NumberColumn(format="dollar"),
        "Reward share": st.column_config.ProgressColumn(format="%.0f%%", min_value=0, max_value=100),
        "IL risk": st.column_config.CheckboxColumn(),
        "Link": st.column_config.LinkColumn(display_text="DefiLlama ↗"),
    },
)
st.markdown('<div class="footer-note">Data: DefiLlama Yields · Not financial advice · refreshes every 15 minutes</div>',
            unsafe_allow_html=True)
