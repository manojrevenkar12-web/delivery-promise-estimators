# 0008. How designs are compared

## Status

Accepted.

## Decision

- **Same luck.** Every design meets the same orders, stop truths, street noise and driver shows. Draws are keyed by
  what they are about (`dpe/keyed.py`), so asking in a different order changes nothing.
- **Development and held-out hubs.** Three development hubs tune the work. Three held-out hubs are run once, behind
  a lock.
- **Uncertainty.** Intervals are a paired bootstrap over (hub, day) blocks: a resampled day carries every design's
  outcome on it.
- **One gate** (`config/gate.yaml`), checked on the held-out hubs, covering:
  - late deliveries halved against the hub as found;
  - cost not above it;
  - at most 6% of orders turned away;
  - coverage within 8 points of the served percentile.

## Consequences

The held-out numbers are the ones to quote. A change made after that run is recorded in `docs/heldout.md`.
