"""Write a simulated hub's logs to a lake directory, for the training job: `python -m dpe.sim.export`."""
from __future__ import annotations

import argparse
from pathlib import Path

from dpe.config import load, world_config
from dpe.ops.lake import write_day
from dpe.sim.run import shift_needs
from dpe.world import SHIFTS, World


def export(seed: int, through: int, out: Path) -> None:
    cfg = world_config()
    w = World(cfg, seed)
    needs = shift_needs(w, range(cfg["history_days"]), load("planner"))
    for d in range(through):
        need = {s: needs.get((w.weekday(d), s), 0) for s in SHIFTS}
        write_day(out, d, w.weekday(d), w.forecast(d), w.stop_log(d), w.leg_log(d), w.shift_log(d, need),
                  len(w.zone), w.n_zones)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dpe.sim.export")
    ap.add_argument("--seed", type=int, default=9101)
    ap.add_argument("--through", type=int, default=28)
    ap.add_argument("--out", type=Path, default=Path("data/lake"))
    a = ap.parse_args(argv)
    export(a.seed, a.through, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
