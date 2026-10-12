import numpy as np
import pandas as pd
import pytest

import depeg_model as dm


def series(values, start="2024-01-01"):
    return pd.Series(values, index=pd.date_range(start, periods=len(values), freq="D"))


def test_labels_look_ahead_exactly_horizon_days():
    prices = [1.0] * 40
    prices[30] = 0.98                                # a 2% depeg on day 30
    labels = dm.build_labels(series(prices))
    assert labels.iloc[29] == 1 and labels.iloc[30 - dm.HORIZON_DAYS] == 1
    assert labels.iloc[30 - dm.HORIZON_DAYS - 1] == 0
    assert labels.iloc[-dm.HORIZON_DAYS:].isna().all()          # window not complete yet


def test_features_have_no_lookahead():
    base = [1.0 + 0.0001 * np.sin(i) for i in range(60)]
    shocked = base[:50] + [0.9] * 10
    a, b = dm.build_features(series(base)), dm.build_features(series(shocked))
    pd.testing.assert_frame_equal(a.iloc[:50], b.iloc[:50])     # the future can't change past rows


def test_latest_features_requires_history_but_allows_missing_supply():
    assert dm.latest_features(series([1.0] * 10)) is None
    f = dm.latest_features(series([1.0] * 60))
    assert f is not None and f["supply_change_7d"] is None
    sup = series(np.linspace(1e9, 0.9e9, 60))
    f2 = dm.latest_features(series([1.0] * 60), sup)
    assert f2["supply_change_7d"] < 0


@pytest.fixture(scope="module")
def engine():
    """A RiskEngine with the committed model loaded, without touching the database or network."""
    import json

    import joblib
    from chainintel_core import META_PATH, MODEL_PATH, RiskEngine
    e = RiskEngine.__new__(RiskEngine)
    e.model = joblib.load(MODEL_PATH)
    with open(META_PATH) as fh:
        e.model_meta = json.load(fh)
    return e


def test_live_model_scores_calm_and_shaky_coins(engine):
    rng = np.random.default_rng(0)
    calm = engine.predict_from_prices(series(1 + rng.normal(0, 0.0002, 120)))
    shaky_vals = 1 + rng.normal(0, 0.004, 120)
    shaky_vals[-1] = 0.999
    shaky = engine.predict_from_prices(series(shaky_vals))
    assert 0 <= calm["probability"] <= 100 and 0 <= shaky["probability"] <= 100
    assert shaky["probability"] > calm["probability"]


def test_off_peg_coins_are_not_forecast(engine):
    r = engine.predict_from_prices(series([1.0] * 59 + [0.98]))
    assert r["probability"] is None and r["label"] == "Off peg now"
