"""Deterministic τ² mock-domain scoring for CI (provider=mock, no tau2 install)."""

from __future__ import annotations

from typing import Any

from rsi_harness.adapters.tau2.prompt import harness_corpus_text
from rsi_harness.core.types import HarnessSpec, Task


def _required_literals(payload: dict[str, Any]) -> list[str]:
    literals: list[str] = []
    criteria = payload.get("evaluation_criteria") or {}
    for action in criteria.get("actions") or []:
        if not isinstance(action, dict):
            continue
        args = action.get("arguments") or {}
        if isinstance(args, dict):
            for value in args.values():
                if isinstance(value, str) and len(value) >= 3:
                    literals.append(value)
    return literals


def evaluate_mock_task(
    task: Task, harness: HarnessSpec
) -> tuple[float, bool, list[dict[str, object]]]:
    literals = _required_literals(task.payload)
    corpus = harness_corpus_text(harness)
    missing = [lit for lit in literals if lit not in corpus]
    passed = not missing
    trace: list[dict[str, object]] = [
        {"event": "mock_evaluate", "task_id": task.id, "passed": passed, "literals": literals},
    ]
    if missing:
        trace.append(
            {
                "event": "diagnosis_hint",
                "missing_token": missing[0],
                "missing_literals": missing,
            }
        )
    return (1.0 if passed else 0.0), passed, trace
