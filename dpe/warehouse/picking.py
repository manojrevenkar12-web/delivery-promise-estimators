"""Picking in a single-block, picker-to-parts warehouse: where things are, which orders go on one cart, and the
path through the aisles.

- **Layout.** Parallel aisles with a cross-aisle at the front and at the back; the depot (pack-out) is at the
  front, in the middle. Distances are shortest walks along aisles and cross-aisles.
- **Routing.** S-shape (walk every aisle that has a pick end to end), return (in and back out of each aisle),
  and a tour over the pick locations themselves: nearest neighbour, then 2-opt on the true walking distances.
- **Batching.** First come, first served onto a cart, or seed-and-savings: start from the oldest order, then add
  the order that adds the least walking, within the cart's crate capacity.
- **Slotting.** Move the most picked SKUs to the slots closest to the depot, from the order history.

Everything here works from what the warehouse system records (slots, order lines); it never reads the world.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class Layout:
    aisles: int
    slots: int                 # per side, along an aisle
    length: float              # metres
    gap: float                 # metres between aisle centres

    @classmethod
    def from_config(cls, w: dict) -> Layout:
        return cls(w["aisles"], w["slots_per_aisle"], float(w["aisle_length_m"]), float(w["aisle_gap_m"]))

    @property
    def depot(self) -> tuple[float, float]:
        return ((self.aisles - 1) * self.gap / 2, -2.0)

    def position(self, slot: np.ndarray) -> np.ndarray:
        """(aisle, slot index) -> (x, y) in metres."""
        slot = np.atleast_2d(slot)
        return np.stack([slot[:, 0] * self.gap, (slot[:, 1] + 0.5) * self.length / self.slots], axis=1)

    def dist(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Walking distance between points (x, y); same aisle: straight; otherwise via the shorter cross-aisle."""
        a, b = np.atleast_2d(a), np.atleast_2d(b)
        same = np.isclose(a[:, None, 0], b[None, :, 0])
        ya, yb = np.clip(a[:, None, 1], 0, self.length), np.clip(b[None, :, 1], 0, self.length)
        dx = np.abs(a[:, None, 0] - b[None, :, 0])
        via = dx + np.minimum(ya + yb, 2 * self.length - ya - yb)
        d = np.where(same, np.abs(ya - yb), via)
        # the depot sits in front of the front cross-aisle
        d = d + np.where(a[:, None, 1] < 0, -a[:, None, 1], 0) + np.where(b[None, :, 1] < 0, -b[None, :, 1], 0)
        return d


def route_length(layout: Layout, pts: np.ndarray, policy: str) -> float:
    """Metres from the depot through every pick location and back."""
    if len(pts) == 0:
        return 0.0
    dep = np.array(layout.depot)
    if policy == "tsp":
        return _tsp(layout, pts, dep)
    xs = np.unique(pts[:, 0])
    span = (xs.max() - xs.min()) if len(xs) else 0.0
    horiz = 2 * (span + min(abs(dep[0] - xs.min()), abs(dep[0] - xs.max())))
    if policy == "return":
        deep = np.array([pts[pts[:, 0] == x, 1].max() for x in xs])
        return float(horiz + 2 * deep.sum() + 2 * abs(dep[1]))
    if policy == "s_shape":
        k = len(xs)
        through = layout.length * (k if k % 2 == 0 else k - 1)
        last = 0.0
        if k % 2 == 1:   # the last aisle: in to the deepest pick and back
            last = 2 * pts[pts[:, 0] == xs[-1], 1].max()
        return float(horiz + through + last + 2 * abs(dep[1]))
    raise ValueError(policy)


def _tsp(layout: Layout, pts: np.ndarray, dep: np.ndarray) -> float:
    p = np.unique(pts, axis=0)
    nodes = np.vstack([dep, p])
    D = layout.dist(nodes, nodes)
    n = len(nodes)
    tour, left = [0], set(range(1, n))
    while left:
        last = tour[-1]
        nxt = min(left, key=lambda j: D[last, j])
        tour.append(nxt)
        left.remove(nxt)
    tour.append(0)
    improved = True
    while improved:
        improved = False
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                a, b, c, d = tour[i - 1], tour[i], tour[j], tour[j + 1]
                if D[a, c] + D[b, d] < D[a, b] + D[c, d] - 1e-9:
                    tour[i:j + 1] = tour[i:j + 1][::-1]
                    improved = True
    return float(sum(D[tour[k], tour[k + 1]] for k in range(len(tour) - 1)))


def batches(policy: str, order_pts: list[np.ndarray], crates: np.ndarray, capacity: int, max_orders: int,
            layout: Layout) -> list[list[int]]:
    """Group a wave's orders onto carts. Orders are given oldest first."""
    idx = list(range(len(order_pts)))
    out: list[list[int]] = []
    if policy == "fcfs":
        cur, load = [], 0
        for i in idx:
            if cur and (load + crates[i] > capacity or len(cur) >= max_orders):
                out.append(cur)
                cur, load = [], 0
            cur.append(i)
            load += crates[i]
        if cur:
            out.append(cur)
        return out
    if policy != "savings":
        raise ValueError(policy)
    left = idx[:]
    while left:
        seed = left.pop(0)
        cur, load = [seed], crates[seed]
        pts = order_pts[seed]
        while left and len(cur) < max_orders:
            base = route_length(layout, pts, "return")
            best, best_add = None, None
            for i in left:
                if load + crates[i] > capacity:
                    continue
                add = route_length(layout, np.vstack([pts, order_pts[i]]), "return") - base
                if best_add is None or add < best_add:
                    best, best_add = i, add
            if best is None:
                break
            cur.append(best)
            load += crates[best]
            pts = np.vstack([pts, order_pts[best]])
            left.remove(best)
        out.append(cur)
    return out


def reslot(layout: Layout, slots: np.ndarray, history_lines: list[np.ndarray]) -> np.ndarray:
    """Most picked SKUs to the slots nearest the depot. Returns a new slot table (same shape as `slots`)."""
    counts = np.zeros(len(slots))
    for lines in history_lines:
        np.add.at(counts, lines, 1)
    rank = np.argsort(-counts, kind="stable")
    all_slots = np.array([(a, s) for a in range(layout.aisles) for s in range(layout.slots)])
    d = layout.dist(np.array([layout.depot]), layout.position(all_slots))[0]
    near = all_slots[np.argsort(d, kind="stable")]
    new = slots.copy()
    # two sides per slot position: the k-th most picked SKU gets the (k // 2)-th nearest position
    for k, sku in enumerate(rank):
        new[sku] = near[min(k // 2, len(near) - 1)]
    return new
