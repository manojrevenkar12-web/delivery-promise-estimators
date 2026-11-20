"""One hub, every design, day by day.

History days fill the feature store with the company's logs. Each evaluation day, every design:

1. retrains if its schedule or a drift alarm says so, through the gate;
2. sizes each shift's roster from its availability estimate, and learns who really came;
3. hands the planner its stop and travel estimates (falling back during outages) and runs the day on the truth;
4. scores its estimates against the day's logs.

Then the day's logs (the same for every design) go into the feature store.
Models are cached by training window, so designs that would train the same model share it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from dpe.estimators.models import pinball, roster_size
from dpe.estimators.pipeline import DriftMonitor, EstimatorSet, Served, gate, train
from dpe.features.store import FeatureStore
from dpe.sim.designs import Design
from dpe.sim.planner import DayResult, Driver, simulate_day
from dpe.world import SHIFTS, World


def shift_needs(world: World, store_days: range, pcfg: dict) -> dict[tuple[int, str], int]:
    """The hub's shift plan from history: drivers needed on the road per weekday and shift."""
    r = pcfg["rostering"]
    counts: dict[tuple[int, str], list[int]] = {}
    for d in store_days:
        o = world.orders(d)
        wd = world.weekday(d)
        h = o["placed"].to_numpy() // 60
        for shift, (a, b) in (("early", r["early_hours"]), ("late", r["late_hours"])):
            counts.setdefault((wd, shift), []).append(int(((h >= a) & (h < b)).sum()))
    return {k: max(1, math.ceil(np.mean(v) * r["work_minutes_per_order"] / (480 * r["utilisation"])))
            for k, v in counts.items()}


@dataclass
class DesignRun:
    design: Design
    champion: EstimatorSet | None = None
    monitor: DriftMonitor | None = None
    last_train: int = 0
    fast_until: int = -1
    alarm: bool = False
    days: list[dict] = field(default_factory=list)
    retrains: list[dict] = field(default_factory=list)
    series: dict = field(default_factory=dict)


def run_seed(world_cfg: dict, seed: int, designs: list[Design], est_cfg: dict, pcfg: dict,
             series_day: int | None = None) -> dict:
    w = World(world_cfg, seed)
    H, E = world_cfg["history_days"], world_cfg["eval_days"]
    store = FeatureStore(len(w.zone), w.n_zones)
    needs = shift_needs(w, range(H), pcfg)

    def needed(day: int) -> dict[str, int]:
        return {s: needs.get((w.weekday(day), s), 0) for s in SHIFTS}

    def ingest(day: int) -> None:
        store.add_day(day, w.weekday(day), w.forecast(day), w.stop_log(day), w.leg_log(day),
                      w.shift_log(day, needed(day)))

    for d in range(H):
        ingest(d)
    cache: dict[int, EstimatorSet] = {}

    def model(through: int) -> EstimatorSet:
        if through not in cache:
            cache[through] = train(store, through, est_cfg)
        return cache[through]

    runs = [DesignRun(d) for d in designs]
    for r in runs:
        if r.design.service != "rule" or r.design.travel != "rule" or r.design.availability != "rule":
            r.champion = model(H)
        r.last_train = H
        q = _q(r.design, est_cfg)
        r.monitor = DriftMonitor(min(q["service"], q["travel"]), est_cfg["drift"]["coverage_band"],
                                 est_cfg["drift"]["alarm_days"])

    for day in range(H, H + E):
        wd = w.weekday(day)
        if wd == 6:                      # closed on Sunday
            ingest(day)
            continue
        orders = w.orders(day)
        fc = w.forecast(day)
        stop_log, leg_log = w.stop_log(day), w.leg_log(day)
        for r in runs:
            _maybe_retrain(r, day, store, model, est_cfg)
            q = _q(r.design, est_cfg)
            served = Served(r.champion, pcfg["rule_of_thumb"], store, w.n_zones)
            est = served.service(orders, day, wd, fc, r.design.service, q["service"])
            out = np.array([w.outage(day, t) for t in orders["placed"].to_numpy()])
            if out.any() and r.design.service != "rule":
                fb = served.fallback(orders[out], q["service"]) if r.design.fallback else served.rule_service(orders[out])
                est = est.copy()
                est[out] = fb
            F = served.travel_matrix(day, wd, fc, r.design.travel, q["travel"])
            drivers, rostered, need_total, short, surplus = [], 0, 0, 0, 0
            for shift, (a, b) in SHIFTS.items():
                need = needed(day)[shift]
                order = w.roster_order(day, shift)
                if r.design.availability == "rule":
                    n = math.ceil(need / pcfg["rule_of_thumb"]["show_rate"])
                else:
                    p = served.show_probs(day, shift, order, w.tenure(day)[order], wd, fc, r.design.availability)
                    n = roster_size(p, need, q["availability"] if r.design.availability == "quantile" else None)
                asked = order[:n]
                came = asked[w.shows(day, shift, asked)]
                drivers += [Driver(int(i), a, b, shift == "late", float(a)) for i in came]
                rostered += n
                need_total += need
                short += int(len(came) < need - 1)          # two or more drivers short of the plan
                surplus += max(0, len(came) - need)
            res: DayResult = simulate_day(w, day, orders, est, F, drivers, pcfg, keep_series=(day == series_day))
            res.rostered, res.needed = rostered, need_total
            res.short_shifts, res.surplus_drivers = short, surplus
            m = _estimate_metrics(served, r.design, q, stop_log, leg_log, day, wd, fc, est_cfg)
            if r.design.service == "quantile" or r.design.travel == "quantile":
                r.alarm = r.monitor.observe(day, m["stop_coverage"], m["travel_coverage"])
            r.days.append({"day": day, "weekday": wd, "outage": bool(out.any()), "version": getattr(r.champion, "version", "rules"),
                           **{k: v for k, v in res.__dict__.items() if k != "series"}, **m})
            if res.series:
                r.series = res.series
        ingest(day)

    return {"seed": seed, "needs": {f"{k[0]}-{k[1]}": v for k, v in needs.items()},
            "roadworks_day": w.roadworks_day, "outage_days": sorted(w.outages),
            "designs": {r.design.name: {"days": r.days, "retrains": r.retrains, "series": r.series} for r in runs}}


