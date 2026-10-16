"""Wire budget meter, LLM client, and trace store for a run."""

from __future__ import annotations

from pathlib import Path

from rsi_harness.config import RunConfig
from rsi_harness.core.budget import BudgetMeter
from rsi_harness.core.llm import CacheNamespace, LLMClient, build_llm_client
from rsi_harness.core.trace_store import TraceStore


def run_workdir(config: RunConfig) -> Path:
    return config.workdir / config.run_id


def bootstrap_runtime(
    config: RunConfig,
    *,
    cache_namespace: CacheNamespace = "opt",
) -> tuple[BudgetMeter, LLMClient, TraceStore]:
    wd = run_workdir(config)
    meter = BudgetMeter(config.budget, checkpoint_path=wd / "checkpoint_budget.json")
    client = build_llm_client(
        config.llm,
        meter,
        wd,
        config.models,
        cache_namespace=cache_namespace,
    )
    store = TraceStore(wd / "traces")
    return meter, client, store
