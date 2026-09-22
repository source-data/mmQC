"""Tests for evaluation check discovery and Streamlit helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from soda_mmqc.reporting.display import build_figure_image_plot
from soda_mmqc.reporting.load import discover_evaluation_checks, try_load_run_summaries
from soda_mmqc.reporting.plots import plot_mean_score_with_instances
from soda_mmqc.reporting.streamlit_app import _selected_instance_index


# The committed snapshot these tests read instead of soda_mmqc/data/evaluation.
# Reading the live corpus meant asserting whichever evaluation runs happened to
# be committed -- a statement about data, not about the reporting code -- so the
# tests broke whenever that corpus was regenerated or removed.
FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/reporting_snapshots"


@pytest.fixture(autouse=True)
def _use_fixture_corpus(monkeypatch):
    """Point the loader at the committed snapshot, not the live corpus."""
    monkeypatch.setattr("soda_mmqc.reporting.load.EVALUATION_DIR", FIXTURES)



class TestDiscoverEvaluationChecks:
    def test_discovers_micrograph_scale_bar(self):
        refs = discover_evaluation_checks()
        assert any(
            ref.checklist == "fig-checklist" and ref.check == "micrograph-scale-bar"
            for ref in refs
        )

    def test_empty_when_no_evaluation_dir(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(
            "soda_mmqc.reporting.load.EVALUATION_DIR",
            tmp_path / "missing",
        )
        assert discover_evaluation_checks() == ()

    def test_finds_check_with_a_scored_leaf(self, tmp_path: Path, monkeypatch):
        """A model directory is a run root: its children are arms.

        The analysis lives at <model>/<arm>/rep-NN/analysis.json, so a
        file directly inside the model directory is not a scored run.
        """
        eval_root = tmp_path / "evaluation"
        leaf = (
            eval_root / "fig-checklist" / "demo-check" / "model-b"
            / "pinned" / "rep-00"
        )
        leaf.mkdir(parents=True)
        (leaf / "analysis.json").write_text(
            json.dumps({"flat": []}), encoding="utf-8"
        )
        monkeypatch.setattr("soda_mmqc.reporting.load.EVALUATION_DIR", eval_root)
        refs = discover_evaluation_checks()
        assert len(refs) == 1
        assert refs[0].checklist == "fig-checklist"
        assert refs[0].check == "demo-check"

    def test_a_run_with_no_analysis_is_not_discovered(
        self, tmp_path: Path, monkeypatch
    ):
        """Predictions without a score are an unscored run, not a result."""
        eval_root = tmp_path / "evaluation"
        leaf = (
            eval_root / "fig-checklist" / "demo-check" / "model-b"
            / "pinned" / "rep-00" / "doc-a"
        )
        leaf.mkdir(parents=True)
        (leaf / "prediction.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr("soda_mmqc.reporting.load.EVALUATION_DIR", eval_root)
        assert discover_evaluation_checks() == ()


class TestMeanScorePlotSelection:
    def test_return_instances_includes_customdata(self, arm1_summary):
        fig, inst = plot_mean_score_with_instances(
            arm1_summary,
            return_instances=True,
        )
        scatter = next(trace for trace in fig.data if trace.type == "scatter")
        assert len(scatter.customdata) == len(inst)
        assert "source" in inst.columns


class TestFigureImagePlot:
    def test_build_figure_image_plot(self):
        image_path = (
            Path(__file__).resolve().parents[1]
            / "soda_mmqc/data/examples/10.1038_s44318-026-00715-1/content/1"
            / "content/1.png"
        )
        if not image_path.is_file():
            pytest.skip("figure fixture image missing")
        fig = build_figure_image_plot(image_path, height=200)
        assert fig is not None
        assert fig.layout.dragmode == "zoom"


class TestTryLoadRunSummaries:
    def test_missing_manifest_returns_message(self, tmp_path: Path, monkeypatch):
        eval_root = tmp_path / "evaluation"
        check_eval = eval_root / "fig-checklist" / "demo-check"
        leaf = check_eval / "model-b" / "pinned" / "rep-00"
        leaf.mkdir(parents=True)
        (leaf / "analysis.json").write_text(
            json.dumps({"flat": []}),
            encoding="utf-8",
        )
        checklist_root = tmp_path / "checklist" / "fig-checklist" / "demo-check"
        checklist_root.mkdir(parents=True)

        monkeypatch.setattr("soda_mmqc.reporting.load.EVALUATION_DIR", eval_root)
        monkeypatch.setattr("soda_mmqc.reporting.load.CHECKLIST_DIR", tmp_path / "checklist")

        summaries, error = try_load_run_summaries("fig-checklist", "demo-check")
        assert summaries is None
        assert error is not None
        assert "eval-manifest.json" in error

    def test_loads_when_manifest_present(self, tmp_path: Path, monkeypatch):
        eval_root = tmp_path / "evaluation"
        check_eval = eval_root / "fig-checklist" / "demo-check"
        leaf = check_eval / "model-b" / "pinned" / "rep-00"
        leaf.mkdir(parents=True)
        (leaf / "analysis.json").write_text(
            json.dumps({"flat": []}),
            encoding="utf-8",
        )
        checklist_root = tmp_path / "checklist" / "fig-checklist" / "demo-check"
        checklist_root.mkdir(parents=True)
        (checklist_root / "eval-manifest.json").write_text(
            json.dumps(
                {
                    "checklist": "fig-checklist",
                    "check": "demo-check",
                    "defaults": {},
                    "fields": {},
                }
            ),
            encoding="utf-8",
        )

        monkeypatch.setattr("soda_mmqc.reporting.load.EVALUATION_DIR", eval_root)
        monkeypatch.setattr("soda_mmqc.reporting.load.CHECKLIST_DIR", tmp_path / "checklist")

        summaries, error = try_load_run_summaries("fig-checklist", "demo-check")
        assert error is None
        assert summaries is not None
        assert len(summaries) == 1

    def test_loads_run_summaries_for_a_check(self):
        # Named for the behaviour, not for one check: it asserts that a check
        # with results loads without error, and the check it happens to read
        # was never what was under test.
        summaries, error = try_load_run_summaries(
            "fig-checklist",
            "micrograph-scale-bar",
        )
        assert error is None, error
        assert summaries is not None
        assert len(summaries) > 0
        assert "model-a" in summaries.models


class TestStreamlitSelectionParsing:
    def test_selected_instance_index_from_customdata(self):
        class Selection:
            points = [{"customdata": [3]}]

        class Event:
            selection = Selection()

        assert _selected_instance_index(Event().selection) == 3

    def test_selected_instance_index_empty(self):
        assert _selected_instance_index(None) is None
        assert _selected_instance_index(type("S", (), {"points": []})()) is None


@pytest.fixture
def arm1_summary():
    from soda_mmqc.reporting import aggregate_run, load_evaluation_dir

    runs = load_evaluation_dir(
        "fig-checklist",
        "micrograph-scale-bar",
        models="model-a",
        arms="pinned",
    )
    return aggregate_run(runs[0])
