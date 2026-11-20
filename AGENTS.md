# AGENTS.md

How to work in this repository, for people and for coding agents.

## Fast feedback

- `python -m pytest`: everything, about half a minute, on a small hub.
- `python -m dpe.eval.cli quick`: one hub, eight days, three designs.
- `ruff check .`, and in `web/` run `pnpm build`.

## Invariants

1. **The truth stays in the world.**
   - `dpe/world` holds the hubs: true stop minutes, street speeds and who turns up.
   - The platform (`dpe/estimators`, `dpe/features`, `dpe/service`, `dpe/warehouse`, `dpe/ops`) never imports
     `dpe.world` or `dpe.sim` (`tests/test_invariants.py`).
   - It gets what the company records: orders, address data, the driver app's stop times, telematics legs, the
     shift log and the morning forecast.
2. **The world does not read the platform's settings.** It reads `config/world.yaml` (and the held-out overlay)
   only.
3. **Same luck for every design.** Every draw is keyed by what it is about (`dpe/keyed.py`), so every design meets
   the same orders, streets and absences.
4. **Point in time.** A feature for day `d` uses only logs from before `d`. Training and serving build features with
   the same code (`FeatureStore`).
5. **The model reads and code decides.**
   - The roster explanation may be reworded by a language model, but its numbers are checked against facts that
     code computed.
   - Nothing a model writes changes a roster or an estimate.
6. **The planner always gets an answer.** It gets the model, the fallback table, or the rule of thumb, and the
   response says which.
7. **Settings in config.** Quantiles, windows, the gate, prices and effort estimates live in `config/*.yaml`.
8. **Generated reports.** `reports/`, the charts, the decision memo and the README results block are written by
   `dpe.eval.cli`; never edit them by hand.

## The held-out rule

- The held-out hubs (`config/heldout.yaml`) are run once with `python -m dpe.eval.cli heldout`. The run writes
  `config/heldout.lock`, and the command refuses to run again.
- Tune on the development hubs only.
- A change made after the held-out run is recorded in `docs/heldout.md`; the held-out numbers are not re-run.
