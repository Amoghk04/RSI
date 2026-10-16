"""I4: edits outside declared surface must be rejected."""

import pytest

from rsi_harness.core.harness import (
    ArtifactSurface,
    HarnessManager,
    SurfaceDecl,
    SurfaceError,
    make_harness_spec,
)
from rsi_harness.core.playbook import empty_playbook
from rsi_harness.core.types import Edit


def test_manager_rejects_protected_artifact_name() -> None:
    surface = SurfaceDecl(
        editable={"system_prompt": ArtifactSurface(max_chars=500, kind="text")},
        protected=["domain_policy"],
    )
    mgr = HarnessManager(surface)
    root = make_harness_spec({"system_prompt": "hi"})
    with pytest.raises(SurfaceError):
        mgr.apply_edits(
            root,
            [Edit(artifact="domain_policy", op="replace", text="leak")],
        )


def test_register_rejects_extra_artifacts() -> None:
    surface = SurfaceDecl(
        editable={"system_prompt": ArtifactSurface(max_chars=500, kind="text")},
        protected=[],
    )
    mgr = HarnessManager(surface)
    bad = make_harness_spec({"system_prompt": "hi", "notes/playbook.json": empty_playbook()})
    with pytest.raises(SurfaceError):
        mgr.register(bad)
