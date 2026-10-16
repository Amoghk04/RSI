"""P2: targeted small edits from failure traces (reflective; mock-LLM fallback)."""

from __future__ import annotations

import json
import re
from typing import Literal, cast

from rsi_harness.core.llm import LLMClient, LLMRequest
from rsi_harness.core.types import Diagnosis, Edit, FailureEntry, HarnessSpec, LineageMemory

PLAYBOOK_ARTIFACT = "notes/playbook.json"
_EDIT_EXAMPLE = (
    '[{"artifact":"notes/playbook.json","op":"add_bullet","bullet_id":"airplane-mode",'
    '"text":"If the status bar shows Airplane Mode, ask the user to turn it off and '
    'confirm the bar before trying other fixes."}]'
)

EditOp = Literal[
    "replace",
    "append",
    "insert",
    "delete",
    "add_bullet",
    "update_bullet",
    "remove_bullet",
]


def _is_task_identity(token: str, task_id: str) -> bool:
    """True when the hint is the task id, not a skill token.

    Toy and mock hints are short execution feedback (for example ``TOK-A``).
    A τ² task id is a compositional label and must not be copied into the playbook.
    """
    if token == task_id or (task_id and task_id in token):
        return True
    return "[PERSONA:" in token


def _edits_from_traces(diagnosis: Diagnosis) -> list[Edit]:
    edits: list[Edit] = []
    seen_tokens: set[str] = set()
    for failure in diagnosis.failures:
        for entry in failure.trace:
            if entry.get("event") != "diagnosis_hint":
                continue
            token = entry.get("missing_token")
            if not isinstance(token, str) or not token.strip():
                continue
            token = token.strip()
            if _is_task_identity(token, failure.task_id) or token in seen_tokens:
                continue
            seen_tokens.add(token)
            edits.append(
                Edit(
                    artifact=PLAYBOOK_ARTIFACT,
                    op="add_bullet",
                    bullet_id=f"fix-{len(edits) + 1}",
                    text=token,
                )
            )
    return edits


def _failure_brief(entry: FailureEntry) -> str:
    """Outcome text for the proposer. Task ids stay out of the prompt."""
    parts = [f"score={entry.score}"]
    for event in entry.trace:
        if event.get("event") == "diagnosis_hint":
            continue
        termination = event.get("termination")
        if isinstance(termination, str) and termination:
            parts.append(f"termination={termination}")
        reason = event.get("invalid_reason")
        if isinstance(reason, str) and reason:
            parts.append(f"invalid_reason={reason}")
        tools = event.get("tools")
        if isinstance(tools, list) and tools:
            names = [str(name) for name in tools if isinstance(name, str)]
            if names:
                parts.append("tools=" + ",".join(names))
        tool_errors = event.get("tool_errors")
        if isinstance(tool_errors, list) and tool_errors:
            snippets = [str(item) for item in tool_errors if isinstance(item, str) and item]
            if snippets:
                parts.append("errors=" + " | ".join(snippets))
        for key in ("agent_tools", "user_tools"):
            names = event.get(key)
            if isinstance(names, list) and names:
                shown = [str(name) for name in names if isinstance(name, str)]
                if shown:
                    parts.append(f"{key}=" + ",".join(shown))
    return "; ".join(parts)


def _drop_task_identity_edits(edits: list[Edit], diagnosis: Diagnosis) -> list[Edit]:
    task_ids = {failure.task_id for failure in diagnosis.failures}
    kept: list[Edit] = []
    for edit in edits:
        if edit.text in task_ids or "[PERSONA:" in edit.text:
            continue
        if any(len(task_id) >= 12 and task_id in edit.text for task_id in task_ids):
            continue
        kept.append(edit)
    return kept


class P2ReflectiveProposer:
    name = "p2_reflective"

    def __init__(
        self,
        llm: LLMClient,
        *,
        max_edit_chars: int = 800,
        max_bullets_touched: int = 3,
    ) -> None:
        self._llm = llm
        self._max_edit_chars = max_edit_chars
        self._max_bullets_touched = max_bullets_touched

    def propose(
        self,
        current: HarnessSpec,
        diagnosis: Diagnosis,
        memory: LineageMemory,
        k: int,
    ) -> list[list[Edit]]:
        heuristic = _edits_from_traces(diagnosis)
        if heuristic:
            return [heuristic[: self._max_bullets_touched]][:k]

        briefs = [_failure_brief(failure) for failure in diagnosis.failures]
        prompt = (
            "Return ONLY a JSON list of playbook bullets. No markdown.\n"
            "Each object must use these keys:\n"
            '- "artifact": "notes/playbook.json"\n'
            '- "op": "add_bullet"\n'
            '- "text": one concrete step based on the tool errors\n'
            '- "bullet_id": a short id\n'
            "Do not replace system_prompt. Do not copy task names or ids.\n"
            "agent_tools are the only tools the assistant may call. "
            "user_tools are phone actions: ask the user to perform them. "
            "Never tell the assistant to call a user_tool itself.\n"
            f"Max {self._max_bullets_touched} edits, {self._max_edit_chars} chars.\n"
            f"Example: {_EDIT_EXAMPLE}\n"
            f"{diagnosis.summary}\n"
            f"outcomes={json.dumps(briefs)}"
        )
        model = self._llm.model_for_role("proposer")
        try:
            import asyncio

            resp = asyncio.run(
                self._llm.complete(
                    LLMRequest(
                        role="proposer",
                        model=model.name,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=model.temperature,
                        sample_index=len(memory.rejected_edits),
                    )
                )
            )
            parsed = [
                edit
                for edit in _drop_task_identity_edits(_parse_edits_json(resp.content), diagnosis)
                if edit.artifact == PLAYBOOK_ARTIFACT and edit.op == "add_bullet"
            ]
            if parsed:
                return [parsed[: self._max_bullets_touched]][:k]
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        return []


_EDIT_OPS = {
    "replace",
    "append",
    "insert",
    "delete",
    "add_bullet",
    "update_bullet",
    "remove_bullet",
}


def _parse_edits_json(text: str) -> list[Edit]:
    """Parse a JSON list of edits. Items that are not harness edits are skipped."""
    if not isinstance(text, str) or not text.strip():
        return []
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    raw = json.loads(match.group())
    if not isinstance(raw, list):
        return []
    edits: list[Edit] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        artifact = item.get("artifact")
        text_value = item.get("text")
        if not isinstance(artifact, str) or not artifact:
            continue
        if not isinstance(text_value, str):
            continue
        op_raw = str(item.get("op", "append"))
        if op_raw not in _EDIT_OPS:
            continue
        bullet_id = item.get("bullet_id")
        anchor = item.get("anchor")
        edits.append(
            Edit(
                artifact=artifact,
                op=cast(EditOp, op_raw),
                text=text_value,
                bullet_id=bullet_id if isinstance(bullet_id, str) else None,
                anchor=anchor if isinstance(anchor, str) else None,
            )
        )
    return edits
