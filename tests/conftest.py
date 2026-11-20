import pytest

from dpe.config import load, world_config


@pytest.fixture(scope="session")
def small_cfg() -> dict:
    """A small hub: two weeks of history, five evaluation days, a few hundred orders a day."""
    c = world_config()
    c["seeds"] = [4242]
    c["history_days"], c["eval_days"] = 14, 5
    c["hub"]["addresses"] = 700
    c["orders"]["per_day"] = 230
    c["travel"]["legs_logged_per_day"] = 300
    c["drivers"]["pool"] = 30
    c["drivers"]["hired_during"] = 2
    c["regime"]["roadworks_eval_day"] = 2
    c["outages"]["per_eval"] = 1
    return c


@pytest.fixture(scope="session")
def small_est() -> dict:
    e = load("estimators")
    e["training_window_days"] = 14
    e["xgboost"]["n_estimators"] = 40
    return e


@pytest.fixture(scope="session")
def pcfg() -> dict:
    return load("planner")
