"""Orchestrator checkpoint state (resumable runs)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class OrchestratorState:
    run_id: str
    config_fingerprint: str
    round_index: int
    current_harness_id: str
    accepted_harness_ids: list[str] = field(default_factory=list)
    guard_task_ids: list[str] = field(default_factory=list)
    aa_sigma: float = 0.0
    patience_remaining: int = 0
    rng_state: dict[str, Any] = field(default_factory=dict)
    finished: bool = False
    finalist_harness_id: str | None = None
    rounds_without_accept: int = 0

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"

    @classmethod
    def from_json(cls, raw: str) -> OrchestratorState:
        data = json.loads(raw)
        return cls(**data)


def state_path(workdir: Path) -> Path:
    return workdir / "orchestrator_state.json"


def load_state(workdir: Path) -> OrchestratorState | None:
    path = state_path(workdir)
    if not path.exists():
        return None
    return OrchestratorState.from_json(path.read_text())


def save_state(workdir: Path, state: OrchestratorState) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    state_path(workdir).write_text(state.to_json())
