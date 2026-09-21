"""`init` drafts gold, from an existing run or by running the check."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from soda_mmqc.agentic.session import PREDICTION_FILENAME
from soda_mmqc.core.gold_drafts import DRAFT_REPLICATE, init_expected_outputs

CHECKLIST = "fig-checklist"
CHECK = "micrograph-scale-bar"
EXAMPLE_A = "doc-a/content/1"
EXAMPLE_B = "doc-b/content/2"


def _prediction(panel_label: str) -> Dict[str, Any]:
    return {"outputs": [{"panel_label": panel_label, "micrograph": "yes"}]}


def _write_one_prediction(
    leaf: Path, example: str, payload: Dict[str, Any]
) -> Path:
    target = leaf / example
    target.mkdir(parents=True, exist_ok=True)
    (target / PREDICTION_FILENAME).write_text(
        json.dumps(payload), encoding="utf-8"
    )
    return leaf


def _capture_saved_expected_outputs(monkeypatch) -> Dict[tuple, Any]:
    """Intercept `save_expected_output` instead of letting it write.

    The gold corpus under `soda_mmqc/data/` is curated by hand. A test that
    let these writes through would overwrite real expected outputs with
    fixture data, and the damage would not show up until someone scored a
    check against them.
    """
    saved: Dict[tuple, Any] = {}

    class _StubExample:
        def __init__(self, relative_source_path: str) -> None:
            self.relative_source_path = relative_source_path

        def save_expected_output(self, output, check_name, overwrite=False):
            saved[(self.relative_source_path, check_name)] = output
            return Path("/dev/null")

    monkeypatch.setattr(
        "soda_mmqc.core.gold_drafts.EXAMPLE_FACTORY.create",
        lambda relative_source_path, _cls: _StubExample(
            relative_source_path
        ),
    )
    return saved


class TestInitFromAnExistingRun:
    """A run already paid for can seed the drafts.

    Runs are expensive and we keep them, so re-running a check only to
    write expected_output.json spends money for predictions we already
    have.
    """

    def test_it_writes_one_draft_per_example(self, tmp_path, monkeypatch):
        leaf = tmp_path / "pinned" / DRAFT_REPLICATE
        _write_one_prediction(leaf, EXAMPLE_A, _prediction("A"))
        _write_one_prediction(leaf, EXAMPLE_B, _prediction("B"))
        saved = _capture_saved_expected_outputs(monkeypatch)

        written = init_expected_outputs(CHECKLIST, [CHECK], from_run=tmp_path)

        assert sorted(written[CHECK]) == sorted([EXAMPLE_A, EXAMPLE_B])
        assert len(saved) == 2
        assert list(saved.values())[0]["outputs"][0]["panel_label"] in {
            "A", "B"
        }

    def test_it_takes_rep_00_not_a_consensus(self, tmp_path, monkeypatch):
        """A curator corrects one draft; an average hides disagreement."""
        for replicate, label in ((DRAFT_REPLICATE, "A"), ("rep-01", "Z")):
            _write_one_prediction(
                tmp_path / "pinned" / replicate, EXAMPLE_A, _prediction(label)
            )
        saved = _capture_saved_expected_outputs(monkeypatch)

        init_expected_outputs(CHECKLIST, [CHECK], from_run=tmp_path)

        drafted = next(iter(saved.values()))
        assert drafted["outputs"][0]["panel_label"] == "A"

    def test_it_refuses_a_root_with_no_rep_00(self, tmp_path, monkeypatch):
        _write_one_prediction(
            tmp_path / "pinned" / "rep-03", EXAMPLE_A, _prediction("A")
        )
        _capture_saved_expected_outputs(monkeypatch)

        with pytest.raises(ValueError, match=DRAFT_REPLICATE):
            init_expected_outputs(CHECKLIST, [CHECK], from_run=tmp_path)

    def test_it_refuses_a_root_with_no_baseline_arm(
        self, tmp_path, monkeypatch
    ):
        """An unpinned variant is a comparison, not a candidate for gold."""
        _write_one_prediction(
            tmp_path / f"{CHECK}@v2" / DRAFT_REPLICATE,
            EXAMPLE_A,
            _prediction("A"),
        )
        _capture_saved_expected_outputs(monkeypatch)

        with pytest.raises(ValueError, match="pinned"):
            init_expected_outputs(CHECKLIST, [CHECK], from_run=tmp_path)

    def test_it_finds_the_per_check_level_of_a_multi_check_root(
        self, tmp_path, monkeypatch
    ):
        """experiments/runs/<exp>/ holds one directory per check."""
        _write_one_prediction(
            tmp_path / CHECK / "pinned" / DRAFT_REPLICATE,
            EXAMPLE_A,
            _prediction("A"),
        )
        saved = _capture_saved_expected_outputs(monkeypatch)

        written = init_expected_outputs(CHECKLIST, [CHECK], from_run=tmp_path)

        assert written[CHECK] == [EXAMPLE_A]
        assert len(saved) == 1


class TestInitByRunning:
    def test_it_runs_the_check_when_given_no_run(self, tmp_path, monkeypatch):
        """Default: produce the predictions, then write them as drafts."""
        calls = []

        def fake_run_check_live(checklist, check, **kwargs):
            calls.append((checklist, check))
            leaf = Path(kwargs["output"]) / "pinned" / DRAFT_REPLICATE
            _write_one_prediction(leaf, EXAMPLE_A, _prediction("A"))
            return Path(kwargs["output"]), []

        monkeypatch.setattr(
            "soda_mmqc.core.gold_drafts.run_check_live", fake_run_check_live
        )
        saved = _capture_saved_expected_outputs(monkeypatch)

        written = init_expected_outputs(CHECKLIST, [CHECK], limit=1)

        assert calls == [(CHECKLIST, CHECK)]
        assert written[CHECK] == [EXAMPLE_A]
        assert len(saved) == 1

    def test_the_run_does_not_land_in_the_run_tree(
        self, tmp_path, monkeypatch
    ):
        """It exists to seed gold, not to be scored later."""
        seen = {}

        def fake_run_check_live(checklist, check, **kwargs):
            seen["output"] = Path(kwargs["output"])
            leaf = Path(kwargs["output"]) / "pinned" / DRAFT_REPLICATE
            _write_one_prediction(leaf, EXAMPLE_A, _prediction("A"))
            return Path(kwargs["output"]), []

        monkeypatch.setattr(
            "soda_mmqc.core.gold_drafts.run_check_live", fake_run_check_live
        )
        _capture_saved_expected_outputs(monkeypatch)

        init_expected_outputs(CHECKLIST, [CHECK], limit=1)

        assert not seen["output"].exists(), (
            "the scratch run should be cleaned up, not left beside real runs"
        )


class TestCheckSelection:
    def test_an_unknown_check_is_named(self):
        with pytest.raises(ValueError, match="no-such-check"):
            init_expected_outputs(CHECKLIST, ["no-such-check"])
