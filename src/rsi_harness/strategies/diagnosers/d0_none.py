from rsi_harness.core.types import Diagnosis, FailureEntry, RunResult


class D0Diagnoser:
    name = "d0_none"

    def diagnose(self, failures: list[RunResult], successes: list[RunResult]) -> Diagnosis:
        fail_entries = [
            FailureEntry(task_id=r.task_id, score=r.score, trace=r.trace) for r in failures
        ]
        ok_entries = [
            FailureEntry(task_id=r.task_id, score=r.score, trace=r.trace) for r in successes
        ]
        summary = f"{len(fail_entries)} failures, {len(ok_entries)} successes on opt batch"
        return Diagnosis(summary=summary, failures=fail_entries, successes=ok_entries)
