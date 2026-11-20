import numpy as np

from dpe.world import World


def test_same_luck_for_every_caller(small_cfg):
    a, b = World(small_cfg, 4242), World(small_cfg, 4242)
    oa, ob = a.orders(3), b.orders(3)
    assert oa.equals(ob)
    assert np.allclose(a.stop_minutes(3, oa), b.stop_minutes(3, ob))
    ds = a.roster_order(3, "early")[:5]
    assert (a.shows(3, "early", ds) == b.shows(3, "early", ds)).all()
    # a draw does not depend on what else was asked first
    assert a.shows(3, "early", ds[:2]).tolist() == b.shows(3, "early", ds)[:2].tolist()


def test_closed_on_sunday_and_more_orders_on_saturday(small_cfg):
    w = World(small_cfg, 4242)
    sundays = [d for d in range(w.days) if w.weekday(d) == 6]
    assert sundays and all(w.orders(d).empty for d in sundays)
    sat = np.mean([len(w.orders(d)) for d in range(w.days) if w.weekday(d) == 5])
    tue = np.mean([len(w.orders(d)) for d in range(w.days) if w.weekday(d) == 1])
    assert sat > tue


def test_road_works_slow_their_zones_from_their_day(small_cfg):
    w = World(small_cfg, 4242)
    z = int(np.flatnonzero(w.roadworks)[0])
    other = int(np.flatnonzero(~w.roadworks)[0])
    h = np.array([11.0])
    before = w.travel_factor(w.roadworks_day - 2, np.array([z]), np.array([z]), h)[0]
    after = w.travel_factor(w.roadworks_day, np.array([z]), np.array([z]), h)[0]
    unaffected = w.travel_factor(w.roadworks_day, np.array([other]), np.array([other]), h)[0]
    assert after > before * 1.2 and unaffected < after


def test_stairs_without_a_lift_take_longer(small_cfg):
    w = World(small_cfg, 4242)
    o = w.orders(2)
    m = w.stop_minutes(2, o)
    stairs = (o["floor"] >= 4) & (o["lift"] == 0)
    ground = o["floor"] == 0
    assert m[stairs.to_numpy()].mean() > m[ground.to_numpy()].mean()


def test_outages_only_on_evaluation_days(small_cfg):
    w = World(small_cfg, 4242)
    assert w.outages and all(d >= small_cfg["history_days"] for d in w.outages)
