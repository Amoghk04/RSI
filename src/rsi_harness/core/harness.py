"""HarnessSpec lineage, edit application, I4/I10 enforcement (M2)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from rsi_harness.core.leakage import assert_no_leakage
from rsi_harness.core.playbook import PlaybookError, parse_playbook, serialize_playbook
from rsi_harness.core.types import Bullet, Edit, HarnessSpec

ArtifactKind = Literal["text", "playbook"]


class SurfaceError(ValueError):
    """I4: edit targets a non-editable artifact or violates surface rules."""


class EditBoundsError(ValueError):
    """I10: too many artifacts, characters, or bullets touched."""


@dataclass(frozen=True)
class ArtifactSurface:
    max_chars: int
    description: str = ""
    kind: ArtifactKind = "text"


@dataclass(frozen=True)
class SurfaceDecl:
    editable: dict[str, ArtifactSurface]
    protected: list[str]


@dataclass(frozen=True)
class EditLimits:
    max_artifacts_touched: int = 3
    max_edit_chars: int = 800
    max_bullets_touched: int = 3
    allow_playbook_replace: bool = False


def make_harness_spec(
    artifacts: dict[str, str],
    parent_id: str | None = None,
) -> HarnessSpec:
    return HarnessSpec(
        id=harness_content_id(artifacts),
        parent_id=parent_id,
        artifacts=dict(artifacts),
    )


def harness_content_id(artifacts: dict[str, str]) -> str:
    blob = json.dumps(artifacts, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(blob.encode()).hexdigest()
    return f"h_{digest[:32]}"


def _char_delta_text(before: str, after: str) -> int:
    return abs(len(after) - len(before))


class HarnessLineageStore:
    """Persist content-addressed specs; parent links form a DAG."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)
        self._by_id: dict[str, HarnessSpec] = {}

    def load(self) -> None:
        self._by_id.clear()
        for path in self._root.glob("*.json"):
            spec = _spec_from_json(json.loads(path.read_text()))
            self._by_id[spec.id] = spec

    def save(self, spec: HarnessSpec) -> None:
        if spec.id in self._by_id and self._by_id[spec.id] != spec:
            raise ValueError(f"harness id collision with different content: {spec.id}")
        self._by_id[spec.id] = spec
        path = self._root / f"{spec.id}.json"
        path.write_text(json.dumps(_spec_to_json(spec), indent=2) + "\n")

    def get(self, harness_id: str) -> HarnessSpec | None:
        return self._by_id.get(harness_id)

    def ancestors(self, harness_id: str) -> list[HarnessSpec]:
        chain: list[HarnessSpec] = []
        current = self.get(harness_id)
        while current is not None:
            chain.append(current)
            if current.parent_id is None:
                break
            current = self.get(current.parent_id)
        return chain


def _spec_to_json(spec: HarnessSpec) -> dict[str, Any]:
    return {
        "id": spec.id,
        "parent_id": spec.parent_id,
        "artifacts": spec.artifacts,
    }


def _spec_from_json(data: dict[str, Any]) -> HarnessSpec:
    artifacts = data["artifacts"]
    if not isinstance(artifacts, dict):
        raise ValueError("artifacts must be a mapping")
    spec = HarnessSpec(
        id=data["id"],
        parent_id=data.get("parent_id"),
        artifacts={str(k): str(v) for k, v in artifacts.items()},
    )
    expected = harness_content_id(spec.artifacts)
    if spec.id != expected:
        raise ValueError(f"harness id {spec.id} does not match content hash {expected}")
    return spec


