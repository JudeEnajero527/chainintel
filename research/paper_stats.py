"""
Extra statistics for the working paper "Forecasting Stablecoin Depegs".

Run from the project folder:   python3 research/paper_stats.py
Writes research/paper_stats.json and prints a summary. Takes a few minutes (it refits the model
for each robustness setting). Uses the same data, features and recipe as train_model.py and does
not touch the live model files.
"""
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import depeg_model as dm                                         # noqa: E402
from train_model import (ALERT_THRESHOLD, CALIB_END, TRAIN_END, purged_split,  # noqa: E402
                         fit_calibrated, new_model)

SIZE_BUCKETS = [(0, 1e7, "under $10M"), (1e7, 1e8, "$10M to $100M"), (1e8, 1e9, "$100M to $1B"), (1e9, np.inf, "$1B and over")]


def labels(prices: pd.Series, threshold: float, horizon: int) -> pd.Series:
    s = prices.sort_index()
    s = s[~s.index.duplicated(keep="last")].asfreq("D").ffill(limit=2)
    abs_dev = (s - 1.0).abs()
    future = pd.concat([abs_dev.shift(-k) for k in range(1, horizon + 1)], axis=1)
    out = (future.max(axis=1) >= threshold).astype(float)
    return out.where(future.notna().all(axis=1))


def dataset(history, supply, threshold=dm.DEPEG_THRESHOLD, horizon=dm.HORIZON_DAYS):
    sup = {c: g.set_index("date")["supply"] for c, g in supply.groupby("coin")}
    frames = []
    for coin, g in history.groupby("coin"):
        s = g.set_index("date")["price"]
        if len(s) < dm.MIN_HISTORY_DAYS + horizon:
            continue
        f = dm.build_features(s, sup.get(coin))
        f["label"] = labels(s, threshold, horizon)
        f["coin"] = coin
        frames.append(f)
    df = pd.concat(frames).rename_axis("date").reset_index()
    df = df[df["abs_dev"] < dm.PEGGED_THRESHOLD]
    return df.dropna(subset=dm.PRICE_FEATURES + ["label"])


def split(df, horizon=dm.HORIZON_DAYS):
    return purged_split(df, horizon)       # drops the last `horizon` dates before each boundary


def select_features(train, calib):
    """Same rule as train_model.py: fit raw trees on train, keep the input set with the higher
    validation average precision (price only vs price + supply)."""
    cands = {"price only": dm.PRICE_FEATURES, "price + supply": dm.FEATURES}
    val = {}
    for name, f in cands.items():
        raw = new_model().fit(train[f], train["label"])
        val[name] = average_precision_score(calib["label"], raw.predict_proba(calib[f])[:, 1])
    chosen = max(val, key=val.get)
    return chosen, cands[chosen], {k: round(float(v), 3) for k, v in val.items()}


def scores(y, p):
    y = np.asarray(y)
    if y.sum() == 0 or y.sum() == len(y):
        return {"rows": int(len(y)), "positives": int(y.sum()), "pr_auc": None}
    alert = p >= ALERT_THRESHOLD
    tp = int((alert & (y == 1)).sum())
    return {
        "rows": int(len(y)), "positives": int(y.sum()), "prevalence": round(float(y.mean()), 4),
        "pr_auc": round(float(average_precision_score(y, p)), 3),
        "roc_auc": round(float(roc_auc_score(y, p)), 3),
        "brier": round(float(brier_score_loss(y, p)), 4),
        "recall_at_alert": round(tp / y.sum(), 3),
        "precision_at_alert": round(tp / alert.sum(), 3) if alert.sum() else None,
    }


def episodes(history, threshold=dm.DEPEG_THRESHOLD):
    """Distinct depeg episodes: runs of consecutive days at least `threshold` off peg (gaps of 1 day merged)."""
    out = []
    for coin, g in history.groupby("coin"):
        s = g.set_index("date")["price"].sort_index()
        s = s[~s.index.duplicated(keep="last")].asfreq("D").ffill(limit=2)
        off = ((s - 1).abs() >= threshold) & s.notna()
        days = off[off].index
        if not len(days):
            continue
        start = prev = days[0]
        for d in days[1:]:
            if (d - prev).days > 2:
                out.append((coin, start, prev))
                start = d
            prev = d
        out.append((coin, start, prev))
    ep = pd.DataFrame(out, columns=["coin", "start", "end"])
    ep["days"] = (ep["end"] - ep["start"]).dt.days + 1
    return ep


