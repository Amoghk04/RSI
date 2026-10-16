"""I11: literal overlap with opt payloads must be rejected."""

import pytest

from rsi_harness.core.harness import ArtifactSurface, HarnessManager, SurfaceDecl, make_harness_spec
from rsi_harness.core.leakage import LeakageError, find_leaked_literals, literals_from_payloads
from rsi_harness.core.playbook import empty_playbook
from rsi_harness.core.types import Edit


def test_literals_from_nested_payload() -> None:
    payloads = [{"a": {"b": "short"}, "c": "long-enough-string"}]
    lits = literals_from_payloads(payloads, min_literal_len=12)
    assert lits == {"long-enough-string"}


def test_find_leaked_literals_in_artifact() -> None:
    spec = make_harness_spec(
        {"system_prompt": "use long-enough-string here", "notes/playbook.json": empty_playbook()}
    )
    hits = find_leaked_literals(
        spec.artifacts,
        [{"x": "long-enough-string"}],
        min_literal_len=12,
    )
    assert hits == [("system_prompt", "long-enough-string")]


def test_manager_enforces_i11_on_apply() -> None:
    surface = SurfaceDecl(
        editable={
            "system_prompt": ArtifactSurface(max_chars=2000, kind="text"),
            "notes/playbook.json": ArtifactSurface(max_chars=2000, kind="playbook"),
        },
        protected=[],
    )
    mgr = HarnessManager(surface, leakage_min_literal_len=10)
    root = make_harness_spec(
        {"system_prompt": "ok", "notes/playbook.json": empty_playbook()},
    )
    lit = "CUSTOMER_NAME_XYZ"
    with pytest.raises(LeakageError):
        mgr.apply_edits(
            root,
            [Edit(artifact="system_prompt", op="replace", text=lit)],
            opt_payloads=[{"customer": lit}],
        )
