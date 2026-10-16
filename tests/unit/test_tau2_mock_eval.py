from rsi_harness.adapters.tau2.adapter import Tau2Adapter
from rsi_harness.adapters.tau2.mock_eval import evaluate_mock_task
from rsi_harness.core.harness import make_harness_spec
from rsi_harness.core.types import Task


def test_mock_eval_passes_when_literal_in_playbook() -> None:
    harness = make_harness_spec(
        {
            "system_prompt": "base",
            "notes/playbook.json": (
                '[{"id":"b1","text":"Important Meeting","useful":0,"harmful":0}]'
            ),
        }
    )
    task = Task(
        id="create_task_1",
        benchmark="tau2",
        payload={
            "evaluation_criteria": {
                "actions": [{"arguments": {"title": "Important Meeting"}}],
            }
        },
    )
    score, passed, _ = evaluate_mock_task(task, harness)
    assert passed
    assert score == 1.0


def test_tau2_mock_adapter_loads_manifest() -> None:
    adapter = Tau2Adapter.from_benchmark_config(
        {
            "name": "tau2",
            "domain": "mock",
            "splits_manifest": "data/splits/tau2_mock.json",
        }
    )
    assert len(adapter.tasks("opt")) == 2
