"""Adapter factory (imported by CLI/orchestrator only — not from core)."""

from __future__ import annotations

from pathlib import Path

from rsi_harness.adapters.protocol import BenchmarkAdapter
from rsi_harness.adapters.tau2 import Tau2Adapter
from rsi_harness.adapters.toy_bench import ToyBenchAdapter
from rsi_harness.config import BenchmarkConfig


def load_adapter(benchmark: BenchmarkConfig) -> BenchmarkAdapter:
    name = benchmark.name
    if name == "toy_bench":
        manifest = benchmark.splits_manifest
        path = Path(manifest) if manifest else ToyBenchAdapter.default_manifest()
        return ToyBenchAdapter(path)
    if name == "tau2":
        return Tau2Adapter.from_benchmark_config(benchmark)
    raise ValueError(f"unknown benchmark adapter: {name}")
