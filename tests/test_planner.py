import numpy as np

from dpe.sim.planner import Driver, simulate_day
from dpe.world import World


def _drivers(n: int) -> list[Driver]:
    return [Driver(i, 420, 900, False, 420.0) for i in range(n)] + [Driver(10 + i, 840, 1320, True, 840.0)
                                                                   for i in range(n)]


def test_underestimates_accept_orders_that_arrive_late(small_cfg, pcfg):
    w = World(small_cfg, 4242)
    day = 3
    o = w.orders(day)
    truth = w.stop_minutes(day, o)
    F = np.full((w.n_zones, w.n_zones, 24), 1.3)
    good = simulate_day(w, day, o, truth * 1.1, F, _drivers(4), pcfg)
    low = simulate_day(w, day, o, truth * 0.4, F * 0.6, _drivers(4), pcfg)
    assert low.accepted >= good.accepted
    assert low.late / max(low.accepted, 1) > good.late / max(good.accepted, 1)


def test_every_order_is_accepted_or_turned_away_and_none_without_drivers(small_cfg, pcfg):
    w = World(small_cfg, 4242)
    o = w.orders(4)
    F = np.ones((w.n_zones, w.n_zones, 24))
    r = simulate_day(w, 4, o, np.full(len(o), 4.0), F, _drivers(3), pcfg)
    assert r.accepted + r.rejected == len(o) and r.on_time + r.late == r.accepted
    none = simulate_day(w, 4, o, np.full(len(o), 4.0), F, [], pcfg)
    assert none.accepted == 0 and none.rejected == len(o)


def test_the_day_is_the_same_when_run_twice(small_cfg, pcfg):
    w = World(small_cfg, 4242)
    o = w.orders(5)
    F = np.ones((w.n_zones, w.n_zones, 24))
    a = simulate_day(w, 5, o, np.full(len(o), 4.0), F, _drivers(3), pcfg)
    b = simulate_day(w, 5, o, np.full(len(o), 4.0), F, _drivers(3), pcfg)
    assert a.__dict__ == b.__dict__
