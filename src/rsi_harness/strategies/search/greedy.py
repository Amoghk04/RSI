from rsi_harness.core.types import HarnessSpec


class GreedySearchPolicy:
    name = "greedy"

    def select(
        self,
        current: HarnessSpec,
        accepted: list[HarnessSpec],
    ) -> HarnessSpec:
        if not accepted:
            return current
        return accepted[-1]
