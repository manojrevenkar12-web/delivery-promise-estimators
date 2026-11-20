# 0003. Travel time as a correction over the map router, served as a matrix

## Status

Accepted.

## Context

- **What the router gets right and wrong.** A map router knows distances. It does not know this city's rush hours
  by district, rain, or the road works that started on Tuesday.
- **Call volume.** The planner asks for thousands of legs a minute, so a model call per leg is not an option.

## Decision

- **Learn the ratio.** The model learns actual minutes over router minutes, by zone pair, hour, weekday and rain
  forecast, from telematics legs.
- **Serve a matrix.** Each morning the service computes a matrix of factors (zone × zone × hour) at the served
  quantile. The planner multiplies router minutes by it.

## Consequences

- **The router stays the base.** It still supplies the distance. The model only corrects it.
- **Leg-level detail is lost.** Zone resolution misses differences inside a zone. That is a deliberate trade for
  serving cost, and a finer grid is a config change.
