import pytest

from rsi_harness.core.playbook import PlaybookError, parse_playbook, serialize_playbook
from rsi_harness.core.types import Bullet


def test_roundtrip() -> None:
    bullets = [Bullet(id="a", text="one", useful=1, harmful=0)]
    raw = serialize_playbook(bullets)
    assert parse_playbook(raw) == bullets


def test_duplicate_id_rejected() -> None:
    raw = '[{"id":"x","text":"1"},{"id":"x","text":"2"}]'
    with pytest.raises(PlaybookError):
        parse_playbook(raw)
