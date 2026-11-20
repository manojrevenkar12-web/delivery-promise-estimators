from dpe.sim.designs import BY_NAME
from dpe.sim.run import run_seed


def test_every_design_meets_the_same_orders_and_retrains_through_the_gate(small_cfg, small_est, pcfg):
    names = ["as_found", "mean_models", "platform", "platform_no_retrain"]
    out = run_seed(small_cfg, 4242, [BY_NAME[n] for n in names], small_est, pcfg)
    orders = {n: [d["orders"] for d in out["designs"][n]["days"]] for n in names}
    assert len({tuple(v) for v in orders.values()}) == 1
    p = out["designs"]["platform"]
    assert p["days"] and all(0 <= d["stop_coverage"] <= 1 for d in p["days"])
    assert out["designs"]["platform_no_retrain"]["retrains"] == []
    assert out["designs"]["as_found"]["days"][0]["version"] == "rules"
