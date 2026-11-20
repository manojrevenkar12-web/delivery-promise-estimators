"""What the estimator service loads: a trained version plus the feature snapshot it needs to serve.

The training job writes a bundle; the service reads it. The snapshot holds per-address and per-zone statistics
as of the end of training, and the last 28 days of the shift log, so serving computes features exactly as
training did (`FeatureStore`).
"""
from __future__ import annotations

import pickle
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from dpe.estimators.pipeline import EstimatorSet
from dpe.features.store import FeatureStore

FILE = "bundle.pkl"


@dataclass
class Bundle:
    est: EstimatorSet
    snapshot: tuple
    shifts: dict[int, pd.DataFrame]
    recent: dict
    n_addresses: int
    n_zones: int
    quantiles: dict[str, float]

    @classmethod
    def from_store(cls, est: EstimatorSet, store: FeatureStore, quantiles: dict[str, float]) -> Bundle:
        snap = store.snapshot(est.through)
        shifts = {d: s for d, s in store.shifts.items() if est.through - 28 <= d < est.through}
        recent = {est.through: store.recent_zone_slowdown(est.through)}
        return cls(est, snap, shifts, recent, store.n_addr, store.n_zones, quantiles)

    def store(self) -> FeatureStore:
        s = FeatureStore(self.n_addresses, self.n_zones)
        s._sum, s._cnt, s._expected, s._zsum, s._zcnt = (a.copy() for a in self.snapshot)
        s.shifts = dict(self.shifts)
        s._recent = dict(self.recent)
        last = max(self.recent)
        s.recent_zone_slowdown = lambda day: s._recent.get(day, s._recent[last])  # served from the training snapshot
        return s

    def save(self, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / FILE
        path.write_bytes(pickle.dumps(self))
        return path

    @classmethod
    def load(cls, directory: Path) -> Bundle:
        # bundles are written by our own training job; never load one from elsewhere
        return pickle.loads((Path(directory) / FILE).read_bytes())
