"""The company's route planner, run on estimates and scored on the truth.

The planner is not what this repository builds: Operations Research owns it. It is modelled here plainly and
identically for every design, because estimators can only be judged by what they make it do:

- **Acceptance.** When an order comes in, the planner estimates when it could be delivered from the work already
  waiting, the drivers on duty and the order itself. Over the promise, the shop turns the order away.
- **Dispatch.** A free driver takes the most urgent ready order, then adds the nearest ready orders while the van
  has room and every stop still makes its promise on the estimates.
- **The truth.** The tour is then driven with true travel and true minutes at each door. Late is late.

Over-estimates turn customers away and leave drivers idle; under-estimates accept orders that arrive late.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

BIN = 15            # minutes per bin in the day's series


@dataclass
class DayResult:
    orders: int = 0
    accepted: int = 0
    rejected: int = 0
    on_time: int = 0
    late: int = 0
    late_minutes: float = 0.0
    paid_minutes: float = 0.0
    busy_minutes: float = 0.0
    tours: int = 0
    drivers: int = 0
    rostered: int = 0
    needed: int = 0
    short_shifts: int = 0
    surplus_drivers: int = 0
    series: dict = field(default_factory=dict)


@dataclass
class Driver:
    id: int
    start: int
    end: int
    late_shift: bool
    free_at: float
    last_return: float = 0.0
    busy: float = 0.0
    est_return: float = 0.0


def simulate_day(world, day: int, orders: pd.DataFrame, est_service: np.ndarray, est_factor: np.ndarray,
                 drivers: list[Driver], pcfg: dict, keep_series: bool = False) -> DayResult:
    res = DayResult(orders=len(orders), drivers=len(drivers))
    n = len(orders)
    if n == 0:
        return res
    xy = world.xy[orders["address"].to_numpy()]
    zone = orders["zone"].to_numpy()
    placed = orders["placed"].to_numpy().astype(float)
    crates = orders["crates"].to_numpy()
    ids = orders["order"].to_numpy()
    true_stop = world.stop_minutes(day, orders)
    depot = np.zeros(2)
    depot_zone = int(world.zone_of(depot))
    promise, lead = pcfg["promise_minutes"], pcfg["pick_lead_minutes"]
    deadline = placed + promise
    ready = placed + lead

    def est_leg_from(a_xy: np.ndarray, a_zone: int, b_idx: np.ndarray, t: float) -> np.ndarray:
        h = min(int(t // 60), 23)
        return world.router_minutes(a_xy, xy[b_idx]) * est_factor[a_zone, zone[b_idx], h]

    depot_leg = world.router_minutes(depot, xy) * est_factor[depot_zone, zone, np.minimum(placed // 60, 23).astype(int)]
    share = pcfg["acceptance_leg_share"]
    pending: list[int] = []
    pending_work = 0.0
    accepted = np.zeros(n, dtype=bool)
    delivered = np.full(n, np.nan)
    nbins = 1440 // BIN
    ser = {k: np.zeros(nbins) for k in ("accepted", "rejected", "late", "on_road")} if keep_series else None

    events: list[tuple[float, int, str, int]] = []
    seq = 0
    for i in range(n):
        heapq.heappush(events, (placed[i], seq, "order", i))
        seq += 1
    for d in drivers:
        heapq.heappush(events, (float(d.start), seq, "free", d.id))
        seq += 1

    def on_duty(t: float) -> list[Driver]:
        return [d for d in drivers if d.start <= t < d.end]

    def try_dispatch(t: float) -> None:
        nonlocal pending_work, seq
        free = [d for d in drivers if d.free_at <= t and d.start <= t
                and (t < d.end or (d.late_shift and pcfg["rostering"]["overtime_after_shift"] and pending))]
        while free and pending:
            ready_now = [i for i in pending if ready[i] <= t]
            if not ready_now:
                return
            d = free.pop(0)
            seed_i = min(ready_now, key=lambda i: deadline[i])
            tour = [seed_i]
            load = crates[seed_i]
            cur_xy, cur_z = depot, depot_zone
            est_t = t + float(est_leg_from(cur_xy, cur_z, np.array([seed_i]), t)[0]) + est_service[seed_i]
            cur_xy, cur_z = xy[seed_i], zone[seed_i]
            cand = [i for i in ready_now if i != seed_i]
            while cand and len(tour) < pcfg["max_stops"]:
                c = np.array(cand)
                legs = est_leg_from(cur_xy, cur_z, c, est_t)
                order = np.argsort(legs)
                added = False
                for k in order:
                    i = int(c[k])
                    if legs[k] > pcfg["max_leg_minutes"]:
                        break
                    if load + crates[i] > pcfg["crates_per_van"]:
                        continue
                    if est_t + legs[k] > deadline[i]:
                        continue
                    tour.append(i)
                    load += crates[i]
                    est_t += legs[k] + est_service[i]
                    cur_xy, cur_z = xy[i], zone[i]
                    cand.remove(i)
                    added = True
                    break
                if not added:
                    break
            est_t += float(world.router_minutes(cur_xy, depot)) * est_factor[cur_z, depot_zone, min(int(est_t // 60), 23)]
            for i in tour:
                pending.remove(i)
                pending_work -= est_service[i] + share * depot_leg[i]
            # drive it, for real
            tt, prev_xy, prev_key = t, depot, "hub"
            factor = world.driver_factor(day, d.id)
            for i in tour:
                tt += world.leg_minutes(day, prev_xy, xy[i], tt, f"{prev_key}>{ids[i]}")
                delivered[i] = tt
                tt += true_stop[i] * factor
                prev_xy, prev_key = xy[i], ids[i]
            tt += world.leg_minutes(day, prev_xy, depot, tt, f"{prev_key}>hub")
            if ser is not None:
                ser["on_road"][int(t // BIN):min(int(tt // BIN) + 1, nbins)] += 1
            d.busy += tt - t
            d.free_at = d.last_return = tt
            d.est_return = est_t
            res.tours += 1
            heapq.heappush(events, (tt, seq, "free", d.id))
            seq += 1

    while events:
        t, _, kind, i = heapq.heappop(events)
        if kind == "order":
            duty = on_duty(t)
            work = est_service[i] + share * depot_leg[i]
            if duty:
                road = sum(max(0.0, d.est_return - t) for d in duty)
                eta = t + lead + (pending_work + road + work) / len(duty) + (1 - share) * depot_leg[i]
                ok = eta <= deadline[i]
            else:
                ok = False
            b = min(int(t // BIN), nbins - 1)
            if ok:
                accepted[i] = True
                pending.append(i)
                pending_work += work
                heapq.heappush(events, (ready[i], seq, "ready", i))
                seq += 1
                if ser is not None:
                    ser["accepted"][b] += 1
            elif ser is not None:
                ser["rejected"][b] += 1
        try_dispatch(t)

    acc = np.flatnonzero(accepted)
    late = delivered[acc] > deadline[acc] + 1e-9
    res.accepted, res.rejected = len(acc), n - len(acc)
    res.late = int(late.sum())
    res.on_time = res.accepted - res.late
    res.late_minutes = float(np.nansum(np.maximum(delivered[acc] - deadline[acc], 0)))
    for d in drivers:
        res.paid_minutes += max(d.end, d.last_return) - d.start
        res.busy_minutes += d.busy
    if ser is not None:
        for i in acc[late]:
            ser["late"][min(int(delivered[i] // BIN), nbins - 1)] += 1
        res.series = {k: v.tolist() for k, v in ser.items()}
    return res
