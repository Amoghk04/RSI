"""Benchmark-facing protocols (core must not import adapters — I7)."""

from __future__ import annotations

from typing import Protocol

from rsi_harness.core.harness import SurfaceDecl
from rsi_harness.core.llm import LLMClient
from rsi_harness.core.types import HarnessSpec, RunResult, Split, Task


class BenchmarkPort(Protocol):
    name: str
    version: str

    def tasks(self, split: Split) -> list[Task]: ...

    def surface(self) -> SurfaceDecl: ...

    def default_harness(self) -> HarnessSpec: ...

    def run(self, task: Task, harness: HarnessSpec, llm: LLMClient, seed: int) -> RunResult: ...
