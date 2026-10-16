"""User-simulator exclusion accounting (Q-007)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExclusionStats:
    attempts: int = 0
    excluded_invalid: int = 0
    retried: int = 0
    reasons: dict[str, int] = field(default_factory=dict)

    def record(self, reason: str, *, excluded: bool, retried: bool) -> None:
        self.attempts += 1
        if retried:
            self.retried += 1
        if excluded:
            self.excluded_invalid += 1
            self.reasons[reason] = self.reasons.get(reason, 0) + 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempts": self.attempts,
            "excluded_invalid": self.excluded_invalid,
            "retried": self.retried,
            "reasons": dict(self.reasons),
        }


def invalid_reason_from_simulation(sim: Any) -> str | None:
    """Return exclusion reason if trial should be dropped from paired stats."""
    termination = getattr(sim, "termination_reason", None)
    if termination is not None:
        name = getattr(termination, "value", str(termination))
        if name in {
            "user_error",
            "infrastructure_error",
            "context_window_exceeded",
            "unexpected_error",
        }:
            return name

    check = getattr(sim, "hallucination_check", None)
    if check is not None and getattr(check, "hallucination_found", False):
        return "user_sim_hallucination"

    return None
