"""I11: reject harness text that copies literals from optimization task payloads."""

from __future__ import annotations

from typing import Any

from rsi_harness.core.types import HarnessSpec


class LeakageError(ValueError):
    """Candidate copies a forbidden literal from task payloads."""

    def __init__(self, message: str, literal: str, artifact: str) -> None:
        super().__init__(message)
        self.literal = literal
        self.artifact = artifact


def _collect_strings(obj: Any, out: set[str]) -> None:
    if isinstance(obj, str):
        out.add(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_strings(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _collect_strings(v, out)


def literals_from_payloads(
    payloads: list[dict[str, Any]],
    min_literal_len: int,
) -> set[str]:
    raw: set[str] = set()
    for payload in payloads:
        _collect_strings(payload, raw)
    return {s for s in raw if len(s) >= min_literal_len}


def find_leaked_literals(
    artifacts: dict[str, str],
    payloads: list[dict[str, Any]],
    *,
    min_literal_len: int = 12,
) -> list[tuple[str, str]]:
    """Return (artifact_name, literal) pairs found in artifact text."""
    forbidden = literals_from_payloads(payloads, min_literal_len)
    if not forbidden:
        return []
    hits: list[tuple[str, str]] = []
    for name, text in artifacts.items():
        for lit in forbidden:
            if lit in text:
                hits.append((name, lit))
    return hits


def assert_no_leakage(
    spec: HarnessSpec,
    payloads: list[dict[str, Any]],
    *,
    min_literal_len: int = 12,
) -> None:
    hits = find_leaked_literals(spec.artifacts, payloads, min_literal_len=min_literal_len)
    if hits:
        artifact, lit = hits[0]
        raise LeakageError(
            f"artifact {artifact!r} contains literal from opt payload "
            f"(len={len(lit)}): {lit[:48]!r}…",
            lit,
            artifact,
        )

