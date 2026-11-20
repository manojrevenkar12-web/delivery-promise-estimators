from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dpe.estimators.bundle import Bundle
from dpe.estimators.pipeline import train
from dpe.features.store import FeatureStore
from dpe.service.api import create_app
from dpe.service.explain import numbers, phrase
from dpe.sim.run import shift_needs
from dpe.world import SHIFTS, World


@pytest.fixture(scope="module")
def model_dir(tmp_path_factory, small_cfg, small_est, pcfg) -> tuple[Path, World]:
    w = World(small_cfg, 4242)
    s = FeatureStore(len(w.zone), w.n_zones)
    needs = shift_needs(w, range(14), pcfg)
    for d in range(14):
        need = {k: needs.get((w.weekday(d), k), 0) for k in SHIFTS}
        s.add_day(d, w.weekday(d), w.forecast(d), w.stop_log(d), w.leg_log(d), w.shift_log(d, need))
    est = train(s, 14, small_est)
    out = tmp_path_factory.mktemp("model")
    Bundle.from_store(est, s, {"service": 0.7, "travel": 0.7, "availability": 0.5}).save(out)
    return out, w


def _orders(w: World, day: int) -> list[dict]:
    o = w.orders(day).head(20)
    cols = ["order", "address", "zone", "placed", "crates", "empties", "items", "floor", "lift", "building"]
    return [{k: (int(v) if k != "order" else v) for k, v in r.items()} for r in o[cols].to_dict("records")]


def test_stop_times_travel_and_roster(model_dir):
    path, w = model_dir
    c = TestClient(create_app(path))
    assert c.get("/health").json()["model"] == "v14"
    fc = w.forecast(15)
    r = c.post("/v1/stop-times", json={"day": 15, "weekday": w.weekday(15), "forecast": fc, "orders": _orders(w, 15)}).json()
    assert len(r["minutes"]) == 20 and r["source"] == "v14"
    assert all(a <= b for a, b in zip(r["quantiles"]["0.5"], r["quantiles"]["0.9"], strict=True))
    m = c.post("/v1/travel-matrix", json={"day": 15, "weekday": 2, "forecast": fc}).json()
    assert len(m["factor"]) == w.n_zones and len(m["factor"][0][0]) == 24
    order = w.roster_order(15, "late")
    ro = c.post("/v1/roster", json={"day": 15, "shift": "late", "weekday": w.weekday(15), "needed": 6, "forecast": fc,
                                    "drivers": [{"driver": int(d), "tenure": int(w.tenure(15)[d])} for d in order]}).json()
    assert ro["ask"] >= 6 and ro["explanation"].startswith(f"Ask {ro['ask']} drivers")
    assert "dpe_requests" in c.get("/metrics").text


def test_without_a_model_the_planner_still_gets_rule_of_thumb_answers(model_dir):
    _, w = model_dir
    c = TestClient(create_app(None))
    r = c.post("/v1/stop-times", json={"day": 15, "weekday": 1, "forecast": w.forecast(15), "orders": _orders(w, 15)}).json()
    assert r["source"] == "rule_of_thumb" and len(r["minutes"]) == 20


def test_a_failing_model_falls_back_to_the_table(model_dir, monkeypatch):
    path, w = model_dir
    app = create_app(path)
    from dpe.estimators.models import QuantileModel

    def boom(self, x):
        raise RuntimeError("model crashed")

    monkeypatch.setattr(QuantileModel, "predict_all", boom)
    r = TestClient(app).post("/v1/stop-times", json={"day": 15, "weekday": 1, "forecast": w.forecast(15),
                                                      "orders": _orders(w, 15)}).json()
    assert r["source"] == "fallback" and len(r["minutes"]) == 20


def test_bad_requests_are_refused(model_dir):
    path, _ = model_dir
    c = TestClient(create_app(path))
    r = c.post("/v1/roster", json={"day": 1, "shift": "night", "weekday": 1, "needed": 3,
                                   "forecast": {"forecast_temp": 10, "forecast_rain_prob": 0.2}, "drivers": [{"driver": 1, "tenure": 9}]})
    assert r.status_code == 422


def test_a_model_may_reword_the_facts_but_not_invent_numbers():
    facts = {"needed": 12, "asked": 14, "expected_shows": 12.4, "planned_shows": 12.1, "percentile": 50,
             "unlikely_drivers": 2, "lowers": ["drivers in their first weeks"], "raises": []}
    ok, src = phrase(facts, lambda f: "Ask 14 drivers so 12 are on the road; 12.4 should come.")
    assert src == "model" and ok.startswith("Ask 14")
    bad, src = phrase(facts, lambda f: "Ask 17 drivers, 3 are sick.")
    assert src == "template" and "17" not in numbers(bad)
    _, src = phrase(facts, lambda f: (_ for _ in ()).throw(TimeoutError()))
    assert src == "template"
