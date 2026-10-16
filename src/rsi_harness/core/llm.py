"""Single metered LLM client (I5). All production LLM calls go through here."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast
from urllib import error, request

from rsi_harness.config import LLMProviderConfig, ModelRoleConfig
from rsi_harness.core.budget import BudgetMeter

logger = logging.getLogger(__name__)

Role = Literal["agent", "user_sim", "proposer", "other"]
CacheNamespace = Literal["opt", "val", "select", "test"]


@dataclass(frozen=True)
class LLMRequest:
    role: Role
    model: str
    messages: list[dict[str, Any]]
    temperature: float
    sample_index: int
    max_tokens: int | None = None
    tools: tuple[dict[str, Any], ...] | None = None
    tool_choice: str | None = None


@dataclass(frozen=True)
class LLMResponse:
    content: str
    prompt_tokens: int
    completion_tokens: int
    dollars: float
    cached: bool
    latency_seconds: float
    tool_calls: list[dict[str, Any]] | None = None


_CACHE_SCHEMA_VERSION = 2


def _normalize_chat_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                if part.get("type") == "text":
                    parts.append(str(part.get("text", "")))
                elif "text" in part:
                    parts.append(str(part["text"]))
            else:
                parts.append(str(part))
        return "".join(parts)
    return str(content)


def _parse_openrouter_tool_calls(message: dict[str, Any]) -> list[dict[str, Any]] | None:
    raw_tools = message.get("tool_calls") or []
    if not raw_tools:
        return None
    parsed: list[dict[str, Any]] = []
    for tc in raw_tools:
        func = tc.get("function") or {}
        name = str(func.get("name") or tc.get("name") or "").strip()
        if not name:
            continue
        args_raw = func.get("arguments") or tc.get("arguments") or "{}"
        if isinstance(args_raw, str):
            try:
                arguments = json.loads(args_raw) if args_raw else {}
            except json.JSONDecodeError:
                arguments = {}
        elif isinstance(args_raw, dict):
            arguments = args_raw
        else:
            arguments = {}
        parsed.append(
            {
                "id": str(tc.get("id") or ""),
                "name": name,
                "arguments": arguments,
            }
        )
    return parsed or None


def _cache_key(req: LLMRequest) -> str:
    payload = {
        "schema_version": _CACHE_SCHEMA_VERSION,
        "model": req.model,
        "messages": req.messages,
        "temperature": req.temperature,
        "max_tokens": req.max_tokens,
        "sample_index": req.sample_index,
        "tools": req.tools,
        "tool_choice": req.tool_choice,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Rough $/token defaults when the provider does not return cost."""
    # Prototype estimates; override via env RSI_HARNESS_PRICE_PER_1M_PROMPT etc. later.
    if model == "mock" or model.startswith("mock/"):
        return (prompt_tokens + completion_tokens) * 1e-6
    low_cost = ("flash", "mini", "haiku", "8b", "gpt-oss")
    name = model.lower()
    if any(x in name for x in low_cost):
        prompt_m = 0.15
        completion_m = 0.60
    else:
        prompt_m = 1.0
        completion_m = 3.0
    return (prompt_tokens * prompt_m + completion_tokens * completion_m) / 1_000_000


