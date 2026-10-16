"""Budget metering and hard caps (I5, I8)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from rsi_harness.config import BudgetConfig


class BudgetExceeded(Exception):
    """Raised when a configured dollar cap would be exceeded."""

    def __init__(self, message: str, snapshot: BudgetSnapshot) -> None:
        super().__init__(message)
        self.snapshot = snapshot


@dataclass
class BudgetSnapshot:
    total_spent: float
    total_limit: float
    round_spent: float
    round_limit: float
    candidate_spent: float
    candidate_limit: float
    by_role: dict[str, float] = field(default_factory=dict)
    warned: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BudgetMeter:
    """Tracks all-in spend (every LLM role). Hard-stops at caps."""

    def __init__(self, config: BudgetConfig, checkpoint_path: Path | None = None) -> None:
        self._config = config
        self._checkpoint_path = checkpoint_path
        self._total = 0.0
        self._round = 0.0
        self._candidate = 0.0
        self._by_role: dict[str, float] = {}
        self._warned = False
        self._round_active = False
        self._candidate_active = False

    def snapshot(self) -> BudgetSnapshot:
        return BudgetSnapshot(
            total_spent=self._total,
            total_limit=self._config.total_dollars,
            round_spent=self._round,
            round_limit=self._config.per_round_dollars,
            candidate_spent=self._candidate,
            candidate_limit=self._config.per_candidate_dollars,
            by_role=dict(self._by_role),
            warned=self._warned,
        )

    def begin_round(self) -> None:
        self._round = 0.0
        self._round_active = True

    def end_round(self) -> None:
        self._round_active = False

    def begin_candidate(self) -> None:
        self._candidate = 0.0
        self._candidate_active = True

    def end_candidate(self) -> None:
        self._candidate_active = False

    def charge(self, dollars: float, role: str) -> None:
        if dollars < 0:
            raise ValueError("dollars must be non-negative")
        if dollars == 0:
            return

        next_total = self._total + dollars
        if next_total > self._config.total_dollars:
            snap = self.snapshot()
            self._write_checkpoint(snap, reason="total_cap")
            raise BudgetExceeded(
                f"total budget exceeded: {next_total:.4f} > {self._config.total_dollars}",
                snap,
            )

        if self._round_active:
            next_round = self._round + dollars
            if next_round > self._config.per_round_dollars:
                snap = self.snapshot()
                self._write_checkpoint(snap, reason="round_cap")
                raise BudgetExceeded(
                    f"per-round budget exceeded: {next_round:.4f} > "
                    f"{self._config.per_round_dollars}",
                    snap,
                )
            self._round = next_round

        if self._candidate_active:
            next_cand = self._candidate + dollars
            if next_cand > self._config.per_candidate_dollars:
                snap = self.snapshot()
                self._write_checkpoint(snap, reason="candidate_cap")
                raise BudgetExceeded(
                    f"per-candidate budget exceeded: {next_cand:.4f} > "
                    f"{self._config.per_candidate_dollars}",
                    snap,
                )
            self._candidate = next_cand

        self._total = next_total
        self._by_role[role] = self._by_role.get(role, 0.0) + dollars

        warn_line = self._config.warn_at_fraction * self._config.total_dollars
        if not self._warned and self._total >= warn_line:
            self._warned = True

    def _write_checkpoint(self, snap: BudgetSnapshot, reason: str) -> None:
        if self._checkpoint_path is None:
            return
        self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "reason": reason,
            "at": datetime.now(UTC).isoformat(),
            "budget": snap.to_dict(),
        }
        self._checkpoint_path.write_text(json.dumps(payload, indent=2) + "\n")
