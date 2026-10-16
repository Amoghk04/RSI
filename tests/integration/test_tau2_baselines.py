from pathlib import Path

from rsi_harness.baselines import evaluate_b0, run_baseline
from rsi_harness.config import load_run_config


def test_b0_report_written(tmp_path: Path) -> None:
    cfg = load_run_config(Path("configs/baselines/tau2-mock-b0.yaml"))
    cfg = cfg.model_copy(update={"workdir": tmp_path})
    report_path = evaluate_b0(cfg)
    assert report_path.exists()
    data = report_path.read_text()
    assert '"baseline": "b0"' in data
    assert "by_role" in data


def test_b2_loop_smoke(tmp_path: Path) -> None:
    cfg = load_run_config(Path("configs/baselines/tau2-mock-b2.yaml"))
    loop = cfg.loop.model_copy(update={"rounds": 1})
    cfg = cfg.model_copy(update={"workdir": tmp_path, "loop": loop})
    summary = run_baseline(cfg, "b2")
    assert summary.exists()