class LLMCache:
    """Disk cache (SQLite WAL) keyed by namespace + request hash."""

    def __init__(self, db_path: Path) -> None:
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_cache (
                    namespace TEXT NOT NULL,
                    cache_key TEXT NOT NULL,
                    response_json TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    PRIMARY KEY (namespace, cache_key)
                )
                """
            )
            conn.commit()

    def get(self, namespace: str, cache_key: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT response_json FROM llm_cache WHERE namespace=? AND cache_key=?",
                (namespace, cache_key),
            ).fetchone()
        if row is None:
            return None
        return cast(dict[str, Any], json.loads(row[0]))

    def put(self, namespace: str, cache_key: str, response: dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO llm_cache (namespace, cache_key, response_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (namespace, cache_key, json.dumps(response), time.time()),
            )
            conn.commit()


class LLMClient:
    """
    Metered gateway with disk cache (I5).

    Cache namespaces MUST stay disjoint across opt/val/select/test (I3 cache isolation).
    """

    def __init__(
        self,
        provider: LLMProviderConfig,
        meter: BudgetMeter,
        *,
        cache: LLMCache,
        cache_namespace: CacheNamespace = "opt",
        role_models: dict[str, ModelRoleConfig] | None = None,
        call_log_path: Path | None = None,
        max_concurrent: int = 4,
        api_key: str | None = None,
    ) -> None:
        self._provider = provider
        self._meter = meter
        self._cache = cache
        self._namespace = cache_namespace
        self._role_models = role_models or {}
        self._call_log_path = call_log_path
        self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self._sem = asyncio.Semaphore(max_concurrent)
        self._miss_lock = asyncio.Lock()

    @property
    def cache_namespace(self) -> str:
        return self._namespace

    def model_for_role(self, role: Role) -> ModelRoleConfig:
        if role in self._role_models:
            return self._role_models[role]
        if "agent" in self._role_models:
            return self._role_models["agent"]
        return ModelRoleConfig(name="mock", temperature=0.0)

    async def complete(self, req: LLMRequest) -> LLMResponse:
        key = _cache_key(req)
        cached = self._cache.get(self._namespace, key)
        if cached is not None:
            return self._from_cached(cached, req, key)

        async with self._miss_lock:
            cached = self._cache.get(self._namespace, key)
            if cached is not None:
                return self._from_cached(cached, req, key)

            async with self._sem:
                start = time.perf_counter()
                if self._provider.provider == "mock":
                    body = self._mock_complete(req)
                elif self._provider.provider == "openrouter":
                    body = await asyncio.to_thread(self._openrouter_complete, req)
                else:
                    raise ValueError(f"unknown provider: {self._provider.provider}")

                latency = time.perf_counter() - start
                dollars = body["dollars"]
                self._meter.charge(dollars, req.role)

                self._cache.put(self._namespace, key, body)
                resp = LLMResponse(
                    content=body.get("content") or "",
                    prompt_tokens=body["prompt_tokens"],
                    completion_tokens=body["completion_tokens"],
                    dollars=dollars,
                    cached=False,
                    latency_seconds=latency,
                    tool_calls=body.get("tool_calls"),
                )
                self._log_call(req, resp, cache_key=key)
                return resp

    def _from_cached(self, cached: dict[str, Any], req: LLMRequest, key: str) -> LLMResponse:
        resp = LLMResponse(
            content=cached.get("content") or "",
            prompt_tokens=cached["prompt_tokens"],
            completion_tokens=cached["completion_tokens"],
            dollars=0.0,
            cached=True,
            latency_seconds=0.0,
            tool_calls=cached.get("tool_calls"),
        )
        self._log_call(req, resp, cache_key=key)
        return resp

    def complete_sync(self, req: LLMRequest) -> LLMResponse:
        return asyncio.run(self.complete(req))

    def _mock_complete(self, req: LLMRequest) -> dict[str, Any]:
        digest = hashlib.sha256(_cache_key(req).encode()).hexdigest()[:16]
        content = f"mock:{digest}"
        prompt_tokens = sum(len(str(m.get("content", ""))) for m in req.messages) // 4 + 1
        completion_tokens = 8 + (req.sample_index % 3)
        dollars = _estimate_cost(req.model, prompt_tokens, completion_tokens)
        return {
            "content": content,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "dollars": dollars,
        }

    def _openrouter_complete(self, req: LLMRequest) -> dict[str, Any]:
        if not self._api_key:
            raise RuntimeError("OPENROUTER_API_KEY is required for provider=openrouter")

        payload: dict[str, Any] = {
            "model": req.model,
            "messages": req.messages,
            "temperature": req.temperature,
        }
        if req.max_tokens is not None:
            payload["max_tokens"] = req.max_tokens
        if req.tools:
            payload["tools"] = list(req.tools)
            payload["tool_choice"] = req.tool_choice or "auto"
        elif req.tool_choice is not None:
            payload["tool_choice"] = req.tool_choice

        data = json.dumps(payload).encode()
        url = self._provider.base_url.rstrip("/") + "/chat/completions"
        http_req = request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(http_req, timeout=120) as resp:
                raw = json.loads(resp.read().decode())
        except error.HTTPError as e:
            detail = e.read().decode() if e.fp else str(e)
            raise RuntimeError(f"OpenRouter HTTP {e.code}: {detail}") from e

        message = raw["choices"][0]["message"]
        content = _normalize_chat_content(message.get("content"))
        tool_calls = _parse_openrouter_tool_calls(message)
        usage = raw.get("usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        dollars = _estimate_cost(req.model, prompt_tokens, completion_tokens)
        return {
            "content": content,
            "tool_calls": tool_calls,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "dollars": dollars,
        }

    def _log_call(self, req: LLMRequest, resp: LLMResponse, cache_key: str) -> None:
        if self._call_log_path is None:
            return
        self._call_log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": time.time(),
            "namespace": self._namespace,
            "cache_key": cache_key,
            "role": req.role,
            "model": req.model,
            "sample_index": req.sample_index,
            "cached": resp.cached,
            "dollars": resp.dollars,
            "prompt_tokens": resp.prompt_tokens,
            "completion_tokens": resp.completion_tokens,
        }
        line = json.dumps(record) + "\n"
        # Append is not atomic across processes; orchestrator should serialize per run.
        with self._call_log_path.open("a", encoding="utf-8") as f:
            f.write(line)


def build_llm_client(
    provider: LLMProviderConfig,
    meter: BudgetMeter,
    workdir: Path,
    role_models: dict[str, ModelRoleConfig],
    cache_namespace: CacheNamespace = "opt",
) -> LLMClient:
    cache_path = workdir / "cache" / "llm_cache.db"
    log_path = workdir / "logs" / "llm_calls.jsonl"
    return LLMClient(
        provider=provider,
        meter=meter,
        cache=LLMCache(cache_path),
        cache_namespace=cache_namespace,
        role_models=role_models,
        call_log_path=log_path,
    )
