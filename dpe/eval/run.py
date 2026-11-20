"""Run every design on every hub, then summarise with uncertainty.

Intervals are bootstrapped over (hub, day) blocks: a day is resampled whole, with every design's outcome on it,
so differences between designs are paired on the same orders, streets and absences.
"""
from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from dpe.config import load, world_config
from dpe.keyed import rng
from dpe.sim.designs import BY_NAME, DESIGNS, SWEEP
from dpe.sim.run import run_seed
from dpe.sim.warehouse_run import run_warehouse

WAREHOUSE_DAYS = 6


def _one(args) -> tuple[dict, dict]:
    cfg, seed, names, series_day = args
    est, pcfg = load("estimators"), load("planner")
    out = run_seed(cfg, seed, [BY_NAME[n] for n in names], est, pcfg, series_day)
    wh = run_warehouse(cfg, seed, WAREHOUSE_DAYS)
    return out, wh


def run_all(heldout: bool = False, names: list[str] | None = None, eval_days: int | None = None,
            seeds: list[int] | None = None, workers: int | None = None) -> tuple[list[dict], list[dict]]:
    cfg = world_config(heldout)
    if eval_days is not None:
        cfg["eval_days"] = eval_days
    seeds = seeds or cfg["seeds"]
    names = names or [d.name for d in DESIGNS] + ([] if heldout else [d.name for d in SWEEP])
    args = [(cfg, s, names, None) for s in seeds]
    workers = workers or min(len(seeds), os.cpu_count() or 1)
    if workers == 1:
        res = [_one(a) for a in args]
    else:
        with ProcessPoolExecutor(workers) as ex:
            res = list(ex.map(_one, args))
    return [r[0] for r in res], [r[1] for r in res]


def _cost(day: dict, v: dict) -> float:
    return (day["rejected"] * v["margin_per_order_eur"] + day["late"] * v["late_cost_eur"]
            + day["paid_minutes"] / 60 * v["driver_hour_eur"])


def summarize(runs: list[dict], n_boot: int = 2000) -> dict:
    v = load("value")
    est = load("estimators")
    names = list(runs[0]["designs"])
    blocks = [(r["seed"], i) for r in runs for i in range(len(r["designs"][names[0]]["days"]))]
    per = {n: [r["designs"][n]["days"][i] for r in runs for i in range(len(r["designs"][n]["days"]))] for n in names}
    rb = rng("bootstrap", len(blocks))
    idx = rb.integers(0, len(blocks), size=(n_boot, len(blocks)))
    base = np.array([_cost(d, v) for d in per["as_found"]]) if "as_found" in per else None
    plat = np.array([_cost(d, v) for d in per["platform"]]) if "platform" in per else None
    out = {}
    for n in names:
        ds = per[n]
        a = {k: np.array([d[k] for d in ds], dtype=float) for k in
             ("orders", "accepted", "rejected", "late", "on_time", "paid_minutes", "rostered", "needed",
              "short_shifts", "surplus_drivers", "stop_mae", "stop_coverage", "travel_coverage", "stop_bias")}
        cost = np.array([_cost(d, v) for d in ds])
        late_ci = np.percentile(a["late"][idx].mean(axis=1), [2.5, 97.5])
        d_cost = (cost - base) if base is not None else np.zeros_like(cost)
        dc_ci = np.percentile(d_cost[idx].mean(axis=1), [2.5, 97.5]) * v["days_per_month"]
        d_plat = (cost - plat) if plat is not None else np.zeros_like(cost)
        dp_ci = np.percentile(d_plat[idx].mean(axis=1), [2.5, 97.5]) * v["days_per_month"]
        late_plat = (a["late"] - np.array([d["late"] for d in per["platform"]])) if plat is not None else a["late"] * 0
        design = BY_NAME[n]
        q = {"service": design.q_service or est["service_quantile"], "travel": design.q_travel or est["travel_quantile"]}
        rw = [d for d, (seed, _) in zip(ds, blocks, strict=True) if d["day"] >= _rw(runs, seed)]
        retr = [x for r in runs for x in r["designs"][n]["retrains"]]
        out[n] = {
            "label": design.label,
            "days": len(ds),
            "orders_per_day": float(a["orders"].mean()),
            "late_per_day": float(a["late"].mean()), "late_ci": [float(x) for x in late_ci],
            "rejected_per_day": float(a["rejected"].mean()),
            "late_share": float(a["late"].sum() / max(a["accepted"].sum(), 1)),
            "reject_share": float(a["rejected"].sum() / a["orders"].sum()),
            "on_time_share": float(a["on_time"].sum() / a["orders"].sum()),
            "driver_hours_per_day": float(a["paid_minutes"].mean() / 60),
            "short_shifts_per_week": float(a["short_shifts"].mean() * 6),
            "surplus_drivers_per_day": float(a["surplus_drivers"].mean()),
            "cost_per_month": float(cost.mean() * v["days_per_month"]),
            "cost_vs_as_found_per_month": float(d_cost.mean() * v["days_per_month"]), "cost_vs_as_found_ci": [float(x) for x in dc_ci],
            "cost_vs_platform_per_month": float(d_plat.mean() * v["days_per_month"]),
            "cost_vs_platform_ci": [float(x) for x in dp_ci],
            "late_vs_platform_per_day": float(late_plat.mean()),
            "stop_mae": float(a["stop_mae"].mean()), "stop_bias": float(a["stop_bias"].mean()),
            "stop_coverage": float(a["stop_coverage"].mean()), "travel_coverage": float(a["travel_coverage"].mean()),
            "stop_quantile": q["service"] if design.service == "quantile" else None,
            "travel_quantile": q["travel"] if design.travel == "quantile" else None,
            "late_per_day_after_roadworks": float(np.mean([d["late"] for d in rw])) if rw else None,
            "late_on_outage_days": float(np.mean([d["late"] for d in ds if d["outage"]])) if any(d["outage"] for d in ds) else None,
            "retrains": len(retr), "promoted": sum(x["promoted"] for x in retr),
            "drift_retrains": sum(x["reason"] == "drift" for x in retr),
        }
    return {"designs": out, "world": {"hubs": len(runs), "seeds": [r["seed"] for r in runs], "days": len(blocks),
                                      "orders": int(sum(d["orders"] for d in per[names[0]]))}}


def _rw(runs: list[dict], seed: int) -> int:
    return next(r["roadworks_day"] for r in runs if r["seed"] == seed)


def summarize_warehouse(whs: list[dict]) -> dict:
    v = load("value")
    names = list(whs[0]["designs"])
    out = {}
    for n in names:
        t = {k: sum(w["designs"][n][k] for w in whs) for k in ("orders", "carts", "metres", "seconds", "days")}
        hours_per_day = t["seconds"] / 3600 / t["days"]
        out[n] = {"metres_per_order": t["metres"] / t["orders"], "minutes_per_order": t["seconds"] / 60 / t["orders"],
                  "orders_per_cart": t["orders"] / t["carts"], "picker_hours_per_day": hours_per_day,
                  "cost_per_month": hours_per_day * v["picker_hour_eur"] * v["days_per_month"]}
    return {"designs": out, "days": int(sum(w["designs"][names[0]]["days"] for w in whs)), "hubs": len(whs)}
