"""
ChainIntel — depeg forecasting model.

Run:  python3 train_model.py
Saves: chainintel_model.pkl, chainintel_model_meta.json (honest out-of-sample metrics the app displays)

Data: DeFiLlama daily prices for ~230 USD stablecoins (2021 → today), including every coin that
has ever lost its peg — not just the big 9 — so the model sees hundreds of real depeg episodes.

Evaluation is strictly time-based: train on the past, calibrate on the next slice, test on data the
model has never seen. No shuffling, so no leakage from the future.
"""
import json
import os
from datetime import datetime, timezone

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.frozen import FrozenEstimator
from sklearn.inspection import permutation_importance
from sklearn.metrics import average_precision_score, brier_score_loss, precision_score, recall_score, roc_auc_score

from depeg_model import (DEPEG_THRESHOLD, FEATURES, HORIZON_DAYS, MIN_HISTORY_DAYS, PEGGED_THRESHOLD,
                         build_features, build_labels, fetch_price_history)

HERE = os.path.dirname(os.path.abspath(__file__))
TRAIN_END = pd.Timestamp("2024-07-01")   # train  < TRAIN_END
CALIB_END = pd.Timestamp("2025-01-01")   # calibrate [TRAIN_END, CALIB_END), test >= CALIB_END
ALERT_THRESHOLD = 0.20                   # probability at which the app shows "High Risk"


def make_dataset(history: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for coin, g in history.groupby("coin"):
        s = g.set_index("date")["price"]
        if len(s) < MIN_HISTORY_DAYS + HORIZON_DAYS:
            continue
        f = build_features(s)
        f["label"] = build_labels(s)
        f["coin"] = coin
        frames.append(f)
    df = pd.concat(frames).rename_axis("date").reset_index()
    # Only coins that are on peg today — the question is "will it break?", not "is it broken?"
    df = df[df["abs_dev"] < PEGGED_THRESHOLD]
    return df.dropna(subset=FEATURES + ["label"])


def new_model():
    return HistGradientBoostingClassifier(
        max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=100,
        l2_regularization=1.0, class_weight="balanced", random_state=42,
    )


def fit_calibrated(fit_df, calib_df):
    base = new_model().fit(fit_df[FEATURES], fit_df["label"])
    cal = CalibratedClassifierCV(FrozenEstimator(base), method="isotonic")
    return cal.fit(calib_df[FEATURES], calib_df["label"])


def main():
    print("Downloading DeFiLlama stablecoin price history…")
    history = fetch_price_history()
    print(f"  {len(history):,} daily prices · {history['coin'].nunique()} coins · "
          f"{history['date'].min():%Y-%m-%d} → {history['date'].max():%Y-%m-%d}")

    df = make_dataset(history)
    train = df[df["date"] < TRAIN_END]
    calib = df[(df["date"] >= TRAIN_END) & (df["date"] < CALIB_END)]
    test  = df[df["date"] >= CALIB_END]
    for name, part in [("train", train), ("calibrate", calib), ("test", test)]:
        print(f"  {name:9s} {len(part):7,} rows · {int(part['label'].sum()):5,} depeg-ahead · "
              f"{part['label'].mean()*100:.2f}% positive")

    # ── Out-of-sample evaluation ──────────────────────────────────────────────
    model = fit_calibrated(train, calib)
    p = model.predict_proba(test[FEATURES])[:, 1]
    y = test["label"].values
    baseline = test["max_abs_dev_30d"].values          # naive rule: "was it wobbly recently?"
    alert = p >= ALERT_THRESHOLD

    metrics = {
        "pr_auc":            round(float(average_precision_score(y, p)), 3),
        "pr_auc_baseline":   round(float(average_precision_score(y, baseline)), 3),
        "roc_auc":           round(float(roc_auc_score(y, p)), 3),
        "brier":             round(float(brier_score_loss(y, p)), 4),
        "prevalence":        round(float(y.mean()), 4),
        "alert_threshold":   ALERT_THRESHOLD,
        "precision_at_alert": round(float(precision_score(y, alert, zero_division=0)), 3),
        "recall_at_alert":    round(float(recall_score(y, alert, zero_division=0)), 3),
        "test_rows":         int(len(test)),
        "test_positives":    int(y.sum()),
        "test_start":        f"{CALIB_END:%Y-%m-%d}",
        "test_end":          f"{test['date'].max():%Y-%m-%d}",
    }
    print("\nOut-of-sample (test) results:")
    for k, v in metrics.items():
        print(f"  {k:20s} {v}")

    sample = test.sample(min(len(test), 20_000), random_state=0)
    imp = permutation_importance(model, sample[FEATURES], sample["label"],
                                 scoring="average_precision", n_repeats=3, random_state=0)
    importance = dict(sorted(((f, round(float(v), 4)) for f, v in zip(FEATURES, imp.importances_mean)),
                             key=lambda kv: -kv[1]))
    print("\nPermutation importance (drop in PR-AUC):")
    for f, v in importance.items():
        print(f"  {f:18s} {v:+.4f}")

    # ── Final model: same recipe, shifted forward to use all data ─────────────
    last = df["date"].max()
    final_calib_start = last - pd.Timedelta(days=183)
    final = fit_calibrated(df[df["date"] < final_calib_start], df[df["date"] >= final_calib_start])

    joblib.dump(final, os.path.join(HERE, "chainintel_model.pkl"))
    meta = {
        "trained_at":       datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "model":            "Gradient-boosted trees (HistGradientBoosting) + isotonic calibration",
        "question":         f"Will a currently-pegged stablecoin trade ≥{DEPEG_THRESHOLD:.0%} off peg within {HORIZON_DAYS} days?",
        "horizon_days":     HORIZON_DAYS,
        "depeg_threshold":  DEPEG_THRESHOLD,
        "pegged_threshold": PEGGED_THRESHOLD,
        "features":         FEATURES,
        "coins":            int(history["coin"].nunique()),
        "training_rows":    int(len(df)),
        "data_start":       f"{history['date'].min():%Y-%m-%d}",
        "data_end":         f"{last:%Y-%m-%d}",
        "metrics":          metrics,
        "importance":       importance,
    }
    with open(os.path.join(HERE, "chainintel_model_meta.json"), "w") as fh:
        json.dump(meta, fh, indent=2)
    for stale in ("chainintel_scaler.pkl", "chainintel_features.pkl"):
        if os.path.exists(os.path.join(HERE, stale)):
            os.remove(os.path.join(HERE, stale))
    print("\n✅ Saved chainintel_model.pkl + chainintel_model_meta.json")


if __name__ == "__main__":
    main()
