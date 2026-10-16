from rsi_harness.adapters.toy_bench.agent import evaluate_task, harness_corpus
from rsi_harness.core.harness import make_harness_spec
from rsi_harness.core.playbook import empty_playbook, serialize_playbook
from rsi_harness.core.types import Bullet, Task


def test_pass_when_token_in_playbook() -> None:
    harness = make_harness_spec(
        {
            "system_prompt": "base",
            "notes/playbook.json": serialize_playbook([Bullet(id="b1", text="TOK-A")]),
        }
    )
    task = Task(id="t1", benchmark="toy_bench", payload={"required_token": "TOK-A"})
    score, passed, _ = evaluate_task(task, harness)
    assert passed and score == 1.0


def test_fail_when_token_missing() -> None:
    harness = make_harness_spec(
        {"system_prompt": "base", "notes/playbook.json": empty_playbook()},
    )
    task = Task(id="t1", benchmark="toy_bench", payload={"required_token": "TOK-A"})
    score, passed, trace = evaluate_task(task, harness)
    assert not passed and score == 0.0
    assert any(e.get("event") == "diagnosis_hint" for e in trace)


def test_corpus_includes_system_prompt() -> None:
    harness = make_harness_spec(
        {"system_prompt": "contains TOK-Z", "notes/playbook.json": empty_playbook()},
    )
    task = Task(id="t1", benchmark="toy_bench", payload={"required_token": "TOK-Z"})
    _, passed, _ = evaluate_task(task, harness)
    assert passed
    assert "TOK-Z" in harness_corpus(harness)