def _q(d: Design, cfg: dict) -> dict[str, float]:
    return {"service": d.q_service or cfg["service_quantile"], "travel": d.q_travel or cfg["travel_quantile"],
            "availability": d.q_availability or cfg["availability_quantile"]}


def _maybe_retrain(r: DesignRun, day: int, store: FeatureStore, model, cfg: dict) -> None:
    d = r.design
    if r.champion is None or not d.retrain:
        return
    g = cfg["gate"]
    fast = d.drift_retrain and (r.alarm or day <= r.fast_until)
    if r.alarm and d.drift_retrain:
        r.fast_until = day + g["fast_days"]
        r.alarm = False
        r.monitor.reset()
    due = day - r.last_train >= cfg["retrain_every_days"]
    if not (due or fast):
        return
    v = g["validation_days_fast"] if fast and not due else g["validation_days"]
    open_days = [x for x in range(day - 1, day - 15, -1) if x in store.stops and len(store.stops[x])][:v]
    through = min(open_days)
    if through <= r.champion.through:
        return
    challenger = model(through)
    q = _q(d, cfg)
    ok, detail = gate(r.champion, challenger, store, range(through, day), q["service"], q["travel"],
                      g["max_pinball_regression"])
    r.retrains.append({"day": day, "reason": "weekly" if due else "drift", "challenger": challenger.version,
                       "promoted": ok, **detail})
    r.last_train = day
    if ok:
        r.champion = challenger


def _estimate_metrics(served: Served, d: Design, q: dict, stop_log: pd.DataFrame, leg_log: pd.DataFrame, day: int,
                      wd: int, fc: dict, cfg: dict) -> dict:
    y = stop_log["minutes"].to_numpy()
    est = served.service(stop_log, day, wd, fc, d.service, q["service"])
    F = served.travel_matrix(day, wd, fc, d.travel, q["travel"])
    ratio = (leg_log["minutes"] / leg_log["router"]).to_numpy()
    fpred = F[leg_log["z_from"].to_numpy(), leg_log["z_to"].to_numpy(), np.minimum(leg_log["hour"].to_numpy().astype(int), 23)]
    return {"stop_mae": float(np.mean(np.abs(y - est))), "stop_bias": float(np.mean(est - y)),
            "stop_pinball": pinball(y, est, q["service"]), "stop_coverage": float(np.mean(y <= est)),
            "travel_mae": float(np.mean(np.abs(ratio - fpred))), "travel_coverage": float(np.mean(ratio <= fpred)),
            "travel_pinball": pinball(ratio, fpred, q["travel"])}
