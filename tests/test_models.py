import numpy as np
import pandas as pd

from dpe.estimators.models import FallbackTable, QuantileModel, pinball, roster_size
from dpe.estimators.pipeline import DriftMonitor, recency


def test_quantiles_are_ordered_and_roughly_calibrated(small_est):
    r = np.random.default_rng(0)
    x = pd.DataFrame({"a": r.uniform(0, 4, 6000), "b": r.integers(0, 3, 6000)})
    y = np.exp(0.3 * x["a"] + 0.2 * x["b"] + r.normal(0, 0.4, 6000))
    m = QuantileModel(["a", "b"], [0.5, 0.7, 0.9], small_est | {"xgboost": small_est["xgboost"] | {"n_estimators": 80}})
    m.fit(x.iloc[:4000], y[:4000])
    allq = m.predict_all(x.iloc[4000:])
    assert (np.diff(allq, axis=1) >= 0).all()
    for i, q in enumerate([0.5, 0.7, 0.9]):
        assert abs(np.mean(y[4000:] <= allq[:, i]) - q) < 0.06


def test_a_lower_quantile_of_shows_asks_more_drivers():
    p = np.full(40, 0.85)
    expected = roster_size(p, 20, None)
    cautious = roster_size(p, 20, 0.2)
    bold = roster_size(p, 20, 0.7)
    assert bold <= expected <= cautious
    assert roster_size(np.full(5, 0.9), 20, 0.5) == 5          # cannot ask more drivers than there are


def test_pinball_penalises_the_side_that_matters():
    y = np.array([10.0])
    assert pinball(y, np.array([8.0]), 0.9) > pinball(y, np.array([12.0]), 0.9)


def test_fallback_table_uses_its_band_and_a_default():
    x = pd.DataFrame({"zone": [1, 1, 2], "crates": [1, 1, 5], "floor": [0, 0, 3], "lift": [0, 0, 0]})
    t = FallbackTable.build(x, np.array([2.0, 4.0, 9.0]), 0.5)
    got = t.lookup(pd.DataFrame({"zone": [1, 7], "crates": [1, 1], "floor": [0, 0], "lift": [0, 0]}))
    assert got[0] == 3.0 and got[1] == t.default


def test_drift_alarm_needs_consecutive_low_days():
    m = DriftMonitor(target=0.7, band=0.1, alarm_days=2)
    assert not m.observe(1, 0.55, 0.7)
    assert m.observe(2, 0.7, 0.5)
    m.reset()
    assert not m.observe(3, 0.5, 0.5)
    assert not m.observe(4, 0.72, 0.71)


def test_recent_days_weigh_more():
    w = recency(np.array([0, 9, 19]), 20, 10.0)
    assert w[2] == 1.0 and abs(w[1] - 0.5) < 1e-9 and w[0] < w[1]
