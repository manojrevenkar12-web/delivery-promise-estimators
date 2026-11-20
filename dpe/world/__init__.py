"""The simulated hubs, and the truth about them.

A hub delivers from one depot to customers in a 12 x 12 km square. The world knows what nobody in the company
knows directly:

- how long a stop really takes (the parking at that address, the customer, a lift that is broken);
- how slow the streets really are (rush hours by zone, rain, road works that start mid-period);
- who will really turn up for a shift (a flu wave, a driver who is often ill).

What the company can see comes out of the world as logs (`stop_log`, `leg_log`, `shift_log`), orders, address
data that customers typed in, and a weather forecast. Estimators never import this package
(`tests/test_invariants.py`).

Every draw is keyed by what it is about (`dpe.keyed`), so every design meets the same orders, streets and
absences.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import numpy as np
import pandas as pd

from dpe.keyed import rng

MIN_PER_DAY = 1440
SHIFTS = {"early": (7 * 60, 15 * 60), "late": (14 * 60, 22 * 60)}


@dataclass(frozen=True)
class Weather:
    temp: float
    rain: bool
    forecast_temp: float
    forecast_rain_prob: float


class World:
    def __init__(self, cfg: dict, seed: int):
        self.cfg, self.seed = cfg, seed
        self.days = cfg["history_days"] + cfg["eval_days"]
        self.start = dt.date.fromisoformat(cfg["start"])
        h = cfg["hub"]
        r = rng(seed, "hub")
        k = h["zones_per_side"]
        self.n_zones = k * k
        w = h["half_width_km"]
        n = h["addresses"]
        self.xy = r.uniform(-w, w, size=(n, 2))
        cell = (2 * w) / k
        zx = np.minimum(((self.xy[:, 0] + w) // cell).astype(int), k - 1)
        zy = np.minimum(((self.xy[:, 1] + w) // cell).astype(int), k - 1)
        self.zone = zy * k + zx
        s = cfg["service"]
        lo, hi = s["zone_parking"]
        self.zone_parking = r.uniform(lo, hi, self.n_zones)
        highrise = r.uniform(0.1, 0.8, self.n_zones)
        u = r.random(n)
        self.building = np.where(u < highrise[self.zone], 1, np.where(u < highrise[self.zone] + 0.12, 2, 0))
        self.floor = np.where(self.building == 0, r.integers(0, 2, n),
                              np.where(self.building == 1, r.integers(0, 8, n), r.integers(0, 5, n)))
        lift_p = np.where(self.building == 2, 0.8, np.where(self.floor >= 3, 0.6, 0.15))
        self.lift = (r.random(n) < lift_p) & (self.building > 0)
        # hidden, per address
        self.parking = np.clip(self.zone_parking[self.zone] + r.normal(0, s["parking_sd"], n), 0, None)
        self.customer = np.exp(r.normal(0, s["customer_sd"], n))
        pop = r.pareto(1.2, n) + 1
        self.popularity = pop / pop.sum()
        t = cfg["travel"]
        self.rush = r.uniform(*t["rush_amp"], self.n_zones)
        rg = cfg["regime"]
        self.roadworks = np.zeros(self.n_zones, dtype=bool)
        self.roadworks[r.choice(self.n_zones, rg["roadworks_zones"], replace=False)] = True
        self.roadworks_day = cfg["history_days"] + rg["roadworks_eval_day"]
        d = cfg["drivers"]
        pool = d["pool"]
        self.tenure0 = r.integers(46, 1100, pool)
        hires = r.choice(pool, d["hired_during"], replace=False)
        self.tenure0[hires] = -r.integers(-10, self.days - 7, d["hired_during"])   # some join during the period
        self.driver_reliability = r.normal(0, d["driver_sd"], pool)
        self.flu = np.zeros(self.days)
        for _ in range(r.integers(d["flu_waves"][0], d["flu_waves"][1] + 1)):
            a = int(r.integers(5, self.days - 8))
            self.flu[a:a + int(r.integers(*d["flu_days"]))] = max(self.flu[a], r.uniform(*d["flu_penalty"]))
        wcfg = cfg["weather"]
        ts = np.linspace(wcfg["temp_start"], wcfg["temp_end"], self.days)
        self._weather = []
        for day in range(self.days):
            rw = rng(seed, "weather", day)
            temp = float(ts[day] + rw.normal(0, wcfg["temp_sd"]))
            rain = bool(rw.random() < wcfg["rain_prob"])
            fp = float(np.clip((0.75 if rain else 0.15) + rw.normal(0, 0.1), 0.02, 0.98))
            self._weather.append(Weather(temp, rain, float(temp + rw.normal(0, wcfg["forecast_temp_sd"])), fp))
        o = cfg["outages"]
        self.outages: dict[int, list[tuple[int, int]]] = {}
        ro = rng(seed, "outages")
        eval_days = [x for x in range(cfg["history_days"], self.days) if self.weekday(x) != 6]
        for day in ro.choice(eval_days, o["per_eval"], replace=False):
            s0 = int(ro.integers(*o["window"]))
            self.outages.setdefault(int(day), []).append((s0, s0 + int(ro.integers(*o["minutes"]))))
        self._orders: dict[int, pd.DataFrame] = {}

    # -- calendar and weather -------------------------------------------------------------------------------
    def date(self, day: int) -> dt.date:
        return self.start + dt.timedelta(days=day)

    def weekday(self, day: int) -> int:
        return self.date(day).weekday()

    def weather(self, day: int) -> Weather:
        return self._weather[day]

    def forecast(self, day: int) -> dict:
        w = self._weather[day]
        return {"forecast_temp": w.forecast_temp, "forecast_rain_prob": w.forecast_rain_prob}

    # -- addresses: what customers typed in -----------------------------------------------------------------
    def addresses(self) -> pd.DataFrame:
        return pd.DataFrame({"address": np.arange(len(self.zone)), "x": self.xy[:, 0], "y": self.xy[:, 1],
                             "zone": self.zone, "building": self.building, "floor": self.floor,
                             "lift": self.lift.astype(int)})

    # -- orders ---------------------------------------------------------------------------------------------
    def orders(self, day: int) -> pd.DataFrame:
        if day in self._orders:
            return self._orders[day]
        o = self.cfg["orders"]
        wd = self.weekday(day)
        r = rng(self.seed, "orders", day)
        temp = self._weather[day].temp
        lam = o["per_day"] * o["weekday_factor"][wd] * (1 + o["hot_per_10c"] * max(0.0, temp - 18) / 10)
        n = int(r.poisson(lam)) if lam > 0 else 0
        hours = np.arange(o["first_hour"], o["last_hour"] + 1)
        prof = np.array(o["hour_profile"])
        prof = prof / prof.sum()
        hour = r.choice(hours, n, p=prof)
        placed = np.sort(hour * 60 + r.integers(0, 60, n))
        regular = r.random(n) < self.cfg["hub"]["regulars_share"]
        addr = np.where(regular, r.choice(len(self.zone), n, p=self.popularity), r.integers(0, len(self.zone), n))
        crates = 1 + r.poisson(o["crates_mean"] - 1, n)
        empties = r.binomial(crates, o["empties_share"])
        items = r.poisson(o["items_mean"], n)
        df = pd.DataFrame({"order": [f"{day}-{i}" for i in range(n)], "day": day, "placed": placed,
                           "address": addr, "crates": crates, "empties": empties, "items": items})
        df["zone"] = self.zone[addr]
        df["building"] = self.building[addr]
        df["floor"] = self.floor[addr]
        df["lift"] = self.lift[addr].astype(int)
        self._orders[day] = df
        return df

    # -- the truth at the door ------------------------------------------------------------------------------
    def stop_minutes(self, day: int, orders: pd.DataFrame) -> np.ndarray:
        """True minutes at the door for each order, before the driver's own speed (see `driver_factor`)."""
        s = self.cfg["service"]
        a = orders["address"].to_numpy()
        crates = orders["crates"].to_numpy()
        stairs = 1 + s["stairs_per_floor"] * self.floor[a] * (1 - self.lift[a])
        base = (s["base"] + s["per_crate"] * crates * stairs + s["per_empty"] * orders["empties"].to_numpy()
                + s["per_item"] * orders["items"].to_numpy() + self.parking[a] + np.array(s["building"])[self.building[a]])
        r = rng(self.seed, "stops", day)
        n = len(orders)
        noise = np.exp(r.normal(0, s["noise_sigma"], n))
        wait = np.where(r.random(n) < s["wait_prob"], r.uniform(*s["wait_minutes"], n), 0.0)
        rain = 1 + s["rain"] * self._weather[day].rain
        return base * self.customer[a] * rain * noise + wait

    def tenure(self, day: int) -> np.ndarray:
        return self.tenure0 + day

    def driver_factor(self, day: int, driver: int) -> float:
        return 1 + self.cfg["service"]["new_driver"] * (0 <= self.tenure(day)[driver] < 45)

    # -- the truth on the street ----------------------------------------------------------------------------
    def router_minutes(self, a_xy: np.ndarray, b_xy: np.ndarray) -> np.ndarray:
        """What a map router says: street distance at a fixed speed. Visible to everyone."""
        h = self.cfg["hub"]
        km = np.abs(a_xy - b_xy).sum(axis=-1) * h["detour"] + 0.15
        return km / h["router_kmh"] * 60

    def zone_of(self, xy: np.ndarray) -> np.ndarray:
        w, k = self.cfg["hub"]["half_width_km"], self.cfg["hub"]["zones_per_side"]
        cell = 2 * w / k
        zx = np.clip(((xy[..., 0] + w) // cell).astype(int), 0, k - 1)
        zy = np.clip(((xy[..., 1] + w) // cell).astype(int), 0, k - 1)
        return zy * k + zx

    def travel_factor(self, day: int, z_from: np.ndarray, z_to: np.ndarray, hour: np.ndarray) -> np.ndarray:
        """True slowdown over the router, without noise."""
        t = self.cfg["travel"]
        peak = (np.exp(-((hour - t["morning_peak"]) / 1.2) ** 2)
                + 0.8 * np.exp(-((hour - t["evening_peak"]) / 1.5) ** 2))
        f = 1 + 0.5 * (self.rush[z_from] + self.rush[z_to]) * peak
        if self.weekday(day) == 5:
            f = f * t["saturday"]
        if self._weather[day].rain:
            f = f * t["rain"]
        if day >= self.roadworks_day:
            f = f * np.where(self.roadworks[z_from] | self.roadworks[z_to], self.cfg["regime"]["roadworks_factor"], 1.0)
        return f

    def leg_minutes(self, day: int, a_xy: np.ndarray, b_xy: np.ndarray, depart: float, key: str) -> float:
        za, zb = self.zone_of(a_xy), self.zone_of(b_xy)
        f = self.travel_factor(day, np.array([za]), np.array([zb]), np.array([depart / 60.0]))[0]
        noise = float(np.exp(rng(self.seed, "leg", day, key).normal(0, self.cfg["travel"]["noise_sigma"])))
        return float(self.router_minutes(a_xy, b_xy)) * f * noise

    # -- the truth about drivers ----------------------------------------------------------------------------
    def eligible(self, day: int) -> np.ndarray:
        return np.flatnonzero(self.tenure(day) >= 0)

    def roster_order(self, day: int, shift: str) -> np.ndarray:
        """The order in which the hub asks drivers to work a shift (the same for every design)."""
        e = self.eligible(day)
        return rng(self.seed, "roster", day, shift).permutation(e)

    def show_prob(self, day: int, shift: str, drivers: np.ndarray) -> np.ndarray:
        d = self.cfg["drivers"]
        wd = self.weekday(day)
        p = (d["base_show"] - d["new_penalty"] * (self.tenure(day)[drivers] < 45) - d["monday_penalty"] * (wd == 0)
             - d["saturday_late_penalty"] * (wd == 5 and shift == "late") - d["rain_penalty"] * self._weather[day].rain
             - self.flu[day] + self.driver_reliability[drivers])
        return np.clip(p, 0.3, 0.995)

    def shows(self, day: int, shift: str, drivers: np.ndarray) -> np.ndarray:
        p = self.show_prob(day, shift, drivers)
        u = np.array([rng(self.seed, "show", day, shift, int(i)).random() for i in drivers])
        return u < p

    # -- infrastructure -------------------------------------------------------------------------------------
    def outage(self, day: int, minute: float) -> bool:
        return any(a <= minute < b for a, b in self.outages.get(day, []))

    # -- logs: what the company records, the same for every design -----------------------------------------
    def stop_log(self, day: int) -> pd.DataFrame:
        """Every stop of the day with its measured minutes at the door (from the driver app)."""
        o = self.orders(day).copy()
        if o.empty:
            return o.assign(minutes=[], driver_new=[])
        r = rng(self.seed, "stoplog-driver", day)
        ten = self.tenure(day)
        drivers = r.choice(self.eligible(day), len(o))
        new = (ten[drivers] < 45).astype(int)
        o["driver_new"] = new
        o["minutes"] = self.stop_minutes(day, o) * (1 + self.cfg["service"]["new_driver"] * new)
        o["rain"] = int(self._weather[day].rain)
        o["weekday"] = self.weekday(day)
        return o

    def leg_log(self, day: int) -> pd.DataFrame:
        """A sample of driven legs from the telematics: router minutes and actual minutes."""
        o = self.orders(day)
        if o.empty:
            return pd.DataFrame(columns=["day", "z_from", "z_to", "hour", "router", "minutes", "rain", "weekday"])
        r = rng(self.seed, "leglog", day)
        n = self.cfg["travel"]["legs_logged_per_day"]
        pts = np.vstack([self.xy[o["address"].to_numpy()], [[0.0, 0.0]]])
        i, j = r.integers(0, len(pts), n), r.integers(0, len(pts), n)
        j = np.where(i == j, (j + 1) % len(pts), j)
        hour = o["placed"].to_numpy()[r.integers(0, len(o), n)] / 60 + r.uniform(0.2, 1.6, n)
        za, zb = self.zone_of(pts[i]), self.zone_of(pts[j])
        router = self.router_minutes(pts[i], pts[j])
        f = self.travel_factor(day, za, zb, hour) * np.exp(r.normal(0, self.cfg["travel"]["noise_sigma"], n))
        return pd.DataFrame({"day": day, "z_from": za, "z_to": zb, "hour": hour, "router": router,
                             "minutes": router * f, "rain": int(self._weather[day].rain), "weekday": self.weekday(day)})

    def shift_log(self, day: int, needed: dict[str, int]) -> pd.DataFrame:
        """Who was asked to work each shift (the hub's usual rule: needed / 0.9) and who came."""
        rows = []
        if self.weekday(day) == 6:
            return pd.DataFrame(columns=["day", "shift", "driver", "tenure", "showed"])
        for shift in SHIFTS:
            n = int(np.ceil(needed[shift] / 0.9))
            ds = self.roster_order(day, shift)[:n]
            came = self.shows(day, shift, ds)
            ten = self.tenure(day)
            for dr, c in zip(ds, came, strict=True):
                rows.append({"day": day, "shift": shift, "driver": int(dr), "tenure": int(ten[dr]), "showed": int(c)})
        return pd.DataFrame(rows)

    # -- the warehouse --------------------------------------------------------------------------------------
    def sku_slots(self) -> np.ndarray:
        """Slot of each SKU: aisle, position along the aisle (0..slots-1). Fast movers are not near the front."""
        w = self.cfg["warehouse"]
        r = rng(self.seed, "slots")
        return np.stack([r.integers(0, w["aisles"], w["skus"]), r.integers(0, w["slots_per_aisle"], w["skus"])], axis=1)

    def order_lines(self, day: int) -> list[np.ndarray]:
        """SKUs of each order: crates and loose items, drawn from a skewed assortment."""
        o = self.orders(day)
        skus = self.cfg["warehouse"]["skus"]
        r = rng(self.seed, "lines", day)
        p = 1 / np.arange(1, skus + 1) ** 0.9
        p = p / p.sum()
        n_lines = np.maximum(1, np.minimum(o["crates"].to_numpy(), 4) + np.minimum(o["items"].to_numpy(), 6))
        return [r.choice(skus, k, p=p, replace=False) for k in n_lines]
