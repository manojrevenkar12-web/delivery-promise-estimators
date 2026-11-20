# 0001. Judge estimators by what the planner does with them

## Status

Accepted.

## Context

The usual way to choose a model is its error: mean absolute error, RMSE. But nobody at a hub sees the error.
They see what the route planner does with an estimate:

- **Too low.** The planner accepts orders it cannot deliver in 120 minutes, and some arrive late.
- **Too high.** It turns customers away while drivers stand idle.

The two mistakes cost different amounts, and the planner reacts to them differently.

## Decision

- **Replay the planner.** Every design is scored by replaying the planner (`dpe/sim/planner.py`) on the same orders,
  streets and drivers, then counting what the business counts: late deliveries, orders turned away, driver hours
  and shifts short of plan.
- **Convert to money.** The counts are turned into money with `config/value.yaml`.
- **Keep error as a diagnostic.** Mean absolute error and coverage are still reported, but they choose nothing.

## Consequences

- **Error is not the target.** The design with the lowest stop-time error (the median) is not the one served; see
  [ADR 0002](0002-serve-a-quantile.md).
- **The planner is a stand-in.** It is a plain model of the real one, and the ranking matters more than the euro
  amounts. With the real planner, the same replay runs against it.
