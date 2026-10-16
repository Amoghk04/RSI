"""I2: committed split manifests are hash-stable and internally consistent."""

from pathlib import Path

from rsi_harness.core.splits import SPLIT_NAMES, load_split_manifest


def test_committed_toy_manifest_passes_i2() -> None:
    path = Path(__file__).resolve().parents[2] / "data/splits/toy_bench.json"
    manifest = load_split_manifest(path)
    for name in SPLIT_NAMES:
        assert name in manifest.splits
    assert sum(manifest.counts.values()) == len(
        {tid for ids in manifest.splits.values() for tid in ids}
    )
