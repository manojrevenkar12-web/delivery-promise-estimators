"""Generated reports: the README results block and the charts. Never edited by hand."""
from __future__ import annotations

import json
from pathlib import Path

from dpe.config import ROOT, load

REPORTS = ROOT / "reports"
CHARTS = REPORTS / "charts"
README = ROOT / "README.md"
START, END = "<!-- results:start -->", "<!-- results:end -->"

# validated with the dataviz palette checker (light surface): orange, teal, blue
AS_FOUND, MEAN, PLATFORM = "#C2410C", "#00897B", "#1D4ED8"
INK, MUTED, GRID, SURFACE = "#1F2430", "#5E6573", "#E4E6EA", "#FCFCFB"
FONT = 'font-family="Inter, system-ui, sans-serif"'


def _load(name: str) -> dict | None:
    p = REPORTS / f"{name}.json"
    return json.loads(p.read_text()) if p.exists() else None


def eur(x: float) -> str:
    return ("−" if x < 0 else "") + f"€{abs(x):,.0f}"


def pct(x: float, d: int = 1) -> str:
    return f"{x * 100:.{d}f}%"


# -- charts ---------------------------------------------------------------------------------------------------
def _svg(w: int, h: int, title: str, body: list[str]) -> str:
    return "\n".join([f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" {FONT} role="img" '
                      f'aria-label="{title}">', f'<rect width="{w}" height="{h}" fill="{SURFACE}"/>',
                      f'<text x="20" y="28" font-size="15" font-weight="600" fill="{INK}">{title}</text>', *body,
                      "</svg>"]) + "\n"


