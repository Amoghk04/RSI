"""Map HarnessSpec artifacts into τ² agent instructions (domain policy stays protected)."""

from __future__ import annotations

from rsi_harness.adapters.toy_bench.agent import harness_corpus
from rsi_harness.core.types import HarnessSpec

DEFAULT_AGENT_INSTRUCTION = """
You are a customer service agent that helps the user according to the <policy> provided below.
In each turn you can either:
- Send a message to the user.
- Make a tool call.
You cannot do both at the same time.

Try to be helpful and always follow the policy. Always make sure you generate valid JSON only.
""".strip()


def render_agent_instruction(harness: HarnessSpec) -> str:
    """Extra guidance appended to τ² instructions (S3: prompt + playbook)."""
    system = harness.artifacts.get("system_prompt", "").strip()
    playbook = harness.artifacts.get("notes/playbook.json", "[]")
    blocks = [DEFAULT_AGENT_INSTRUCTION]
    if system:
        blocks.append(f"<harness_system_prompt>\n{system}\n</harness_system_prompt>")
    if playbook and playbook.strip() not in ("[]", "{}"):
        blocks.append(f"<harness_playbook>\n{playbook}\n</harness_playbook>")
    return "\n\n".join(blocks)


def harness_corpus_text(harness: HarnessSpec) -> str:
    return harness_corpus(harness)
