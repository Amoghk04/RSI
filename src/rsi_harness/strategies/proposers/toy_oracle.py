"""Toy-bench oracle proposer (dev only)."""

from __future__ import annotations

from rsi_harness.adapters.toy_bench.reference_loop import propose_toy_edits
from rsi_harness.core.types import Diagnosis, Edit, HarnessSpec, LineageMemory


class ToyOracleProposer:
    name = "toy_oracle"

    def propose(
        self,
        current: HarnessSpec,
        diagnosis: Diagnosis,
        memory: LineageMemory,
        k: int,
    ) -> list[list[Edit]]:
        results = memory.last_opt_results
        edits = propose_toy_edits(results)
        if not edits:
            return []
        # One candidate with all fixes; duplicate up to k with no-op variants omitted.
        return [edits][:k]