def chart_tradeoff(dev: dict, sweep_names: list[str]) -> str:
    """Late deliveries against orders turned away, for each quantile handed to the planner."""
    d = dev["designs"]
    pts = []
    for n in [*sweep_names, "platform_q90"]:
        if n in d and d[n]["stop_quantile"]:
            pts.append((d[n]["rejected_per_day"], d[n]["late_per_day"], f"{round(d[n]['stop_quantile'] * 100)}th"))
    pts.sort(key=lambda p: p[0])
    others = [(d[n]["rejected_per_day"], d[n]["late_per_day"], lab, col) for n, lab, col in
              (("as_found", "As found", AS_FOUND), ("mean_models", "Mean models", MEAN)) if n in d]
    W, H, L, R, T, B = 760, 420, 70, 30, 56, 56
    xs = [p[0] for p in pts] + [o[0] for o in others]
    ys = [p[1] for p in pts] + [o[1] for o in others]
    xmax, ymax = max(xs) * 1.1, max(ys) * 1.1

    def X(v):
        return L + (W - L - R) * v / xmax

    def Y(v):
        return H - B - (H - T - B) * v / ymax

    body = [f'<text x="20" y="46" font-size="12" fill="{MUTED}">Each point: the percentile of stop and travel time '
            f'given to the planner, averaged over development hubs and days</text>']
    for k in range(5):
        v = ymax * k / 4
        body.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{GRID}"/>')
        body.append(f'<text x="{L - 8}" y="{Y(v) + 4:.1f}" font-size="11" text-anchor="end" fill="{MUTED}">{v:.0f}</text>')
    for k in range(5):
        v = xmax * k / 4
        body.append(f'<text x="{X(v):.1f}" y="{H - B + 18}" font-size="11" text-anchor="middle" fill="{MUTED}">{v:.0f}</text>')
    body.append(f'<text x="{(L + W - R) / 2}" y="{H - 14}" font-size="12" text-anchor="middle" fill="{MUTED}">'
                f'Orders turned away per day</text>')
    body.append(f'<text x="18" y="{(T + H - B) / 2}" font-size="12" fill="{MUTED}" transform="rotate(-90 18 '
                f'{(T + H - B) / 2})" text-anchor="middle">Late deliveries per day</text>')
    body.append('<polyline fill="none" stroke="{}" stroke-width="2" points="{}"/>'.format(
        PLATFORM, " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b, _ in pts)))
    q = load("estimators")["service_quantile"]
    for a, b, lab in pts:
        chosen = lab == f"{round(q * 100)}th"
        body.append(f'<circle cx="{X(a):.1f}" cy="{Y(b):.1f}" r="{6 if chosen else 4.5}" fill="{PLATFORM}" '
                    f'stroke="{SURFACE}" stroke-width="2"/>')
        body.append(f'<text x="{X(a) + 9:.1f}" y="{Y(b) - 8:.1f}" font-size="11" fill="{INK}"'
                    f'{" font-weight=\"600\"" if chosen else ""}>{lab}{" (served)" if chosen else ""}</text>')
    for a, b, lab, col in others:
        body.append(f'<rect x="{X(a) - 5:.1f}" y="{Y(b) - 5:.1f}" width="10" height="10" fill="{col}" '
                    f'stroke="{SURFACE}" stroke-width="2"/>')
        body.append(f'<text x="{X(a) + 10:.1f}" y="{Y(b) + 4:.1f}" font-size="11" fill="{INK}">{lab}</text>')
    return _svg(W, H, "Late deliveries against orders turned away", body)


def chart_cost(dev: dict, order: list[str]) -> str:
    d = dev["designs"]
    rows = [n for n in order if n in d and n != "as_found"]
    W, L, R, T, rowh = 780, 330, 40, 60, 26
    H = T + rowh * len(rows) + 40
    vals = [d[n]["cost_vs_as_found_ci"] for n in rows]
    lo, hi = min(min(v[0] for v in vals), 0), max(max(v[1] for v in vals), 0)
    span = (hi - lo) or 1

    def X(v):
        return L + (W - L - R) * (v - lo) / span

    body = [f'<text x="20" y="46" font-size="12" fill="{MUTED}">Operating cost per hub per month against the hub as '
            f'found (turned away, late, driver hours); bars show 95% intervals</text>',
            f'<line x1="{X(0):.1f}" x2="{X(0):.1f}" y1="{T - 6}" y2="{H - 34}" stroke="{MUTED}"/>']
    for i, n in enumerate(rows):
        y = T + i * rowh + rowh / 2
        a, b = d[n]["cost_vs_as_found_ci"]
        m = d[n]["cost_vs_as_found_per_month"]
        col = PLATFORM if n == "platform" else (MEAN if n == "mean_models" else "#8A8F99")
        wt = ' font-weight="600"' if n == "platform" else ""
        body.append(f'<text x="{L - 10}" y="{y + 4:.1f}" font-size="12" text-anchor="end" fill="{INK}"{wt}>'
                    f'{d[n]["label"].split(":")[0]}</text>')
        body.append(f'<line x1="{X(a):.1f}" x2="{X(b):.1f}" y1="{y:.1f}" y2="{y:.1f}" stroke="{col}" stroke-width="2"/>')
        body.append(f'<circle cx="{X(m):.1f}" cy="{y:.1f}" r="4.5" fill="{col}"/>')
        body.append(f'<text x="{max(X(b), X(m)) + 8:.1f}" y="{y + 4:.1f}" font-size="11" fill="{MUTED}">{eur(m)}</text>')
    for v in (lo, 0, hi):
        body.append(f'<text x="{X(v):.1f}" y="{H - 16}" font-size="11" text-anchor="middle" fill="{MUTED}">{eur(v)}</text>')
    return _svg(W, H, "What each design costs against the hub as found", body)


def chart_day(day: dict) -> str:
    W, H, L, R, T, B = 780, 360, 60, 120, 56, 46
    series = {k: v for k, v in day["series"].items() if v}
    if not series:
        return _svg(W, H, "Late deliveries through the day", [])
    bins = len(next(iter(series.values()))["late"])
    first, last = 7 * 4, 23 * 4
    ymax = max(max(s["late"][first:last]) for s in series.values()) * 1.15 or 1

    def X(i):
        return L + (W - L - R) * (i - first) / (last - first)

    def Y(v):
        return H - B - (H - T - B) * v / ymax

    body = [f'<text x="20" y="46" font-size="12" fill="{MUTED}">Hub {day["seed"]}, {day["date"]}: the first open day after road '
            f'works start; late deliveries per 15 minutes</text>']
    for k in range(5):
        v = ymax * k / 4
        body.append(f'<line x1="{L}" x2="{W - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}" stroke="{GRID}"/>')
        body.append(f'<text x="{L - 8}" y="{Y(v) + 4:.1f}" font-size="11" text-anchor="end" fill="{MUTED}">{v:.0f}</text>')
    for h in range(8, 24, 3):
        body.append(f'<text x="{X(h * 4):.1f}" y="{H - B + 18}" font-size="11" text-anchor="middle" fill="{MUTED}">{h:02d}:00</text>')
    cols = {"as_found": (AS_FOUND, "As found"), "mean_models": (MEAN, "Mean models"), "platform": (PLATFORM, "Platform")}
    ends = []
    for n, s in series.items():
        col, lab = cols.get(n, (MUTED, n))
        pts = " ".join(f"{X(i):.1f},{Y(s['late'][i]):.1f}" for i in range(first, min(last, bins)))
        body.append(f'<polyline fill="none" stroke="{col}" stroke-width="2" points="{pts}"/>')
        ends.append([Y(s["late"][last - 1]), lab, col])
    ends.sort()
    for i in range(1, len(ends)):
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + 14)
    for y, lab, _col in ends:
        body.append(f'<text x="{W - R + 8}" y="{y + 4:.1f}" font-size="12" fill="{INK}">{lab}</text>')
    return _svg(W, H, "Late deliveries through one day", body)


def chart_warehouse(wh: dict) -> str:
    d = wh["designs"]
    rows = list(d)
    W, L, R, T, rowh = 760, 300, 80, 60, 28
    H = T + rowh * len(rows) + 30
    vmax = max(d[n]["metres_per_order"] for n in rows) * 1.05

    def X(v):
        return L + (W - L - R) * v / vmax

    body = [f'<text x="20" y="46" font-size="12" fill="{MUTED}">Walking per order in the warehouse, same order '
            f'lines for every design</text>']
    for i, n in enumerate(rows):
        y = T + i * rowh
        col = PLATFORM if n == "platform" else (AS_FOUND if n == "as_found" else "#8A8F99")
        label = {"as_found": "As found", "platform": "Platform"}.get(n, n.replace("platform_", "Platform, ").replace("_", " "))
        body.append(f'<text x="{L - 10}" y="{y + 15}" font-size="12" text-anchor="end" fill="{INK}">{label}</text>')
        body.append(f'<rect x="{L}" y="{y + 4}" width="{X(d[n]["metres_per_order"]) - L:.1f}" height="16" rx="3" fill="{col}"/>')
        body.append(f'<text x="{X(d[n]["metres_per_order"]) + 8:.1f}" y="{y + 16}" font-size="11" fill="{MUTED}">'
                    f'{d[n]["metres_per_order"]:.0f} m</text>')
    return _svg(W, H, "Metres walked per order", body)


def charts(dev: dict, day: dict | None, wh: dict | None, order: list[str], sweep_names: list[str]) -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    (CHARTS / "tradeoff.svg").write_text(chart_tradeoff(dev, sweep_names))
    (CHARTS / "cost.svg").write_text(chart_cost(dev, order))
    if day:
        (CHARTS / "day.svg").write_text(chart_day(day))
    if wh:
        (CHARTS / "warehouse.svg").write_text(chart_warehouse(wh))


# -- README block ---------------------------------------------------------------------------------------------
def _cost_cell(x: dict) -> str:
    lo, hi = x["cost_vs_as_found_ci"]
    if lo == hi == x["cost_vs_as_found_per_month"] == 0:
        return "–"
    return f"{eur(x['cost_vs_as_found_per_month'])} ({eur(lo)} to {eur(hi)})"


def _num(v: float | None) -> str:
    return "–" if v is None else f"{v:.1f}"


def _headline(s: dict, title: str) -> list[str]:
    d = s["designs"]
    cols = [n for n in ("platform", "mean_models", "as_found") if n in d]
    names = {"platform": "Platform", "mean_models": "Mean models", "as_found": "As found"}
    rows = [
        ("Late deliveries per day (95% interval)", lambda x: f"{x['late_per_day']:.1f} ({x['late_ci'][0]:.1f}–{x['late_ci'][1]:.1f})"),
        ("Accepted orders delivered late", lambda x: pct(x["late_share"])),
        ("Orders turned away", lambda x: pct(x["reject_share"])),
        ("Orders delivered within the promise", lambda x: pct(x["on_time_share"])),
        ("Driver hours per day", lambda x: f"{x['driver_hours_per_day']:.0f}"),
        ("Shifts two or more drivers short of plan, per week", lambda x: f"{x['short_shifts_per_week']:.1f}"),
        ("Operating cost per hub per month against as found", _cost_cell),
        ("Stop-time error (mean absolute, minutes)", lambda x: f"{x['stop_mae']:.2f}"),
        ("Stops under the served estimate", lambda x: pct(x["stop_coverage"], 0)),
        ("Legs under the served travel estimate", lambda x: pct(x["travel_coverage"], 0)),
    ]
    out = [f"| {title} | " + " | ".join(names[c] for c in cols) + " |", "|---|" + "---:|" * len(cols)]
    for lab, f in rows:
        out.append(f"| {lab} | " + " | ".join(("**" + f(d[c]) + "**") if c == "platform" else f(d[c]) for c in cols) + " |")
    w = s["world"]
    out += ["", f"{w['hubs']} simulated hubs, {w['days']} open days, {w['orders']:,} orders. Money uses "
                f"`config/value.yaml`; the interval is a paired bootstrap over hub-days."]
    return out


def _designs(s: dict, order: list[str]) -> list[str]:
    d = s["designs"]
    out = ["| Design | Late per day | Turned away | Driver hours | Short shifts / week | Stop MAE | Cost vs as found / month |",
           "|---|---:|---:|---:|---:|---:|---:|"]
    for n in order:
        if n not in d:
            continue
        x = d[n]
        b = "**" if n == "platform" else ""
        out.append(f"| {b}{x['label']}{b} | {x['late_per_day']:.1f} | {pct(x['reject_share'])} | "
                   f"{x['driver_hours_per_day']:.0f} | {x['short_shifts_per_week']:.1f} | {x['stop_mae']:.2f} | "
                   f"{eur(x['cost_vs_as_found_per_month'])} |")
    return out


def _ops(s: dict) -> list[str]:
    d = s["designs"]
    out = ["| Design | Late per day after road works | Late on outage days | Retrains (promoted) | Drift retrains |",
           "|---|---:|---:|---:|---:|"]
    for n in ("platform_no_retrain", "platform_weekly_only", "platform_no_fallback", "platform"):
        if n in d:
            x = d[n]
            out.append(f"| {x['label']} | {_num(x['late_per_day_after_roadworks'])} | {_num(x['late_on_outage_days'])} | "
                       f"{x['retrains']} ({x['promoted']}) | {x['drift_retrains']} |")
    return out


def _warehouse(wh: dict) -> list[str]:
    d = wh["designs"]
    out = ["| Picking design | Metres per order | Picker minutes per order | Orders per cart | Picker hours per day |",
           "|---|---:|---:|---:|---:|"]
    from dpe.sim.warehouse_run import PICK_DESIGNS
    labels = {p.name: p.label for p in PICK_DESIGNS}
    for n, x in d.items():
        b = "**" if n == "platform" else ""
        out.append(f"| {b}{labels.get(n, n)}{b} | {x['metres_per_order']:.0f} | {x['minutes_per_order']:.2f} | "
                   f"{x['orders_per_cart']:.1f} | {x['picker_hours_per_day']:.0f} |")
    return out


def readme(order: list[str], check: bool = False) -> bool:
    from dpe.eval.gate import gate

    dev, ho, wh = _load("dev"), _load("heldout"), _load("warehouse")
    if dev is None:
        block = f"{START}\n_No results yet: run `python -m dpe.eval.cli evaluate`._\n{END}"
    else:
        lines = [START, "", "### Dashboard (development hubs)", "", *_headline(dev, "Development"), "",
                 "![Late deliveries against orders turned away](reports/charts/tradeoff.svg)", "",
                 "![Cost against the hub as found](reports/charts/cost.svg)", "",
                 "![Late deliveries through one day](reports/charts/day.svg)", "",
                 "### Every design on the same hubs", "", *_designs(dev, order), "",
                 "### Retraining, drift and outages", "", *_ops(dev)]
        if wh:
            lines += ["", "### Warehouse picking", "", *_warehouse(wh), "",
                      "![Metres walked per order](reports/charts/warehouse.svg)"]
        if ho:
            fails = gate(ho)
            lines += ["", "### Held-out hubs (run once)", "", *_headline(ho, "Held-out"), "",
                      "Gate (`config/gate.yaml`) on the held-out hubs: " +
                      ("**passed**." if not fails else "**not passed**: " + "; ".join(fails) + "."),
                      "", "The record of that run: [docs/heldout.md](docs/heldout.md)."]
        lines += ["", "The decision memo for management, generated from these numbers: "
                      "[reports/decision_memo.md](reports/decision_memo.md).", "", END]
        block = "\n".join(lines)
    text = README.read_text()
    a, b = text.index(START), text.index(END) + len(END)
    new = text[:a] + block + text[b:]
    changed = new != text
    if changed and not check:
        README.write_text(new)
    return changed


def write(name: str, obj: dict) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    p = REPORTS / f"{name}.json"
    p.write_text(json.dumps(obj, indent=1, sort_keys=True, default=float) + "\n")
    return p
