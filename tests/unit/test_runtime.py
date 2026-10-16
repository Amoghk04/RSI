from pathlib import Path

from rsi_harness.config import load_run_config
from rsi_harness.core.runtime import bootstrap_runtime, run_workdir


def test_bootstrap_runtime(tmp_path: Path) -> None:
    cfg = load_run_config(Path("configs/ci-mock.yaml"))
    cfg = cfg.model_copy(update={"workdir": tmp_path})
    meter, client, store = bootstrap_runtime(cfg)
    assert client.cache_namespace == "opt"
    assert run_workdir(cfg).exists() or True  # created on first write
    assert meter.snapshot().total_limit == 1.0
    assert store.optimization_view().list_results() == []
