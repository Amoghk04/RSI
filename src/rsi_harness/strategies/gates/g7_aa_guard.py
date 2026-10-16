from rsi_harness.core.stats import bootstrap_ci_lower, paired_deltas
from rsi_harness.core.types import Decision, HarnessSpec, PairedEvidence


class G7AAGuardGate:
    name = "g7_aa_guard"

    def __init__(
        self,
        *,
        alpha: float = 0.05,
        guard_tolerance: float = 0.05,
        k_sigma: float = 1.0,
        guard_task_ids: set[str],
    ) -> None:
        self._alpha = alpha
        self._guard_tolerance = guard_tolerance
        self._k_sigma = k_sigma
        self._guard_task_ids = guard_task_ids

    def decide(
        self,
        current: HarnessSpec,
        candidate: HarnessSpec,
        evidence: PairedEvidence,
    ) -> Decision:
        deltas = paired_deltas(evidence.current_scores, evidence.candidate_scores)
        if not deltas:
            return Decision(self.name, False, "no valid paired val scores")

        delta_mean, ci_low = bootstrap_ci_lower(deltas, alpha=self._alpha)
        sigma = evidence.aa_sigma or 0.0
        threshold = self._k_sigma * sigma

        guard_regs = evidence.guard_regressions
        if self._guard_task_ids:
            rate = guard_regs / len(self._guard_task_ids)
            if rate > self._guard_tolerance:
                return Decision(
                    self.name,
                    False,
                    f"guard regressions {guard_regs}/{len(self._guard_task_ids)}",
                )

        if ci_low <= 0:
            return Decision(self.name, False, f"bootstrap ci_low={ci_low:.4f} <= 0")
        if delta_mean <= threshold:
            return Decision(
                self.name,
                False,
                f"delta_mean={delta_mean:.4f} <= k*sigma={threshold:.4f}",
            )
        return Decision(
            self.name,
            True,
            f"ci_low={ci_low:.4f}, delta={delta_mean:.4f}, guard_ok",
        )
