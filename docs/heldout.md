# Held-out run

The held-out hubs are seeds 9201, 9202 and 9203 (`config/heldout.yaml`). They are run once with
`python -m dpe.eval.cli heldout`, which writes `config/heldout.lock` and refuses to run again.

## Record

- **Run:** once, on 2026-11-20; `config/heldout.lock` holds the time and the config hash.
- **Configuration:** the percentiles the development replay picked (60th for stops and travel, 20th for driver
  shows).
- **Result:** the gate (`config/gate.yaml`) passed. The numbers are in `reports/heldout.json` and in the README,
  exactly as they came out.

### What the held-out hubs say that the development hubs did not

- **The saving is smaller.** It is €13,605 a month per hub against €18,928 on the development hubs. The interval
  still excludes zero.
- **Three safeguards are within noise in money.** Weekly retraining, drift retraining and the fallback table
  matter for late deliveries after the road works start, not for the monthly total.
- **Mean models are cheaper again, and over the cap.** They cost less money but turn away 6.1% of orders, over the
  6% service level, and deliver more orders late.

## Changes made after the run

Only reporting changes; nothing in the models, the planner, the world or the configuration changed.

- The decision memo now explains negative values (pieces whose absence breaks the service level).
- The "if a late delivery is worth more" table now searches only pairs within the service level.
- The README text was written.
