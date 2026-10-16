"""Shared types. Invariants: scores in [0,1]; opt/val/select/test splits are explicit."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Split = Literal["opt", "val", "select", "test"]


@dataclass(frozen=True)
class Task:
    id: str
    benchmark: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class Bullet:
    id: str
    text: str
    useful: int = 0
    harmful: int = 0


@dataclass(frozen=True)
class HarnessSpec:
    id: str
    parent_id: str | None
    artifacts: dict[str, str]


@dataclass(frozen=True)
class Edit:
    artifact: str
    op: Literal[
        "replace",
        "append",
        "insert",
        "delete",
        "add_bullet",
        "update_bullet",
        "remove_bullet",
    ]
    text: str = ""
    anchor: str | None = None
    bullet_id: str | None = None


@dataclass
class Cost:
    prompt_tokens: int
    completion_tokens: int
    dollars: float
    seconds: float
    by_role: dict[str, float] = field(default_factory=dict)


@dataclass
class RunResult:
    task_id: str
    harness_id: str
    seed: int
    score: float
    passed: bool
    valid: bool
    trace: list[dict[str, Any]]
    cost: Cost
    error: str | None = None


@dataclass
class FailureEntry:
    task_id: str
    score: float
    trace: list[dict[str, Any]]


@dataclass
class Diagnosis:
    summary: str
    failures: list[FailureEntry]
    successes: list[FailureEntry]


@dataclass(frozen=True)
class PairedEvidence:
    task_ids: list[str]
    seeds: list[int]
    current_scores: list[float]
    candidate_scores: list[float]
    inclusion_probs: list[float] | None
    estimated_full_val_delta: float | None
    guard_regressions: int
    edit_chars: int
    aa_sigma: float | None
    cost: Cost


@dataclass(frozen=True)
class Decision:
    name: str
    accept: bool
    reason: str


@dataclass
class LineageMemory:
    """Proposer-visible memory (opt split only; no test/select)."""

    rejected_edits: list[dict[str, Any]] = field(default_factory=list)
    last_opt_results: list[RunResult] = field(default_factory=list)
