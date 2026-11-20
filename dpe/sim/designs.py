"""The designs compared on the same hubs.

A design says which estimate the planner gets for each of the three questions (a rule of thumb, a mean model or
a quantile model), at which quantile, and which of the operational safeguards run around the models.
"""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Design:
    name: str
    label: str
    service: str = "quantile"          # rule | mean | quantile
    travel: str = "quantile"
    availability: str = "quantile"
    q_service: float | None = None     # None: from config/estimators.yaml
    q_travel: float | None = None
    q_availability: float | None = None
    retrain: bool = True               # weekly, through the gate
    drift_retrain: bool = True         # early retrain when coverage drops
    fallback: bool = True              # last-known-good table while the service is down


AS_FOUND = Design("as_found", "As found: rules of thumb for stops, the map router for travel, a 90% show rate",
                  service="rule", travel="rule", availability="rule", retrain=False, drift_retrain=False,
                  fallback=False)
MEAN = Design("mean_models", "Mean models: XGBoost on squared error, trained once", service="mean", travel="mean",
              availability="mean", retrain=False, drift_retrain=False, fallback=False)
PLATFORM = Design("platform", "Platform: quantile models chosen by planner replay, retrained through a gate")

DESIGNS = [
    AS_FOUND,
    MEAN,
    replace(PLATFORM, name="platform_rule_service", label="Platform, rule of thumb for stop times", service="rule"),
    replace(PLATFORM, name="platform_router_travel", label="Platform, map router for travel", travel="rule"),
    replace(PLATFORM, name="platform_rule_availability", label="Platform, a 90% show rate", availability="rule"),
    replace(PLATFORM, name="platform_mean", label="Platform, mean instead of quantiles", service="mean",
            travel="mean", availability="mean"),
    replace(PLATFORM, name="platform_q50", label="Platform, the median for stops and travel", q_service=0.5,
            q_travel=0.5),
    replace(PLATFORM, name="platform_q90", label="Platform, the 90th percentile for stops and travel",
            q_service=0.9, q_travel=0.9),
    replace(PLATFORM, name="platform_no_retrain", label="Platform, never retrained", retrain=False,
            drift_retrain=False),
    replace(PLATFORM, name="platform_weekly_only", label="Platform, weekly retrain without drift alarms",
            drift_retrain=False),
    replace(PLATFORM, name="platform_no_fallback", label="Platform, rules of thumb during outages", fallback=False),
    PLATFORM,
]
BY_NAME = {d.name: d for d in DESIGNS}
ORDER = [d.name for d in DESIGNS]

# Development only: the replay that picks the percentiles in config/estimators.yaml (stops and travel x shows).
SWEEP = [replace(PLATFORM, name=f"sweep_q{q}_a{a}", label=f"Stops and travel at the {round(q * 100)}th percentile, "
                 f"roster to the {round(a * 100)}th percentile of shows", q_service=q, q_travel=q, q_availability=a)
         for q in (0.5, 0.6, 0.7) for a in (0.1, 0.2, 0.35, 0.5)]
BY_NAME.update({d.name: d for d in SWEEP})
