"""Per-run τ² session state (exclusions, optional live bridge)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rsi_harness.adapters.tau2.exclusions import ExclusionStats


@dataclass
class Tau2Session:
    domain: str
    tau2_root: Path | None
    workdir: Path | None = None
    exclusions: ExclusionStats = field(default_factory=ExclusionStats)
    use_live: bool = False

    def write_report(self) -> Path | None:
        if self.workdir is None:
            return None
        path = self.workdir / "tau2_exclusions.json"
        path.write_text(
            __import__("json").dumps(
                {"domain": self.domain, "exclusions": self.exclusions.to_dict()},
                indent=2,
            )
            + "\n"
        )
        return path

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "tau2_root": str(self.tau2_root) if self.tau2_root else None,
            "use_live": self.use_live,
            "exclusions": self.exclusions.to_dict(),
        }
