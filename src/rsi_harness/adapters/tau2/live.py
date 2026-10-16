"""Live τ² rollouts (optional tau2-bench install)."""

from __future__ import annotations

import re
from typing import Any

from rsi_harness.adapters.tau2.exclusions import invalid_reason_from_simulation
from rsi_harness.adapters.tau2.llm_bridge import (
    activate_bridge,
    deactivate_bridge,
    install_generate_patch,
    restore_generate_patch,
)
from rsi_harness.adapters.tau2.rsi_agent import set_active_harness
from rsi_harness.adapters.tau2.session import Tau2Session
from rsi_harness.adapters.tau2.tool_catalog import telecom_tool_surfaces
from rsi_harness.core.llm import LLMClient
from rsi_harness.core.types import Cost, HarnessSpec, RunResult, Task

_AGENT_NAME = "rsi_harness_llm_agent"
_registered = False
_PERSONA = re.compile(r"\[PERSONA:[^\]]+\]")


def _scrub(text: str, task_id: str) -> str:
    cleaned = text.replace(task_id, "")
    cleaned = _PERSONA.sub("", cleaned)
    return " ".join(cleaned.split())


def episode_outcome(sim: Any, *, task_id: str) -> dict[str, object]:
    """Tool names and error snippets. The task id is not included."""
    tools: list[str] = []
    errors: list[str] = []
    messages: list[Any] = []
    if sim is not None and hasattr(sim, "get_messages"):
        try:
            messages = list(sim.get_messages())
        except Exception:
            messages = list(getattr(sim, "messages", None) or [])
    for msg in messages:
        for call in getattr(msg, "tool_calls", None) or []:
            name = getattr(call, "name", None)
            if isinstance(name, str) and name and name not in tools:
                tools.append(name)
        if getattr(msg, "error", False):
            raw = getattr(msg, "content", None) or "tool error"
            snippet = _scrub(str(raw), task_id)[:160]
            if snippet and snippet not in errors:
                errors.append(snippet)
    return {"tools": tools[:12], "tool_errors": errors[:6]}


def _ensure_agent_registered() -> None:
    global _registered
    if _registered:
        return
    from tau2.registry import registry

    from rsi_harness.adapters.tau2.rsi_agent import build_rsi_llm_agent

    if registry.get_agent_factory(_AGENT_NAME) is None:
        registry.register_agent_factory(build_rsi_llm_agent, _AGENT_NAME)
    _registered = True


def run_live_task(
    task: Task,
    harness: HarnessSpec,
    llm: LLMClient,
    seed: int,
    *,
    domain: str,
    session: Tau2Session,
) -> RunResult:
    from tau2.data_model.simulation import TextRunConfig
    from tau2.data_model.tasks import Task as Tau2Task
    from tau2.evaluator.evaluator import EvaluationType
    from tau2.runner import run_single_task

    _ensure_agent_registered()
    tau2_task = Tau2Task.model_validate(task.payload)

    agent_model = llm.model_for_role("agent")
    user_model = llm.model_for_role("user_sim")
    config = TextRunConfig(
        domain=domain,
        agent=_AGENT_NAME,
        llm_agent=agent_model.name,
        llm_user=user_model.name,
        llm_args_agent={"temperature": agent_model.temperature},
        llm_args_user={"temperature": user_model.temperature},
        seed=seed,
    )

    spend_before = llm._meter.snapshot() if hasattr(llm, "_meter") else None
    set_active_harness(harness)
    activate_bridge(llm, seed=seed)
    patched_generate = install_generate_patch()
    invalid_reason: str | None = None
    sim: Any = None
    retried = False
    try:
        for attempt in range(2):
            try:
                sim = run_single_task(
                    config,
                    tau2_task,
                    seed=seed,
                    evaluation_type=EvaluationType.ALL,
                    save_dir=None,
                    verbose_logs=False,
                )
            except ValueError as exc:
                invalid_reason = f"simulation_error:{exc}"
                sim = None
                if attempt == 0:
                    retried = True
                    session.exclusions.record(invalid_reason, excluded=False, retried=True)
                    continue
                break
            invalid_reason = invalid_reason_from_simulation(sim)
            if invalid_reason is None:
                break
            if attempt == 0:
                retried = True
                session.exclusions.record(invalid_reason, excluded=False, retried=True)
        if invalid_reason is not None:
            session.exclusions.record(invalid_reason, excluded=True, retried=retried)
    finally:
        restore_generate_patch(patched_generate)
        deactivate_bridge()

    valid = invalid_reason is None
    score = 0.0
    passed = False
    reward_info = getattr(sim, "reward_info", None) if sim is not None else None
    if reward_info is not None:
        score = float(getattr(reward_info, "reward", 0.0) or 0.0)
        passed = score >= 1.0

    after = llm._meter.snapshot() if hasattr(llm, "_meter") else None
    before = spend_before
    by_role: dict[str, float] = {}
    dollars = 0.0
    if before is not None and after is not None:
        dollars = after.total_spent - before.total_spent
        for role, total in after.by_role.items():
            by_role[role] = total - before.by_role.get(role, 0.0)
    cost = Cost(
        prompt_tokens=0,
        completion_tokens=0,
        dollars=dollars,
        seconds=float(getattr(sim, "duration", 0.0) or 0.0) if sim else 0.0,
        by_role=by_role,
    )

    outcome = episode_outcome(sim, task_id=task.id)
    surfaces = telecom_tool_surfaces() if domain == "telecom" else {}
    trace: list[dict[str, object]] = [
        {
            "event": "tau2_live",
            "task_id": task.id,
            "valid": valid,
            "invalid_reason": invalid_reason,
            "score": score,
            "termination": str(getattr(sim, "termination_reason", "")),
            "tools": outcome["tools"],
            "tool_errors": outcome["tool_errors"],
            "agent_tools": surfaces.get("agent_tools", []),
            "user_tools": surfaces.get("user_tools", []),
        }
    ]
    return RunResult(
        task_id=task.id,
        harness_id=harness.id,
        seed=seed,
        score=score,
        passed=passed,
        valid=valid,
        trace=trace,
        cost=cost,
        error=invalid_reason,
    )
