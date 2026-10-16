"""Itemized playbook artifacts (JSON list of bullets)."""

from __future__ import annotations

import json
from typing import Any

from rsi_harness.core.types import Bullet


class PlaybookError(ValueError):
    pass


def parse_playbook(raw: str) -> list[Bullet]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise PlaybookError(f"invalid playbook JSON: {e}") from e
    if not isinstance(data, list):
        raise PlaybookError("playbook must be a JSON array")
    bullets: list[Bullet] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            raise PlaybookError("each playbook entry must be an object")
        bid = item.get("id")
        text = item.get("text")
        if not isinstance(bid, str) or not bid:
            raise PlaybookError("bullet id must be a non-empty string")
        if not isinstance(text, str):
            raise PlaybookError("bullet text must be a string")
        if bid in seen:
            raise PlaybookError(f"duplicate bullet id: {bid}")
        seen.add(bid)
        useful = int(item.get("useful", 0))
        harmful = int(item.get("harmful", 0))
        bullets.append(Bullet(id=bid, text=text, useful=useful, harmful=harmful))
    return bullets


def serialize_playbook(bullets: list[Bullet]) -> str:
    payload: list[dict[str, Any]] = [
        {"id": b.id, "text": b.text, "useful": b.useful, "harmful": b.harmful} for b in bullets
    ]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def empty_playbook() -> str:
    return "[]"