def main():
    print("Downloading DefiLlama data…")
    meta = dm.fetch_meta()
    history = dm.fetch_price_history(meta=meta)
    supply = dm.fetch_supply_history([m for m in meta if m["gecko_id"] in set(history["coin"])])
    out = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
           "coins": int(history["coin"].nunique()),
           "data_start": f"{history['date'].min():%Y-%m-%d}", "data_end": f"{history['date'].max():%Y-%m-%d}"}
    feats = dm.FEATURES

    # 1. Descriptive statistics
    ep = episodes(history)
    ep["year"] = ep["start"].dt.year
    out["episodes_by_year"] = {int(y): {"episodes": int(len(g)), "coins": int(g["coin"].nunique()),
                                        "median_days": float(g["days"].median())} for y, g in ep.groupby("year")}
    out["episode_length_days"] = {q: float(ep["days"].quantile(v)) for q, v in [("p25", .25), ("median", .5), ("p75", .75), ("p90", .9)]}
    out["coins_by_first_year"] = {int(y): int(n) for y, n in history.groupby("coin")["date"].min().dt.year.value_counts().sort_index().items()}

    # 2. Main model again, with breakdowns
    df = dataset(history, supply)
    train, calib, test = split(df)
    out["split_rows"] = {n: {"rows": int(len(p)), "positives": int(p["label"].sum())} for n, p in [("train", train), ("validate", calib), ("test", test)]}
    chosen, feats, val_scores = select_features(train, calib)
    out["feature_set"] = {"chosen": chosen, "validation_ap": val_scores}
    model = fit_calibrated(train, calib, feats)
    p = model.predict_proba(test[feats])[:, 1]
    test = test.assign(p=p)
    out["main"] = scores(test["label"], p)

    # Calibration: forecasts grouped into bands, mean forecast vs share that depegged
    bands = [0, .02, .05, .10, .20, .40, 1.0001]
    test["band"] = pd.cut(test["p"], bands, right=False)
    out["calibration"] = [{"band": f"{b.left*100:.0f}% to {min(b.right,1)*100:.0f}%", "rows": int(len(g)),
                           "mean_forecast": round(float(g["p"].mean()), 4), "observed_rate": round(float(g["label"].mean()), 4)}
                          for b, g in test.groupby("band", observed=True)]

    # By calendar year and by coin size
    out["by_year"] = {int(y): scores(g["label"], g["p"].values) for y, g in test.groupby(test["date"].dt.year)}
    size = 10 ** test["log_supply"]
    out["by_size"] = {}
    for lo, hi, name in SIZE_BUCKETS:
        g = test[(size >= lo) & (size < hi)]
        out["by_size"][name] = {**scores(g["label"], g["p"].values), "coins": int(g["coin"].nunique())}
    g = test[test["log_supply"].isna()]
    out["by_size"]["supply unknown"] = {**scores(g["label"], g["p"].values), "coins": int(g["coin"].nunique())}

    # Episode-level: was there an alert in the 7 days before an episode began? (test-period episodes only)
    tep = ep[ep["start"] >= CALIB_END]
    alerts = test[test["p"] >= ALERT_THRESHOLD][["coin", "date"]]
    hit = 0
    for _, e in tep.iterrows():
        a = alerts[(alerts["coin"] == e["coin"]) & (alerts["date"] < e["start"]) & (alerts["date"] >= e["start"] - pd.Timedelta(days=7))]
        hit += int(len(a) > 0)
    out["episode_level"] = {"test_episodes": int(len(tep)), "warned_within_7d": hit,
                            "share_warned": round(hit / len(tep), 3) if len(tep) else None}

    # 3. Robustness: other thresholds and horizons (same recipe, refit each time)
    out["robustness"] = []
    for thr in (0.01, 0.02, 0.03):
        for hz in (1, 3, 7, 14):
            d = dataset(history, supply, thr, hz)
            tr, ca, te = split(d, hz)
            if te["label"].sum() == 0 or ca["label"].sum() == 0:
                continue
            _, f_hz, _ = select_features(tr, ca)
            m = fit_calibrated(tr, ca, f_hz)
            pp = m.predict_proba(te[f_hz])[:, 1]
            base = average_precision_score(te["label"], te["max_abs_dev_30d"])
            out["robustness"].append({"threshold": thr, "horizon_days": hz, **scores(te["label"], pp),
                                      "pr_auc_baseline": round(float(base), 3)})
            print(f"  threshold {thr:.0%} horizon {hz:2d}d  PR-AUC {out['robustness'][-1]['pr_auc']}  baseline {base:.3f}")

    with open(os.path.join(HERE, "paper_stats.json"), "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print(json.dumps({k: out[k] for k in ("main", "episode_level", "by_size")}, indent=2))
    print("\nSaved research/paper_stats.json")


if __name__ == "__main__":
    main()
