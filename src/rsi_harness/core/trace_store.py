"""Trace persistence; split-isolated read paths (I3)."""

from __future__ import annotations

import json
import sqlite3
import time
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path

from rsi_harness.core.types import Cost, RunResult, Split

_OPTIMIZATION_SPLITS: frozenset[Split] = frozenset({"opt", "val"})
_SELECT_SPLITS: frozenset[Split] = frozenset({"select"})
_TEST_SPLITS: frozenset[Split] = frozenset({"test"})


class SplitAccessError(PermissionError):
    """Attempt to read a split through the wrong view."""


class TraceStore:
    """SQLite (WAL) + JSONL mirror for run results and traces."""

    def __init__(self, workdir: Path) -> None:
        self._workdir = workdir
        workdir.mkdir(parents=True, exist_ok=True)
        self._db_path = workdir / "traces.db"
        self._jsonl_path = workdir / "traces.jsonl"
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS run_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    split TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    harness_id TEXT NOT NULL,
                    seed INTEGER NOT NULL,
                    score REAL NOT NULL,
                    passed INTEGER NOT NULL,
                    valid INTEGER NOT NULL,
                    cost_json TEXT NOT NULL,
                    error TEXT,
                    trace_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_run_split ON run_results(split)"
            )
            conn.commit()

    def write_optimization(self, split: Split, result: RunResult) -> int:
        """Persist opt/val runs only (I3 write path)."""
        if split not in _OPTIMIZATION_SPLITS:
            raise SplitAccessError(
                f"optimization writer cannot persist split {split!r}; "
                "use write_select or write_test"
            )
        return self._write(split, result)

    def write_select(self, result: RunResult) -> int:
        return self._write("select", result)

    def write_test(self, result: RunResult) -> int:
        return self._write("test", result)

    def write(self, split: Split, result: RunResult) -> int:
        """Low-level write (tests). Prefer write_optimization / write_select / write_test."""
        return self._write(split, result)

    def _write(self, split: Split, result: RunResult) -> int:
        row = {
            "split": split,
            "task_id": result.task_id,
            "harness_id": result.harness_id,
            "seed": result.seed,
            "score": result.score,
            "passed": int(result.passed),
            "valid": int(result.valid),
            "cost_json": json.dumps(asdict(result.cost)),
            "error": result.error,
            "trace_json": json.dumps(result.trace),
            "created_at": time.time(),
        }
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO run_results (
                    split, task_id, harness_id, seed, score, passed, valid,
                    cost_json, error, trace_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["split"],
                    row["task_id"],
                    row["harness_id"],
                    row["seed"],
                    row["score"],
                    row["passed"],
                    row["valid"],
                    row["cost_json"],
                    row["error"],
                    row["trace_json"],
                    row["created_at"],
                ),
            )
            conn.commit()
            assert cur.lastrowid is not None
            row_id = int(cur.lastrowid)

        mirror = {**row, "id": row_id}
        with self._jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(mirror) + "\n")
        return row_id

    def _iter_splits(self, allowed: frozenset[Split]) -> Iterator[RunResult]:
        placeholders = ",".join("?" for _ in allowed)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM run_results WHERE split IN ({placeholders}) ORDER BY id",
                tuple(allowed),
            ).fetchall()
        for r in rows:
            cost_data = json.loads(r["cost_json"])
            yield RunResult(
                task_id=r["task_id"],
                harness_id=r["harness_id"],
                seed=r["seed"],
                score=r["score"],
                passed=bool(r["passed"]),
                valid=bool(r["valid"]),
                trace=json.loads(r["trace_json"]),
                cost=Cost(**cost_data),
                error=r["error"],
            )

    def optimization_view(self) -> OptimizationTraceView:
        return OptimizationTraceView(self)

    def select_view(self) -> SelectTraceView:
        return SelectTraceView(self)

    def test_view(self) -> TestTraceView:
        return TestTraceView(self)


class OptimizationTraceView:
    """Readable splits: opt, val — not select/test (I3)."""

    def __init__(self, store: TraceStore) -> None:
        self._store = store

    def list_results(self) -> list[RunResult]:
        return list(self._store._iter_splits(_OPTIMIZATION_SPLITS))

    def assert_split_allowed(self, split: Split) -> None:
        if split not in _OPTIMIZATION_SPLITS:
            raise SplitAccessError(f"split {split!r} not visible in optimization view")


class SelectTraceView:
    """Readable splits: select only (ChampionAudit)."""

    def __init__(self, store: TraceStore) -> None:
        self._store = store

    def list_results(self) -> list[RunResult]:
        return list(self._store._iter_splits(_SELECT_SPLITS))

    def assert_split_allowed(self, split: Split) -> None:
        if split not in _SELECT_SPLITS:
            raise SplitAccessError(f"split {split!r} not visible in select view")


class TestTraceView:
    """Readable splits: test only (Phase C reporter)."""

    def __init__(self, store: TraceStore) -> None:
        self._store = store

    def list_results(self) -> list[RunResult]:
        return list(self._store._iter_splits(_TEST_SPLITS))

    def assert_split_allowed(self, split: Split) -> None:
        if split not in _TEST_SPLITS:
            raise SplitAccessError(f"split {split!r} not visible in test view")
