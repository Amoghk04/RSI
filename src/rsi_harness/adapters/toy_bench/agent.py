"""Deterministic toy agent: pass iff required_token appears in harness text."""

from __future__ import annotations

from rsi_harness.core.playbook import parse_playbook
from rsi_harness.core.types import HarnessSpec, Task


def harness_corpus(harness: HarnessSpec) -> str:
    parts: list[str] = [harness.artifacts.get("system_prompt", "")]
    raw = harness.artifacts.get("notes/playbook.json", "[]")
    try:
        bullets = parse_playbook(raw)
    except ValueError:
        bullets = []
    for bullet in bullets:
        parts.append(bullet.text)
    return "\n".join(parts)


def evaluate_task(task: Task, harness: HarnessSpec) -> tuple[float, bool, list[dict[str, object]]]:
    token = str(task.payload["required_token"])
    corpus = harness_corpus(harness)
    passed = token in corpus
    trace: list[dict[str, object]] = [
        {"event": "evaluate", "task_id": task.id, "passed": passed},
    ]
    if not passed:
        # Toy-only diagnostic in trace (simulates execution feedback, not scorer access).
        trace.append({"event": "diagnosis_hint", "missing_token": token})
    score = 1.0 if passed else 0.0
    return score, passed, trace
