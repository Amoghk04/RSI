"""Load τ² Task payloads for manifest ids."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from rsi_harness.core.splits import SplitManifest

_FIXTURES = Path(__file__).resolve().parents[4] / "data" / "fixtures" / "tau2_mock_tasks.json"


def load_task_payloads(
    manifest: SplitManifest,
    *,
    tau2_root: Path | None,
) -> dict[str, dict[str, Any]]:
    domain = str((manifest.extra or {}).get("domain", "telecom"))
    if domain == "mock":
        return _load_fixture_payloads(manifest)

    if tau2_root is None:
        raise FileNotFoundError(
            "tau2_root required for non-mock domains "
            "(benchmark.tau2_root or TAU2_BENCH_ROOT)"
        )
    return _load_tau2_payloads(manifest, tau2_root, domain)


def _load_fixture_payloads(manifest: SplitManifest) -> dict[str, dict[str, Any]]:
    if not _FIXTURES.exists():
        raise FileNotFoundError(f"missing fixture tasks: {_FIXTURES}")
    raw = json.loads(_FIXTURES.read_text())
    by_id = {str(t["id"]): t for t in raw}
    needed = {tid for ids in manifest.splits.values() for tid in ids}
    missing = needed - set(by_id)
    if missing:
        raise KeyError(f"fixture tasks missing ids: {sorted(missing)[:5]}")
    return {tid: by_id[tid] for tid in needed}


def _load_tau2_payloads(
    manifest: SplitManifest,
    tau2_root: Path,
    domain: str,
) -> dict[str, dict[str, Any]]:
    tasks_path = tau2_root / "data" / "tau2" / "domains" / domain / "tasks.json"
    if not tasks_path.exists():
        raise FileNotFoundError(f"tau2 tasks.json not found: {tasks_path}")
    raw = json.loads(tasks_path.read_text())
    by_id = {str(t["id"]): t for t in raw}
    needed = {tid for ids in manifest.splits.values() for tid in ids}
    missing = needed - set(by_id)
    if missing:
        first = next(iter(missing))
        raise KeyError(f"tau2 tasks missing {len(missing)} manifest ids (first: {first})")
    return {tid: by_id[tid] for tid in needed}
