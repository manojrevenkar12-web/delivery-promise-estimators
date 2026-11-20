# 0006. The planner always gets an answer

## Status

Accepted.

## Decision

- **No answer is not an option.** Estimator outages happen, and a planner without estimates stops taking orders.
- **When the model fails or the service is unreachable,** the planner falls back to a last-known-good table: the
  served percentile by zone, crate band and stairs, built at training.
- **With no model loaded,** the service answers with the rule of thumb and says so in `source`.
- **Health is visible.** `/metrics` counts the fallbacks.
- **Deployment.** Two or more replicas, a disruption budget, and readiness on `/health`. An init container fetches
  the champion before a pod takes traffic.

## Consequences

The measured effect of the fallback is small, because the outages simulated are short (90 to 200 minutes on two
days). The table costs little to keep and is the difference between estimates and none in a longer outage.
