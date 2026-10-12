import json
import math

import numpy as np

from chainintel_core import _jsonable, compute_risk, liquidity_risk, peg_risk, summarize_reddit


def test_peg_risk_scale():
    assert peg_risk(1.0) == 0
    assert math.isclose(peg_risk(0.999), 10, rel_tol=1e-6)
    assert peg_risk(0.98) == 100          # capped
    assert peg_risk(None) is None


def test_liquidity_risk_is_log_scaled_and_clamped():
    assert liquidity_risk(500e6) == 0
    assert liquidity_risk(5e6) == 100
    assert 40 < liquidity_risk(50e6) < 60
    assert liquidity_risk(None) is None and liquidity_risk(0) is None


def test_no_price_means_no_score():
    r = compute_risk(None, 100e6, 20)
    assert r["total"] is None


def test_missing_components_are_dropped_not_guessed():
    only_peg = compute_risk(0.999, None, None)
    assert only_peg["total"] == round(peg_risk(0.999), 1)       # weights re-normalised, no fake 50s
    assert only_peg["used"] == ["peg"]
    full = compute_risk(1.0, 500e6, 0)
    assert full["total"] == 0


def test_snapshot_payloads_serialise_numpy_values():
    payload = {"x": np.float64(1.5), "y": np.int64(2)}
    assert json.loads(json.dumps(payload, default=_jsonable)) == {"x": 1.5, "y": 2}


def test_reddit_buzz():
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    posts = [{"title": "a", "time": now - timedelta(hours=2)}] + [{"title": "b", "time": now - timedelta(days=3)}] * 6
    s = summarize_reddit(posts, "api")
    assert s["count_24h"] == 1 and s["count_7d"] == 7 and s["buzz"] == 50
