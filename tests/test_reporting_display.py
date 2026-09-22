"""Phase 2 tests for soda_mmqc.reporting.display."""

from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from soda_mmqc.reporting import (
    comparison_errors_table,
    load_evaluation_dir,
    show_comparison_errors,
    show_layer1_errors,
    show_layer2_errors,
    show_table,
    sort_frame,
    summarize_runs,
)
from soda_mmqc.reporting.display import (
    _column_search_cols,
    _itables_available,
    sort_frame as sort_frame_fn,
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



class TestSortFrame:
    def test_sorts_by_default_columns(self):
        frame = pd.DataFrame(
            {"doc_id": ["b", "a"], "field": ["y", "x"], "path": ["p2", "p1"]}
        )
        sorted_frame = sort_frame(frame, ("doc_id", "field"))
        assert sorted_frame["doc_id"].tolist() == ["a", "b"]


class TestComparisonErrorsTable:
    @pytest.fixture
    def summaries(self):
        runs = load_evaluation_dir(
            "fig-checklist",
            "micrograph-scale-bar",
            models="model-a",
            arms=["pinned", "micrograph-scale-bar@v2"],
        )
        return summarize_runs(runs)

    def test_arm_contrast_includes_arm_column(self, summaries):
        frame = comparison_errors_table(
            summaries,
            compare="arm",
            model="model-a",
        )
        if frame.empty:
            pytest.skip("no layer-2 errors in fixture run")
        assert "arm" in frame.columns
        assert set(frame["arm"].unique()).issubset({"pinned", "micrograph-scale-bar@v2"})

    def test_second_arm_has_layer2_matching_errors(self, summaries):
        frame = comparison_errors_table(
            summaries,
            compare="arm",
            model="model-a",
        )
        arm2 = frame.loc[frame["arm"] == "micrograph-scale-bar@v2"]
        assert not arm2.empty
        assert arm2["layer2"].isin({"FP", "FN", "mismatch"}).all()
        assert "layer1" not in arm2.columns

    def test_model_contrast_requires_arm(self, summaries):
        with pytest.raises(ValueError, match="arm is required"):
            comparison_errors_table(summaries, compare="model")


class TestColumnSearchCols:
    def test_builds_search_cols_aligned_to_frame(self):
        frame = pd.DataFrame({"layer1": ["a"], "field": ["x"]})
        assert _column_search_cols(frame, {"layer1": "spurious_applicable"}) == [
            {"search": "spurious_applicable"},
            None,
        ]


class TestShowTable:
    def test_show_table_uses_itables_when_available(self):
        frame = pd.DataFrame({"a": [1]})
        if not _itables_available():
            pytest.skip("itables not installed")

        with patch("itables.show", return_value="widget") as mock_show:
            result = show_table(frame, caption="test", default_sort=("a",))
        mock_show.assert_called_once()
        assert result == "widget"

    def test_show_table_passes_column_search(self):
        frame = pd.DataFrame({"layer1": ["spurious_applicable"], "field": ["x"]})
        if not _itables_available():
            pytest.skip("itables not installed")

        with patch("itables.show", return_value="widget") as mock_show:
            show_table(frame, column_search={"layer1": "spurious_applicable"})
        assert mock_show.call_args.kwargs["searchCols"] == [
            {"search": "spurious_applicable"},
            None,
        ]

    def test_show_table_fallback_without_itables(self):
        frame = pd.DataFrame({"doc_id": ["x"], "field": ["micrograph"]})
        with patch("soda_mmqc.reporting.display._itables_available", return_value=False):
            with patch("IPython.display.display") as mock_display:
                result = show_table(frame)
        assert isinstance(result, pd.DataFrame)
        assert mock_display.call_count >= 1

    def test_show_layer1_errors_presets_layer1_column_search(self):
        runs = load_evaluation_dir(
            "fig-checklist",
            "micrograph-scale-bar",
            models="model-b",
            arms="micrograph-scale-bar@v2",
        )
        summaries = summarize_runs(runs)
        summary = next(
            s for s in summaries.values()
            if s.model == "model-b" and s.arm == "micrograph-scale-bar@v2"
        )

        with patch("soda_mmqc.reporting.display.show_table") as mock_show:
            show_layer1_errors(summary, layer1="spurious_applicable")
        assert mock_show.call_args.kwargs["column_search"] == {
            "layer1": "spurious_applicable",
        }
        passed_frame = mock_show.call_args[0][0]
        assert "layer1" in passed_frame.columns

    def test_show_layer2_errors_filters_field(self):
        runs = load_evaluation_dir(
            "fig-checklist",
            "micrograph-scale-bar",
            models="model-a",
            arms="micrograph-scale-bar@v2",
        )
        summaries = summarize_runs(runs)
        summary = next(
            s for s in summaries.values()
            if s.model == "model-a" and s.arm == "micrograph-scale-bar@v2"
        )

        with patch("soda_mmqc.reporting.display.show_table") as mock_show:
            show_layer2_errors(summary, field="micrograph")
        passed_frame = mock_show.call_args[0][0]
        assert not passed_frame.empty
        assert (passed_frame["leaf_property"] == "micrograph").all()
        assert "layer1" not in passed_frame.columns

    def test_show_comparison_errors_delegates(self):
        runs = load_evaluation_dir(
            "fig-checklist",
            "micrograph-scale-bar",
            models="model-a",
            arms=["pinned", "micrograph-scale-bar@v2"],
        )
        summaries = summarize_runs(runs)
        with patch("soda_mmqc.reporting.display.show_table") as mock_show:
            show_comparison_errors(
                summaries,
                compare="arm",
                model="model-a",
            )
        mock_show.assert_called_once()
        passed_frame = mock_show.call_args[0][0]
        assert "arm" in passed_frame.columns
