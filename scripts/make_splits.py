#!/usr/bin/env python3
"""Generate and validate frozen split manifests (I2)."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from rsi_harness.core.splits import (
    compute_manifest_hash,
    load_split_manifest,
    verify_disjoint,
)

INTENT_RE = re.compile(r"^\[([^\]]+)\]")


def intent_and_depth(task_id: str) -> tuple[str, int]:
    m = INTENT_RE.match(task_id)
    intent = m.group(1) if m else "unknown"
    depth = task_id.split("[PERSONA:", 1)[0].count("|") + 1
    return intent, depth


def stratified_shuffle(items: list[str], seed: int, key_fn) -> list[str]:
    import random

    rng = random.Random(seed)
    buckets: dict[tuple, list[str]] = {}
    for item in items:
        buckets.setdefault(key_fn(item), []).append(item)
    for bucket in buckets.values():
        rng.shuffle(bucket)
    keys = sorted(buckets.keys())
    rng.shuffle(keys)
    out: list[str] = []
    while any(buckets[k] for k in keys):
        for k in keys:
            if buckets[k]:
                out.append(buckets[k].pop())
    return out


def make_tau2_mock(seed: int = 0) -> dict:
    splits = {
        "opt": ["create_task_1", "update_task_1"],
        "val": ["create_task_1_with_env_assertions"],
        "select": ["update_task_with_message_history"],
        "test": ["update_task_with_initialization_data"],
    }
    verify_disjoint(splits)
    return {
        "benchmark": "tau2",
        "domain": "mock",
        "version": "0.1.0",
        "seed": seed,
        "splits": splits,
        "manifest_hash": compute_manifest_hash(splits),
    }


def make_toy_bench(seed: int = 0) -> dict:
    """Canonical toy manifest (matches committed data/splits/toy_bench.json)."""
    task_defs = {
        "t1": {"required_token": "TOK-A", "family": "alpha"},
        "t2": {"required_token": "TOK-B", "family": "alpha"},
        "t3": {"required_token": "TOK-C", "family": "beta"},
        "t4": {"required_token": "TOK-A", "family": "beta"},
        "t5": {"required_token": "TOK-E", "family": "gamma"},
        "t6": {"required_token": "TOK-F", "family": "gamma"},
    }
    splits = {
        "opt": ["t1", "t2", "t3"],
        "val": ["t4"],
        "select": ["t5"],
        "test": ["t6"],
    }
    verify_disjoint(splits)
    return {
        "benchmark": "toy_bench",
        "version": "0.1.0",
        "seed": seed,
        "task_defs": task_defs,
        "splits": splits,
        "manifest_hash": compute_manifest_hash(splits),
    }


def _tau2_commit(tau2_root: Path) -> str | None:
    import subprocess

    try:
        out = subprocess.check_output(
            ["git", "-C", str(tau2_root), "rev-parse", "HEAD"],
            text=True,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def make_tau2_telecom(
    tau2_root: Path,
    seed: int,
    opt_frac: float = 0.40,
    val_frac: float = 0.20,
    select_frac: float = 0.15,
) -> dict:
    telecom = tau2_root / "data" / "tau2" / "domains" / "telecom"
    splits_path = telecom / "split_tasks.json"
    tasks_path = telecom / "tasks.json"
    if not splits_path.exists() or not tasks_path.exists():
        raise FileNotFoundError(f"Expected tau2 telecom data under {telecom}")

    upstream = json.loads(splits_path.read_text())
    base = set(upstream["base"])
    with tasks_path.open() as f:
        all_tasks = json.load(f)
    if isinstance(all_tasks, list):
        full_ids = [t["id"] if isinstance(t, dict) else str(t) for t in all_tasks]
    else:
        raise ValueError("Unexpected tasks.json shape")

    full_set = set(full_ids)
    pool = sorted(full_set - base)
    if len(base) != 114:
        raise ValueError(f"expected 114 base tasks, got {len(base)}")
    if len(pool) != len(full_set) - len(base):
        raise ValueError("pool construction failed")

    ordered = stratified_shuffle(pool, seed, lambda tid: intent_and_depth(tid))
    n = len(ordered)
    n_opt = int(n * opt_frac)
    n_val = int(n * val_frac)
    n_select = int(n * select_frac)
    opt = ordered[:n_opt]
    val = ordered[n_opt : n_opt + n_val]
    select = ordered[n_opt + n_val : n_opt + n_val + n_select]

    split_map = {
        "opt": opt,
        "val": val,
        "select": select,
        "test": sorted(base),
    }
    verify_disjoint(split_map)

    commit = _tau2_commit(tau2_root)
    manifest = {
        "benchmark": "tau2",
        "domain": "telecom",
        "seed": seed,
        "tau2_bench_commit": commit,
        "upstream_files": {
            "split_tasks.json": "data/tau2/domains/telecom/split_tasks.json",
            "tasks.json": "data/tau2/domains/telecom/tasks.json",
        },
        "test_source": "upstream:base",
        "pool_rule": "tasks.json ids minus upstream base (114)",
        "ratios_on_pool": {"opt": opt_frac, "val": val_frac, "select": select_frac},
        "counts": {
            "full": len(full_set),
            "test": len(base),
            "pool": n,
            "opt": len(opt),
            "val": len(val),
            "select": len(select),
        },
        "splits": split_map,
        "manifest_hash": compute_manifest_hash(split_map),
    }
    return manifest


def cmd_validate(path: Path) -> None:
    manifest = load_split_manifest(path)
    print(
        f"OK {path} benchmark={manifest.benchmark} "
        f"hash={manifest.manifest_hash[:16]}… counts={manifest.counts}"
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate", help="write a manifest JSON file")
    gen.add_argument(
        "--benchmark",
        choices=("toy", "mock", "tau2"),
        required=True,
    )
    gen.add_argument("--tau2-root", type=Path, help="Path to cloned tau2-bench repo")
    gen.add_argument("--seed", type=int, default=7)
    gen.add_argument("-o", type=Path, required=True)

    val = sub.add_parser("validate", help="verify manifest hash and disjoint splits")
    val.add_argument("manifest", type=Path)

    args = p.parse_args()

    if args.command == "validate":
        cmd_validate(args.manifest)
        return

    if args.benchmark == "toy":
        manifest = make_toy_bench(seed=args.seed)
    elif args.benchmark == "mock":
        manifest = make_tau2_mock(seed=args.seed)
    else:
        if args.tau2_root is None:
            p.error("--tau2-root is required for tau2")
        manifest = make_tau2_telecom(args.tau2_root, args.seed)

    args.o.parent.mkdir(parents=True, exist_ok=True)
    args.o.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {args.o} hash={manifest['manifest_hash'][:16]}…")


if __name__ == "__main__":
    main()
