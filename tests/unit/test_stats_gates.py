from rsi_harness.core.stats import bootstrap_ci_lower, paired_deltas
from rsi_harness.core.types import Cost, HarnessSpec, PairedEvidence
from rsi_harness.strategies.gates.g7_aa_guard import G7AAGuardGate


def _evidence(current: list[float], candidate: list[float]) -> PairedEvidence:
    return PairedEvidence(
        task_ids=["t1"],
        seeds=[0],
        current_scores=current,
        candidate_scores=candidate,
        inclusion_probs=None,
        estimated_full_val_delta=None,
        guard_regressions=0,
        edit_chars=10,
        aa_sigma=0.0,
        cost=Cost(0, 0, 0.0, 0.0),
    )


def test_g7_accepts_clear_improvement() -> None:
    gate = G7AAGuardGate(guard_task_ids=set())
    current = HarnessSpec(id="h1", parent_id=None, artifacts={})
    candidate = HarnessSpec(id="h2", parent_id="h1", artifacts={})
    decision = gate.decide(current, candidate, _evidence([0.0, 0.0], [1.0, 1.0]))
    assert decision.accept


def test_bootstrap_ci_positive() -> None:
    deltas = paired_deltas([0, 0], [1, 1])
    mean_d, lo = bootstrap_ci_lower(deltas, n_boot=200, seed=1)
    assert mean_d == 1.0
    assert lo > 0
