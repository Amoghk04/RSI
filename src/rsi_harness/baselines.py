"""Baseline runners B0–B3 (M6)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from rsi_harness.adapters.registry import load_adapter
from rsi_harness.config import RunConfig
from rsi_harness.core.budget import BudgetMeter
from rsi_harness.core.llm import build_llm_client
from rsi_harness.core.runtime import run_workdir
from rsi_harness.core.types import Split
from rsi_harness.runner import run_orchestrator

BaselineId = Literal["b0", "b2", "b3"]


def _splits_for_eval() -> tuple[Split, ...]:
    return ("opt", "val")


def run_baseline(config: RunConfig, baseline: BaselineId) -> Path:
    if baseline == "b0":
        return evaluate_b0(config)
    return _run_loop_baseline(config, baseline)


def _run_loop_baseline(config: RunConfig, baseline: BaselineId) -> Path:
    state = run_orchestrator(config)
    workdir = run_workdir(config)
    cost: dict[str, object] = {}
    summary_path = workdir / "budget_summary.json"
    if summary_path.exists():
        cost = json.loads(summary_path.read_text())
    exclusions = {}
    adapter = load_adapter(config.benchmark)
    if hasattr(adapter, "session"):
        exclusions = adapter.session.exclusions.to_dict()

    report = {
        "baseline": baseline,
        "run_id": config.run_id,
        "finished": state.finished,
        "rounds": state.round_index,
        "finalist_harness_id": state.finalist_harness_id,
        "budget": cost,
        "tau2_exclusions": exclusions,
        "at": datetime.now(UTC).isoformat(),
    }
    path = workdir / f"baseline_{baseline}_summary.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    return path


def evaluate_b0(config: RunConfig) -> Path:
    """B0: default harness, no edits — score dev opt/val and log cost by role."""
    workdir = run_workdir(config)
    workdir.mkdir(parents=True, exist_ok=True)
    adapter = load_adapter(config.benchmark)
    if hasattr(adapter, "attach_workdir"):
        adapter.attach_workdir(workdir)

    meter = BudgetMeter(config.budget, checkpoint_path=workdir / "checkpoint_budget.json")
    llm = build_llm_client(
        config.llm,
        meter,
        workdir,
        config.models,
        cache_namespace="opt",
    )
    harness = adapter.default_harness()

    per_split: dict[str, dict[str, float | int]] = {}
    for split in _splits_for_eval():
        tasks = adapter.tasks(split)
        passed = 0
        total = 0
        for task in tasks:
            for seed in config.loop.seeds:
                result = adapter.run(task, harness, llm, seed)
                if not result.valid:
                    continue
                total += 1
                if result.passed:
                    passed += 1
        rate = (passed / total) if total else 0.0
        per_split[split] = {
            "tasks": len(tasks),
            "trials": total,
            "passed": passed,
            "pass_rate": rate,
        }

    snap = meter.snapshot()
    exclusions = {}
    if hasattr(adapter, "session"):
        exclusions = adapter.session.exclusions.to_dict()
        adapter.session.write_report()

    report = {
        "baseline": "b0",
        "run_id": config.run_id,
        "benchmark": config.benchmark.name,
        "harness_id": harness.id,
        "splits": per_split,
        "cost": {
            "dollars": snap.total_spent,
            "by_role": snap.by_role,
        },
        "tau2_exclusions": exclusions,
        "at": datetime.now(UTC).isoformat(),
    }
    path = workdir / "baseline_b0_report.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    return path