class HarnessManager:
    """
    Applies typed edits, enforces surface (I4) and bounds (I10), optional leakage (I11).

    Playbook artifacts use JSON bullet lists; text artifacts use string ops.
    """

    def __init__(
        self,
        surface: SurfaceDecl,
        limits: EditLimits | None = None,
        store: HarnessLineageStore | None = None,
        *,
        leakage_min_literal_len: int = 12,
    ) -> None:
        self._surface = surface
        self._limits = limits or EditLimits()
        self._store = store
        self._leakage_min = leakage_min_literal_len

    @property
    def surface(self) -> SurfaceDecl:
        return self._surface

    def register(self, spec: HarnessSpec) -> None:
        self._validate_artifacts_on_surface(spec.artifacts)
        if self._store:
            self._store.save(spec)

    def rollback(self, harness_id: str) -> HarnessSpec:
        if self._store is None:
            raise RuntimeError("lineage store required for rollback")
        spec = self._store.get(harness_id)
        if spec is None:
            raise KeyError(f"unknown harness id: {harness_id}")
        return spec

    def apply_edits(
        self,
        current: HarnessSpec,
        edits: list[Edit],
        *,
        opt_payloads: list[dict[str, Any]] | None = None,
        check_leakage: bool = True,
        persist: bool = True,
    ) -> HarnessSpec:
        if not edits:
            raise EditBoundsError("at least one edit required")

        self._validate_edit_bounds(current, edits)
        artifacts = dict(current.artifacts)

        for edit in edits:
            self._apply_one(artifacts, edit)

        for name, body in artifacts.items():
            if name in self._surface.editable:
                self._enforce_max_chars(name, body)

        new_id = harness_content_id(artifacts)
        candidate = HarnessSpec(id=new_id, parent_id=current.id, artifacts=artifacts)

        if candidate.id == current.id:
            raise EditBoundsError("edits produced identical harness (no-op)")

        if check_leakage and opt_payloads:
            assert_no_leakage(
                candidate,
                opt_payloads,
                min_literal_len=self._leakage_min,
            )

        if persist and self._store:
            self._store.save(candidate)
        return candidate

    def _validate_edit_bounds(self, current: HarnessSpec, edits: list[Edit]) -> None:
        lim = self._limits
        artifacts_touched: set[str] = set()
        char_delta = 0
        bullets_touched: set[str] = set()

        for edit in edits:
            if edit.artifact not in self._surface.editable:
                raise SurfaceError(f"artifact not editable (I4): {edit.artifact!r}")

            artifacts_touched.add(edit.artifact)
            meta = self._surface.editable[edit.artifact]

            if meta.kind == "playbook":
                if edit.op == "replace" and not lim.allow_playbook_replace:
                    raise SurfaceError(
                        f"playbook replace on {edit.artifact!r} requires allow_playbook_replace"
                    )
                bullets_touched.update(self._bullet_touch(edit))

            before = current.artifacts.get(edit.artifact, "")
            after = self._preview_artifact(before, edit, meta.kind)
            char_delta += _char_delta_text(before, after)

        if len(artifacts_touched) > lim.max_artifacts_touched:
            raise EditBoundsError(
                f"too many artifacts touched: {len(artifacts_touched)} > "
                f"{lim.max_artifacts_touched}"
            )
        if char_delta > lim.max_edit_chars:
            raise EditBoundsError(f"edit too large: {char_delta} chars > {lim.max_edit_chars}")
        if len(bullets_touched) > lim.max_bullets_touched:
            raise EditBoundsError(
                f"too many bullets touched: {len(bullets_touched)} > {lim.max_bullets_touched}"
            )

    def _bullet_touch(self, edit: Edit) -> set[str]:
        if edit.op in ("add_bullet", "update_bullet", "remove_bullet"):
            if not edit.bullet_id:
                raise SurfaceError(f"{edit.op} requires bullet_id")
            return {edit.bullet_id}
        if edit.op in ("replace", "append", "insert", "delete"):
            return set()
        raise SurfaceError(f"unknown op: {edit.op}")

    def _preview_artifact(self, current: str, edit: Edit, kind: ArtifactKind) -> str:
        copy = {edit.artifact: current}
        self._apply_one(copy, edit)
        return copy[edit.artifact]

    def _apply_one(self, artifacts: dict[str, str], edit: Edit) -> None:
        if edit.artifact not in self._surface.editable:
            raise SurfaceError(f"artifact not editable (I4): {edit.artifact!r}")

        meta = self._surface.editable[edit.artifact]
        current = artifacts.get(edit.artifact, "" if meta.kind == "text" else "[]")

        if meta.kind == "playbook":
            artifacts[edit.artifact] = self._apply_playbook(current, edit, meta)
        else:
            artifacts[edit.artifact] = self._apply_text(current, edit)

    def _apply_text(self, current: str, edit: Edit) -> str:
        if edit.op == "replace":
            return edit.text
        if edit.op == "append":
            return current + edit.text
        if edit.op == "delete":
            if edit.anchor and edit.anchor in current:
                return current.replace(edit.anchor, "", 1)
            return ""
        if edit.op == "insert":
            if not edit.anchor:
                raise SurfaceError("insert requires anchor")
            if edit.anchor not in current:
                raise SurfaceError(f"anchor not found in {edit.artifact!r}")
            return current.replace(edit.anchor, edit.anchor + edit.text, 1)
        raise SurfaceError(f"op {edit.op!r} invalid for text artifact {edit.artifact!r}")

    def _apply_playbook(self, current: str, edit: Edit, meta: ArtifactSurface) -> str:
        try:
            bullets = parse_playbook(current or "[]")
        except PlaybookError as e:
            raise SurfaceError(str(e)) from e

        if edit.op == "replace":
            if not self._limits.allow_playbook_replace:
                raise SurfaceError("playbook replace not allowed")
            return edit.text

        by_id = {b.id: b for b in bullets}

        if edit.op == "add_bullet":
            if not edit.bullet_id:
                raise SurfaceError("add_bullet requires bullet_id")
            if edit.bullet_id in by_id:
                raise SurfaceError(f"bullet already exists: {edit.bullet_id}")
            bullets.append(Bullet(id=edit.bullet_id, text=edit.text))
        elif edit.op == "update_bullet":
            if not edit.bullet_id or edit.bullet_id not in by_id:
                raise SurfaceError(f"unknown bullet: {edit.bullet_id!r}")
            bullets = [
                Bullet(id=b.id, text=edit.text, useful=b.useful, harmful=b.harmful)
                if b.id == edit.bullet_id
                else b
                for b in bullets
            ]
        elif edit.op == "remove_bullet":
            if not edit.bullet_id or edit.bullet_id not in by_id:
                raise SurfaceError(f"unknown bullet: {edit.bullet_id!r}")
            bullets = [b for b in bullets if b.id != edit.bullet_id]
        elif edit.op in ("append", "insert", "delete"):
            raise SurfaceError(f"op {edit.op!r} invalid for playbook {edit.artifact!r}")
        else:
            raise SurfaceError(f"unknown op: {edit.op}")

        out = serialize_playbook(bullets)
        self._enforce_max_chars(edit.artifact, out)
        return out

    def _enforce_max_chars(self, name: str, body: str) -> None:
        cap = self._surface.editable[name].max_chars
        if len(body) > cap:
            raise EditBoundsError(
                f"artifact {name!r} length {len(body)} exceeds max_chars {cap}"
            )

    def _validate_artifacts_on_surface(self, artifacts: dict[str, str]) -> None:
        for name in artifacts:
            if name not in self._surface.editable:
                raise SurfaceError(f"artifact not on editable surface: {name!r}")
            self._enforce_max_chars(name, artifacts[name])


def preview_edits(
    manager: HarnessManager,
    current: HarnessSpec,
    edits: list[Edit],
    *,
    opt_payloads: list[dict[str, Any]] | None = None,
) -> HarnessSpec:
    """Apply edits in memory only (no lineage write). Runs I11 when payloads given."""
    return manager.apply_edits(
        current,
        edits,
        opt_payloads=opt_payloads,
        check_leakage=opt_payloads is not None,
        persist=False,
    )
