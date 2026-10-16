"""Paired validation on val (and rotating subsets)."""

from __future__ import annotations

import random

from rsi_harness.core.llm import LLMClient
from rsi_harness.core.ports import BenchmarkPort
from rsi_harness.core.stats import mean, paired_deltas
from rsi_harness.core.types import Cost, HarnessSpec, PairedEvidence, Task


class Validator:
    def __init__(self, adapter: BenchmarkPort, llm: LLMClient, rng: random.Random) -> None:
        self._adapter = adapter
        self._llm = llm
        self._rng = rng

    def compare(
        self,
        current: HarnessSpec,
        candidate: HarnessSpec,
        val_tasks: list[Task],
        seeds: list[int],
        *,
        max_tasks: int | None = None,
        inclusion_probs: list[float] | None = None,
        aa_sigma: float | None = None,
        edit_chars: int = 0,
        guard_regressions: int = 0,
    ) -> PairedEvidence:
        tasks = list(val_tasks)
        if max_tasks is not None and len(tasks) > max_tasks:
            self._rng.shuffle(tasks)
            tasks = tasks[:max_tasks]

        task_ids: list[str] = []
        current_scores: list[float] = []
        candidate_scores: list[float] = []
        total_cost = Cost(0, 0, 0.0, 0.0)

        for task in tasks:
            for seed in seeds:
                r0 = self._adapter.run(task, current, self._llm, seed)
                r1 = self._adapter.run(task, candidate, self._llm, seed)
                if not r0.valid or not r1.valid:
                    continue
                task_ids.append(task.id)
                current_scores.append(r0.score)
                candidate_scores.append(r1.score)
                total_cost.prompt_tokens += r0.cost.prompt_tokens + r1.cost.prompt_tokens
                total_cost.completion_tokens += (
                    r0.cost.completion_tokens + r1.cost.completion_tokens
                )
                total_cost.dollars += r0.cost.dollars + r1.cost.dollars
                total_cost.seconds += r0.cost.seconds + r1.cost.seconds

        deltas = paired_deltas(current_scores, candidate_scores)
        est_delta = mean(deltas)
        if inclusion_probs and len(inclusion_probs) == len(tasks):
            p_mean = mean(inclusion_probs[: len(tasks)])
            if p_mean > 0:
                est_delta = est_delta / p_mean

        return PairedEvidence(
            task_ids=task_ids,
            seeds=seeds,
            current_scores=current_scores,
            candidate_scores=candidate_scores,
            inclusion_probs=inclusion_probs,
            estimated_full_val_delta=est_delta,
            guard_regressions=guard_regressions,
            edit_chars=edit_chars,
            aa_sigma=aa_sigma,
            cost=total_cost,
        )
