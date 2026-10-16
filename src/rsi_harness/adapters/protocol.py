"""Benchmark adapter contract (YELLOW). Adapters may import core; core must not import adapters."""

from __future__ import annotations

from typing import Protocol

from rsi_harness.core.harness import SurfaceDecl
from rsi_harness.core.llm import LLMClient
from rsi_harness.core.types import HarnessSpec, RunResult, Split, Task


class BenchmarkAdapter(Protocol):
    name: str
    version: str

    def tasks(self, split: Split) -> list[Task]: ...

    def surface(self) -> SurfaceDecl: ...

    def default_harness(self) -> HarnessSpec: ...

    def run(self, task: Task, harness: HarnessSpec, llm: LLMClient, seed: int) -> RunResult: ...
