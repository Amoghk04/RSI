"""ChampionAudit on select split only (I3)."""

from __future__ import annotations

from rsi_harness.core.harness import HarnessLineageStore
from rsi_harness.core.llm import LLMClient
from rsi_harness.core.ports import BenchmarkPort
from rsi_harness.core.stats import mean
from rsi_harness.core.types import HarnessSpec


class ChampionAuditor:
    """Re-score top-K accepted versions on `select` once after the loop (stub: mean pass rate)."""

    def __init__(
        self,
        adapter: BenchmarkPort,
        store: HarnessLineageStore,
        llm: LLMClient,
    ) -> None:
        self._adapter = adapter
        self._store = store
        self._llm = llm

    def pick_finalist(
        self,
        candidates: list[HarnessSpec],
        *,
        seed: int = 0,
    ) -> HarnessSpec:
        if not candidates:
            raise ValueError("no candidates for champion audit")
        select_tasks = self._adapter.tasks("select")
        if not select_tasks:
            return candidates[0]

        best = candidates[0]
        best_score = -1.0
        for harness in candidates:
            scores = [
                self._adapter.run(task, harness, self._llm, seed).score for task in select_tasks
            ]
            avg = mean(scores)
            if avg > best_score:
                best_score = avg
                best = harness
        return best
