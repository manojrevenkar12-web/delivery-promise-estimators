"""Point-in-time features from the logs.

The estimators see what the company records: orders and the address data customers typed in, the driver app's
stop times, telematics legs, the shift log, and the morning weather forecast. Every feature for day `d` is built
only from logs of days before `d`, so training rows and serving rows are computed the same way and nothing leaks
from the day being predicted (`tests/test_features.py`).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

STOP_FEATURES = ["crates", "empties", "items", "floor", "lift", "building", "zone", "hour", "weekday",
                 "rain_p", "temp", "addr_n", "addr_mean", "addr_ratio", "zone_mean"]
TRAVEL_FEATURES = ["z_from", "z_to", "hour", "weekday", "rain_p", "router", "from_recent", "to_recent"]
RECENT_DAYS = 3
DRIVER_FEATURES = ["tenure", "new", "weekday", "late", "rain_p", "temp", "driver_absence", "driver_shifts",
                   "hub_absence_7", "hub_absence_2"]


class FeatureStore:
    """Logs by day, plus running per-address statistics snapshotted at the start of each day."""

    def __init__(self, n_addresses: int, n_zones: int):
        self.n_addr, self.n_zones = n_addresses, n_zones
        self.stops: dict[int, pd.DataFrame] = {}
        self.legs: dict[int, pd.DataFrame] = {}
        self.shifts: dict[int, pd.DataFrame] = {}
        self.forecasts: dict[int, dict] = {}
        self.weekdays: dict[int, int] = {}
        self._sum = np.zeros(n_addresses)
        self._cnt = np.zeros(n_addresses)
        self._expected = np.zeros(n_addresses)        # sum of a simple norm, to learn how slow an address is
        self._zsum = np.zeros(n_zones)
        self._zcnt = np.zeros(n_zones)
        self._snap: dict[int, tuple[np.ndarray, ...]] = {}
        self._recent: dict[int, np.ndarray] = {}

    # -- ingest ---------------------------------------------------------------------------------------------
    def add_day(self, day: int, weekday: int, forecast: dict, stops: pd.DataFrame, legs: pd.DataFrame,
                shifts: pd.DataFrame) -> None:
        if day in self.weekdays:
            raise ValueError(f"day {day} already ingested")      # a day is written once
        if self.weekdays and day != max(self.weekdays) + 1:
            raise ValueError(f"days must arrive in order, got {day} after {max(self.weekdays)}")
        self.snapshot(day)
        self.weekdays[day], self.forecasts[day] = weekday, forecast
        self.stops[day], self.legs[day], self.shifts[day] = stops, legs, shifts
        if len(stops):
            a = stops["address"].to_numpy()
            np.add.at(self._sum, a, stops["minutes"].to_numpy())
            np.add.at(self._cnt, a, 1)
            np.add.at(self._expected, a, _norm(stops))
            z = stops["zone"].to_numpy()
            np.add.at(self._zsum, z, stops["minutes"].to_numpy())
            np.add.at(self._zcnt, z, 1)

    def snapshot(self, day: int) -> tuple[np.ndarray, ...]:
        """Address and zone statistics as they stood at the start of `day`."""
        if day not in self._snap:
            self._snap[day] = (self._sum.copy(), self._cnt.copy(), self._expected.copy(),
                               self._zsum.copy(), self._zcnt.copy())
        return self._snap[day]

    @property
    def last_day(self) -> int:
        return max(self.weekdays) if self.weekdays else -1

    # -- stop features --------------------------------------------------------------------------------------
    def stop_frame(self, orders: pd.DataFrame, day: int, weekday: int, forecast: dict) -> pd.DataFrame:
        s, c, e, zs, zc = self.snapshot(day)
        a = orders["address"].to_numpy()
        z = orders["zone"].to_numpy()
        with np.errstate(invalid="ignore", divide="ignore"):
            addr_mean = np.where(c[a] > 0, s[a] / np.maximum(c[a], 1), np.nan)
            addr_ratio = np.where(c[a] > 0, s[a] / np.maximum(e[a], 1e-9), np.nan)
            zone_mean = np.where(zc[z] > 0, zs[z] / np.maximum(zc[z], 1), np.nan)
        return pd.DataFrame({
            "crates": orders["crates"].to_numpy(), "empties": orders["empties"].to_numpy(),
            "items": orders["items"].to_numpy(), "floor": orders["floor"].to_numpy(), "lift": orders["lift"].to_numpy(),
            "building": orders["building"].to_numpy(), "zone": z, "hour": orders["placed"].to_numpy() // 60,
            "weekday": weekday, "rain_p": forecast["forecast_rain_prob"], "temp": forecast["forecast_temp"],
            "addr_n": c[a], "addr_mean": addr_mean, "addr_ratio": addr_ratio, "zone_mean": zone_mean,
        })

    def stop_training(self, days: range) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
        """Features, minutes, and the day each row comes from."""
        xs, ys, ds = [], [], []
        for d in days:
            st = self.stops.get(d)
            if st is None or st.empty:
                continue
            xs.append(self.stop_frame(st, d, self.weekdays[d], self.forecasts[d]))
            ys.append(st["minutes"].to_numpy())
            ds.append(np.full(len(st), d))
        return pd.concat(xs, ignore_index=True), np.concatenate(ys), np.concatenate(ds)

    # -- travel features ------------------------------------------------------------------------------------
    def recent_zone_slowdown(self, day: int) -> np.ndarray:
        """A live congestion index per zone from the last few logged days of telematics, so a new road works site
        shows up the next morning. Fitted as log(slowdown) = c[zone_from] + c[zone_to] by ridge least squares, so
        a leg's index is the product of its two zones' factors and a slow zone does not make its neighbours look
        slow. NaN for zones without legs."""
        if day in self._recent:
            return self._recent[day]
        past = [self.legs[d] for d in sorted(self.legs) if day - 7 <= d < day and len(self.legs[d])][-RECENT_DAYS:]
        out = np.full(self.n_zones, np.nan)
        if past:
            lg = pd.concat(past, ignore_index=True)
            zf, zt = lg["z_from"].to_numpy().astype(int), lg["z_to"].to_numpy().astype(int)
            a = np.zeros((len(lg), self.n_zones))
            np.add.at(a, (np.arange(len(lg)), zf), 1)
            np.add.at(a, (np.arange(len(lg)), zt), 1)
            y = np.log((lg["minutes"] / lg["router"]).to_numpy())
            lam = 5.0
            c = np.linalg.solve(a.T @ a + lam * np.eye(self.n_zones), a.T @ y)
            seen = a.sum(axis=0) > 0
            out[seen] = np.exp(c[seen])
        self._recent[day] = out
        return out

    def travel_training(self, days: range) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
        xs, ys, ds = [], [], []
        for d in days:
            lg = self.legs.get(d)
            if lg is None or lg.empty:
                continue
            rec = self.recent_zone_slowdown(d)
            zf, zt = lg["z_from"].to_numpy().astype(int), lg["z_to"].to_numpy().astype(int)
            xs.append(pd.DataFrame({"z_from": zf, "z_to": zt, "hour": lg["hour"].to_numpy(), "weekday": self.weekdays[d],
                                    "rain_p": self.forecasts[d]["forecast_rain_prob"], "router": lg["router"].to_numpy(),
                                    "from_recent": rec[zf], "to_recent": rec[zt]}))
            ys.append(lg["minutes"].to_numpy() / lg["router"].to_numpy())
            ds.append(np.full(len(lg), d))
        return pd.concat(xs, ignore_index=True), np.concatenate(ys), np.concatenate(ds)

    def travel_grid(self, day: int, weekday: int, forecast: dict, hours: range, router: float = 8.0) -> pd.DataFrame:
        n = self.n_zones
        zf, zt, h = np.meshgrid(np.arange(n), np.arange(n), np.array(list(hours)) + 0.5, indexing="ij")
        rec = self.recent_zone_slowdown(day)
        return pd.DataFrame({"z_from": zf.ravel(), "z_to": zt.ravel(), "hour": h.ravel(), "weekday": weekday,
                             "rain_p": forecast["forecast_rain_prob"], "router": router,
                             "from_recent": rec[zf.ravel()], "to_recent": rec[zt.ravel()]})

    # -- driver features ------------------------------------------------------------------------------------
    def driver_frame(self, day: int, shift: str, drivers: np.ndarray, tenure: np.ndarray, weekday: int,
                     forecast: dict) -> pd.DataFrame:
        past = [self.shifts[d] for d in range(day - 28, day) if d in self.shifts and len(self.shifts[d])]
        hist = pd.concat(past, ignore_index=True) if past else pd.DataFrame(columns=["day", "driver", "showed"])
        by = hist.groupby("driver")["showed"].agg(["mean", "count"]) if len(hist) else None

        def hub_rate(k: int) -> float:
            h = hist[hist["day"] >= day - k] if len(hist) else hist
            return float(1 - h["showed"].mean()) if len(h) else np.nan

        absence = np.array([1 - by.loc[d, "mean"] if by is not None and d in by.index else np.nan for d in drivers])
        count = np.array([by.loc[d, "count"] if by is not None and d in by.index else 0 for d in drivers])
        return pd.DataFrame({"tenure": np.minimum(tenure, 400), "new": (tenure < 45).astype(int), "weekday": weekday,
                             "late": int(shift == "late"), "rain_p": forecast["forecast_rain_prob"],
                             "temp": forecast["forecast_temp"], "driver_absence": absence, "driver_shifts": count,
                             "hub_absence_7": hub_rate(7), "hub_absence_2": hub_rate(2)})

    def driver_training(self, days: range) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
        xs, ys, ds = [], [], []
        for d in days:
            sh = self.shifts.get(d)
            if sh is None or sh.empty:
                continue
            for shift, g in sh.groupby("shift"):
                dr = g["driver"].to_numpy()
                xs.append(self.driver_frame(d, shift, dr, g["tenure"].to_numpy(), self.weekdays[d], self.forecasts[d]))
                ys.append(g["showed"].to_numpy())
                ds.append(np.full(len(g), d))
        return pd.concat(xs, ignore_index=True), np.concatenate(ys), np.concatenate(ds)


def _norm(stops: pd.DataFrame) -> np.ndarray:
    """A plain norm for a stop (the planner's rule of thumb), so an address's history says how slow it is
    relative to what its orders would suggest, not just how big its orders are."""
    return 2.0 + 0.8 * stops["crates"].to_numpy()
