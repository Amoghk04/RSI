"""I7: core/ MUST NOT import adapters."""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CORE = REPO / "src" / "rsi_harness" / "core"


def _imports_in_file(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def test_core_does_not_import_adapters() -> None:
    violations: list[str] = []
    for path in CORE.rglob("*.py"):
        for mod in _imports_in_file(path):
            if mod == "rsi_harness.adapters" or mod.startswith("rsi_harness.adapters."):
                violations.append(f"{path.relative_to(REPO)} imports {mod}")
    assert not violations, "\n".join(violations)
