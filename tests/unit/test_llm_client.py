import asyncio
from pathlib import Path

import pytest

from rsi_harness.config import BudgetConfig, LLMProviderConfig, ModelRoleConfig
from rsi_harness.core.budget import BudgetExceeded, BudgetMeter
from rsi_harness.core.llm import LLMCache, LLMClient, LLMRequest


def _client(tmp_path: Path, total: float = 1.0) -> tuple[LLMClient, BudgetMeter]:
    meter = BudgetMeter(
        BudgetConfig(total_dollars=total, per_round_dollars=total, per_candidate_dollars=total),
        checkpoint_path=tmp_path / "ckpt.json",
    )
    client = LLMClient(
        provider=LLMProviderConfig(provider="mock"),
        meter=meter,
        cache=LLMCache(tmp_path / "cache.db"),
        cache_namespace="opt",
        role_models={"agent": ModelRoleConfig(name="mock", temperature=0.0)},
        call_log_path=tmp_path / "calls.jsonl",
    )
    return client, meter


def _req(sample_index: int = 0) -> LLMRequest:
    return LLMRequest(
        role="agent",
        model="mock",
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.0,
        sample_index=sample_index,
    )


def test_cache_replay_costs_zero(tmp_path: Path) -> None:
    client, meter = _client(tmp_path)
    first = asyncio.run(client.complete(_req()))
    second = asyncio.run(client.complete(_req()))
    assert not first.cached
    assert first.dollars > 0
    assert second.cached
    assert second.dollars == 0.0
    assert meter.snapshot().total_spent == first.dollars


def test_sample_index_changes_cache_key(tmp_path: Path) -> None:
    client, meter = _client(tmp_path)
    r0 = asyncio.run(client.complete(_req(0)))
    r1 = asyncio.run(client.complete(_req(1)))
    assert not r0.cached and not r1.cached
    assert r0.content != r1.content
    assert meter.snapshot().total_spent == r0.dollars + r1.dollars


def test_budget_cap_on_uncached_calls(tmp_path: Path) -> None:
    client, meter = _client(tmp_path, total=0.000001)
    with pytest.raises(BudgetExceeded):
        asyncio.run(client.complete(_req(0)))
        asyncio.run(client.complete(_req(1)))


def test_disjoint_cache_namespaces(tmp_path: Path) -> None:
    meter = BudgetMeter(
        BudgetConfig(total_dollars=1.0, per_round_dollars=1.0, per_candidate_dollars=1.0),
    )
    cache = LLMCache(tmp_path / "cache.db")
    opt_client = LLMClient(
        provider=LLMProviderConfig(provider="mock"),
        meter=meter,
        cache=cache,
        cache_namespace="opt",
    )
    test_client = LLMClient(
        provider=LLMProviderConfig(provider="mock"),
        meter=meter,
        cache=cache,
        cache_namespace="test",
    )
    asyncio.run(opt_client.complete(_req()))
    hit = asyncio.run(opt_client.complete(_req()))
    miss = asyncio.run(test_client.complete(_req()))
    assert hit.cached
    assert not miss.cached


async def _concurrent_hits(client: LLMClient, n: int) -> list[bool]:
    tasks = [client.complete(_req()) for _ in range(n)]
    results = await asyncio.gather(*tasks)
    return [r.cached for r in results]


def test_concurrent_cache_populates_once(tmp_path: Path) -> None:
    client, meter = _client(tmp_path)
    cached_flags = asyncio.run(_concurrent_hits(client, 8))
    assert cached_flags.count(False) == 1
    assert cached_flags.count(True) == 7
    assert meter.snapshot().total_spent > 0
