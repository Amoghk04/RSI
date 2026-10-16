"""M3: toy-bench reference loop improves held-out split scores in tests."""

from pathlib import Path

import pytest

from rsi_harness.adapters.registry import load_adapter
from rsi_harness.adapters.toy_bench.reference_loop import toy_reference_round
from rsi_harness.config import BenchmarkConfig, load_run_config
from rsi_harness.core.budget import BudgetConfig, BudgetMeter
from rsi_harness.core.harness import EditLimits, HarnessLineageStore, HarnessManager
from rsi_harness.core.llm import LLMCache, LLMClient, LLMProviderConfig
from rsi_harness.core.types import RunResult


def mean_pass(results: list[RunResult]) -> float:
    if not results:
        return 0.0
    return sum(1.0 if r.passed else 0.0 for r in results) / len(results)


@pytest.fixture
def toy_stack(tmp_path: Path):
    cfg = load_run_config(Path("configs/toy-bench.yaml"))
    adapter = load_adapter(cfg.benchmark)
    surface = adapter.surface()
    store = HarnessLineageStore(tmp_path / "lineage")
    limits = EditLimits(max_artifacts_touched=1, max_bullets_touched=4, max_edit_chars=200)
    manager = HarnessManager(surface, limits=limits, store=store)
    harness = adapter.default_harness()
    manager.register(harness)
    meter = BudgetMeter(
        BudgetConfig(total_dollars=1.0, per_round_dollars=1.0, per_candidate_dollars=1.0)
    )
    llm = LLMClient(
        provider=LLMProviderConfig(provider="mock"),
        meter=meter,
        cache=LLMCache(tmp_path / "llm.db"),
    )
    return adapter, manager, harness, llm


def test_default_harness_fails_opt_tasks(toy_stack) -> None:
    adapter, _, harness, llm = toy_stack
    tasks = adapter.tasks("opt")
    assert len(tasks) >= 2
    results = [adapter.run(t, harness, llm, 0) for t in tasks]
    assert mean_pass(results) == 0.0


def test_reference_loop_improves_opt_to_perfect(toy_stack) -> None:
    adapter, manager, harness, llm = toy_stack
    final, before, after = toy_reference_round(
        adapter,
        manager,
        harness,
        "opt",
        llm,
        seed=0,
        opt_payloads=None,
    )
    assert mean_pass(before) == 0.0
    assert mean_pass(after) == 1.0
    assert final.id != harness.id
    assert final.parent_id == harness.id


def test_val_passes_after_opt_fixes_shared_token(toy_stack) -> None:
    """Val task t4 shares TOK-A with opt task t1 (manifest tuned for gate demos)."""
    adapter, manager, harness, llm = toy_stack
    after_opt, _, _ = toy_reference_round(
        adapter, manager, harness, "opt", llm, opt_payloads=None,
    )
    val_tasks = adapter.tasks("val")
    val_after = [adapter.run(t, after_opt, llm, 0) for t in val_tasks]
    assert mean_pass(val_after) == 1.0


def test_smoke_three_tasks_on_default_manifest() -> None:
    adapter = load_adapter(BenchmarkConfig(name="toy_bench", splits_manifest=None))
    harness = adapter.default_harness()
    meter = BudgetMeter(
        BudgetConfig(total_dollars=1.0, per_round_dollars=1.0, per_candidate_dollars=1.0)
    )
    import tempfile

    llm = LLMClient(
        provider=LLMProviderConfig(provider="mock"),
        meter=meter,
        cache=LLMCache(Path(tempfile.mkdtemp()) / "llm.db"),
    )
    for split in ("opt", "val", "test"):
        tasks = adapter.tasks(split)[:1]
        for task in tasks:
            r = adapter.run(task, harness, llm, 0)
            assert 0.0 <= r.score <= 1.0
            assert r.valid
