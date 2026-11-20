# 0004. Driver availability per driver, rostered at a percentile of shows

## Status

Accepted.

## Context

- **The rule of thumb.** Hubs ask for "needed ÷ 0.9" drivers.
- **Where it fails.** It is right on average, and wrong in flu weeks and with many new drivers.

## Decision

- **A probability per driver.** A classifier estimates each rostered driver's chance of coming. Its features are:
  - tenure;
  - the driver's own recent absences;
  - absences across the hub in the last two and seven days (a flu wave shows here first);
  - weekday, shift and forecast.
- **Sum into shows.** The probabilities are summed into a distribution of shows: a normal approximation of a sum
  of Bernoullis.
- **Size the roster.** Drivers are asked, in the hub's roster order, until the chosen percentile of shows covers the
  plan.

## Consequences

- **The replay chose the 20th percentile.** Rostering to fewer drivers is cheaper at €23 a driver hour, but it
  turns away more orders. Of the pairs that keep orders turned away under the 6% the business allows, the 20th
  percentile of shows (with the 60th for stops and travel) was cheapest.
- **The value is the service level, not money.** Without the model (the 90% rule), the hub is cheaper but turns
  away more than 6% of orders. The memo says so instead of hiding it.
- **Independence is assumed.** Shows inside a flu wave are correlated, so the spread is understated. The
  hub-absence features carry most of that signal.
