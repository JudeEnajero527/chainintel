"""
ChainIntel data + risk engine. No Streamlit imports — also used by send_digest.py.

Every external call is cached in-process (see `ttl_cache`) so a dozen open tabs auto-refreshing
every minute still only hit each API a few times per hour. Failures return None / an `error`
field rather than plausible-looking defaults, so the UI can say "unavailable" instead of
showing fake calm numbers.
"""
import functools
import json
import logging
import math
import os
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html import unescape

import joblib
import pandas as pd
import requests

import config
import db
import depeg_model

log = logging.getLogger("chainintel")

HERE       = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, "chainintel_model.pkl")
META_PATH  = os.path.join(HERE, "chainintel_model_meta.json")

ETHERSCAN_API_KEY = config.get("ETHERSCAN_API_KEY")
ETHERSCAN_URL     = "https://api.etherscan.io/v2/api"

REDDIT_UA = "python:chainintel:v2.0 (stablecoin risk monitor)"

FETCH_ERRORS = (requests.RequestException, ValueError, KeyError, TypeError, IndexError, ET.ParseError)

# ── Assets ──────────────────────────────────────────────────────────────────────

ASSETS = {
    "USDC":   {"coingecko_id": "usd-coin",    "issuer": "Circle",       "color": "#2775ca", "decimals": 6,  "contract": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"},
    "USDT":   {"coingecko_id": "tether",      "issuer": "Tether",       "color": "#26a17b", "decimals": 6,  "contract": "0xdAC17F958D2ee523a2206206994597C13D831ec7"},
    "DAI":    {"coingecko_id": "dai",         "issuer": "MakerDAO",     "color": "#f5ac37", "decimals": 18, "contract": "0x6B175474E89094C44Da98b954EedeAC495271d0F"},
    "FRAX":   {"coingecko_id": "frax",        "issuer": "Frax Finance", "color": "#e5e7eb", "decimals": 18, "contract": "0x853d955aCEf822Db058eb8505911ED77F175b99e"},
    "USDe":   {"coingecko_id": "ethena-usde", "issuer": "Ethena",       "color": "#9b59b6", "decimals": 18, "contract": "0x4c9EDD5852cd905f086C759E8383e09bff1E68B3"},
    "PYUSD":  {"coingecko_id": "paypal-usd",  "issuer": "PayPal",       "color": "#3b7bdb", "decimals": 6,  "contract": "0x6c3ea9036406852006290770BEdFcAbA0e23A0e8"},
    "TUSD":   {"coingecko_id": "true-usd",    "issuer": "TrueUSD",      "color": "#4f7cff", "decimals": 18, "contract": "0x0000000000085d4780B73119b644AE5ecd22b376"},
    "LUSD":   {"coingecko_id": "liquity-usd", "issuer": "Liquity",      "color": "#745ddf", "decimals": 18, "contract": "0x5f98805A4E8be255a32880FDeC7F6728C6568bA0"},
    "crvUSD": {"coingecko_id": "crvusd",      "issuer": "Curve",        "color": "#f7b731", "decimals": 18, "contract": "0xf939E0A03FB07F59A73314E73794Be0E57ac1b4E"},
}
for _t, _c in ASSETS.items():
    _c["ticker"] = _t

DEPEG_EVENTS = {
    "USDC": [{"date": "2023-03-11", "label": "SVB collapse",          "price": 0.877}],
    "USDT": [{"date": "2018-10-15", "label": "Reserve transparency FUD", "price": 0.85},
             {"date": "2022-05-12", "label": "UST contagion",         "price": 0.9476}],
    "DAI":  [{"date": "2020-03-12", "label": "Black Thursday",        "price": 1.11},
             {"date": "2023-03-11", "label": "USDC exposure",         "price": 0.897}],
    "FRAX": [{"date": "2023-03-11", "label": "USDC exposure",         "price": 0.874}],
    "TUSD": [{"date": "2023-06-10", "label": "Binance listing FUD",   "price": 0.978}],
}

# Historical worst prints — used for stress-test scenarios.
WORST_CASE = {
    "USDC": 0.877, "USDT": 0.850, "DAI": 0.897, "FRAX": 0.874, "USDe": 0.965,
    "PYUSD": 0.980, "TUSD": 0.880, "LUSD": 0.950, "crvUSD": 0.960,
}

# ── Risk scoring (pure functions) ───────────────────────────────────────────────

RISK_WEIGHTS = {"peg": 0.5, "liquidity": 0.3, "sentiment": 0.2}
LIQ_SAFE, LIQ_DANGER = 500e6, 5e6   # ≥$500M DEX liquidity = 0 risk, ≤$5M = 100


def peg_risk(price):
    """0 at $1.00, 100 at ≥1% off peg."""
    return None if price is None else min(abs(1.0 - price) * 10_000, 100.0)


def liquidity_risk(liquidity_usd):
    """Log-scaled: deep liquidity → 0, thin liquidity → 100."""
    if not liquidity_usd:
        return None
    span = math.log10(LIQ_SAFE) - math.log10(LIQ_DANGER)
    return max(0.0, min(100.0, 100 * (math.log10(LIQ_SAFE) - math.log10(liquidity_usd)) / span))


def compute_risk(price, liquidity_usd=None, sentiment=None) -> dict:
    """
    Composite 0–100 score from whichever components are available. Missing inputs are dropped and
    the weights re-normalised — they are never filled with a made-up "neutral" value. No price → no score.
    """
    parts = {"peg": peg_risk(price), "liquidity": liquidity_risk(liquidity_usd), "sentiment": sentiment}
    total = None
    if parts["peg"] is not None:
        avail = {k: v for k, v in parts.items() if v is not None}
        weight = sum(RISK_WEIGHTS[k] for k in avail)
        total = round(sum(v * RISK_WEIGHTS[k] for k, v in avail.items()) / weight, 1)
    return {**parts, "total": total, "used": [k for k, v in parts.items() if v is not None]}


# ── Caching ─────────────────────────────────────────────────────────────────────

def ttl_cache(seconds: int, failure_seconds: int = 60):
    """Thread-safe per-argument cache. Failed results (None, or dicts with an 'error') expire sooner."""
    def deco(fn):
        store, lock = {}, threading.Lock()

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = (args[1:] if args and isinstance(args[0], RiskEngine) else args, tuple(sorted(kwargs.items())))
            now = time.time()
            with lock:
                hit = store.get(key)
                if hit and hit[0] > now:
                    return hit[1]
            value = fn(*args, **kwargs)
            failed = value is None or (isinstance(value, dict) and value.get("error"))
            with lock:
                store[key] = (now + (failure_seconds if failed else seconds), value)
            return value
        wrapper.cache_clear = store.clear
        return wrapper
    return deco


_session = requests.Session()
_session.headers["User-Agent"] = "Mozilla/5.0 (compatible; ChainIntel/2.0; stablecoin risk monitor)"


def _get(url, timeout=8, **params):
    r = _session.get(url, params=params or None, timeout=timeout)
    r.raise_for_status()
    return r


def summarize_reddit(posts: list[dict], source: str) -> dict:
    """Buzz = posts in the last 24h relative to the weekly daily average (50 = normal day, 100 = 2× normal)."""
    now = datetime.now(timezone.utc)
    last_day = [p for p in posts if p["time"] and now - p["time"] < timedelta(days=1)]
    daily_avg = len(posts) / 7
    buzz = min(100.0, len(last_day) / max(daily_avg, 1) * 50)
    posts = sorted(posts, key=lambda p: p["time"] or now, reverse=True)
    return {"posts": posts[:10], "count_24h": len(last_day), "count_7d": len(posts), "buzz": round(buzz), "source": source}


SNAPSHOT_MAX_AGE = 420        # seconds — the collector runs every 5 minutes


def _jsonable(o):
    """json.dumps fallback for numpy / pandas scalars."""
    if hasattr(o, "item"):
        return o.item()
    if isinstance(o, (datetime, pd.Timestamp)):
        return o.isoformat()
    raise TypeError(f"not JSON serializable: {type(o)}")


def _risk_level(score):
    if score is None:
        return "unknown"
    return "stable" if score < 30 else "elevated" if score < 60 else "critical"


# ── Engine ──────────────────────────────────────────────────────────────────────

class RiskEngine:
    def __init__(self):
        self._sentiment_pipe = None
        self._sentiment_lock = threading.Lock()
        self.sentiment_status = "Loads on first use"
        self._reddit_lock = threading.Lock()
        self._reddit_auth = None

        self.model, self.model_meta = None, {}
        if os.path.exists(MODEL_PATH) and os.path.exists(META_PATH):
            try:
                self.model = joblib.load(MODEL_PATH)
                with open(META_PATH) as fh:
                    self.model_meta = json.load(fh)
            except Exception as e:      # stale/incompatible pickle — run train_model.py
                log.warning("Could not load depeg model: %s", e)
        self.ml_status = "Online" if self.model else "Not trained — run train_model.py"
        self.init_db()

    # ── storage ────────────────────────────────────────────────────────────────
    def init_db(self):
        with db.connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS risk_history (
                    timestamp TEXT, ticker TEXT, price REAL, liquidity REAL,
                    sentiment_score REAL, total_risk REAL
                )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_risk_ticker_ts ON risk_history (ticker, timestamp)")
            conn.execute(f"CREATE TABLE IF NOT EXISTS snapshots (id {db.AUTO_ID}, created TEXT NOT NULL, payload TEXT NOT NULL)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS forecast_log (
                    date TEXT NOT NULL, ticker TEXT NOT NULL, probability REAL, price REAL,
                    level TEXT, outcome INTEGER, max_dev REAL, resolved_at TEXT,
                    PRIMARY KEY (date, ticker)
                )""")

    def log_snapshot(self, ticker, price, liquidity, sentiment, total_risk, min_gap_minutes=5):
        """Record a reading at most once every `min_gap_minutes` per ticker."""
        if price is None or total_risk is None:
            return
        with db.connect() as conn:
            last = conn.execute("SELECT MAX(timestamp) FROM risk_history WHERE ticker=?", (ticker,)).fetchone()[0]
            if last and datetime.now() - datetime.fromisoformat(str(last)) < timedelta(minutes=min_gap_minutes):
                return
            conn.execute(
                "INSERT INTO risk_history (timestamp, ticker, price, liquidity, sentiment_score, total_risk) VALUES (?,?,?,?,?,?)",
                (datetime.now().isoformat(sep=" "), ticker, price, liquidity, sentiment, total_risk),
            )

    def get_history(self, ticker, days=None) -> pd.DataFrame:
        query, params = "SELECT timestamp, price, liquidity, sentiment_score, total_risk FROM risk_history WHERE ticker=?", [ticker]
        if days:
            query += " AND timestamp >= ?"
            params.append((datetime.now() - timedelta(days=days)).isoformat(sep=" "))
        with db.connect() as conn:
            rows = conn.execute(query + " ORDER BY timestamp", params).fetchall()
        df = pd.DataFrame(rows, columns=["timestamp", "price", "liquidity", "sentiment_score", "total_risk"])
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"], format="ISO8601")
            df = df.set_index("timestamp")
        return df

    # ── shared snapshots (collector ↔ app) ─────────────────────────────────────
    def save_snapshot(self, data: dict):
        with db.connect() as conn:
            conn.execute("INSERT INTO snapshots (created, payload) VALUES (?, ?)",
                         (datetime.now(timezone.utc).isoformat(), json.dumps(data, default=_jsonable)))
            conn.execute("DELETE FROM snapshots WHERE created < ?",
                         ((datetime.now(timezone.utc) - timedelta(days=2)).isoformat(),))

    def load_snapshot(self, max_age_seconds: int) -> dict | None:
        with db.connect() as conn:
            row = conn.execute("SELECT created, payload FROM snapshots ORDER BY id DESC LIMIT 1").fetchone()
        if not row or datetime.now(timezone.utc) - datetime.fromisoformat(row[0]) > timedelta(seconds=max_age_seconds):
            return None
        return json.loads(row[1])

    # ── forecast track record ──────────────────────────────────────────────────
    def log_forecasts(self, data: dict) -> int:
        """Store today's 7-day forecast for each coin (first one of the UTC day wins). Returns rows added."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        added = 0
        with db.connect() as conn:
            for t, d in data.items():
                ml = d["ml"]
                if ml.get("probability") is None:
                    continue
                if conn.execute("SELECT 1 FROM forecast_log WHERE date=? AND ticker=?", (today, t)).fetchone():
                    continue
                conn.execute("INSERT INTO forecast_log (date, ticker, probability, price, level) VALUES (?,?,?,?,?)",
                             (today, t, ml["probability"], d["price"], ml["level"]))
                added += 1
        return added

    def resolve_forecasts(self) -> int:
        """Score forecasts whose 7-day window has closed against DefiLlama daily prices. Returns rows resolved."""
        horizon = depeg_model.HORIZON_DAYS
        cutoff = (datetime.now(timezone.utc) - timedelta(days=horizon + 1)).strftime("%Y-%m-%d")
        with db.connect() as conn:
            pending = conn.execute("SELECT date, ticker FROM forecast_log WHERE outcome IS NULL AND date <= ?", (cutoff,)).fetchall()
        resolved = 0
        for date, ticker in pending:
            prices = self.get_daily_prices(ticker)
            if prices is None:
                continue
            start = pd.Timestamp(date) + pd.Timedelta(days=1)
            window = prices[(prices.index >= start) & (prices.index < start + pd.Timedelta(days=horizon))]
            if len(window) < horizon - 1:          # tolerate one missing day
                continue
            max_dev = float((window - 1).abs().max())
            with db.connect() as conn:
                conn.execute("UPDATE forecast_log SET outcome=?, max_dev=?, resolved_at=? WHERE date=? AND ticker=?",
                             (int(max_dev >= depeg_model.DEPEG_THRESHOLD), max_dev,
                              datetime.now(timezone.utc).isoformat(), date, ticker))
            resolved += 1
        return resolved

    def forecast_record(self) -> pd.DataFrame:
        with db.connect() as conn:
            rows = conn.execute("SELECT date, ticker, probability, price, level, outcome, max_dev FROM forecast_log ORDER BY date DESC, ticker").fetchall()
        return pd.DataFrame(rows, columns=["date", "ticker", "probability", "price", "level", "outcome", "max_dev"])

    # ── prices ─────────────────────────────────────────────────────────────────
    @ttl_cache(60)
    def get_all_prices(self) -> dict:
        """{ticker: price or None} from CoinGecko, one request."""
        try:
            ids = ",".join(a["coingecko_id"] for a in ASSETS.values())
            data = _get("https://api.coingecko.com/api/v3/simple/price", ids=ids, vs_currencies="usd").json()
            return {t: data.get(c["coingecko_id"], {}).get("usd") for t, c in ASSETS.items()}
        except FETCH_ERRORS as e:
            log.warning("CoinGecko prices failed: %s", e)
            return {t: None for t in ASSETS}

    def get_price(self, ticker):
        return self.get_all_prices().get(ticker)

    @ttl_cache(6 * 3600, failure_seconds=600)
    def _llama_history(self) -> pd.DataFrame | None:
        try:
            return depeg_model.fetch_price_history(timeout=30)
        except FETCH_ERRORS as e:
            log.warning("DeFiLlama history failed: %s", e)
            return None

    @ttl_cache(6 * 3600, failure_seconds=600)
    def _llama_supply(self) -> pd.DataFrame | None:
        """Daily circulating supply for the tracked assets (a model input)."""
        try:
            ids = {a["coingecko_id"] for a in ASSETS.values()}
            meta = [m for m in depeg_model.fetch_meta(timeout=30) if m["gecko_id"] in ids]
            return depeg_model.fetch_supply_history(meta)
        except FETCH_ERRORS as e:
            log.warning("DeFiLlama supply failed: %s", e)
            return None

    def get_supply(self, ticker) -> pd.Series | None:
        sup = self._llama_supply()
        if sup is None:
            return None
        s = sup[sup["coin"] == ASSETS[ticker]["coingecko_id"]].set_index("date")["supply"]
        return s if len(s) else None

    def get_daily_prices(self, ticker) -> pd.Series | None:
        """Full daily price history for a tracked asset (DeFiLlama), as a date-indexed Series."""
        hist = self._llama_history()
        if hist is None:
            return None
        s = hist[hist["coin"] == ASSETS[ticker]["coingecko_id"]].set_index("date")["price"]
        return s if len(s) else None

    # ── on-chain liquidity ─────────────────────────────────────────────────────
    @ttl_cache(300)
    def get_dex_stats(self, ticker) -> dict:
        """Aggregate Ethereum DEX liquidity/volume/txns for a token across all its pools (DexScreener)."""
        contract = ASSETS[ticker]["contract"].lower()
        try:
            pairs = _get(f"https://api.dexscreener.com/token-pairs/v1/ethereum/{contract}").json()
        except FETCH_ERRORS as e:
            return {"error": str(e)}
        if not isinstance(pairs, list) or not pairs:
            return {"error": "no pools found"}

        liquidity = sum(float((p.get("liquidity") or {}).get("usd") or 0) for p in pairs)
        volume    = sum(float((p.get("volume") or {}).get("h24") or 0) for p in pairs)
        buys = sells = 0
        for p in pairs:
            tx = (p.get("txns") or {}).get("h24") or {}
            # "buys" of the token = txns where it's the base token being bought, or the quote token being sold
            if p["baseToken"]["address"].lower() == contract:
                buys, sells = buys + tx.get("buys", 0), sells + tx.get("sells", 0)
            else:
                buys, sells = buys + tx.get("sells", 0), sells + tx.get("buys", 0)
        top = max(pairs, key=lambda p: float((p.get("liquidity") or {}).get("usd") or 0))
        other = top["quoteToken"] if top["baseToken"]["address"].lower() == contract else top["baseToken"]
        return {
            "liquidity":     liquidity,
            "volume24h":     volume,
            "pools":         len(pairs),
            "buys":          buys,
            "sells":         sells,
            "sell_pressure": round(sells / (buys + sells) * 100, 1) if buys + sells else None,
            "turnover":      round(volume / liquidity, 3) if liquidity else None,
            "top_pool":      f"{top.get('dexId', '?').title()} {ticker}/{other.get('symbol', '?')}",
            "error":         None,
        }

    # ── news + sentiment ───────────────────────────────────────────────────────
    def _sentiment_model(self):
        with self._sentiment_lock:
            if self._sentiment_pipe is None and self.sentiment_status != "Offline":
                try:
                    import torch
                    torch.classes.__path__ = []          # stops Streamlit's file watcher from tripping over torch.classes
                    from transformers import pipeline
                    # CPU on purpose: calling a GPU/MPS pipeline from several threads can crash the process.
                    self._sentiment_pipe = pipeline("sentiment-analysis", model="ProsusAI/finbert", device=-1)
                    self.sentiment_status = "Online"
                except Exception as e:
                    log.warning("FinBERT unavailable: %s", e)
                    self.sentiment_status = "Offline"
        return self._sentiment_pipe

    @ttl_cache(900)
    def get_news(self, ticker) -> list[dict] | None:
        """Recent Google News headlines: [{title, link, source}]."""
        try:
            xml = _get("https://news.google.com/rss/search",
                       q=f'"{ticker}" stablecoin when:7d', hl="en-US", gl="US", ceid="US:en").text
            items = []
            for it in ET.fromstring(xml).iter("item"):
                title = unescape(it.findtext("title") or "").strip()
                source = it.findtext("source") or ""
                if source and title.endswith(f" - {source}"):
                    title = title[: -len(source) - 3]
                if len(title) >= 10:
                    items.append({"title": title, "link": it.findtext("link") or "", "source": source})
            return items[:10]
        except FETCH_ERRORS as e:
            log.warning("News for %s failed: %s", ticker, e)
            return None

    @ttl_cache(900)
    def get_sentiment(self, ticker) -> dict:
        """FinBERT over recent headlines → {score (0 good … 100 bad), items, error}."""
        news = self.get_news(ticker)
        if news is None:
            return {"score": None, "items": [], "error": "news unavailable"}
        if not news:
            return {"score": None, "items": [], "error": "no recent headlines"}
        pipe = self._sentiment_model()
        if pipe is None:
            return {"score": None, "items": [dict(n, label="unscored") for n in news], "error": "sentiment model offline"}
        with self._sentiment_lock:                   # the pipeline isn't thread-safe; assess_all runs coins in parallel
            results = pipe([n["title"] for n in news])
        risk = {"positive": 0, "neutral": 50, "negative": 100}
        items = [dict(n, label=r["label"], confidence=round(r["score"], 2)) for n, r in zip(news, results)]
        score = sum(risk.get(i["label"], 50) for i in items) / len(items)
        return {"score": round(score, 1), "items": items, "error": None}

    # ── ML forecast ────────────────────────────────────────────────────────────
    def predict_from_prices(self, daily_prices: pd.Series, live_price=None, supply: pd.Series | None = None) -> dict:
        """7-day depeg probability for a daily price series (optionally with today's live price appended)."""
        if self.model is None:
            return {"probability": None, "level": "unknown", "label": "Model not trained"}
        s = daily_prices
        if s is None:
            return {"probability": None, "level": "unknown", "label": "No price history"}
        if live_price is not None:
            s = s.copy()
            s.loc[pd.Timestamp.now("UTC").tz_localize(None).normalize()] = live_price
        features = self.model_meta.get("features", depeg_model.FEATURES)
        feats = depeg_model.latest_features(s, supply, features)
        if feats is None:
            return {"probability": None, "level": "unknown", "label": "Not enough history"}
        if feats["abs_dev"] >= depeg_model.PEGGED_THRESHOLD:
            return {"probability": None, "level": "critical", "label": "Off peg now", "features": feats}
        X = pd.DataFrame([{k: (float("nan") if v is None else v) for k, v in feats.items()}])[features]
        prob = float(self.model.predict_proba(X)[0, 1]) * 100
        alert = self.model_meta.get("metrics", {}).get("alert_threshold", 0.2) * 100
        level = "stable" if prob < alert / 2 else "elevated" if prob < alert else "critical"
        label = {"stable": "Low risk", "elevated": "Watch", "critical": "High risk"}[level]
        return {"probability": round(prob, 1), "level": level, "label": label, "features": feats}

    def predict_depeg(self, ticker, live_price=None) -> dict:
        return self.predict_from_prices(self.get_daily_prices(ticker), live_price, self.get_supply(ticker))

    # ── full assessment ────────────────────────────────────────────────────────
    def assess(self, ticker, with_sentiment=True) -> dict:
        price = self.get_price(ticker)
        dex = self.get_dex_stats(ticker)
        liquidity = None if dex.get("error") else dex["liquidity"]
        sent = self.get_sentiment(ticker) if with_sentiment else {"score": None, "items": [], "error": "skipped"}
        risk = compute_risk(price, liquidity, sent["score"])
        ml = self.predict_depeg(ticker, price)
        self.log_snapshot(ticker, price, liquidity, sent["score"], risk["total"])
        return {
            "ticker": ticker, "cfg": ASSETS[ticker], "price": price, "dex": dex, "liquidity": liquidity,
            "sentiment": sent, "risk": risk, "level": _risk_level(risk["total"]), "ml": ml,
            "assessed_at": datetime.now(timezone.utc).isoformat(),
        }

    @ttl_cache(300, failure_seconds=300)
    def assess_all(self, with_sentiment=True, fresh=False) -> dict:
        """
        Assess every asset. Reuses a snapshot saved in the last few minutes (by the background collector or
        another visitor) so pages load instantly; otherwise computes live, in parallel, and saves one.
        """
        if with_sentiment and not fresh:
            snap = self.load_snapshot(max_age_seconds=SNAPSHOT_MAX_AGE)
            if snap and set(snap) == set(ASSETS):
                return snap
        self.get_all_prices()
        self._llama_history()
        self._llama_supply()
        if with_sentiment:
            self._sentiment_model()          # load once before the threads race for it
        with ThreadPoolExecutor(max_workers=len(ASSETS)) as pool:
            results = dict(zip(ASSETS, pool.map(lambda t: self.assess(t, with_sentiment), ASSETS)))
        if with_sentiment and all(r["price"] is not None for r in results.values()):
            self.save_snapshot(results)
        return results

    # ── whales ─────────────────────────────────────────────────────────────────
    @ttl_cache(120)
    def get_whale_alerts(self, ticker, min_usd=1_000_000) -> dict:
        """Large transfers among the latest 1,000 on-chain transfers of the token (Etherscan V2)."""
        if not ETHERSCAN_API_KEY:
            return {"error": "ETHERSCAN_API_KEY is not set — get a free key at etherscan.io/apis and add it to .env", "transfers": []}
        cfg = ASSETS[ticker]
        try:
            data = _get(ETHERSCAN_URL, timeout=15, chainid=1, module="account", action="tokentx",
                        contractaddress=cfg["contract"], page=1, offset=1000, sort="desc",
                        apikey=ETHERSCAN_API_KEY).json()
            if data.get("status") != "1":
                return {"error": f"Etherscan: {data.get('result') or data.get('message')}", "transfers": []}
            txs = data["result"]
        except FETCH_ERRORS as e:
            return {"error": f"Etherscan request failed: {e}", "transfers": []}

        now = time.time()
        oldest = min(int(t["timeStamp"]) for t in txs) if txs else now
        transfers = []
        for tx in txs:
            amount = int(tx["value"]) / 10 ** cfg["decimals"]
            if amount < min_usd:
                continue
            transfers.append({
                "amount": amount, "from": tx["from"], "to": tx["to"],
                "hash": tx["hash"], "age_secs": now - int(tx["timeStamp"]),
            })
        return {"error": None, "transfers": transfers, "scanned": len(txs), "window_secs": now - oldest}

    # ── market context ─────────────────────────────────────────────────────────
    @ttl_cache(600)
    def get_fear_greed(self) -> dict | None:
        try:
            data = _get("https://api.alternative.me/fng/", limit=30).json()["data"]
            return {"value": int(data[0]["value"]), "label": data[0]["value_classification"],
                    "history": [int(d["value"]) for d in reversed(data)]}
        except FETCH_ERRORS as e:
            log.warning("Fear & Greed failed: %s", e)
            return None

    @ttl_cache(120)
    def get_gas_price(self) -> dict | None:
        if not ETHERSCAN_API_KEY:
            return None
        try:
            r = _get(ETHERSCAN_URL, chainid=1, module="gastracker", action="gasoracle", apikey=ETHERSCAN_API_KEY).json()["result"]
            return {"safe": float(r["SafeGasPrice"]), "propose": float(r["ProposeGasPrice"]), "fast": float(r["FastGasPrice"])}
        except FETCH_ERRORS as e:
            log.warning("Gas oracle failed: %s", e)
            return None

    @ttl_cache(1800)
    def get_google_trends(self, ticker) -> dict | None:
        """7-day search interest (0–100) for '<ticker> depeg' or the ticker. Google rate-limits this heavily."""
        try:
            from pytrends.request import TrendReq
            query = f"{ticker} depeg" if ticker in ("USDC", "USDT", "DAI", "FRAX") else ticker
            tr = TrendReq(hl="en-US", tz=360, timeout=(5, 10))
            tr.build_payload([query], timeframe="now 7-d")
            df = tr.interest_over_time()
            if df.empty or query not in df.columns:
                return None
            s = df[query].dropna()
            score, avg = int(s.iloc[-1]), float(s.mean())
            trend = "spiking" if score > avg * 1.3 else "falling" if score < avg * 0.7 else "steady"
            return {"query": query, "score": score, "week_avg": round(avg), "trend": trend, "series": s}
        except Exception as e:      # pytrends raises its own exception types
            log.warning("Google Trends failed: %s", e)
            return None

    REDDIT_SUBS = "CryptoCurrency+defi+stablecoins+ethfinance"
    # Searching the bare ticker mostly finds unrelated chatter ("how do I send USDC…"); these terms find stress.
    STRESS_TERMS = ["depeg", "depegged", "peg", "redeem", "redemption", "bank run", "reserves", "collapse",
                    "exploit", "hack", "freeze", "frozen", "insolvent", "audit"]

    def _reddit_query(self, ticker) -> str:
        terms = " OR ".join(f'"{t}"' if " " in t else t for t in self.STRESS_TERMS)
        return f"{ticker} ({terms})"

    def _reddit_token(self) -> str | None:
        """App-only OAuth token (client-credentials grant), refreshed shortly before it expires."""
        cid, secret = config.get("REDDIT_CLIENT_ID"), config.get("REDDIT_CLIENT_SECRET")
        if not (cid and secret):
            return None
        with self._reddit_lock:
            if self._reddit_auth and self._reddit_auth[1] > time.time():
                return self._reddit_auth[0]
            r = _session.post("https://www.reddit.com/api/v1/access_token", auth=(cid, secret),
                              data={"grant_type": "client_credentials"}, timeout=10,
                              headers={"User-Agent": REDDIT_UA})
            r.raise_for_status()
            body = r.json()
            self._reddit_auth = (body["access_token"], time.time() + int(body.get("expires_in", 3600)) - 120)
            return self._reddit_auth[0]

    def _reddit_api_posts(self, ticker, token) -> list[dict]:
        r = _session.get(f"https://oauth.reddit.com/r/{self.REDDIT_SUBS}/search", timeout=10,
                         params={"q": self._reddit_query(ticker), "restrict_sr": 1, "sort": "new", "t": "week", "limit": 100, "raw_json": 1},
                         headers={"Authorization": f"bearer {token}", "User-Agent": REDDIT_UA})
        r.raise_for_status()
        posts = []
        for child in r.json()["data"]["children"]:
            d = child["data"]
            posts.append({
                "title": d.get("title", ""), "url": "https://www.reddit.com" + d.get("permalink", ""),
                "sub": d.get("subreddit", ""), "score": d.get("score"), "comments": d.get("num_comments"),
                "time": datetime.fromtimestamp(d["created_utc"], timezone.utc) if d.get("created_utc") else None,
            })
        return posts

    def _reddit_rss_posts(self, ticker) -> list[dict]:
        ns = {"a": "http://www.w3.org/2005/Atom"}
        xml = _get(f"https://www.reddit.com/r/{self.REDDIT_SUBS}/search.rss",
                   timeout=10, q=self._reddit_query(ticker), restrict_sr=1, sort="new", t="week", limit=50).text
        posts = []
        for e in ET.fromstring(xml).findall("a:entry", ns):
            ts = e.findtext("a:updated", namespaces=ns) or e.findtext("a:published", namespaces=ns)
            cat, link = e.find("a:category", ns), e.find("a:link", ns)
            posts.append({
                "title": unescape(e.findtext("a:title", namespaces=ns) or ""),
                "url":   link.get("href") if link is not None else "",
                "sub":   cat.get("label", "").removeprefix("r/") if cat is not None else "",
                "score": None, "comments": None,
                "time":  datetime.fromisoformat(ts) if ts else None,
            })
        return posts

    @ttl_cache(1800, failure_seconds=600)
    def get_reddit_mentions(self, ticker) -> dict | None:
        """Recent posts mentioning the ticker in crypto subreddits. Official API if configured, else public RSS."""
        source = "rss"
        try:
            token = self._reddit_token()
            if token:
                posts, source = self._reddit_api_posts(ticker, token), "api"
            else:
                posts = self._reddit_rss_posts(ticker)
        except FETCH_ERRORS as e:
            log.warning("Reddit (%s) failed: %s", source, e)
            return None
        return self._score_posts(summarize_reddit(posts, source))

    def _score_posts(self, summary: dict) -> dict:
        """Adds FinBERT labels to post titles and the share that read as negative (0–100)."""
        posts = summary["posts"]
        pipe = self._sentiment_model() if posts else None
        if pipe is None:
            summary["negative_share"] = None
            return summary
        with self._sentiment_lock:
            results = pipe([p["title"][:500] for p in posts])
        for p, r in zip(posts, results):
            p["sentiment"] = r["label"]
        summary["negative_share"] = round(100 * sum(r["label"] == "negative" for r in results) / len(results), 1)
        return summary

    # ── DeFiLlama ──────────────────────────────────────────────────────────────
    @ttl_cache(600)
    def get_stablecoin_market_caps(self) -> list | None:
        try:
            coins = _get("https://stablecoins.llama.fi/stablecoins", timeout=15, includePrices="true").json()["peggedAssets"]
        except FETCH_ERRORS as e:
            log.warning("DeFiLlama stablecoins failed: %s", e)
            return None
        result = []
        for c in coins:
            cap = sum(v for v in (c.get("circulating") or {}).values() if isinstance(v, (int, float)))
            if cap < 1_000_000:
                continue
            result.append({
                "name": c.get("name", ""), "symbol": c.get("symbol", ""),
                "peg_type": (c.get("pegType") or "").removeprefix("pegged"),
                "peg_mech": c.get("pegMechanism") or "", "market_cap": cap,
                "price": c.get("price"), "chain_count": len(c.get("chains") or []),
                "yield_bearing": bool(c.get("yieldBearing")),
            })
        result.sort(key=lambda x: -x["market_cap"])
        return result[:25]

    @ttl_cache(600)
    def get_defi_protocols(self) -> list | None:
        targets = {"makerdao": "MakerDAO", "sky": "Sky", "aave-v3": "Aave V3", "compound-v3": "Compound V3",
                   "curve-dex": "Curve", "uniswap-v3": "Uniswap V3", "convex-finance": "Convex",
                   "lido": "Lido", "spark": "Spark", "ethena-usde": "Ethena", "frax-finance": "Frax", "liquity-v1": "Liquity"}
        try:
            protocols = _get("https://api.llama.fi/protocols", timeout=15).json()
        except FETCH_ERRORS as e:
            log.warning("DeFiLlama protocols failed: %s", e)
            return None
        result = [{
            "name": targets[p["slug"]], "slug": p["slug"], "tvl": p.get("tvl") or 0,
            "change_1d": p.get("change_1d"), "change_7d": p.get("change_7d"),
            "category": p.get("category", ""), "chains": p.get("chains", []),
        } for p in protocols if p.get("slug") in targets and (p.get("tvl") or 0) > 0]
        result.sort(key=lambda x: -x["tvl"])
        return result

    @ttl_cache(900)
    def get_stablecoin_yields(self) -> list | None:
        """Every DeFiLlama pool made up only of stablecoins (DeFiLlama's own `stablecoin` flag), TVL ≥ $100k."""
        try:
            pools = _get("https://yields.llama.fi/pools", timeout=20).json()["data"]
        except FETCH_ERRORS as e:
            log.warning("DeFiLlama yields failed: %s", e)
            return None
        return [{
            "protocol": p.get("project", ""), "symbol": p.get("symbol", ""), "chain": p.get("chain", ""),
            "apy": float(p.get("apy") or 0), "apy_base": float(p.get("apyBase") or 0),
            "apy_reward": float(p.get("apyReward") or 0), "tvl": float(p.get("tvlUsd") or 0),
            "il_risk": p.get("ilRisk") == "yes", "exposure": p.get("exposure", ""),
            "apy_mean_30d": p.get("apyMean30d"), "pool_id": p.get("pool", ""),
        } for p in pools
          if p.get("stablecoin") and (p.get("tvlUsd") or 0) >= 100_000 and (p.get("apy") or 0) > 0]
