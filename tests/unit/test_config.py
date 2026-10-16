from pathlib import Path

import pytest

from rsi_harness.config import RunConfig, load_run_config


def test_load_base_config() -> None:
    root = Path(__file__).resolve().parents[2]
    cfg = load_run_config(root / "configs" / "base.yaml")
    assert cfg.run_id == "prototype-dev"
    assert cfg.budget.total_dollars == 50.0
    assert cfg.models["agent"].name == "google/gemini-2.5-flash"
    assert len(cfg.loop.seeds) == 2


def test_budget_caps_rejected() -> None:
    with pytest.raises(ValueError, match="per_round"):
        RunConfig.model_validate(
            {
                "run_id": "x",
                "models": {"agent": {"name": "m"}},
                "budget": {
                    "total_dollars": 1.0,
                    "per_round_dollars": 5.0,
                    "per_candidate_dollars": 0.1,
                },
                "loop": {
                    "rounds": 1,
                    "opt_batch": 1,
                    "candidates_per_round": 1,
                    "val_tasks_per_round": 1,
                    "seeds": [0],
                    "patience": 1,
                    "champion_top_k": 1,
                },
                "strategies": {
                    "diagnoser": {"name": "d"},
                    "proposer": {"name": "p"},
                    "gate": {"name": "g"},
                    "search": {"name": "s"},
                },
                "benchmark": {"name": "toy"},
            }
        )
