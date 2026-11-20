"""The estimator service the route planner calls, and the dashboard's reports.

- `POST /v1/stop-times`: minutes at the door for each order, at the served quantile (and every quantile).
- `POST /v1/travel-matrix`: the slowdown over the map router per zone pair and hour, for one day.
- `POST /v1/roster`: how many drivers to ask for a shift, with an explanation a hub lead can read.
- `GET /health`, `GET /metrics` (Prometheus text): version, requests, fallbacks, latency.
- `GET /api/*`: the generated reports, for the dashboard; the built dashboard is served at `/`.

If no model is loaded or a model call fails, the service answers with the fallback table (or the rule of thumb
when there is no table) and says so in `source`; the planner always gets an answer.
"""
from __future__ import annotations

import json
import math
import os
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from dpe.config import ROOT, load
from dpe.estimators.bundle import Bundle
from dpe.estimators.models import roster_size
from dpe.estimators.pipeline import Served
from dpe.service.explain import claude_phraser, phrase, roster_facts

REPORTS = ROOT / "reports"


class Forecast(BaseModel):
    forecast_temp: float
    forecast_rain_prob: float = Field(ge=0, le=1)


class Order(BaseModel):
    order: str
    address: int = Field(ge=0)
    zone: int = Field(ge=0)
    placed: int = Field(ge=0, lt=1440)
    crates: int = Field(ge=0, le=60)
    empties: int = Field(ge=0, le=60)
    items: int = Field(ge=0, le=200)
    floor: int = Field(ge=0, le=40)
    lift: int = Field(ge=0, le=1)
    building: int = Field(ge=0, le=2)


class StopRequest(BaseModel):
    day: int
    weekday: int = Field(ge=0, le=6)
    forecast: Forecast
    orders: list[Order] = Field(max_length=5000)


class TravelRequest(BaseModel):
    day: int
    weekday: int = Field(ge=0, le=6)
    forecast: Forecast


class RosterDriver(BaseModel):
    driver: int
    tenure: int


class RosterRequest(BaseModel):
    day: int
    shift: str = Field(pattern="^(early|late)$")
    weekday: int = Field(ge=0, le=6)
    needed: int = Field(ge=0, le=500)
    forecast: Forecast
    drivers: list[RosterDriver] = Field(min_length=1, max_length=1000, description="in the hub's roster order")


