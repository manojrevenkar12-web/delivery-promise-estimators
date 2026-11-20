import pytest

from dpe.features.store import FeatureStore
from dpe.sim.run import shift_needs
from dpe.world import SHIFTS, World


def _fill(w: World, store: FeatureStore, days: range, pcfg) -> None:
    needs = shift_needs(w, range(7), pcfg)
    for d in days:
        need = {s: needs.get((w.weekday(d), s), 0) for s in SHIFTS}
        store.add_day(d, w.weekday(d), w.forecast(d), w.stop_log(d), w.leg_log(d), w.shift_log(d, need))


def test_features_for_a_day_use_only_earlier_days(small_cfg, pcfg):
    w = World(small_cfg, 4242)
    s = FeatureStore(len(w.zone), w.n_zones)
    _fill(w, s, range(8), pcfg)
    o = w.orders(8)
    before = s.stop_frame(o, 8, w.weekday(8), w.forecast(8))
    _fill(w, s, range(8, 10), pcfg)
    after = s.stop_frame(o, 8, w.weekday(8), w.forecast(8))
    assert before.equals(after)


def test_days_are_written_once_and_in_order(small_cfg, pcfg):
    w = World(small_cfg, 4242)
    s = FeatureStore(len(w.zone), w.n_zones)
    _fill(w, s, range(3), pcfg)
    with pytest.raises(ValueError):
        _fill(w, s, range(2, 3), pcfg)
    with pytest.raises(ValueError):
        _fill(w, s, range(5, 6), pcfg)


def test_address_history_is_learned_from_logs(small_cfg, pcfg):
    w = World(small_cfg, 4242)
    s = FeatureStore(len(w.zone), w.n_zones)
    _fill(w, s, range(12), pcfg)
    x, y, days = s.stop_training(range(6, 12))
    seen = x["addr_n"] > 0
    assert seen.mean() > 0.3 and len(x) == len(y) == len(days)
