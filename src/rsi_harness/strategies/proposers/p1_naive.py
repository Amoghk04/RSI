"""P1: single-shot system-prompt rewrite from failure summaries (naive baseline)."""

from __future__ import annotations

from rsi_harness.core.llm import LLMClient, LLMRequest
from rsi_harness.core.types import Diagnosis, Edit, HarnessSpec, LineageMemory

SYSTEM_PROMPT_ARTIFACT = "system_prompt"


class P1NaiveProposer:
    name = "p1_naive"

    def __init__(self, llm: LLMClient, *, max_edit_chars: int = 1200) -> None:
        self._llm = llm
        self._max_edit_chars = max_edit_chars

    def propose(
        self,
        current: HarnessSpec,
        diagnosis: Diagnosis,
        memory: LineageMemory,
        k: int,
    ) -> list[list[Edit]]:
        if not diagnosis.failures:
            return []

        summary = diagnosis.summary or "Failures on optimization batch."
        failure_lines = [
            f"- {f.task_id}: score={f.score}" for f in diagnosis.failures[:8]
        ]
        prompt = (
            "Rewrite the agent system prompt to address these failures. "
            f"Return ONLY the new prompt text (max {self._max_edit_chars} chars).\n"
            f"{summary}\n"
            + "\n".join(failure_lines)
        )
        model = self._llm.model_for_role("proposer")
        resp = self._llm.complete_sync(
            LLMRequest(
                role="proposer",
                model=model.name,
                messages=[{"role": "user", "content": prompt}],
                temperature=model.temperature,
                sample_index=0,
            )
        )
        text = resp.content.strip()[: self._max_edit_chars]
        if not text:
            text = current.artifacts.get(SYSTEM_PROMPT_ARTIFACT, "") + "\n" + summary
            text = text[: self._max_edit_chars]

        edits = [Edit(artifact=SYSTEM_PROMPT_ARTIFACT, op="replace", text=text)]
        return [edits][:k]
