"""Picking designs on the same order lines: every 10 minutes, the orders placed since the last wave are batched
onto carts and walked. Scored in metres and picker minutes per order."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from dpe.warehouse.picking import Layout, batches, reslot, route_length
from dpe.world import World


@dataclass(frozen=True)
class PickDesign:
    name: str
    label: str
    batching: str = "savings"
    routing: str = "tsp"
    reslot: bool = True


PICK_DESIGNS = [
    PickDesign("as_found", "As found: first come first served, S-shape, slots as they are", "fcfs", "s_shape", False),
    PickDesign("platform_fcfs", "Platform, first come first served", batching="fcfs"),
    PickDesign("platform_s_shape", "Platform, S-shape routes", routing="s_shape"),
    PickDesign("platform_return", "Platform, return routes", routing="return"),
    PickDesign("platform_no_reslot", "Platform, slots as they are", reslot=False),
    PickDesign("platform", "Platform: savings batching, 2-opt routes over the picks, busiest SKUs near pack-out"),
]
PICK_ORDER = [d.name for d in PICK_DESIGNS]


def run_warehouse(world_cfg: dict, seed: int, days: int, wave_minutes: int = 10, cart_crates: int = 12,
                  cart_orders: int = 6) -> dict:
    w = World(world_cfg, seed)
    wc = world_cfg["warehouse"]
    layout = Layout.from_config(wc)
    H = world_cfg["history_days"]
    slots0 = w.sku_slots()
    history = [lines for d in range(H) for lines in w.order_lines(d)]
    slots1 = reslot(layout, slots0, history)
    eval_days = [d for d in range(H, H + world_cfg["eval_days"]) if w.weekday(d) != 6][:days]
    out = {}
    for pd_ in PICK_DESIGNS:
        slots = slots1 if pd_.reslot else slots0
        metres = seconds = n_orders = carts = 0.0
        for day in eval_days:
            o = w.orders(day)
            lines = w.order_lines(day)
            crates = o["crates"].to_numpy()
            items = o["items"].to_numpy()
            wave = (o["placed"].to_numpy() // wave_minutes).astype(int)
            for wv in np.unique(wave):
                idx = np.flatnonzero(wave == wv)
                pts = [layout.position(slots[lines[i]]) for i in idx]
                for b in batches(pd_.batching, pts, crates[idx], cart_crates, cart_orders, layout):
                    allpts = np.vstack([pts[k] for k in b])
                    m = route_length(layout, allpts, pd_.routing)
                    members = idx[b]
                    metres += m
                    seconds += (m / wc["walk_m_per_s"] + wc["pick_seconds_per_crate"] * crates[members].sum()
                                + wc["pick_seconds_per_item"] * items[members].sum() + 15 * len(members))
                    carts += 1
                n_orders += len(idx)
        out[pd_.name] = {"orders": int(n_orders), "carts": int(carts), "metres": metres, "seconds": seconds,
                         "days": len(eval_days)}
    return {"seed": seed, "designs": out}
