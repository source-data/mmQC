"""The run directory layout, read by one walker.

`core/gold_drafts.py` takes one named leaf and `reporting/load.py` takes
every leaf under a root. Both go through here, because two walkers over
one layout disagree the first time the layout gains anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from soda_mmqc.core.run_layout import (
    BASELINE_ARM,
    iter_leaves,
    leaf,
    replicate_dirname,
    resolve_check_root,
)


def _make(root: Path, arm: str, replicate: int) -> Path:
    path = root / arm / replicate_dirname(replicate)
    path.mkdir(parents=True, exist_ok=True)
    return path


class TestIterLeaves:
    def test_it_yields_every_arm_and_replicate_sorted(self, tmp_path):
        _make(tmp_path, BASELINE_ARM, 1)
        _make(tmp_path, BASELINE_ARM, 0)
        _make(tmp_path, "check@v2", 0)

        assert [(a, r) for a, r, _ in iter_leaves(tmp_path)] == [
            ("check@v2", 0),
            (BASELINE_ARM, 0),
            (BASELINE_ARM, 1),
        ]

    def test_a_directory_that_is_not_rep_nn_is_not_a_replicate(self, tmp_path):
        """Guards against a stray directory becoming a phantom replicate."""
        _make(tmp_path, BASELINE_ARM, 0)
        (tmp_path / BASELINE_ARM / "notes").mkdir()
        (tmp_path / BASELINE_ARM / "rep-x").mkdir()

        assert [r for _, r, _ in iter_leaves(tmp_path)] == [0]

    def test_two_digit_replicates_sort_numerically(self, tmp_path):
        for replicate in (0, 2, 10):
            _make(tmp_path, BASELINE_ARM, replicate)
        assert [r for _, r, _ in iter_leaves(tmp_path)] == [0, 2, 10]

    def test_a_missing_root_is_an_error(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            list(iter_leaves(tmp_path / "nope"))

    def test_an_empty_root_yields_nothing(self, tmp_path):
        assert list(iter_leaves(tmp_path)) == []


class TestResolveCheckRoot:
    def test_a_root_holding_one_check_per_directory(self, tmp_path):
        """experiments/runs/<exp>/ holds one directory per check."""
        _make(tmp_path / "my-check", BASELINE_ARM, 0)
        assert resolve_check_root(tmp_path, "my-check") == tmp_path / "my-check"

    def test_a_root_that_is_already_the_check(self, tmp_path):
        """experiments/runs/<exp>/<check>/ has arms as its children."""
        _make(tmp_path, BASELINE_ARM, 0)
        assert resolve_check_root(tmp_path, "my-check") == tmp_path


class TestLeaf:
    def test_it_returns_the_named_leaf(self, tmp_path):
        made = _make(tmp_path, BASELINE_ARM, 3)
        assert leaf(tmp_path, arm=BASELINE_ARM, replicate=3) == made

    def test_a_missing_arm_says_what_is_there(self, tmp_path):
        _make(tmp_path, "check@v2", 0)
        with pytest.raises(ValueError, match="check@v2"):
            leaf(tmp_path, arm=BASELINE_ARM, replicate=0)

    def test_a_missing_replicate_says_what_is_there(self, tmp_path):
        _make(tmp_path, BASELINE_ARM, 3)
        with pytest.raises(ValueError, match="rep-03"):
            leaf(tmp_path, arm=BASELINE_ARM, replicate=0)
