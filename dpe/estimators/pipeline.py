"""Training, the release gate, drift monitoring and what the planner is served.

A version is the five models trained on the same window of logs. A challenger replaces the champion only if,
on the last few days it did not train on, its pinball loss at the served quantiles is no worse than the
champion's by more than the configured margin. A drift monitor compares each day's actuals with what was served:
if actuals land under the served quantile clearly less often than they should, two days running, it asks for an
early retrain instead of waiting for the weekly one.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from dpe.estimators.models import AvailabilityModel, FallbackTable, MeanModel, QuantileModel, RelativeModel, pinball
from dpe.features.store import DRIVER_FEATURES, STOP_FEATURES, TRAVEL_FEATURES, FeatureStore

HOURS = range(6, 24)


@dataclass
class EstimatorSet:
    version: str
    through: int                       # trained on logs of days before this one
    stop_q: QuantileModel
    stop_mean: MeanModel
    travel_q: RelativeModel
    travel_mean: RelativeModel
    avail: AvailabilityModel
    fallback: dict[float, FallbackTable]
    rows: dict[str, int] = field(default_factory=dict)


def recency(days: np.ndarray, through: int, half_life: float) -> np.ndarray:
    """Training weight of a row: halves every `half_life` days back, so a new street pattern counts soon."""
    return 0.5 ** ((through - 1 - days) / half_life)


def train(store: FeatureStore, through: int, cfg: dict) -> EstimatorSet:
    days = range(through - cfg["training_window_days"], through)
    qs = list(cfg["quantiles"])
    hl = cfg["half_life_days"]
    xs, ys, ds = store.stop_training(days)
    xt, yt, dt = store.travel_training(days)
    xd, yd, dd = store.driver_training(days)
    ws, wt, wd = recency(ds, through, hl), recency(dt, through, hl), recency(dd, through, hl)
    return EstimatorSet(
        version=f"v{through}", through=through,
        stop_q=QuantileModel(STOP_FEATURES, qs, cfg).fit(xs, ys, ws),
        stop_mean=MeanModel(STOP_FEATURES, cfg).fit(xs, ys, ws),
        travel_q=RelativeModel(QuantileModel(TRAVEL_FEATURES, qs, cfg)).fit(xt, yt, wt),
        travel_mean=RelativeModel(MeanModel(TRAVEL_FEATURES, cfg)).fit(xt, yt, wt),
        avail=AvailabilityModel(DRIVER_FEATURES, cfg).fit(xd, yd, wd),
        fallback={q: FallbackTable.build(xs, ys, q) for q in qs},
        rows={"stops": len(ys), "legs": len(yt), "rosters": len(yd)},
    )


def gate(champion: EstimatorSet, challenger: EstimatorSet, store: FeatureStore, days: range, q_stop: float,
         q_travel: float, max_regression: float) -> tuple[bool, dict]:
    """Promote the challenger only if its pinball loss on `days` is at most `max_regression` worse than the
    champion's, for stop times and for travel. Neither model trained on `days`."""
    xs, ys, _ = store.stop_training(days)
    xt, yt, _ = store.travel_training(days)
    out = {
        "stop": (pinball(ys, champion.stop_q.predict(xs, q_stop), q_stop),
                 pinball(ys, challenger.stop_q.predict(xs, q_stop), q_stop)),
        "travel": (pinball(yt, champion.travel_q.predict(xt, q_travel), q_travel),
                   pinball(yt, challenger.travel_q.predict(xt, q_travel), q_travel)),
    }
    ok = all(ch <= c * (1 + max_regression) for c, ch in out.values())
    return ok, {k: {"champion": round(c, 4), "challenger": round(ch, 4)} for k, (c, ch) in out.items()}


@dataclass
class DriftMonitor:
    target: float
    band: float
    alarm_days: int
    history: list[tuple[int, float, float]] = field(default_factory=list)   # day, stop coverage, travel coverage

    def observe(self, day: int, stop_cov: float, travel_cov: float) -> bool:
        """Record a day's coverage; True when an early retrain is due."""
        self.history.append((day, stop_cov, travel_cov))
        low = [min(s, t) < self.target - self.band for _, s, t in self.history[-self.alarm_days:]]
        return len(low) == self.alarm_days and all(low)

    def reset(self) -> None:
        self.history.append((-1, np.nan, np.nan))       # a marker: count consecutive days from here


class Served:
    """What the planner gets for one day from one estimator mode ('rule', 'mean' or 'quantile')."""

    def __init__(self, est: EstimatorSet | None, rules: dict, store: FeatureStore, n_zones: int):
        self.est, self.rules, self.store, self.n_zones = est, rules, store, n_zones

    def rule_service(self, orders: pd.DataFrame) -> np.ndarray:
        r = self.rules
        return r["service_base"] + r["service_per_crate"] * orders["crates"].to_numpy()

    def service(self, orders: pd.DataFrame, day: int, weekday: int, forecast: dict, mode: str, q: float) -> np.ndarray:
        if mode == "rule" or self.est is None:
            return self.rule_service(orders)
        x = self.store.stop_frame(orders, day, weekday, forecast)
        return self.est.stop_mean.predict(x) if mode == "mean" else self.est.stop_q.predict(x, q)

    def fallback(self, orders: pd.DataFrame, q: float) -> np.ndarray:
        return self.est.fallback[q].lookup(orders) if self.est is not None else self.rule_service(orders)

    def travel_matrix(self, day: int, weekday: int, forecast: dict, mode: str, q: float) -> np.ndarray:
        """Slowdown factor F[zone_from, zone_to, hour] for hours 0..23."""
        full = np.full((self.n_zones, self.n_zones, 24), self.rules["travel_factor"], dtype=float)
        if mode == "rule" or self.est is None:
            return full
        g = self.store.travel_grid(day, weekday, forecast, HOURS)
        f = self.est.travel_mean.predict(g) if mode == "mean" else self.est.travel_q.predict(g, q)
        full[:, :, HOURS.start:HOURS.stop] = f.reshape(self.n_zones, self.n_zones, len(HOURS))
        full[:, :, :HOURS.start] = full[:, :, [HOURS.start]]
        return full

    def show_probs(self, day: int, shift: str, drivers: np.ndarray, tenure: np.ndarray, weekday: int,
                   forecast: dict, mode: str) -> np.ndarray:
        if mode == "rule" or self.est is None:
            return np.full(len(drivers), self.rules["show_rate"])
        x = self.store.driver_frame(day, shift, drivers, tenure, weekday, forecast)
        return self.est.avail.proba(x)
