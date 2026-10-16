from rsi_harness.core.stats import mean, paired_deltas
from rsi_harness.core.types import Decision, HarnessSpec, PairedEvidence


class G1GreedyGate:
    name = "g1_greedy"

    def __init__(self, margin: float = 0.0) -> None:
        self._margin = margin

    def decide(
        self,
        current: HarnessSpec,
        candidate: HarnessSpec,
        evidence: PairedEvidence,
    ) -> Decision:
        deltas = paired_deltas(evidence.current_scores, evidence.candidate_scores)
        delta = mean(deltas)
        if delta > self._margin:
            return Decision(self.name, True, f"mean_delta={delta:.4f} > margin={self._margin}")
        return Decision(self.name, False, f"mean_delta={delta:.4f} <= margin={self._margin}")
