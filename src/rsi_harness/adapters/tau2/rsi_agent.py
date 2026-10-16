"""RSI harness-aware τ² LLM agent (editable instructions only; domain policy unchanged)."""

from __future__ import annotations

from contextvars import ContextVar

from rsi_harness.adapters.tau2.prompt import render_agent_instruction
from rsi_harness.core.types import HarnessSpec

_harness_ctx: ContextVar[HarnessSpec | None] = ContextVar("rsi_tau2_harness", default=None)


def set_active_harness(harness: HarnessSpec) -> None:
    _harness_ctx.set(harness)


def get_active_harness() -> HarnessSpec:
    harness = _harness_ctx.get()
    if harness is None:
        raise RuntimeError("tau2 RSI agent: harness context not set")
    return harness


def build_rsi_llm_agent(tools, domain_policy: str, **kwargs):  # type: ignore[no-untyped-def]
    from tau2.agent.llm_agent import SYSTEM_PROMPT, LLMAgent

    harness = get_active_harness()
    instruction = render_agent_instruction(harness)

    class _RSIHarnessAgent(LLMAgent):
        @property
        def system_prompt(self) -> str:
            return SYSTEM_PROMPT.format(
                domain_policy=domain_policy,
                agent_instruction=instruction,
            )

    return _RSIHarnessAgent(
        tools=tools,
        domain_policy=domain_policy,
        llm=kwargs.get("llm"),
        llm_args=kwargs.get("llm_args"),
    )
