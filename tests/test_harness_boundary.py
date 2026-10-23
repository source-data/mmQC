"""The harness stands apart from the rest of mmQC.

`skills`, `pinning`, `runtime`, `session` and `render` are the part of
`soda_mmqc.agentic` an application will install (thinking/plans/
2026-10-23-harness-in-mmqc-utils.md). They may import the standard library,
third-party packages and each other -- nothing else from `soda_mmqc`, not even
lazily inside a function. Where examples are stored, where checklists live,
which model a benchmark run uses: all of that is mmQC's, and reaches the
harness as arguments.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

AGENTIC = Path(__file__).resolve().parents[1] / "soda_mmqc" / "agentic"
HARNESS = ("skills", "pinning", "runtime", "session", "render")


def _soda_mmqc_imports(module: str):
    tree = ast.parse((AGENTIC / f"{module}.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module] if node.module != "soda_mmqc" else [
                f"soda_mmqc.{alias.name}" for alias in node.names]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        else:
            continue
        for name in names:
            if name == "soda_mmqc" or name.startswith("soda_mmqc."):
                yield node.lineno, name


@pytest.mark.parametrize("module", HARNESS)
def test_the_harness_imports_nothing_else_from_soda_mmqc(module):
    allowed = {f"soda_mmqc.agentic.{name}" for name in HARNESS}
    outside = [f"line {line}: {name}" for line, name in _soda_mmqc_imports(module)
               if name not in allowed]
    assert outside == [], (
        f"agentic/{module}.py reaches into mmQC; pass it in instead: {outside}")


def test_the_session_template_sits_with_the_harness():
    """`CLAUDE.md` travels with the code that copies it into each runtime."""
    from soda_mmqc.agentic.runtime import AGENTIC_CLAUDE_TEMPLATE

    assert AGENTIC_CLAUDE_TEMPLATE == AGENTIC / "CLAUDE.md"
    assert AGENTIC_CLAUDE_TEMPLATE.is_file()
