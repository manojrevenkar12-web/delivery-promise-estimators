# SKILLS.md

## Add a feature to an estimator

1. Compute it in `dpe/features/store.py` from logs before the day, and add it to `STOP_FEATURES`,
   `TRAVEL_FEATURES` or `DRIVER_FEATURES`.
2. Run `pytest tests/test_features.py`. It checks that features for a day do not change when that day's logs
   arrive.
3. Run `python -m dpe.eval.cli quick`, then `evaluate`.

## Change the served percentile

1. Look at `reports/sweep.json` and the sensitivity table in `reports/decision_memo.md`.
2. Edit `service_quantile` and `travel_quantile` in `config/estimators.yaml`. No retrain is needed: one model
   serves every quantile in `quantiles`.

## Add a design or an ablation

1. Add a `Design` in `dpe/sim/designs.py` that changes exactly one thing.
2. Add it to `ORDER` in `web/src/shared/format.ts`.
3. Run `python -m dpe.eval.cli evaluate`.

## Train and serve locally

```bash
python -m dpe.sim.export --seed 9101 --through 40 --out data/lake       # the lake stand-in
MLFLOW_TRACKING_URI=sqlite:///mlflow.db python -m dpe.ops.train_job --lake data/lake --through 40 --out models/current
DPE_MODEL_DIR=models/current uvicorn dpe.service.api:app --port 8080
```

## Regenerate results

Run `python -m dpe.eval.cli evaluate` (about 20 minutes on two cores). Commit `reports/` and `README.md` together.

## Run the held-out hubs (once)

Run `python -m dpe.eval.cli heldout`. Commit `reports/heldout.json`, `config/heldout.lock` and `README.md`, and
record the run in `docs/heldout.md`.

## Deploy to Azure

1. In `infra/terraform`, run `terraform apply -var subscription_id=…`.
2. Fill the `REPLACE_*` values in `deploy/k8s/base` from the outputs.
3. Run `kustomize build deploy/k8s/base | kubectl apply -f -`.
