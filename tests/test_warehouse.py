import numpy as np

from dpe.warehouse.picking import Layout, batches, reslot, route_length

L = Layout(aisles=10, slots=20, length=30.0, gap=4.0)


def test_distances_are_symmetric_and_straight_within_an_aisle():
    a, b = np.array([[8.0, 5.0]]), np.array([[8.0, 20.0]])
    assert L.dist(a, b)[0, 0] == 15.0
    c = np.array([[20.0, 10.0]])
    assert np.isclose(L.dist(a, c)[0, 0], L.dist(c, a)[0, 0])


def test_a_tour_over_the_picks_is_never_longer_than_the_heuristics():
    r = np.random.default_rng(3)
    for _ in range(25):
        k = r.integers(2, 14)
        pts = L.position(np.stack([r.integers(0, 10, k), r.integers(0, 20, k)], axis=1))
        tsp = route_length(L, pts, "tsp")
        assert tsp <= route_length(L, pts, "s_shape") + 1e-6
        assert tsp <= route_length(L, pts, "return") + 1e-6


def test_carts_hold_their_capacity():
    r = np.random.default_rng(4)
    pts = [L.position(np.stack([r.integers(0, 10, 3), r.integers(0, 20, 3)], axis=1)) for _ in range(15)]
    crates = r.integers(1, 6, 15)
    for policy in ("fcfs", "savings"):
        bs = batches(policy, pts, crates, 12, 6, L)
        assert sorted(i for b in bs for i in b) == list(range(15))
        assert all(crates[b].sum() <= 12 or len(b) == 1 for b in bs) and all(len(b) <= 6 for b in bs)


def test_reslotting_puts_the_busiest_sku_nearest_pack_out():
    slots = np.stack([np.arange(50) % 10, (np.arange(50) * 7) % 20], axis=1)
    lines = [np.array([42])] * 30 + [np.array([1])] * 3
    new = reslot(L, slots, lines)
    dep = np.array([L.depot])
    d_new = L.dist(dep, L.position(new[[42]]))[0, 0]
    d_old = L.dist(dep, L.position(slots[[42]]))[0, 0]
    assert d_new <= d_old and d_new == L.dist(dep, L.position(new)).min()
