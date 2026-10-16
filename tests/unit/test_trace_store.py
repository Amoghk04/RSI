from pathlib import Path

import pytest

from rsi_harness.core.trace_store import SplitAccessError, TraceStore
from rsi_harness.core.types import Cost, RunResult


def _result(task_id: str) -> RunResult:
    return RunResult(
        task_id=task_id,
        harness_id="h0",
        seed=0,
        score=1.0,
        passed=True,
        valid=True,
        trace=[{"role": "user", "content": "x"}],
        cost=Cost(1, 2, 0.0, 0.1),
    )


def test_split_views_isolate_reads(tmp_path: Path) -> None:
    store = TraceStore(tmp_path)
    store.write("opt", _result("t-opt"))
    store.write("val", _result("t-val"))
    store.write("select", _result("t-select"))
    store.write("test", _result("t-test"))

    opt_view = store.optimization_view()
    assert {r.task_id for r in opt_view.list_results()} == {"t-opt", "t-val"}

    select_view = store.select_view()
    assert [r.task_id for r in select_view.list_results()] == ["t-select"]

    test_view = store.test_view()
    assert [r.task_id for r in test_view.list_results()] == ["t-test"]

    with pytest.raises(SplitAccessError):
        opt_view.assert_split_allowed("test")

    with pytest.raises(SplitAccessError):
        test_view.assert_split_allowed("opt")
