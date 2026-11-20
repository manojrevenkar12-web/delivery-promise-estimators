"""The three estimators the route planner asks for, and the rules they replace.

- Stop time: minutes at the door. One XGBoost model learns several quantiles at once (`reg:quantileerror` with a
  list of alphas) on log minutes, so the planner can be given whichever quantile the replay says pays best.
- Travel: the slowdown over the map router, by zone pair, hour, weekday and rain. Served to the planner as a
  matrix per day (zone x zone x hour), because the planner asks for thousands of legs a minute.
- Availability: the chance each rostered driver turns up. Summed into a distribution of shows per shift, from
  which the roster is sized at a chosen quantile.

Each has a `mean` variant: the usual squared-error fit, kept to show what a better MAE does and does not buy.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import NormalDist

import numpy as np
import pandas as pd
import xgboost as xgb


def _params(cfg: dict) -> dict:
    x = cfg["xgboost"]
    return dict(n_estimators=x["n_estimators"], max_depth=x["max_depth"], learning_rate=x["learning_rate"],
                subsample=x["subsample"], min_child_weight=x["min_child_weight"], tree_method="hist", n_jobs=1,
                random_state=0)


@dataclass
class QuantileModel:
    """A multi-quantile regressor on log(target); predicts any of its quantiles, monotone across quantiles."""

    features: list[str]
    quantiles: list[float]
    cfg: dict
    model: xgb.XGBRegressor | None = None

    def fit(self, x: pd.DataFrame, y: np.ndarray, w: np.ndarray | None = None) -> QuantileModel:
        self.model = xgb.XGBRegressor(objective="reg:quantileerror", quantile_alpha=np.array(self.quantiles),
                                      **_params(self.cfg))
        self.model.fit(x[self.features], np.log(np.maximum(y, 1e-3)), sample_weight=w)
        return self

    def predict_all(self, x: pd.DataFrame) -> np.ndarray:
        p = self.model.predict(x[self.features]).reshape(len(x), -1)
        return np.exp(np.sort(p, axis=1))          # no crossing quantiles

    def predict(self, x: pd.DataFrame, q: float) -> np.ndarray:
        return self.predict_all(x)[:, self.quantiles.index(q)]


@dataclass
class MeanModel:
    features: list[str]
    cfg: dict
    model: xgb.XGBRegressor | None = None

    def fit(self, x: pd.DataFrame, y: np.ndarray, w: np.ndarray | None = None) -> MeanModel:
        self.model = xgb.XGBRegressor(objective="reg:squarederror", **_params(self.cfg))
        self.model.fit(x[self.features], y, sample_weight=w)
        return self

    def predict(self, x: pd.DataFrame, q: float | None = None) -> np.ndarray:
        return np.maximum(self.model.predict(x[self.features]), 0.05)


def recent_base(x: pd.DataFrame) -> np.ndarray:
    """The live congestion index for a leg: the product of its two zones' recent factors (1 if unknown)."""
    b = x["from_recent"].to_numpy(dtype=float) * x["to_recent"].to_numpy(dtype=float)
    return np.where(np.isfinite(b) & (b > 0), b, 1.0)


@dataclass
class RelativeModel:
    """Learns the slowdown relative to the live congestion index, then scales back.

    Trees cannot extrapolate: a model of the raw slowdown stays low when road works push a zone past anything in
    its training window. Relative to the last days' index, the level shift is carried by the index and the model
    only learns the shape (hour, weekday, rain) around it.
    """

    inner: QuantileModel | MeanModel

    @property
    def quantiles(self) -> list[float]:
        return self.inner.quantiles  # type: ignore[union-attr]

    def fit(self, x: pd.DataFrame, y: np.ndarray, w: np.ndarray | None = None) -> RelativeModel:
        self.inner.fit(x, y / recent_base(x), w)
        return self

    def predict(self, x: pd.DataFrame, q: float | None = None) -> np.ndarray:
        return self.inner.predict(x, q) * recent_base(x)

    def predict_all(self, x: pd.DataFrame) -> np.ndarray:
        return self.inner.predict_all(x) * recent_base(x)[:, None]  # type: ignore[union-attr]


@dataclass
class AvailabilityModel:
    features: list[str]
    cfg: dict
    model: xgb.XGBClassifier | None = None

    def fit(self, x: pd.DataFrame, y: np.ndarray, w: np.ndarray | None = None) -> AvailabilityModel:
        p = _params(self.cfg) | {"n_estimators": 160, "max_depth": 4}
        self.model = xgb.XGBClassifier(objective="binary:logistic", **p)
        self.model.fit(x[self.features], y, sample_weight=w)
        return self

    def proba(self, x: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(x[self.features])[:, 1]

    def contributions(self, x: pd.DataFrame) -> pd.DataFrame:
        """Per-feature contributions (log-odds) to each driver's probability, from the trees themselves."""
        booster = self.model.get_booster()
        c = booster.predict(xgb.DMatrix(x[self.features]), pred_contribs=True)
        return pd.DataFrame(c[:, :-1], columns=self.features).assign(bias=c[:, -1])


def roster_size(p_in_order: np.ndarray, needed: int, quantile: float | None) -> int:
    """How many drivers to ask, in the hub's roster order, so that shows cover `needed`.

    quantile=None plans on expected shows; quantile=q plans on the q-th percentile of shows (normal approximation
    of the sum of independent Bernoullis, with a continuity correction).
    """
    z = NormalDist().inv_cdf(quantile) if quantile is not None else 0.0
    mu = np.cumsum(p_in_order)
    sd = np.sqrt(np.cumsum(p_in_order * (1 - p_in_order)))
    ok = np.flatnonzero(mu + z * sd >= needed - 0.5)
    return int(ok[0] + 1) if len(ok) else len(p_in_order)


@dataclass
class FallbackTable:
    """Last-known-good stop minutes by zone, crate band and stairs, for when the estimator service is down."""

    table: dict[tuple[int, int, int], float] = field(default_factory=dict)
    default: float = 4.0

    @staticmethod
    def key(zone: int, crates: int, floor: int, lift: int) -> tuple[int, int, int]:
        return int(zone), int(min(crates, 4)), int(floor >= 2 and not lift)

    @classmethod
    def build(cls, x: pd.DataFrame, minutes: np.ndarray, q: float) -> FallbackTable:
        df = x[["zone", "crates", "floor", "lift"]].copy()
        df["band"] = np.minimum(df["crates"], 4)
        df["stairs"] = ((df["floor"] >= 2) & (df["lift"] == 0)).astype(int)
        df["m"] = minutes
        g = df.groupby(["zone", "band", "stairs"])["m"].quantile(q)
        return cls({tuple(int(v) for v in k): float(val) for k, val in g.items()}, float(np.quantile(minutes, q)))

    def lookup(self, orders: pd.DataFrame) -> np.ndarray:
        return np.array([self.table.get(self.key(z, c, f, li), self.default) for z, c, f, li in
                         orders[["zone", "crates", "floor", "lift"]].itertuples(index=False)])


def pinball(y: np.ndarray, pred: np.ndarray, q: float) -> float:
    d = y - pred
    return float(np.mean(np.maximum(q * d, (q - 1) * d)))
