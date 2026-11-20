"""The weekly training job: lake files in, a gated model version out.

    python -m dpe.ops.train_job --lake data/lake --through 28 --out models/current

1. Read the last 28 days of logs from the lake (`dpe.ops.lake`).
2. Train a challenger on all but the last few open days.
3. Judge it against the registered champion on those days (`gate`). With no champion yet, it is promoted.
4. Log parameters, row counts, pinball losses and the gate's verdict to MLflow; register the version; move the
   `champion` alias only if the gate passed.
5. Write the champion's bundle to `--out`, which the service loads (`DPE_MODEL_DIR`).

The tracking server comes from `MLFLOW_TRACKING_URI` (a local SQLite file by default).
"""
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

import mlflow
import pandas as pd
from mlflow.tracking import MlflowClient

from dpe.config import load
from dpe.estimators.bundle import Bundle
from dpe.estimators.pipeline import gate, train
from dpe.ops.lake import last_open_days, read_store

NAME = "delivery-promise-estimators"


class EstimatorModel(mlflow.pyfunc.PythonModel):
    """A registry-loadable wrapper: predict stop minutes at the served quantile for a frame of orders."""

    def load_context(self, context) -> None:
        self.bundle = Bundle.load(Path(context.artifacts["bundle"]))
        self.store = self.bundle.store()

    def predict(self, context, model_input: pd.DataFrame, params: dict | None = None):
        p = params or {}
        x = self.store.stop_frame(model_input, int(p.get("day", self.bundle.est.through)), int(p.get("weekday", 0)),
                                  {"forecast_temp": float(p.get("forecast_temp", 12.0)),
                                   "forecast_rain_prob": float(p.get("forecast_rain_prob", 0.3))})
        return self.bundle.est.stop_q.predict(x, self.bundle.quantiles["service"])


def run(lake: Path, through: int, out: Path) -> dict:
    cfg = load("estimators")
    q = {"service": cfg["service_quantile"], "travel": cfg["travel_quantile"],
         "availability": cfg["availability_quantile"]}
    store = read_store(lake, through)
    val = last_open_days(store, through, cfg["gate"]["validation_days"])
    cut = min(val)
    challenger = train(store, cut, cfg)
    client = MlflowClient()
    champion = None
    try:
        mv = client.get_model_version_by_alias(NAME, "champion")
        champion = Bundle.load(Path(mlflow.artifacts.download_artifacts(f"models:/{NAME}@champion") ) / "artifacts" / "bundle")
    except Exception:
        mv = None
    if champion is not None:
        ok, detail = gate(champion.est, challenger, store, range(cut, through), q["service"], q["travel"],
                          cfg["gate"]["max_pinball_regression"])
    else:
        ok, detail = True, {"note": "no champion yet"}
    mlflow.set_experiment(NAME)
    with mlflow.start_run(run_name=f"through-{cut}") as r, tempfile.TemporaryDirectory() as tmp:
        mlflow.log_params({"trained_through": cut, "window_days": cfg["training_window_days"],
                           "half_life_days": cfg["half_life_days"], **{f"q_{k}": v for k, v in q.items()},
                           **{f"xgb_{k}": v for k, v in cfg["xgboost"].items()}})
        mlflow.log_metrics({f"rows_{k}": v for k, v in challenger.rows.items()})
        for k, v in detail.items():
            if isinstance(v, dict):
                mlflow.log_metrics({f"{k}_pinball_{who}": val for who, val in v.items()})
        mlflow.log_dict({"promoted": ok, "detail": detail, "validation_days": val}, "gate.json")
        bundle = Bundle.from_store(challenger, store, q)
        bdir = Path(tmp) / "bundle"
        bundle.save(bdir)
        info = mlflow.pyfunc.log_model(name="estimators", python_model=EstimatorModel(),
                                       artifacts={"bundle": str(bdir)}, registered_model_name=NAME,
                                       pip_requirements=["xgboost", "pandas", "numpy", "scikit-learn"])
        version = info.registered_model_version
        if ok:
            client.set_registered_model_alias(NAME, "champion", version)
        run_id = r.info.run_id
    served = bundle if ok or champion is None else champion
    served.save(out)
    return {"run_id": run_id, "version": version, "promoted": ok, "detail": detail,
            "champion_before": mv.version if mv else None, "served": served.est.version}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dpe.ops.train_job")
    ap.add_argument("--lake", type=Path, default=Path("data/lake"))
    ap.add_argument("--through", type=int, required=True)
    ap.add_argument("--out", type=Path, default=Path("models/current"))
    a = ap.parse_args(argv)
    print(run(a.lake, a.through, a.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
