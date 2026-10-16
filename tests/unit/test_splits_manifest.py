from pathlib import Path

import pytest

from rsi_harness.core.splits import (
    SplitManifestError,
    compute_manifest_hash,
    load_split_manifest,
    verify_disjoint,
)


def test_compute_manifest_hash_stable() -> None:
    splits = {
        "opt": ["t1", "t2"],
        "val": ["t3"],
        "select": ["t4"],
        "test": ["t5"],
    }
    h1 = compute_manifest_hash(splits)
    h2 = compute_manifest_hash(dict(splits))
    assert h1 == h2
    assert len(h1) == 64


def test_verify_disjoint_rejects_overlap() -> None:
    with pytest.raises(SplitManifestError):
        verify_disjoint({"opt": ["a"], "val": ["a"], "select": [], "test": []})


def test_load_toy_manifest(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    manifest = load_split_manifest(repo / "data/splits/toy_bench.json")
    assert manifest.benchmark == "toy_bench"
    assert manifest.ids_for("val") == ["t4"]


def test_tampered_hash_fails(tmp_path: Path) -> None:
    repo = Path(__file__).resolve().parents[2]
    raw = (repo / "data/splits/toy_bench.json").read_text()
    bad = raw.replace("t4", "t4x")
    path = tmp_path / "bad.json"
    path.write_text(bad)
    with pytest.raises(SplitManifestError, match="manifest_hash mismatch"):
        load_split_manifest(path)