def create_app(model_dir: Path | None = None, reports: Path = REPORTS) -> FastAPI:
    app = FastAPI(title="delivery-promise-estimators")
    cfg, rules = load("estimators"), load("planner")["rule_of_thumb"]
    bundle = Bundle.load(model_dir) if model_dir and (Path(model_dir) / "bundle.pkl").exists() else None
    store = bundle.store() if bundle else None
    n_zones = bundle.n_zones if bundle else 16
    served = Served(bundle.est if bundle else None, rules, store, n_zones)
    q = bundle.quantiles if bundle else {"service": cfg["service_quantile"], "travel": cfg["travel_quantile"],
                                         "availability": cfg["availability_quantile"]}
    counts: Counter = Counter()
    latency: list[float] = []
    phraser = claude_phraser()

    def timed(name: str, fn):
        t = time.perf_counter()
        try:
            return fn()
        finally:
            latency.append(time.perf_counter() - t)
            counts[f'requests{{endpoint="{name}"}}'] += 1

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "model": bundle.est.version if bundle else None,
                "trained_through": bundle.est.through if bundle else None, "quantiles": q}

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics() -> str:
        lines = [f"dpe_{k} {v}" for k, v in sorted(counts.items())]
        if latency:
            lines.append(f"dpe_latency_seconds_p95 {np.quantile(latency[-1000:], 0.95):.4f}")
        return "\n".join(lines) + "\n"

    @app.post("/v1/stop-times")
    def stop_times(req: StopRequest) -> dict:
        def run():
            orders = pd.DataFrame([o.model_dump() for o in req.orders])
            if orders.empty:
                return {"minutes": [], "source": "none"}
            fc = req.forecast.model_dump()
            try:
                if bundle is None:
                    raise RuntimeError("no model loaded")
                x = store.stop_frame(orders, req.day, req.weekday, fc)
                allq = bundle.est.stop_q.predict_all(x)
                m = allq[:, bundle.est.stop_q.quantiles.index(q["service"])]
                return {"minutes": np.round(m, 2).tolist(), "quantile": q["service"], "source": bundle.est.version,
                        "quantiles": {str(k): np.round(allq[:, i], 2).tolist()
                                      for i, k in enumerate(bundle.est.stop_q.quantiles)}}
            except Exception:
                counts["fallbacks"] += 1
                m = served.fallback(orders, q["service"]) if bundle else served.rule_service(orders)
                return {"minutes": np.round(m, 2).tolist(), "quantile": q["service"],
                        "source": "fallback" if bundle else "rule_of_thumb"}
        return timed("stop-times", run)

    @app.post("/v1/travel-matrix")
    def travel_matrix(req: TravelRequest) -> dict:
        def run():
            mode = "quantile" if bundle else "rule"
            F = served.travel_matrix(req.day, req.weekday, req.forecast.model_dump(), mode, q["travel"])
            return {"factor": np.round(F, 3).tolist(), "axes": ["zone_from", "zone_to", "hour"],
                    "quantile": q["travel"], "source": bundle.est.version if bundle else "rule_of_thumb"}
        return timed("travel-matrix", run)

    @app.post("/v1/roster")
    def roster(req: RosterRequest) -> dict:
        def run():
            ids = np.array([d.driver for d in req.drivers])
            ten = np.array([d.tenure for d in req.drivers])
            fc = req.forecast.model_dump()
            if bundle is None:
                n = min(len(ids), math.ceil(req.needed / rules["show_rate"]))
                return {"ask": n, "drivers": ids[:n].tolist(), "source": "rule_of_thumb",
                        "explanation": f"Ask {n} drivers: the rule of thumb expects 90% to come."}
            x = store.driver_frame(req.day, req.shift, ids, ten, req.weekday, fc)
            p = bundle.est.avail.proba(x)
            n = roster_size(p, req.needed, q["availability"])
            from statistics import NormalDist
            z = NormalDist().inv_cdf(q["availability"])
            planned = p[:n].sum() + z * math.sqrt(float((p[:n] * (1 - p[:n])).sum()))
            facts = roster_facts(bundle.est.avail.contributions(x), p, req.needed, n, q["availability"], planned)
            text, source = phrase(facts, phraser)
            return {"ask": n, "drivers": ids[:n].tolist(), "show_probability": np.round(p[:n], 3).tolist(),
                    "facts": facts, "explanation": text, "explanation_source": source, "source": bundle.est.version}
        return timed("roster", run)

    def _report(name: str):
        path = reports / f"{name}.json"
        if not path.exists():
            raise HTTPException(404, f"{name} has not been generated: run python -m dpe.eval.cli evaluate")
        return json.loads(path.read_text())

    @app.get("/api/results")
    def results() -> dict:
        ho = reports / "heldout.json"
        from dpe.eval.gate import gate
        heldout = json.loads(ho.read_text()) if ho.exists() else None
        return {"dev": _report("dev"), "heldout": heldout, "heldout_gate_fails": gate(heldout) if heldout else None}

    @app.get("/api/day")
    def day() -> dict:
        return _report("day")

    @app.get("/api/warehouse")
    def warehouse() -> dict:
        return _report("warehouse")

    @app.get("/api/decisions")
    def decisions() -> dict:
        return _report("decisions")

    web = Path(os.environ.get("DPE_WEB_DIST", ROOT / "web" / "dist"))
    if web.exists():
        app.mount("/", StaticFiles(directory=web, html=True), name="web")
    return app


app = create_app(Path(os.environ["DPE_MODEL_DIR"]) if os.environ.get("DPE_MODEL_DIR") else None)
