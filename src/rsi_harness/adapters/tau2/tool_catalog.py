"""Names of τ² telecom tools, split into agent tools and user-device tools."""

from __future__ import annotations

from functools import lru_cache


def _marked_tool_names(cls: type) -> list[str]:
    found: list[str] = []
    for klass in cls.__mro__:
        for name, obj in vars(klass).items():
            if name.startswith("_"):
                continue
            if getattr(obj, "__tool__", False) and name not in found:
                found.append(name)
    return found


@lru_cache(maxsize=1)
def telecom_tool_surfaces() -> dict[str, list[str]]:
    """Agent tools are callable by the assistant. User tools are phone actions."""
    from tau2.domains.telecom.tools import TelecomTools
    from tau2.domains.telecom.user_tools import TelecomUserTools

    return {
        "agent_tools": _marked_tool_names(TelecomTools),
        "user_tools": _marked_tool_names(TelecomUserTools),
    }
