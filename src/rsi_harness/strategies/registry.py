from __future__ import annotations

from typing import Any, Protocol

from rsi_harness.config import RunConfig, StrategyRef
from rsi_harness.core.llm import LLMClient
from rsi_harness.core.types import (
    Decision,
    Diagnosis,
    Edit,
    HarnessSpec,
    LineageMemory,
    PairedEvidence,
    RunResult,
)
from rsi_harness.strategies.diagnosers.d0_none import D0Diagnoser
from rsi_harness.strategies.gates.g0_always import G0AlwaysGate
from rsi_harness.strategies.gates.g1_greedy import G1GreedyGate
from rsi_harness.strategies.gates.g7_aa_guard import G7AAGuardGate
from rsi_harness.strategies.proposers.p1_naive import P1NaiveProposer
from rsi_harness.strategies.proposers.p2_reflective import P2ReflectiveProposer
from rsi_harness.strategies.proposers.toy_oracle import ToyOracleProposer
from rsi_harness.strategies.search.greedy import GreedySearchPolicy


class Diagnoser(Protocol):
    name: str

    def diagnose(self, failures: list[RunResult], successes: list[RunResult]) -> Diagnosis: ...


class Proposer(Protocol):
    name: str

    def propose(
        self,
        current: HarnessSpec,
        diagnosis: Diagnosis,
        memory: LineageMemory,
        k: int,
    ) -> list[list[Edit]]: ...


class Gate(Protocol):
    name: str

    def decide(
        self,
        current: HarnessSpec,
        candidate: HarnessSpec,
        evidence: PairedEvidence,
    ) -> Decision: ...


class SearchPolicy(Protocol):
    name: str

    def select(self, current: HarnessSpec, accepted: list[HarnessSpec]) -> HarnessSpec: ...


def build_diagnoser(ref: StrategyRef) -> Diagnoser:
    if ref.name == "d0_none":
        return D0Diagnoser()
    raise ValueError(f"unknown diagnoser: {ref.name}")


def build_proposer(ref: StrategyRef, llm: LLMClient) -> Proposer:
    extra: dict[str, Any] = dict(ref.model_dump())
    if ref.name == "toy_oracle":
        return ToyOracleProposer()
    if ref.name == "p1_naive":
        return P1NaiveProposer(llm, max_edit_chars=int(extra.get("max_edit_chars", 1200)))
    if ref.name == "p2_reflective":
        return P2ReflectiveProposer(
            llm,
            max_edit_chars=int(extra.get("max_edit_chars", 800)),
            max_bullets_touched=int(extra.get("max_bullets_touched", 3)),
        )
    raise ValueError(f"unknown proposer: {ref.name}")


def build_gate(
    ref: StrategyRef,
    *,
    guard_task_ids: set[str],
) -> Gate:
    extra = ref.model_dump()
    if ref.name == "g0_always":
        return G0AlwaysGate()
    if ref.name == "g1_greedy":
        return G1GreedyGate(margin=float(extra.get("margin", 0.0)))
    if ref.name == "g7_aa_guard":
        return G7AAGuardGate(
            alpha=float(extra.get("alpha", 0.05)),
            guard_tolerance=float(extra.get("guard_tolerance", 0.05)),
            k_sigma=float(extra.get("k_sigma", 1.0)),
            guard_task_ids=guard_task_ids,
        )
    raise ValueError(f"unknown gate: {ref.name}")


def build_search(ref: StrategyRef) -> SearchPolicy:
    if ref.name == "greedy":
        return GreedySearchPolicy()
    raise ValueError(f"unknown search policy: {ref.name}")


def edit_limits_from_config(config: RunConfig) -> tuple[int, int, int]:
    proposer = config.strategies.proposer.model_dump()
    return (
        int(proposer.get("max_artifacts_touched", 3)),
        int(proposer.get("max_edit_chars", 800)),
        int(proposer.get("max_bullets_touched", 3)),
    )
