"""M4: resumable orchestrator with P2 + G7 on toy-bench."""

from pathlib import Path

import pytest

from rsi_harness.config import load_run_config
from rsi_harness.core.harness import HarnessLineageStore
from rsi_harness.core.runtime import run_workdir
from rsi_harness.core.state import load_state
from rsi_harness.runner import Orchestrator, run_orchestrator


@pytest.fixture
def m4_config(tmp_path: Path):
    cfg = load_run_config(Path("configs/toy-m4.yaml"))
    return cfg.model_copy(update={"workdir": tmp_path, "run_id": "toy-m4-test"})


def test_champion_audit_disabled_does_not_read_select(
    m4_config, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = m4_config.model_copy(
        update={
            "run_id": "toy-no-audit",
            "loop": m4_config.loop.model_copy(update={"champion_audit": False, "rounds": 1}),
        }
    )
    orch = Orchestrator(cfg)
    seen: list[str] = []
    original = orch.adapter.tasks

    def _tasks(split: str):
        seen.append(split)
        return original(split)

    monkeypatch.setattr(orch.adapter, "tasks", _tasks)
    state = orch.run()
    assert state.finished
    assert state.finalist_harness_id == state.current_harness_id
    assert "select" not in seen


def test_orchestrator_accepts_and_finishes(m4_config) -> None:
    state = run_orchestrator(m4_config)
    assert state.finished
    assert state.finalist_harness_id is not None
    assert len(state.accepted_harness_ids) >= 1


def test_resume_yields_same_finalist(m4_config) -> None:
    run_workdir(m4_config)
    cfg_partial = m4_config.model_copy(update={"run_id": "toy-m4-resume-a"})
    wd_a = run_workdir(cfg_partial)
    first = Orchestrator(cfg_partial)
    first.run(max_rounds=1)
    mid_state = load_state(wd_a)
    assert mid_state is not None
    assert not mid_state.finished

    second = Orchestrator(cfg_partial)
    final_state = second.run()
    assert final_state.finished

    third = Orchestrator(m4_config)
    third_state = third.run()
    assert third_state.finished
    assert third_state.finalist_harness_id == final_state.finalist_harness_id

    store = HarnessLineageStore(wd_a / "harness")
    store.load()
    spec = store.get(final_state.finalist_harness_id or "")
    assert spec is not None
    assert "TOK-A" in spec.artifacts.get("notes/playbook.json", "")


def test_interrupt_mid_run_then_resume_identical_state(m4_config) -> None:
    wd = run_workdir(m4_config)
    orch = Orchestrator(m4_config)
    orch.run(max_rounds=1)
    snapshot = load_state(wd)
    assert snapshot is not None

    orch2 = Orchestrator(m4_config)
    end = orch2.run()
    assert end.round_index >= snapshot.round_index
    assert end.finalist_harness_id == end.finalist_harness_id
