"""P2 may copy skill tokens from traces, not task ids."""

import json
from types import SimpleNamespace

from rsi_harness.core.types import Diagnosis, FailureEntry, HarnessSpec
from rsi_harness.strategies.proposers.p2_reflective import (
    P2ReflectiveProposer,
    _edits_from_traces,
    _parse_edits_json,
)

TASK = (
    "[mms_issue]airplane_mode_on|break_app_sms_permission[PERSONA:Easy]"
)


def _diagnosis(*failures: FailureEntry) -> Diagnosis:
    return Diagnosis(
        summary="1 failures, 0 successes on opt batch",
        failures=list(failures),
        successes=[],
    )


def test_skill_token_becomes_a_playbook_bullet() -> None:
    diagnosis = _diagnosis(
        FailureEntry(
            task_id="t1",
            score=0.0,
            trace=[{"event": "diagnosis_hint", "missing_token": "TOK-A"}],
        )
    )
    edits = _edits_from_traces(diagnosis)
    assert len(edits) == 1
    assert edits[0].text == "TOK-A"
    assert edits[0].op == "add_bullet"
    assert "t1" not in (edits[0].bullet_id or "")


def test_non_harness_json_is_skipped() -> None:
    """The live proposer once returned edit_type/description objects and crashed."""
    payload = [
        {"edit_type": "add_test_case", "description": "Add a test."},
        {
            "artifact": "notes/playbook.json",
            "op": "add_bullet",
            "text": "Recheck the status bar after the user toggles airplane mode.",
            "bullet_id": "b2",
        },
    ]
    edits = _parse_edits_json("```json\n" + json.dumps(payload) + "\n```")
    assert len(edits) == 1
    assert edits[0].text.startswith("Recheck")


def test_failure_brief_includes_tools_not_task_id() -> None:
    from rsi_harness.strategies.proposers.p2_reflective import _failure_brief

    brief = _failure_brief(
        FailureEntry(
            task_id=TASK,
            score=0.0,
            trace=[
                {
                    "event": "tau2_live",
                    "task_id": TASK,
                    "termination": "TerminationReason.USER_STOP",
                    "tools": ["get_customer_by_phone", "check_status_bar"],
                    "tool_errors": ["Unknown tool: toggle_airplane_mode"],
                }
            ],
        )
    )
    assert "check_status_bar" in brief
    assert "toggle_airplane_mode" in brief
    assert TASK not in brief
    assert "[PERSONA:" not in brief


def test_task_id_hint_is_not_a_playbook_bullet() -> None:
    diagnosis = _diagnosis(
        FailureEntry(
            task_id=TASK,
            score=0.0,
            trace=[{"event": "diagnosis_hint", "missing_token": TASK}],
        )
    )
    assert _edits_from_traces(diagnosis) == []


def test_proposer_prompt_omits_task_id_and_drops_echoed_id() -> None:
    seen: dict[str, str] = {}

    class _LLM:
        def model_for_role(self, role: str) -> SimpleNamespace:
            return SimpleNamespace(name="mock", temperature=0.0)

        async def complete(self, req: object) -> SimpleNamespace:
            content = req.messages[0]["content"]  # type: ignore[attr-defined]
            seen["prompt"] = content
            payload = [
                {
                    "artifact": "notes/playbook.json",
                    "op": "add_bullet",
                    "text": TASK,
                    "bullet_id": "b1",
                },
                {
                    "artifact": "notes/playbook.json",
                    "op": "add_bullet",
                    "text": "Ask the user to toggle airplane mode, then recheck the status bar.",
                    "bullet_id": "b2",
                },
                {
                    "artifact": "system_prompt",
                    "op": "replace",
                    "text": "You are a generic phone assistant.",
                },
            ]
            return SimpleNamespace(content=json.dumps(payload))

    diagnosis = _diagnosis(
        FailureEntry(
            task_id=TASK,
            score=0.0,
            trace=[
                {
                    "event": "tau2_live",
                    "task_id": TASK,
                    "termination": "TerminationReason.USER_STOP",
                    "score": 0.0,
                }
            ],
        )
    )
    harness = HarnessSpec(id="h", artifacts={}, parent_id=None)
    edits = P2ReflectiveProposer(_LLM()).propose(harness, diagnosis, memory=_memory(), k=1)
    assert TASK not in seen["prompt"]
    assert "USER_STOP" in seen["prompt"]
    assert '"op":"add_bullet"' in seen["prompt"]
    assert "notes/playbook.json" in seen["prompt"]
    assert "Do not replace system_prompt" in seen["prompt"]
    assert "user_tools" in seen["prompt"]
    assert len(edits) == 1
    assert len(edits[0]) == 1
    assert "airplane mode" in edits[0][0].text
    assert TASK not in edits[0][0].text


def _memory():
    from rsi_harness.core.types import LineageMemory

    return LineageMemory()
