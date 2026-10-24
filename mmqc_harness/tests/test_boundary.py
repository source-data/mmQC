"""The harness stands alone: an application imports it and nothing happens.

mmQC built the harness and benchmarks it; applications install it. Neither may
leak into the other through an import: where examples are stored, where
checklists live and which model a benchmark run uses are mmQC's, and reach the
harness as arguments. The harness depends on `mmqc_utils` (the conversions),
never the other way round.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

HARNESS = Path(__file__).resolve().parents[1] / "src" / "mmqc_harness"
MODULES = sorted(p.stem for p in HARNESS.glob("*.py"))
UTILS = Path(__file__).resolve().parents[2] / "mmqc_utils" / "src" / "mmqc_utils"


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            yield node.lineno, node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name


@pytest.mark.parametrize("module", MODULES)
def test_the_harness_imports_nothing_from_mmqc(module):
    """Lazy imports inside functions included."""
    found = [f"line {line}: {name}" for line, name in _imports(HARNESS / f"{module}.py")
             if name == "soda_mmqc" or name.startswith("soda_mmqc.")]
    assert found == [], f"mmqc_harness/{module}.py reaches into mmQC: {found}"


@pytest.mark.skipif(not UTILS.is_dir(), reason="mmqc_utils' source is not beside this package")
def test_the_conversions_do_not_import_the_harness():
    found = [f"{path.name} line {line}: {name}" for path in sorted(UTILS.rglob("*.py"))
             for line, name in _imports(path)
             if name == "mmqc_harness" or name.startswith("mmqc_harness.")]
    assert found == [], f"mmqc_utils imports the harness: {found}"


def test_importing_the_harness_writes_nothing_and_loads_no_mmqc(tmp_path):
    """No .env read, no log file, no mmQC: an import is only an import."""
    script = (
        "import sys\n"
        "import mmqc_harness\n"
        "from mmqc_harness import runtime, session, skills, pinning, render\n"
        "assert not any(m == 'soda_mmqc' or m.startswith('soda_mmqc.') for m in sys.modules), "
        "sorted(m for m in sys.modules if m.startswith('soda_mmqc'))\n"
        "assert 'claude_agent_sdk' not in sys.modules, 'the SDK is imported only to run a session'\n"
    )
    (tmp_path / ".env").write_text("SHOULD_NOT_BE_READ=1\n", encoding="utf-8")
    before = sorted(tmp_path.rglob("*"))
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=tmp_path, env=env,
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert sorted(tmp_path.rglob("*")) == before
    assert "SHOULD_NOT_BE_READ" not in os.environ


def test_the_session_template_ships_with_the_harness():
    """`CLAUDE.md` is package data, copied into each runtime."""
    from mmqc_harness.runtime import AGENTIC_CLAUDE_TEMPLATE

    assert AGENTIC_CLAUDE_TEMPLATE == HARNESS / "CLAUDE.md"
    assert AGENTIC_CLAUDE_TEMPLATE.is_file()
