"""Run loop wiring (YELLOW): may import adapters; core stays benchmark-blind (I7)."""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import asdict
from typing import Any

from rsi_harness.adapters.registry import load_adapter
from rsi_harness.config import RunConfig
from rsi_harness.core.aa import calibrate_aa_sigma
from rsi_harness.core.audit import ChampionAuditor
from rsi_harness.core.budget import BudgetExceeded, BudgetMeter
from rsi_harness.core.harness import (
    EditBoundsError,
    EditLimits,
    HarnessLineageStore,
    HarnessManager,
    SurfaceError,
)
from rsi_harness.core.leakage import LeakageError
from rsi_harness.core.llm import LLMClient, build_llm_client
from rsi_harness.core.runtime import run_workdir
from rsi_harness.core.state import OrchestratorState, load_state, save_state
from rsi_harness.core.trace_store import TraceStore
from rsi_harness.core.types import Edit, HarnessSpec, LineageMemory, RunResult, Task
from rsi_harness.core.validator import Validator
from rsi_harness.strategies.registry import (
    build_diagnoser,
    build_gate,
    build_proposer,
    build_search,
    edit_limits_from_config,
)


def config_fingerprint(config: RunConfig) -> str:
    blob = config.model_dump_json()
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _edit_char_count(edits: list[Edit]) -> int:
    return sum(len(e.text) for e in edits)


def _count_guard_regressions(
    adapter: Any,
    llm: LLMClient,
    candidate: HarnessSpec,
    guard_ids: set[str],
    val_task_index: dict[str, Task],
    seeds: list[int],
) -> int:
    regressions = 0
    for tid in guard_ids:
        task = val_task_index.get(tid)
        if task is None:
            continue
        failed = False
        for seed in seeds:
            result = adapter.run(task, candidate, llm, seed)
            if not result.passed:
                failed = True
                break
        if failed:
            regressions += 1
    return regressions


