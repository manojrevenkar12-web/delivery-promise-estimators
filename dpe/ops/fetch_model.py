"""Fetch the registered champion's bundle for the service: `python -m dpe.ops.fetch_model --out /models`.

Runs as the service's init container, so a pod only starts with the version the gate promoted.
"""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

import mlflow

from dpe.ops.train_job import NAME


def fetch(out: Path, alias: str = "champion") -> Path:
    src = Path(mlflow.artifacts.download_artifacts(f"models:/{NAME}@{alias}")) / "artifacts" / "bundle"
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src / "bundle.pkl", out / "bundle.pkl")
    return out / "bundle.pkl"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dpe.ops.fetch_model")
    ap.add_argument("--out", type=Path, default=Path("/models"))
    ap.add_argument("--alias", default="champion")
    a = ap.parse_args(argv)
    print(fetch(a.out, a.alias))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
