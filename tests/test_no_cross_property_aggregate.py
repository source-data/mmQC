"""The standing constraint, made checkable.

The unit of measurement is one leaf property. A helper that pools
`panel_label` with `micrograph` is not a convenience, it is a wrong
number: an arm that improves one and degrades the other comes out
looking unchanged.

These catch the obvious reintroductions. They cannot catch a clever one,
which is what review is for.
"""

from __future__ import annotations

import json
import pathlib

PACKAGE = pathlib.Path(__file__).resolve().parents[1] / "soda_mmqc"
NOTEBOOKS = pathlib.Path(__file__).resolve().parents[1] / "notebooks"

#: Names that only make sense for a number spanning several properties.
BANNED_NAMES = ("macro_mean", "across_properties", "pooled_score")


def _notebook_code(path: pathlib.Path) -> str:
    cells = json.loads(path.read_text(encoding="utf-8"))["cells"]
    return "\n".join(
        "".join(cell["source"])
        for cell in cells
        if cell["cell_type"] == "code"
    )


def test_no_module_averages_across_leaf_properties():
    offenders = [
        f"{path.relative_to(PACKAGE)}:{name}"
        for sub in ("reporting", "core")
        for path in (PACKAGE / sub).glob("*.py")
        for name in BANNED_NAMES
        if name in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_the_notebooks_do_not_reimplement_the_walker():
    """Both experiment notebooks hand-rolled leaves() and a weighted mean.

    The walker is `load_run_root` and the statistics live in
    `reporting/aggregate.py`, so a notebook redefining either has
    drifted from the version that has tests.
    """
    for path in sorted(NOTEBOOKS.rglob("*.ipynb")):
        source = _notebook_code(path)
        assert "def leaves(" not in source, path.name
        assert "def weighted(" not in source, path.name


def test_the_notebooks_do_not_average_across_properties():
    """The instance-weighted cross-property mean, specifically.

    It was a workaround for mean_score returning 0.0 when nothing was
    applicable. That is fixed at the source now, and the workaround was
    a worse number than the bug it hid.
    """
    for path in sorted(NOTEBOOKS.rglob("*.ipynb")):
        source = _notebook_code(path)
        for name in BANNED_NAMES:
            assert name not in source, f"{path.name}: {name}"


def test_the_notebooks_use_the_library_loader():
    """An experiment notebook reads runs through reporting, not by hand."""
    for path in sorted(NOTEBOOKS.rglob("experiments/*.ipynb")):
        source = _notebook_code(path)
        assert "load_run_root" in source, (
            f"{path.name} should read runs via load_run_root"
        )
