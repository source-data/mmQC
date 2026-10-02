"""Pinning the gold to a tagged snapshot (soda_mmqc/gold.py, config.gold_root).

A frozen experiment must re-score against the gold its findings used, after
the live gold has been curated and migrated (contract cleanup, W5a).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from soda_mmqc import config
from soda_mmqc.core import examples as examples_module
from soda_mmqc import gold

REPO = Path(__file__).resolve().parents[1]


def _has_tag(tag: str) -> bool:
    return subprocess.run(["git", "rev-parse", "--verify", "-q", f"{tag}^{{commit}}"],
                          cwd=REPO, capture_output=True).returncode == 0


needs_gold_v1 = pytest.mark.skipif(not _has_tag("gold-v1"), reason="gold-v1 tag not present")


def _bare_example(relative: str, source: Path):
    """An Example with only what the gold methods read -- no figure on disk."""
    ex = object.__new__(examples_module.FigureExample)
    ex.relative_source_path = relative
    ex.source_path = source
    return ex


def test_gold_root_is_the_live_tree_unless_pinned(monkeypatch):
    monkeypatch.delenv(config.GOLD_DIR_ENV, raising=False)
    assert config.gold_root() == config.EXAMPLES_DIR
    monkeypatch.setenv(config.GOLD_DIR_ENV, "/somewhere/else")
    assert config.gold_root() == Path("/somewhere/else")


def test_the_env_name_agrees_between_the_two_modules():
    """gold.py imports nothing from soda_mmqc, so it repeats the name."""
    assert gold.GOLD_DIR_ENV == config.GOLD_DIR_ENV


def test_a_pin_redirects_gold_reads_only(tmp_path, monkeypatch):
    example = "doc/content/1"
    snap = tmp_path / "snap"
    target = snap / example / "checks" / "toy"
    target.mkdir(parents=True)
    (target / "expected_output.json").write_text(json.dumps({"outputs": [{"panel_label": "Z"}]}))
    monkeypatch.setenv(config.GOLD_DIR_ENV, str(snap))
    ex = _bare_example(example, tmp_path / "live" / example)
    assert ex.get_expected_output("toy") == {"outputs": [{"panel_label": "Z"}]}


def test_saving_is_refused_while_the_gold_is_pinned(tmp_path, monkeypatch):
    monkeypatch.setenv(config.GOLD_DIR_ENV, str(tmp_path / "snap"))
    ex = _bare_example("doc/content/1", tmp_path / "live" / "doc" / "content" / "1")
    with pytest.raises(RuntimeError, match="pinned"):
        ex.save_expected_output({"outputs": []}, "toy", overwrite=True)
    assert not (tmp_path / "live").exists()


@needs_gold_v1
def test_a_snapshot_holds_gold_only():
    root = gold.snapshot("gold-v1")
    files = [p for p in root.rglob("*") if p.is_file()]
    assert files and all(p.name.startswith("expected_output.") and "checks" in p.parts for p in files)


@needs_gold_v1
def test_a_snapshot_is_the_tagged_gold_not_the_live_one():
    """individual-data-points was migrated after gold-v1; the snapshot is not."""
    root = gold.snapshot("gold-v1")
    values = {r.get("individual_values")
              for p in root.glob("**/checks/individual-data-points/expected_output.json")
              for r in json.loads(p.read_text())["outputs"]}
    assert "not needed" in values and "not_required" not in values


@needs_gold_v1
def test_pinning_twice_to_different_tags_is_refused(monkeypatch):
    monkeypatch.setenv(config.GOLD_DIR_ENV, "/a/different/snapshot")
    with pytest.raises(RuntimeError, match="already pinned"):
        gold.pin_gold("gold-v1")
