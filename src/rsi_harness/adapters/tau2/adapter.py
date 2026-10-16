"""τ²-bench adapter (telecom dev + mock domain for CI)."""

from __future__ import annotations

import os
from pathlib import Path

from rsi_harness.adapters.tau2.mock_eval import evaluate_mock_task
from rsi_harness.adapters.tau2.prompt import render_agent_instruction
from rsi_harness.adapters.tau2.session import Tau2Session
from rsi_harness.adapters.tau2.tasks import load_task_payloads
from rsi_harness.core.harness import (
    ArtifactSurface,
    SurfaceDecl,
    make_harness_spec,
)
from rsi_harness.core.llm import LLMClient
from rsi_harness.core.playbook import empty_playbook
from rsi_harness.core.splits import SplitManifest, load_split_manifest
from rsi_harness.core.types import Cost, HarnessSpec, RunResult, Split, Task

SYSTEM_PROMPT_ARTIFACT = "system_prompt"
PLAYBOOK_ARTIFACT = "notes/playbook.json"


class Tau2Adapter:
    name = "tau2"
    version = "0.1.0"

    def __init__(
        self,
        manifest_path: Path,
        *,
        domain: str,
        tau2_root: Path | None,
        session: Tau2Session | None = None,
        use_live: bool = False,
    ) -> None:
        self._manifest_path = manifest_path
        self._manifest: SplitManifest = load_split_manifest(manifest_path)
        self._domain = domain
        self._tau2_root = tau2_root
        self._session = session or Tau2Session(domain=domain, tau2_root=tau2_root)
        self._session.use_live = use_live
        self._payloads = load_task_payloads(self._manifest, tau2_root=tau2_root)
        extra = self._manifest.extra or {}
        if "version" in extra:
            self.version = str(extra["version"])

    @classmethod
    def from_benchmark_config(cls, benchmark: object) -> Tau2Adapter:
        from rsi_harness.config import BenchmarkConfig

        if isinstance(benchmark, BenchmarkConfig):
            cfg = benchmark
        else:
            cfg = BenchmarkConfig.model_validate(benchmark)
        manifest = cfg.splits_manifest
        path = Path(manifest) if manifest else cls.default_manifest(cfg.domain or "telecom")
        domain = cfg.domain or "telecom"
        root = cls._resolve_tau2_root(cfg.tau2_root)
        use_live = bool(getattr(cfg, "use_live_tau2", False))
        return cls(path, domain=domain, tau2_root=root, use_live=use_live)

    @staticmethod
    def _resolve_tau2_root(configured: str | None) -> Path | None:
        if configured:
            return Path(configured)
        env = os.environ.get("TAU2_BENCH_ROOT")
        return Path(env) if env else None

    @classmethod
    def default_manifest(cls, domain: str = "telecom") -> Path:
        repo = Path(__file__).resolve().parents[4]
        if domain == "mock":
            return repo / "data" / "splits" / "tau2_mock.json"
        return repo / "data" / "splits" / "tau2_telecom.json"

    @property
    def session(self) -> Tau2Session:
        return self._session

    def attach_workdir(self, workdir: Path) -> None:
        self._session.workdir = workdir

    def tasks(self, split: Split) -> list[Task]:
        ids = self._manifest.splits.get(split, [])
        out: list[Task] = []
        for tid in ids:
            payload = self._payloads.get(tid)
            if payload is None:
                raise KeyError(f"unknown task id {tid}")
            out.append(Task(id=tid, benchmark=self.name, payload=payload))
        return out

    def surface(self) -> SurfaceDecl:
        return SurfaceDecl(
            editable={
                SYSTEM_PROMPT_ARTIFACT: ArtifactSurface(
                    max_chars=12_000,
                    description="Agent harness system prompt (prepended to τ² instructions)",
                    kind="text",
                ),
                PLAYBOOK_ARTIFACT: ArtifactSurface(
                    max_chars=16_000,
                    description="Itemized guidance playbook",
                    kind="playbook",
                ),
            },
            protected=["tau2_domain_policy", "tau2_tools", "tau2_scorer"],
        )

    def default_harness(self) -> HarnessSpec:
        return make_harness_spec(
            {
                SYSTEM_PROMPT_ARTIFACT: (
                    "You are the customer-service agent. Follow domain policy. "
                    "Call only the carrier tools you were given, one at a time, and do not "
                    "speak in the same turn. Device actions (airplane mode, SIM, mobile data, "
                    "Wi-Fi, VPN, APN, apps) belong to the user: ask the user to perform them. "
                    "Do not call those names yourself. Apply playbook guidance when relevant."
                ),
                PLAYBOOK_ARTIFACT: empty_playbook(),
            }
        )

    def run(self, task: Task, harness: HarnessSpec, llm: LLMClient, seed: int) -> RunResult:
        if task.benchmark != self.name:
            raise ValueError(f"task {task.id} is not for {self.name}")

        provider = llm._provider.provider  # noqa: SLF001 — adapter boundary
        use_mock_rollout = provider == "mock" and not self._session.use_live
        if not use_mock_rollout:
            from rsi_harness.adapters.tau2.live import run_live_task

            return run_live_task(
                task,
                harness,
                llm,
                seed,
                domain=self._domain,
                session=self._session,
            )

        score, passed, trace = evaluate_mock_task(task, harness)
        _ = render_agent_instruction(harness)
        cost = Cost(0, 0, 0.0, 0.0)
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
