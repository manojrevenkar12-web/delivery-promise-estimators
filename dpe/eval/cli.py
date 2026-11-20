"""python -m dpe.eval.cli evaluate | heldout | gate [--dev] | readme [--check] | quick"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime

from dpe.config import CONFIG, load, world_config
from dpe.eval import report
from dpe.eval.decisions import decisions, memo, served_sweep, write_memo
from dpe.eval.gate import gate
from dpe.eval.run import run_all, summarize, summarize_warehouse
from dpe.sim.designs import ORDER

LOCK = CONFIG / "heldout.lock"


def _config_hash() -> str:
    h = hashlib.sha256()
    for name in ("world", "heldout", "planner", "estimators", "value", "gate"):
        h.update((CONFIG / f"{name}.yaml").read_bytes())
    return h.hexdigest()[:16]


def _day_report() -> dict:
    """Replay one development hub up to the first open day after road works start, keeping the day's series.
    Same luck as the full evaluation, so the day is the one every design met there."""
    from dpe.sim.designs import BY_NAME
    from dpe.sim.run import run_seed
    from dpe.world import World

    cfg = world_config()
    seed = cfg["seeds"][0]
    w = World(cfg, seed)
    day = w.roadworks_day + 1
    while w.weekday(day) == 6:
        day += 1
    cfg["eval_days"] = day - cfg["history_days"] + 1
    out = run_seed(cfg, seed, [BY_NAME[n] for n in ("as_found", "mean_models", "platform")], load("estimators"),
                   load("planner"), series_day=day)
    return {"seed": seed, "day": day, "date": w.date(day).isoformat(), "bin_minutes": 15,
            "series": {n: d["series"] for n, d in out["designs"].items()}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dpe.eval.cli")
    ap.add_argument("cmd", choices=["evaluate", "heldout", "gate", "readme", "quick", "reports", "day"])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--dev", action="store_true", help="gate: judge the development hubs")
    a = ap.parse_args(argv)
    sweep = served_sweep(load("estimators"))

    if a.cmd == "quick":
        runs, _ = run_all(False, names=["as_found", "mean_models", "platform"], eval_days=8, seeds=[9101])
        s = summarize(runs, n_boot=200)["designs"]
        print(json.dumps({n: {k: round(x[k], 3) for k in ("late_per_day", "reject_share", "cost_vs_as_found_per_month")}
                          for n, x in s.items()}, indent=1))
        ok = s["platform"]["late_per_day"] < s["as_found"]["late_per_day"]
        print("platform has fewer late deliveries than as found:", ok)
        return 0 if ok else 1
    if a.cmd == "evaluate":
        runs, whs = run_all(False)
        dev = summarize(runs)
        wh = summarize_warehouse(whs)
        day = _day_report()
        report.write("dev", dev)
        report.write("warehouse", wh)
        report.write("day", day)
        dec = decisions(dev, wh)
        report.write("sweep", dec["selection"])
        report.write("decisions", dec)
        ho = report._load("heldout")
        write_memo(memo(dev, dec, gate(ho) if ho else None))
        report.charts(dev, day, wh, ORDER, sweep)
        report.readme(ORDER)
        print(json.dumps({n: [round(x["late_per_day"], 1), round(x["reject_share"], 3), round(x["cost_vs_as_found_per_month"])]
                          for n, x in dev["designs"].items()}))
        return 0
    if a.cmd == "day":
        report.write("day", _day_report())
        a.cmd = "reports"
    if a.cmd == "reports":
        # rebuild the memo, charts and README from the saved summaries, without re-running anything
        dev, wh, day = report._load("dev"), report._load("warehouse"), report._load("day")
        dec = decisions(dev, wh)
        report.write("decisions", dec)
        report.write("sweep", dec["selection"])
        ho = report._load("heldout")
        write_memo(memo(dev, dec, gate(ho) if ho else None))
        report.charts(dev, day, wh, ORDER, sweep)
        report.readme(ORDER)
        return 0
    if a.cmd == "heldout":
        if LOCK.exists():
            print(f"held-out already run: {LOCK.read_text().strip()}", file=sys.stderr)
            return 1
        runs, _ = run_all(True)
        s = summarize(runs)
        report.write("heldout", s)
        LOCK.write_text(json.dumps({"ran_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                    "config_sha": _config_hash(), "seeds": s["world"]["seeds"]}) + "\n")
        dev = report._load("dev")
        if dev:
            write_memo(memo(dev, report._load("decisions"), gate(s)))
        report.readme(ORDER)
        print("held-out:", gate(s) or "gate passed")
        return 0
    if a.cmd == "gate":
        held = report.REPORTS / "heldout.json"
        path = held if held.exists() and not a.dev else report.REPORTS / "dev.json"
        fails = gate(json.loads(path.read_text()))
        print(f"{path.name}: " + ("; ".join(fails) if fails else "gate passed"))
        return 1 if fails else 0
    if a.cmd == "readme":
        changed = report.readme(ORDER, check=a.check)
        if a.check and changed:
            print("README results block is out of date: run python -m dpe.eval.cli readme", file=sys.stderr)
            return 1
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
