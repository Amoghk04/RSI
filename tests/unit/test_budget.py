from pathlib import Path

import pytest

from rsi_harness.config import BudgetConfig
from rsi_harness.core.budget import BudgetExceeded, BudgetMeter


def test_total_cap_writes_checkpoint(tmp_path: Path) -> None:
    ckpt = tmp_path / "checkpoint_budget.json"
    meter = BudgetMeter(
        BudgetConfig(total_dollars=0.01, per_round_dollars=0.01, per_candidate_dollars=0.01),
        checkpoint_path=ckpt,
    )
    meter.charge(0.005, "agent")
    with pytest.raises(BudgetExceeded):
        meter.charge(0.01, "agent")
    assert ckpt.exists()
    assert "total_cap" in ckpt.read_text()


def test_round_cap(tmp_path: Path) -> None:
    meter = BudgetMeter(
        BudgetConfig(total_dollars=10.0, per_round_dollars=0.05, per_candidate_dollars=1.0),
        checkpoint_path=tmp_path / "ckpt.json",
    )
    meter.begin_round()
    meter.charge(0.04, "proposer")
    with pytest.raises(BudgetExceeded, match="per-round"):
        meter.charge(0.02, "proposer")
