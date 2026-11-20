# 0002. Serve a quantile of stop and travel time, chosen by replay

## Status

Accepted.

## Context

- **Stop times have a long tail.** Stairs, nobody home, no parking. The mean sits well below the bad cases.
- **A mean estimate runs late.** A planner fed means books every tour as if nothing goes wrong, and too many of
  them run late.

## Decision

- **One model, several percentiles.** One XGBoost model per estimate learns several quantiles at once
  (`reg:quantileerror` with a list of alphas), on log minutes.
- **Quantiles never cross.** Its outputs are sorted per row.
- **The replay picks the percentile.** It is chosen on the development hubs by replaying the planner at every
  pair of percentiles: stops and travel, and driver shows (`sweep_q*_a*` in `dpe/sim/designs.py`). The pick is the
  cheapest pair that turns away at most the share of orders the business allows
  (`selection.max_reject_share`). It is stored in `config/estimators.yaml`, and `reports/sweep.json` says whether
  config still matches the pick.
- **Management sees the sensitivity.** The memo shows how the cheapest percentile moves with the cost of a late
  delivery. That cost is a business decision, not a modelling one.

## Consequences

- **One model serves every option.** Changing the served percentile is a config change, not a retrain.
- **Coverage becomes the health signal.** About 60% of stops should come in under a 60th-percentile estimate.
  Drift monitoring watches exactly that ([ADR 0005](0005-retraining-gate-and-drift.md)).
