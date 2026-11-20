"""The data lake stand-in: daily log files, as the driver app, telematics and the shift tool would write them.

`write_day` writes a day's logs as Parquet partitions (`stops/day=…`, `legs/day=…`, `shifts/day=…`) with
the morning forecast; `read_store` loads them into a `FeatureStore`. The training job only ever reads files, so
it runs the same against a real lake export.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from dpe.features.store import FeatureStore


def write_day(lake: Path, day: int, weekday: int, forecast: dict, stops: pd.DataFrame, legs: pd.DataFrame,
              shifts: pd.DataFrame, n_addresses: int, n_zones: int) -> None:
    """Write one day's partitions and update the index."""
    lake.mkdir(parents=True, exist_ok=True)
    for name, df in (("stops", stops), ("legs", legs), ("shifts", shifts)):
        p = lake / name / f"day={day:03d}"
        p.mkdir(parents=True, exist_ok=True)
        df.to_parquet(p / "part.parquet", index=False)
    mp = lake / "meta.json"
    meta = json.loads(mp.read_text()) if mp.exists() else {"n_addresses": n_addresses, "n_zones": n_zones, "days": {}}
    meta["days"][str(day)] = {"weekday": weekday, **forecast}
    mp.write_text(json.dumps(meta, indent=1))


def read_store(lake: Path, through: int | None = None) -> FeatureStore:
    meta = json.loads((lake / "meta.json").read_text())
    store = FeatureStore(meta["n_addresses"], meta["n_zones"])
    days = sorted(int(d) for d in meta["days"])
    for d in days:
        if through is not None and d >= through:
            break
        m = meta["days"][str(d)]
        parts = {n: pd.read_parquet(lake / n / f"day={d:03d}" / "part.parquet") for n in ("stops", "legs", "shifts")}
        store.add_day(d, m["weekday"], {"forecast_temp": m["forecast_temp"], "forecast_rain_prob": m["forecast_rain_prob"]},
                      parts["stops"], parts["legs"], parts["shifts"])
    return store


def last_open_days(store: FeatureStore, before: int, n: int) -> list[int]:
    return [d for d in range(before - 1, max(before - 15, -1), -1) if d in store.stops and len(store.stops[d])][:n]
