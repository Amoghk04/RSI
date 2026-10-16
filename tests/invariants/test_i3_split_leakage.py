"""I3: optimization views must not expose select/test traces."""

from pathlib import Path

import pytest

from rsi_harness.core.trace_store import SplitAccessError, TraceStore
from rsi_harness.core.types import Cost, RunResult


def _minimal(task_id: str) -> RunResult:
    return RunResult(
        task_id=task_id,
        harness_id="h",
        seed=0,
        score=0.0,
        passed=False,
        valid=True,
        trace=[],
        cost=Cost(0, 0, 0.0, 0.0),
    )


def test_optimization_view_never_lists_test_or_select(tmp_path: Path) -> None:
    store = TraceStore(tmp_path)
    store.write("test", _minimal("secret-test"))
    store.write("select", _minimal("secret-select"))
    store.write("opt", _minimal("visible"))

    ids = {r.task_id for r in store.optimization_view().list_results()}
    assert ids == {"visible"}
    assert "secret-test" not in ids
    assert "secret-select" not in ids


def test_optimization_writer_rejects_test_and_select(tmp_path: Path) -> None:
    store = TraceStore(tmp_path)
    result = _minimal("x")
    with pytest.raises(SplitAccessError):
        store.write_optimization("test", result)
    with pytest.raises(SplitAccessError):
        store.write_optimization("select", result)
    store.write_optimization("opt", result)
    assert len(store.optimization_view().list_results()) == 1
