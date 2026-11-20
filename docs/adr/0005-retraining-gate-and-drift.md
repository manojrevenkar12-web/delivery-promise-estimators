# 0005. Weekly retraining through a gate, early retraining after drift

## Status

Accepted.

## Decision

- **Weekly.** Train a challenger on the last 28 days, leaving the last three open days out. Promote it only if its
  pinball loss on those three days is at most 2% worse than the champion's, for stop times and for travel.
- **Recency weights.** Rows halve in weight every 10 days back, so a changed street pattern counts within days.
- **Drift.** Each day, compare actuals with the served percentile. On two consecutive days where actuals fall under
  it clearly less often than they should (by more than 10 points), the service:
  - retrains daily for five days;
  - judges each daily retrain on the last day.
- **Registry.** In production the job (`dpe/ops/train_job.py`) logs every run to MLflow and registers every
  version. It moves the `champion` alias only when the gate passes. The service fetches `@champion` at start.

## Consequences

- **What the ablations measure.** `platform_no_retrain` and `platform_weekly_only` show the value of each layer,
  and the road works mid-period are what they react to.
- **A one-day judgement is noisier.** The fast path accepts that, for a few days, in exchange for speed.
