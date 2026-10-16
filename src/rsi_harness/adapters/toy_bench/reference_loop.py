"""
Toy-only reference improvement loop (M3).

Uses failure traces to add missing tokens to the playbook. Not used for real benchmarks.
"""

from __future__ import annotations

from rsi_harness.adapters.protocol import BenchmarkAdapter
from rsi_harness.adapters.toy_bench.adapter import PLAYBOOK_ARTIFACT
from rsi_harness.core.harness import HarnessManager
from rsi_harness.core.llm import LLMClient
from rsi_harness.core.types import Edit, HarnessSpec, RunResult, Split, Task


def _missing_token_from_trace(trace: list[dict[str, object]]) -> str | None:
    for entry in trace:
        if entry.get("event") == "diagnosis_hint":
            tok = entry.get("missing_token")
            if isinstance(tok, str):
                return tok
    return None


def run_batch(
    adapter: BenchmarkAdapter,
    harness: HarnessSpec,
    tasks: list[Task],
    llm: LLMClient,
    seed: int,
) -> list[RunResult]:
    return [adapter.run(task, harness, llm, seed) for task in tasks]


def propose_toy_edits(results: list[RunResult]) -> list[Edit]:
    edits: list[Edit] = []
    seen_tasks: set[str] = set()
    for result in results:
        if result.passed or result.task_id in seen_tasks:
            continue
        seen_tasks.add(result.task_id)
        token = _missing_token_from_trace(result.trace)
        if token is None:
            continue
        edits.append(
            Edit(
                artifact=PLAYBOOK_ARTIFACT,
                op="add_bullet",
                bullet_id=f"fix-{result.task_id}",
                text=token,
            )
        )
    return edits


def toy_reference_round(
    adapter: BenchmarkAdapter,
    manager: HarnessManager,
    harness: HarnessSpec,
    split: Split,
    llm: LLMClient,
    *,
    seed: int = 0,
    opt_payloads: list[dict[str, object]] | None = None,
) -> tuple[HarnessSpec, list[RunResult], list[RunResult]]:
    """
    One opt/val round: run tasks, apply playbook fixes, re-run.

    Returns (final_harness, before_results, after_results).
    """
    tasks = adapter.tasks(split)
    before = run_batch(adapter, harness, tasks, llm, seed)
    edits = propose_toy_edits(before)
    if not edits:
        return harness, before, before

    payloads = (
        [dict(p) for p in opt_payloads] if opt_payloads is not None else None
    )
    improved = manager.apply_edits(
        harness,
        edits,
        opt_payloads=payloads,
        check_leakage=opt_payloads is not None,
    )
    after = run_batch(adapter, improved, tasks, llm, seed)
    return improved, before, after
