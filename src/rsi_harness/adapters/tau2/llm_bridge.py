"""Route τ² LiteLLM calls through RSI LLMClient (I5 metering + cost by role)."""

from __future__ import annotations

import importlib
import logging
import uuid
from contextvars import ContextVar
from typing import Any

from rsi_harness.core.llm import LLMClient, LLMRequest

logger = logging.getLogger(__name__)

_client_ctx: ContextVar[LLMClient | None] = ContextVar("rsi_tau2_llm_client", default=None)
_seed_ctx: ContextVar[int] = ContextVar("rsi_tau2_seed", default=0)
_sample_ctx: ContextVar[int] = ContextVar("rsi_tau2_sample", default=0)

# τ² binds `generate` at import time in these modules (not only llm_utils).
# Text (half-duplex) paths only — do NOT import user_simulator_streaming (voice → pyaudio).
_GENERATE_PATCH_MODULES: tuple[str, ...] = (
    "tau2.utils.llm_utils",
    "tau2.user.user_simulator",
    "tau2.agent.llm_agent",
    "tau2.evaluator.evaluator_nl_assertions",
    "tau2.evaluator.auth_classifier",
    "tau2.environment.utils.interface_agent",
)

_EMPTY_AGENT_FALLBACK = "Let me check that for you."


def activate_bridge(client: LLMClient, *, seed: int) -> None:
    _client_ctx.set(client)
    _seed_ctx.set(seed)
    _sample_ctx.set(0)


def deactivate_bridge() -> None:
    _client_ctx.set(None)


def _role_from_call_name(call_name: str | None) -> str:
    if not call_name:
        return "agent"
    lowered = call_name.lower()
    if "user" in lowered:
        return "user_sim"
    return "agent"


def _assistant_from_response(resp: Any) -> Any:
    from tau2.data_model.message import AssistantMessage, ToolCall

    tau2_tool_calls: list[ToolCall] | None = None
    if resp.tool_calls:
        tau2_tool_calls = []
        for tc in resp.tool_calls:
            name = str(tc.get("name", "")).strip()
            if not name:
                continue
            tc_id = tc.get("id") or str(uuid.uuid4())
            tau2_tool_calls.append(
                ToolCall(
                    id=str(tc_id),
                    name=name,
                    arguments=dict(tc.get("arguments") or {}),
                )
            )
    if not tau2_tool_calls:
        tau2_tool_calls = None

    text = (resp.content or "").strip()
    content: str | None = text if text else None

    msg = AssistantMessage(role="assistant", content=content, tool_calls=tau2_tool_calls)
    try:
        msg.validate()
    except ValueError:
        return None
    return msg


def bridged_generate(
    model: str,
    messages: list[Any],
    tools: Any = None,
    tool_choice: Any = None,
    call_name: str | None = None,
    **kwargs: Any,
) -> Any:
    """Replacement for tau2.utils.llm_utils.generate."""
    from tau2.data_model.message import AssistantMessage
    from tau2.utils.llm_utils import to_litellm_messages

    client = _client_ctx.get()
    if client is None:
        raise RuntimeError("tau2 LLM bridge not active")

    role = _role_from_call_name(call_name)
    model_cfg = client.model_for_role(role)  # type: ignore[arg-type]
    openai_messages = to_litellm_messages(messages)
    tools_schema: tuple[dict[str, Any], ...] | None = None
    if tools:
        tools_schema = tuple(t.openai_schema for t in tools)
    resolved_tool_choice = tool_choice
    if tools_schema and resolved_tool_choice is None:
        resolved_tool_choice = "auto"

    for attempt in range(3):
        sample = _sample_ctx.get()
        _sample_ctx.set(sample + 1)

        resp = client.complete_sync(
            LLMRequest(
                role=role,  # type: ignore[arg-type]
                model=model_cfg.name,
                messages=openai_messages,
                temperature=model_cfg.temperature,
                sample_index=sample + attempt,
                max_tokens=kwargs.get("max_tokens"),
                tools=tools_schema,
                tool_choice=resolved_tool_choice,
            )
        )
        built = _assistant_from_response(resp)
        if built is not None:
            return built
        logger.warning(
            "tau2 bridge empty LLM response role=%s call=%s attempt=%s tools=%s",
            role,
            call_name,
            attempt,
            bool(tools_schema),
        )

    # Last resort so τ² does not crash mid-simulation (counts as weak agent turn).
    fallback = _EMPTY_AGENT_FALLBACK if tools_schema else "How can I help you today?"
    return AssistantMessage(role="assistant", content=fallback)


def install_generate_patch() -> dict[str, Any]:
    originals: dict[str, Any] = {}
    for mod_name in _GENERATE_PATCH_MODULES:
        mod = importlib.import_module(mod_name)
        if hasattr(mod, "generate"):
            originals[mod_name] = mod.generate
            mod.generate = bridged_generate
    return originals


def restore_generate_patch(originals: dict[str, Any]) -> None:
    for mod_name, original in originals.items():
        mod = importlib.import_module(mod_name)
        mod.generate = original
