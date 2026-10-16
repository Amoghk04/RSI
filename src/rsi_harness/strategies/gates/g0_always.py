from rsi_harness.core.types import Decision, HarnessSpec, PairedEvidence


class G0AlwaysGate:
    """Naive baseline: accept every candidate (B2)."""

    name = "g0_always"

    def decide(
        self,
        current: HarnessSpec,
        candidate: HarnessSpec,
        evidence: PairedEvidence,
    ) -> Decision:
        return Decision(self.name, True, "accept_all")
