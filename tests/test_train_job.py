import mlflow

from dpe.ops import train_job
from dpe.sim.export import export


def test_the_job_registers_a_champion_then_gates_the_next(tmp_path, monkeypatch, small_cfg, small_est):
    monkeypatch.setattr("dpe.sim.export.world_config", lambda: small_cfg)
    monkeypatch.setattr("dpe.ops.train_job.load", lambda name: small_est)
    lake = tmp_path / "lake"
    export(4242, 19, lake)
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path / 'mlflow.db'}")
    monkeypatch.chdir(tmp_path)            # MLflow writes its artifacts under ./mlruns
    first = train_job.run(lake, 16, tmp_path / "model")
    assert first["promoted"] and first["champion_before"] is None
    second = train_job.run(lake, 19, tmp_path / "model")
    assert second["champion_before"] == first["version"]
    assert set(second["detail"]) == {"stop", "travel"}
    assert (tmp_path / "model" / "bundle.pkl").exists()
