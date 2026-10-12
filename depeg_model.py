"""
Depeg forecasting — shared by train_model.py (training) and chainintel_core.py (live inference).

Question the model answers:
    "This stablecoin is on its peg today. Will it trade ≥1% off peg at any point in the next 7 days?"

Both training and inference build features with `build_features`, so the live model always sees
exactly the inputs it was trained on.
"""
import numpy as np
import pandas as pd
import requests

LLAMA_PRICES_URL = "https://stablecoins.llama.fi/stablecoinprices"
LLAMA_META_URL   = "https://stablecoins.llama.fi/stablecoins?includePrices=false"

HORIZON_DAYS     = 7       # how far ahead we forecast
DEPEG_THRESHOLD  = 0.01    # ≥1% off peg counts as a depeg
PEGGED_THRESHOLD = 0.005   # only score coins currently within 0.5% of peg
MIN_HISTORY_DAYS = 30

FEATURES = [
    "abs_dev", "dev", "vol_7d", "vol_30d", "max_abs_dev_7d", "max_abs_dev_30d",
    "mean_dev_7d", "dev_change_1d", "dev_change_7d", "offpeg_days_30d", "history_days",
]

FEATURE_LABELS = {
    "abs_dev":          "Current peg deviation",
    "dev":              "Signed deviation",
    "vol_7d":           "Volatility (7d)",
    "vol_30d":          "Volatility (30d)",
    "max_abs_dev_7d":   "Worst deviation (7d)",
    "max_abs_dev_30d":  "Worst deviation (30d)",
    "mean_dev_7d":      "Average deviation (7d)",
    "dev_change_1d":    "Deviation change (1d)",
    "dev_change_7d":    "Deviation change (7d)",
    "offpeg_days_30d":  "Days off peg (30d)",
    "history_days":     "Price history length",
}


def fetch_price_history(timeout: int = 60) -> pd.DataFrame:
    """Daily prices for every USD-pegged stablecoin DeFiLlama tracks. Columns: date, coin (CoinGecko id), price."""
    meta = requests.get(LLAMA_META_URL, timeout=timeout).json()["peggedAssets"]
    usd_ids = {m["gecko_id"] for m in meta if m.get("pegType") == "peggedUSD" and m.get("gecko_id")}
    raw = requests.get(LLAMA_PRICES_URL, timeout=timeout).json()
    rows = [
        (r["date"], coin, price)
        for r in raw
        for coin, price in r.get("prices", {}).items()
        if coin in usd_ids and isinstance(price, (int, float)) and price > 0
    ]
    df = pd.DataFrame(rows, columns=["date", "coin", "price"])
    df["date"] = pd.to_datetime(df["date"], unit="s").dt.normalize()
    return df[df["date"] >= "2020-01-01"]


def build_features(prices: pd.Series) -> pd.DataFrame:
    """Feature frame for one coin. `prices` is a daily price Series indexed by date."""
    s = prices.sort_index()
    s = s[~s.index.duplicated(keep="last")]
    s = s.asfreq("D").ffill(limit=2)          # bridge short gaps only
    dev = s - 1.0
    abs_dev = dev.abs()
    ret = s.pct_change(fill_method=None)
    f = pd.DataFrame(index=s.index)
    f["abs_dev"]         = abs_dev
    f["dev"]             = dev
    f["vol_7d"]          = ret.rolling(7,  min_periods=5).std()
    f["vol_30d"]         = ret.rolling(30, min_periods=20).std()
    f["max_abs_dev_7d"]  = abs_dev.rolling(7,  min_periods=5).max()
    f["max_abs_dev_30d"] = abs_dev.rolling(30, min_periods=20).max()
    f["mean_dev_7d"]     = dev.rolling(7, min_periods=5).mean()
    f["dev_change_1d"]   = dev.diff()
    f["dev_change_7d"]   = dev - dev.shift(7)
    f["offpeg_days_30d"] = (abs_dev >= PEGGED_THRESHOLD).astype(float).where(abs_dev.notna()).rolling(30, min_periods=20).sum()
    f["history_days"]    = np.minimum(np.arange(1, len(s) + 1), 365).astype(float)
    return f


def build_labels(prices: pd.Series) -> pd.Series:
    """1 if the coin is ≥DEPEG_THRESHOLD off peg on any of the next HORIZON_DAYS days, NaN if the window is incomplete."""
    s = prices.sort_index()
    s = s[~s.index.duplicated(keep="last")].asfreq("D").ffill(limit=2)
    abs_dev = (s - 1.0).abs()
    future = pd.concat([abs_dev.shift(-k) for k in range(1, HORIZON_DAYS + 1)], axis=1)
    label = (future.max(axis=1) >= DEPEG_THRESHOLD).astype(float)
    return label.where(future.notna().all(axis=1))


def latest_features(prices: pd.Series) -> dict | None:
    """Feature row for the most recent day, or None if there isn't enough clean history."""
    if prices is None or len(prices) < MIN_HISTORY_DAYS:
        return None
    row = build_features(prices).iloc[-1]
    if row[FEATURES].isna().any():
        return None
    return row[FEATURES].to_dict()
