"""The held-out gate, used by the CLI, the README and the dashboard alike."""
from __future__ import annotations

from dpe.config import load


def gate(summary: dict) -> list[str]:
    g = load("gate")["platform"]
    d = summary["designs"]
    p, a = d["platform"], d["as_found"]
    fails = []
    if a["late_per_day"] > 0 and 1 - p["late_per_day"] / a["late_per_day"] < g["min_late_reduction"]:
        fails.append(f"late deliveries down {1 - p['late_per_day'] / a['late_per_day']:.0%}, "
                     f"needs {g['min_late_reduction']:.0%}")
    if p["cost_per_month"] > a["cost_per_month"] * g["max_cost_vs_as_found"]:
        fails.append(f"operating cost €{p['cost_per_month']:,.0f} a month against €{a['cost_per_month']:,.0f} as found")
    if p["reject_share"] > g["max_reject_share"]:
        fails.append(f"turns away {p['reject_share']:.1%} of orders")
    for k in ("stop", "travel"):
        cov, q = p[f"{k}_coverage"], p[f"{k}_quantile"]
        if abs(cov - q) > g["coverage_tolerance"]:
            fails.append(f"{k} estimates: actuals under the {q:.0%} quantile {cov:.0%} of the time")
    return fails
