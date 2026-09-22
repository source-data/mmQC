"""Phase 4 tests for comparison reporting workflow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from soda_mmqc.reporting import (
    build_comparison_report,
    load_evaluation_dir,
    plot_comparison_layer_s,
    show_comparison_report,
    summarize_runs,
)

from pathlib import Path


# The committed snapshot these tests read instead of soda_mmqc/data/evaluation.
# Reading the live corpus meant asserting whichever evaluation runs happened to
# be committed -- a statement about data, not about the reporting code -- so the
# tests broke whenever that corpus was regenerated or removed.
FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/reporting_snapshots"


@pytest.fixture(autouse=True)
def _use_fixture_corpus(monkeypatch):
    """Point the loader at the committed snapshot, not the live corpus."""
    monkeypatch.setattr("soda_mmqc.reporting.load.EVALUATION_DIR", FIXTURES)


MODEL_A = "model-a"


@pytest.fixture
def summaries_arm():
    runs = load_evaluation_dir(
        "fig-checklist",
        "micrograph-scale-bar",
        models=MODEL_A,
        arms=["pinned", "micrograph-scale-bar@v2", "micrograph-scale-bar@v3"],
    )
    return summarize_runs(runs)


@pytest.fixture
def summaries_model():
    runs = load_evaluation_dir(
        "fig-checklist",
        "micrograph-scale-bar",
        models=[MODEL_A, "model-b"],
        arms="pinned",
    )
    return summarize_runs(runs)


class TestComparisonReport:
    def test_build_arm_contrast_report(self, summaries_arm):
        report = build_comparison_report(
            summaries_arm,
            compare="arm",
            model=MODEL_A,
        )
        assert report.compare == "arm"
        assert report.anchor == MODEL_A
        assert report.series_labels == ("pinned", "micrograph-scale-bar@v2", "micrograph-scale-bar@v3")
        assert report.layer_s_figure is not None
        assert len(report.layer1_figure.data) > 0
        assert len(report.layer2_binary_figure.data) > 0
        assert len(report.layer2_graded_figure.data) > 0
        assert "arm" in report.errors_table.columns

    def test_build_model_contrast_report(self, summaries_model):
        report = build_comparison_report(
            summaries_model,
            compare="model",
            arm="pinned",
        )
        assert report.compare == "model"
        assert report.anchor == "pinned"
        assert report.series_labels == (MODEL_A, "model-b")
        assert "model" in report.errors_table.columns

    def test_arm_contrast_layer2_errors_only(self, summaries_arm):
        report = build_comparison_report(
            summaries_arm,
            compare="arm",
            model=MODEL_A,
        )
        arm2_errors = report.errors_table.loc[
            report.errors_table["arm"] == "micrograph-scale-bar@v2"
        ]
        assert not arm2_errors.empty
        assert arm2_errors["layer2"].isin({"FP", "FN", "mismatch"}).all()
        assert "layer1" not in arm2_errors.columns

    def test_plot_comparison_layer_s_series(self, summaries_arm):
        fig = plot_comparison_layer_s(
            summaries_arm,
            compare="arm",
            model=MODEL_A,
        )
        assert fig is not None
        assert len(fig.data) == 3
        opacities = [trace.marker.opacity for trace in fig.data]
        assert len(set(opacities)) == 3

    def test_show_comparison_report_returns_report(self, summaries_model):
        with patch("plotly.graph_objects.Figure.show"):
            report = show_comparison_report(
                summaries_model,
                compare="model",
                arm="pinned",
                show_errors_table=False,
            )
        assert report.compare == "model"
        assert len(report.errors_table.columns) > 0

    def test_requires_selector(self, summaries_arm):
        with pytest.raises(ValueError, match="model is required"):
            build_comparison_report(summaries_arm, compare="arm")
