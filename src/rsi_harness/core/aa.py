"""A/A noise-floor calibration for gates (G7)."""

from __future__ import annotations

from rsi_harness.core.llm import LLMClient
from rsi_harness.core.ports import BenchmarkPort
from rsi_harness.core.stats import estimate_aa_sigma
from rsi_harness.core.types import HarnessSpec, Task


def calibrate_aa_sigma(
    adapter: BenchmarkPort,
    harness: HarnessSpec,
    llm: LLMClient,
    tasks: list[Task],
    seed_a: int,
    seed_b: int,
) -> float:
    """Run the same harness twice on the same tasks; return mean |score_a - score_b|."""
    if not tasks:
        return 0.0
    scores_a: list[float] = []
    scores_b: list[float] = []
    for task in tasks:
        scores_a.append(adapter.run(task, harness, llm, seed_a).score)
        scores_b.append(adapter.run(task, harness, llm, seed_b).score)
    return estimate_aa_sigma(scores_a, scores_b)