class Orchestrator:
    def __init__(self, config: RunConfig) -> None:
        self.config = config
        self.workdir = run_workdir(config)
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.adapter = load_adapter(config.benchmark)
        if hasattr(self.adapter, "attach_workdir"):
            self.adapter.attach_workdir(self.workdir)
        self.lineage = HarnessLineageStore(self.workdir / "harness")
        self.lineage.load()

        max_art, max_chars, max_bullets = edit_limits_from_config(config)
        self.manager = HarnessManager(
            self.adapter.surface(),
            limits=EditLimits(
                max_artifacts_touched=max_art,
                max_edit_chars=max_chars,
                max_bullets_touched=max_bullets,
            ),
            store=self.lineage,
            leakage_min_literal_len=int(
                config.strategies.leakage_linter.min_literal_len
                if config.strategies.leakage_linter
                else 12
            ),
        )

        self.meter = BudgetMeter(
            config.budget,
            checkpoint_path=self.workdir / "checkpoint_budget.json",
        )
        self.llm = build_llm_client(
            config.llm,
            self.meter,
            self.workdir,
            config.models,
            cache_namespace="opt",
        )
        self.traces = TraceStore(self.workdir / "traces")
        self.rng = random.Random(config.seed)
        self.memory = LineageMemory()

        self.diagnoser = build_diagnoser(config.strategies.diagnoser)
        self.proposer = build_proposer(config.strategies.proposer, self.llm)
        self.search = build_search(config.strategies.search)
        self.validator = Validator(self.adapter, self.llm, self.rng)

        self._val_tasks = self.adapter.tasks("val")
        self._val_index = {t.id: t for t in self._val_tasks}
        self._opt_tasks = self.adapter.tasks("opt")

        self.state = self._load_or_init_state()
        self.gate = build_gate(
            config.strategies.gate,
            guard_task_ids=set(self.state.guard_task_ids),
        )
        self.auditor = ChampionAuditor(self.adapter, self.lineage, self.llm)

    def _load_or_init_state(self) -> OrchestratorState:
        fp = config_fingerprint(self.config)
        existing = load_state(self.workdir)
        if existing is not None:
            if existing.config_fingerprint != fp:
                raise ValueError("checkpoint config fingerprint mismatch; refuse to resume")
            return existing

        harness = self.adapter.default_harness()
        self.manager.register(harness)
        rng_state = {"version": 3, "state": self.rng.getstate()}
        state = OrchestratorState(
            run_id=self.config.run_id,
            config_fingerprint=fp,
            round_index=0,
            current_harness_id=harness.id,
            patience_remaining=self.config.loop.patience,
        )
        state.rng_state = _serialize_rng(rng_state)
        save_state(self.workdir, state)
        return state

    def current_harness(self) -> HarnessSpec:
        spec = self.lineage.get(self.state.current_harness_id)
        if spec is None:
            raise KeyError(f"missing harness {self.state.current_harness_id}")
        return spec

    def run(self, *, max_rounds: int | None = None) -> OrchestratorState:
        if self.state.finished:
            return self.state

        if self.state.rng_state:
            _restore_rng(self.rng, self.state.rng_state)

        if self.state.aa_sigma == 0.0 and self.config.strategies.gate.name == "g7_aa_guard":
            self.state.aa_sigma = self._calibrate_aa()

        rounds_to_run = self.config.loop.rounds
        if max_rounds is not None:
            rounds_to_run = min(rounds_to_run, self.state.round_index + max_rounds)

        while self.state.round_index < rounds_to_run:
            if self.state.patience_remaining <= 0:
                break
            try:
                self._run_round()
            except BudgetExceeded:
                break
            self.state.round_index += 1
            self.state.rng_state = _serialize_rng({"version": 3, "state": self.rng.getstate()})
            save_state(self.workdir, self.state)

        natural_end = (
            self.state.round_index >= self.config.loop.rounds
            or self.state.patience_remaining <= 0
        )
        if not self.state.finished and natural_end:
            self._finalize()
        if hasattr(self.adapter, "session"):
            self.adapter.session.write_report()
        self._write_budget_summary()
        return self.state

    def _write_budget_summary(self) -> None:
        path = self.workdir / "budget_summary.json"
        path.write_text(json.dumps(self.meter.snapshot().to_dict(), indent=2) + "\n")

    def _calibrate_aa(self) -> float:
        seeds = self.config.loop.seeds
        if not seeds:
            return 0.0
        tasks = self._val_tasks[: self.config.loop.val_tasks_per_round]
        if not tasks:
            return 0.0
        seed_a = seeds[0]
        seed_b = seeds[1] if len(seeds) > 1 else seeds[0]
        return calibrate_aa_sigma(
            self.adapter,
            self.current_harness(),
            self.llm,
            tasks,
            seed_a,
            seed_b,
        )

    def _run_round(self) -> None:
        self.meter.begin_round()
        current = self.current_harness()
        batch = self._sample_opt_batch()

        results: list[RunResult] = []
        for task in batch:
            for seed in self.config.loop.seeds:
                result = self.adapter.run(task, current, self.llm, seed)
                self.traces.write_optimization("opt", result)
                results.append(result)

        failures = [r for r in results if not r.passed and r.valid]
        successes = [r for r in results if r.passed and r.valid]
        self.memory.last_opt_results = results

        diagnosis = self.diagnoser.diagnose(failures, successes)
        candidates = self.proposer.propose(
            current,
            diagnosis,
            self.memory,
            self.config.loop.candidates_per_round,
        )

        accepted_specs: list[HarnessSpec] = []
        for edit_list in candidates:
            if not edit_list:
                continue
            self.meter.begin_candidate()
            try:
                candidate = self.manager.apply_edits(
                    current,
                    edit_list,
                    opt_payloads=None,
                    check_leakage=False,
                )
            except (SurfaceError, EditBoundsError, LeakageError, ValueError) as exc:
                self.memory.rejected_edits.append(
                    {"edits": edit_list, "reason": f"apply_failed:{exc}"}
                )
                self.meter.end_candidate()
                continue

            guard_regs = _count_guard_regressions(
                self.adapter,
                self.llm,
                candidate,
                set(self.state.guard_task_ids),
                self._val_index,
                self.config.loop.seeds,
            )
            evidence = self.validator.compare(
                current,
                candidate,
                self._val_tasks,
                self.config.loop.seeds,
                max_tasks=self.config.loop.val_tasks_per_round,
                aa_sigma=self.state.aa_sigma,
                edit_chars=_edit_char_count(edit_list),
                guard_regressions=guard_regs,
            )
            decision = self.gate.decide(current, candidate, evidence)
            self._log_candidate(decision.accept, decision.reason)

            if decision.accept:
                accepted_specs.append(candidate)
                self._append_evidence(current, candidate, edit_list, evidence, decision)
                self.state.accepted_harness_ids.append(candidate.id)
                self.state.current_harness_id = candidate.id
                self._refresh_guard_set(candidate)
                self.state.rounds_without_accept = 0
            else:
                self.memory.rejected_edits.append(
                    {"edits": [asdict(e) for e in edit_list], "reason": decision.reason}
                )
            self.meter.end_candidate()

        self.meter.end_round()
        if accepted_specs:
            chosen = self.search.select(current, accepted_specs)
            self.state.current_harness_id = chosen.id
            self.state.patience_remaining = self.config.loop.patience
        else:
            self.state.rounds_without_accept += 1
            self.state.patience_remaining -= 1

        self.gate = build_gate(
            self.config.strategies.gate,
            guard_task_ids=set(self.state.guard_task_ids),
        )

    def _sample_opt_batch(self) -> list[Task]:
        pool = list(self._opt_tasks)
        self.rng.shuffle(pool)
        n = min(self.config.loop.opt_batch, len(pool))
        return pool[:n]

    def _refresh_guard_set(self, harness: HarnessSpec) -> None:
        tasks = self._val_tasks
        if not self.config.loop.champion_audit:
            tasks = tasks[: self.config.loop.val_tasks_per_round]
        passing: list[str] = []
        for task in tasks:
            seed = self.config.loop.seeds[0]
            result = self.adapter.run(task, harness, self.llm, seed)
            if result.passed:
                passing.append(task.id)
        merged = set(self.state.guard_task_ids) | set(passing)
        self.state.guard_task_ids = sorted(merged)

    def _finalize(self) -> None:
        current = self.current_harness()
        if not self.config.loop.champion_audit:
            self.state.finalist_harness_id = current.id
            self.state.finished = True
            save_state(self.workdir, self.state)
            return
        top_k = self.config.loop.champion_top_k
        ids = self.state.accepted_harness_ids[-top_k:] or [current.id]
        candidates: list[HarnessSpec] = []
        for hid in ids:
            spec = self.lineage.get(hid)
            if spec:
                candidates.append(spec)
        finalist = self.auditor.pick_finalist(candidates or [current])
        self.state.finalist_harness_id = finalist.id
        self.state.current_harness_id = finalist.id
        self.state.finished = True
        save_state(self.workdir, self.state)

    def _log_candidate(self, accept: bool, reason: str) -> None:
        path = self.workdir / "candidates.jsonl"
        record = {"round": self.state.round_index, "accept": accept, "reason": reason}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def _append_evidence(
        self,
        parent: HarnessSpec,
        candidate: HarnessSpec,
        edits: list[Edit],
        evidence: Any,
        decision: Any,
    ) -> None:
        path = self.workdir / "evidence.jsonl"
        package = {
            "version_id": candidate.id,
            "parent_id": parent.id,
            "diff": [asdict(e) for e in edits],
            "validation": {
                "task_ids": evidence.task_ids,
                "seeds": evidence.seeds,
                "mean_delta": evidence.estimated_full_val_delta,
                "guard_regressions": evidence.guard_regressions,
            },
            "gate": asdict(decision),
        }
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(package) + "\n")


def _serialize_rng(data: dict[str, Any]) -> dict[str, Any]:
    version, state = data["version"], data["state"]
    return {
        "version": version,
        "state": [state[0], list(state[1]), state[2]],
    }


def _restore_rng(rng: random.Random, payload: dict[str, Any]) -> None:
    triple = payload["state"]
    rng.setstate((triple[0], tuple(triple[1]), triple[2]))


def run_orchestrator(config: RunConfig, *, max_rounds: int | None = None) -> OrchestratorState:
    return Orchestrator(config).run(max_rounds=max_rounds)
