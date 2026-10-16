"""Frozen split manifests (I2). Load, hash-verify, disjointness checks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rsi_harness.core.types import Split

SPLIT_NAMES: tuple[Split, ...] = ("opt", "val", "select", "test")


class SplitManifestError(ValueError):
    pass


@dataclass(frozen=True)
class SplitManifest:
    benchmark: str
    seed: int
    splits: dict[str, list[str]]
    manifest_hash: str
    task_defs: dict[str, dict[str, Any]] | None = None
    extra: dict[str, Any] | None = None

    @property
    def counts(self) -> dict[str, int]:
        return {name: len(self.splits.get(name, [])) for name in SPLIT_NAMES}

    def ids_for(self, split: Split) -> list[str]:
        try:
            return list(self.splits[split])
        except KeyError as e:
            raise SplitManifestError(f"missing split {split!r}") from e

    def verify_integrity(self) -> None:
        computed = compute_manifest_hash(self.splits)
        if computed != self.manifest_hash:
            raise SplitManifestError(
                f"manifest_hash mismatch: file={self.manifest_hash[:16]}… "
                f"computed={computed[:16]}…"
            )
        verify_disjoint(self.splits)
        for name in SPLIT_NAMES:
            if name not in self.splits:
                raise SplitManifestError(f"missing required split key: {name}")


def compute_manifest_hash(splits: dict[str, list[str]]) -> str:
    blob = json.dumps(splits, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def verify_disjoint(splits: dict[str, list[str]]) -> None:
    seen: dict[str, str] = {}
    for split_name, ids in splits.items():
        for tid in ids:
            if tid in seen:
                raise SplitManifestError(
                    f"task {tid!r} appears in both {seen[tid]!r} and {split_name!r}"
                )
            seen[tid] = split_name


def load_split_manifest(path: Path, *, verify: bool = True) -> SplitManifest:
    data = json.loads(path.read_text())
    splits = data.get("splits")
    if not isinstance(splits, dict):
        raise SplitManifestError("manifest must contain splits mapping")

    normalized: dict[str, list[str]] = {}
    for key, value in splits.items():
        if not isinstance(value, list):
            raise SplitManifestError(f"split {key!r} must be a list")
        normalized[str(key)] = [str(v) for v in value]

    manifest_hash = data.get("manifest_hash")
    if manifest_hash is None:
        manifest_hash = compute_manifest_hash(normalized)

    manifest = SplitManifest(
        benchmark=str(data.get("benchmark", "unknown")),
        seed=int(data.get("seed", 0)),
        splits=normalized,
        manifest_hash=str(manifest_hash),
        task_defs=data.get("task_defs"),
        extra={k: v for k, v in data.items() if k not in {"splits", "manifest_hash"}},
    )
    if verify:
        manifest.verify_integrity()
    return manifest
