"""Synthetic toy-bench adapter (zero API cost, harness-dependent scoring)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rsi_harness.adapters.toy_bench.agent import evaluate_task
from rsi_harness.core.harness import (
    ArtifactSurface,
    SurfaceDecl,
    make_harness_spec,
)
from rsi_harness.core.llm import LLMClient
from rsi_harness.core.playbook import empty_playbook
from rsi_harness.core.splits import SplitManifest, load_split_manifest
from rsi_harness.core.types import Cost, HarnessSpec, RunResult, Split, Task

PLAYBOOK_ARTIFACT = "notes/playbook.json"
SYSTEM_PROMPT_ARTIFACT = "system_prompt"


class ToyBenchAdapter:
    name = "toy_bench"
    version = "0.1.0"

    def __init__(self, manifest_path: Path) -> None:
        self._manifest_path = manifest_path
        self._manifest: SplitManifest = load_split_manifest(manifest_path)
        extra = self._manifest.extra or {}
        self._task_defs: dict[str, dict[str, Any]] = self._manifest.task_defs or {}
        if not self._task_defs:
            raise ValueError(f"toy manifest {manifest_path} missing task_defs")
        if "version" in extra:
            self.version = str(extra["version"])

    @classmethod
    def default_manifest(cls) -> Path:
        return Path(__file__).resolve().parents[4] / "data" / "splits" / "toy_bench.json"

    def tasks(self, split: Split) -> list[Task]:
        ids = self._manifest.splits.get(split, [])
        out: list[Task] = []
        for tid in ids:
            if tid not in self._task_defs:
                raise KeyError(f"unknown task id {tid} in split {split}")
            out.append(
                Task(
                    id=tid,
                    benchmark=self.name,
                    payload=dict(self._task_defs[tid]),
                )
            )
        return out

    def surface(self) -> SurfaceDecl:
        return SurfaceDecl(
            editable={
                SYSTEM_PROMPT_ARTIFACT: ArtifactSurface(
                    max_chars=4000,
                    description="Agent system prompt",
                    kind="text",
                ),
                PLAYBOOK_ARTIFACT: ArtifactSurface(
                    max_chars=8000,
                    description="Itemized guidance playbook",
                    kind="playbook",
                ),
            },
            protected=["toy_scorer", "required_token lookup"],
        )

    def default_harness(self) -> HarnessSpec:
        return make_harness_spec(
            {
                SYSTEM_PROMPT_ARTIFACT: (
                    "You are the toy-bench agent. Follow guidance in the playbook."
                ),
                PLAYBOOK_ARTIFACT: empty_playbook(),
            }
        )

    def run(self, task: Task, harness: HarnessSpec, llm: LLMClient, seed: int) -> RunResult:
        if task.benchmark != self.name:
            raise ValueError(f"task {task.id} is not for {self.name}")

        score, passed, trace = evaluate_task(task, harness)
        # Optional: one mock LLM ping so runs exercise the gateway without affecting score.
        _ = llm  # reserved for future stochastic toy mode
        cost = Cost(prompt_tokens=0, completion_tokens=0, dollars=0.0, seconds=0.0)

        return RunResult(
            task_id=task.id,
            harness_id=harness.id,
            seed=seed,
            score=score,
            passed=passed,
            valid=True,
            trace=trace,
            cost=cost,
        )
