"""Live episode summaries name tools and errors, not the task id."""

from types import SimpleNamespace

from rsi_harness.adapters.tau2.live import episode_outcome

TASK = "[mms_issue]airplane_mode_on[PERSONA:Easy]"


def test_episode_outcome_lists_tools_and_scrubs_task_id() -> None:
    sim = SimpleNamespace(
        get_messages=lambda: [
            SimpleNamespace(
                tool_calls=[SimpleNamespace(name="get_customer_by_phone")],
                error=False,
            ),
            SimpleNamespace(
                tool_calls=None,
                error=True,
                content=f"failed on {TASK}",
            ),
        ]
    )
    outcome = episode_outcome(sim, task_id=TASK)
    assert outcome["tools"] == ["get_customer_by_phone"]
    assert outcome["tool_errors"] == ["failed on"]
    assert TASK not in str(outcome)
    assert "PERSONA" not in str(outcome)
