"""I5: no direct vendor LLM SDK usage outside core/llm.py (M1 enforces at runtime)."""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PKG = REPO / "src" / "rsi_harness"
FORBIDDEN_TOP = ("openai", "anthropic", "litellm", "google.generativeai")
ALLOWED = PKG / "core" / "llm.py"


def _file_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    mods: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            mods.append(node.module)
    return mods


def test_no_forbidden_llm_imports_outside_gateway() -> None:
    violations: list[str] = []
    for path in PKG.rglob("*.py"):
        if path == ALLOWED:
            continue
        for mod in _file_imports(path):
            for bad in FORBIDDEN_TOP:
                if mod == bad or mod.startswith(bad + "."):
                    violations.append(f"{path.relative_to(REPO)} imports {mod}")
    assert not violations, "\n".join(violations)
