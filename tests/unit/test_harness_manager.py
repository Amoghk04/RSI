from pathlib import Path

import pytest

from rsi_harness.core.harness import (
    ArtifactSurface,
    EditBoundsError,
    EditLimits,
    HarnessLineageStore,
    HarnessManager,
    SurfaceDecl,
    SurfaceError,
    make_harness_spec,
    preview_edits,
)
from rsi_harness.core.leakage import LeakageError
from rsi_harness.core.playbook import empty_playbook, serialize_playbook
from rsi_harness.core.types import Bullet, Edit, HarnessSpec


def _toy_surface() -> SurfaceDecl:
    return SurfaceDecl(
        editable={
            "system_prompt": ArtifactSurface(max_chars=2000, kind="text"),
            "notes/playbook.json": ArtifactSurface(max_chars=4000, kind="playbook"),
        },
        protected=["scorer", "tool behavior"],
    )


def _root() -> tuple[HarnessManager, HarnessSpec]:
    artifacts = {
        "system_prompt": "You are a helpful agent.",
        "notes/playbook.json": empty_playbook(),
    }
    spec = make_harness_spec(artifacts)
    mgr = HarnessManager(_toy_surface())
    mgr.register(spec)
    return mgr, spec


def test_content_hash_stable() -> None:
    a = make_harness_spec({"system_prompt": "x", "notes/playbook.json": "[]"})
    b = make_harness_spec({"system_prompt": "x", "notes/playbook.json": "[]"})
    assert a.id == b.id


def test_i4_rejects_unknown_artifact() -> None:
    mgr, root = _root()
    with pytest.raises(SurfaceError, match="I4"):
        mgr.apply_edits(root, [Edit(artifact="hidden_policy", op="replace", text="x")])


def test_playbook_add_and_update() -> None:
    mgr, root = _root()
    v1 = mgr.apply_edits(
        root,
        [Edit(artifact="notes/playbook.json", op="add_bullet", bullet_id="b1", text="tip")],
    )
    bullets = v1.artifacts["notes/playbook.json"]
    assert "b1" in bullets
    v2 = mgr.apply_edits(
        v1,
        [
            Edit(
                artifact="notes/playbook.json",
                op="update_bullet",
                bullet_id="b1",
                text="better tip",
            )
        ],
    )
    assert "better tip" in v2.artifacts["notes/playbook.json"]
    assert v2.parent_id == v1.id


def test_i10_max_edit_chars() -> None:
    mgr = HarnessManager(_toy_surface(), limits=EditLimits(max_edit_chars=5))
    root = make_harness_spec(
        {
            "system_prompt": "You are a helpful agent.",
            "notes/playbook.json": empty_playbook(),
        }
    )
    with pytest.raises(EditBoundsError, match="edit too large"):
        mgr.apply_edits(
            root,
            [Edit(artifact="system_prompt", op="append", text="0123456789")],
        )


def test_i11_leakage_rejects_payload_literal() -> None:
    mgr, root = _root()
    secret = "ORDER-ID-SECRET-12345"
    payloads = [{"user": {"order_id": secret}}]
    with pytest.raises(LeakageError):
        mgr.apply_edits(
            root,
            [Edit(artifact="system_prompt", op="append", text=f" mention {secret}")],
            opt_payloads=payloads,
        )


def test_preview_does_not_persist(tmp_path: Path) -> None:
    store = HarnessLineageStore(tmp_path / "lineage")
    mgr, root = _root()
    mgr._store = store  # noqa: SLF001
    mgr.register(root)
    candidate = preview_edits(
        mgr,
        root,
        [Edit(artifact="system_prompt", op="append", text="!")],
    )
    assert candidate.id != root.id
    assert store.get(candidate.id) is None


def test_lineage_rollback_restores_exact_hash(tmp_path: Path) -> None:
    store = HarnessLineageStore(tmp_path / "lineage")
    mgr = HarnessManager(_toy_surface(), store=store)
    root = make_harness_spec(
        {"system_prompt": "base", "notes/playbook.json": empty_playbook()},
    )
    mgr.register(root)
    child = mgr.apply_edits(
        root,
        [Edit(artifact="system_prompt", op="replace", text="changed")],
    )
    rolled = mgr.rollback(root.id)
    assert rolled.id == root.id
    assert rolled.artifacts == root.artifacts
    assert child.parent_id == root.id
    assert store.ancestors(child.id)[0].id == child.id
    assert store.ancestors(child.id)[-1].id == root.id


def test_lineage_persists_and_reloads(tmp_path: Path) -> None:
    store = HarnessLineageStore(tmp_path / "lineage")
    mgr = HarnessManager(_toy_surface(), store=store)
    root = make_harness_spec(
        {"system_prompt": "v0", "notes/playbook.json": serialize_playbook([Bullet("b", "t")])},
    )
    mgr.register(root)
    store2 = HarnessLineageStore(tmp_path / "lineage")
    store2.load()
    loaded = store2.get(root.id)
    assert loaded is not None
    assert loaded.id == root.id


def test_noop_edit_rejected() -> None:
    mgr, root = _root()
    with pytest.raises(EditBoundsError, match="no-op"):
        mgr.apply_edits(root, [Edit(artifact="system_prompt", op="append", text="")])


def test_playbook_replace_blocked_by_default() -> None:
    mgr, root = _root()
    with pytest.raises(SurfaceError, match="allow_playbook_replace"):
        mgr.apply_edits(
            root,
            [Edit(artifact="notes/playbook.json", op="replace", text="[]")],
        )
