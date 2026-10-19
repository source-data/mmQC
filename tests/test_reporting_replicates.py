"""Averaging instance scores over the replicates of one arm."""

from __future__ import annotations

import pandas as pd
import pytest

from soda_mmqc.core.eval_manifest import parse_eval_manifest
from soda_mmqc.reporting.aggregate import aggregate_run
from soda_mmqc.reporting.load import FlatRecord, FlatRun, RunRef
from soda_mmqc.reporting.plots import plot_replicate_mean_scores
from soda_mmqc.reporting.replicates import (
    checks_in,
    panel_comparison,
    panel_row_path,
    pooled_instance_scores_frame,
    pooled_mean_scores_frame,
    property_check,
    property_label,
    spurious_rows_frame,
)

# A merged checklist run: two checks' outputs side by side in one answer.
MANIFEST = parse_eval_manifest(
    {
        "checklist": "toy-entry",
        "defaults": {
            "matching_metric": "binary_polarity",
            "positive_value": "yes",
            "negative_value": "no",
            "na_values": [],
        },
        "list_alignment": {
            "scale-bar": ["panel_label"],
            "annotations": ["panel_label"],
        },
        "fields": {
            "scale-bar[].panel_label": {
                "matching_metric": "graded_string",
                "string_compare": "exact",
                "match_threshold": 1.0,
            },
            "scale-bar[].micrograph": {"matching_metric": "binary_polarity"},
            "annotations[].panel_label": {
                "matching_metric": "graded_string",
                "string_compare": "exact",
                "match_threshold": 1.0,
            },
            "annotations[].from_the_caption": {
                "matching_metric": "graded_string",
                "string_compare": "fuzzy",
                "match_threshold": 0.5,
            },
        },
    }
)

FIGURE = "doc-1/content/1"


def _instance(path, exp, pred, score, layer1="correct_applicable", layer2=None):
    check, rest = path.split("[", 1)
    field = rest.split("].", 1)[1]
    return {
        "path": path,
        "leaf_property": f"{check}[].{field}",
        "exp_value": exp,
        "pred_value": pred,
        "score": score,
        "layer1": layer1,
        "layer2": layer2,
    }


def _replicate(replicate, instances, spurious=()):
    rows = [
        {
            "context_path": None,
            "gold_index": None,
            "pred_index": 5,
            "structural": "spurious_row",
            "pred_alignment": label,
        }
        for label in spurious
    ]
    record = FlatRecord(
        doc_id="doc-1",
        metadata={"source": FIGURE, "doc_id": "doc-1", "example_type": "figure"},
        analysis={
            "instances": instances,
            "by_list": {"scale-bar": {"rows": rows}},
        },
    )
    return aggregate_run(
        FlatRun(
            ref=RunRef("toy", "toy-entry", "", "pinned", replicate),
            records=(record,),
            manifest=MANIFEST,
        )
    )


@pytest.fixture
def replicates():
    """Three replicates of one figure with two panels, A and B.

    Panel B's micrograph call is right once and wrong twice; its caption
    quote scores 0.6, 0.9 and is withheld in the third replicate.
    """
    def common(micrograph_b, caption_b, layer1_caption_b="correct_applicable"):
        return [
            _instance("scale-bar[0].panel_label", "A", "A", 1.0, layer2="match"),
            _instance("scale-bar[0].micrograph", "yes", "yes", 1.0, layer2="TP"),
            _instance("scale-bar[1].panel_label", "B", "B", 1.0, layer2="match"),
            _instance(
                "scale-bar[1].micrograph", "yes", micrograph_b,
                1.0 if micrograph_b == "yes" else 0.0,
                layer2="TP" if micrograph_b == "yes" else "FN",
            ),
            _instance("annotations[1].panel_label", "B", "B", 1.0, layer2="match"),
            _instance(
                "annotations[1].from_the_caption", "arrows: cilia",
                None if caption_b is None else "arrows",
                caption_b,
                layer1=layer1_caption_b,
            ),
        ]

    return [
        _replicate(0, common("yes", 0.6), spurious=["C"]),
        _replicate(1, common("no", 0.9), spurious=["C"]),
        _replicate(2, common("no", None, "withheld_applicable")),
    ]


class TestNames:
    def test_a_merged_property_belongs_to_its_check(self):
        assert property_check("scale-bar[].micrograph") == "scale-bar"
        assert property_check("outputs[].micrograph") == "outputs"

    def test_the_label_keeps_nested_lists_apart(self):
        assert property_label("plot-axis-units[].units_provided[].answer") == (
            "units_provided[].answer"
        )
        assert property_label(
            "plot-axis-units[].unit_definition_as_provided[].answer"
        ) == "unit_definition_as_provided[].answer"

    def test_the_panel_row_is_the_top_level_row(self):
        assert panel_row_path("plot-axis-units[0].units_provided[1].answer") == (
            "plot-axis-units[0]"
        )

    def test_checks_follow_the_manifest(self, replicates):
        assert checks_in(replicates) == ["scale-bar", "annotations"]


class TestPooledScores:
    def test_a_dot_is_the_mean_over_replicates(self, replicates):
        inst = pooled_instance_scores_frame(replicates, check="scale-bar")
        row = inst.set_index("path").loc["scale-bar[1].micrograph"]
        assert row["score"] == pytest.approx(1 / 3)
        assert row["n_scored"] == 3

    def test_a_graded_score_is_averaged_not_thresholded(self, replicates):
        """0.6 and 0.9 average to 0.75; the withheld replicate is not a 0."""
        inst = pooled_instance_scores_frame(replicates, check="annotations")
        row = inst.set_index("path").loc["annotations[1].from_the_caption"]
        assert row["score"] == pytest.approx(0.75)
        assert row["n_scored"] == 2
        assert [outcome[:2] for outcome in row["replicates"]] == [
            (0, 0.6), (1, 0.9), (2, None)
        ]
        assert row["replicates"][2][2] == "withheld_applicable"

    def test_the_bar_is_the_mean_over_examples_and_replicates(self, replicates):
        frame = pooled_mean_scores_frame(replicates, check="scale-bar")
        bar = frame.set_index("leaf_property").loc["scale-bar[].micrograph"]
        # Panel A: 1, 1, 1; panel B: 1, 0, 0 -- four of six.
        assert bar["mean_score"] == pytest.approx(4 / 6)
        assert bar["n_scored"] == 6

    def test_one_check_keeps_only_its_properties(self, replicates):
        frame = pooled_mean_scores_frame(replicates, check="annotations")
        assert set(frame["leaf_property"]) == {
            "annotations[].panel_label",
            "annotations[].from_the_caption",
        }

    def test_one_replicate_is_the_single_run_plot(self, replicates):
        inst = pooled_instance_scores_frame(replicates[:1], check="scale-bar")
        assert inst.set_index("path").loc["scale-bar[1].micrograph", "score"] == 1.0


class TestPanelComparison:
    def test_gold_against_each_replicate(self, replicates):
        values, scores = panel_comparison(
            replicates, source=FIGURE, row_path="scale-bar[1]"
        )
        assert list(values.columns) == ["gold", "rep-00", "rep-01", "rep-02"]
        assert list(values.loc["micrograph"]) == ["yes", "yes", "no", "no"]
        assert list(scores.loc["micrograph"]) == [1.0, 0.0, 0.0]

    def test_an_unscored_replicate_has_no_score(self, replicates):
        _, scores = panel_comparison(
            replicates, source=FIGURE, row_path="annotations[1]"
        )
        assert pd.isna(scores.loc["from_the_caption", "rep-02"])
        assert scores.loc["from_the_caption", "rep-01"] == 0.9


class TestSpuriousRows:
    def test_listed_with_the_replicates_that_invented_them(self, replicates):
        frame = spurious_rows_frame(replicates, check="scale-bar")
        assert frame.to_dict("records") == [
            {
                "source": FIGURE,
                "context_path": "scale-bar",
                "label": "C",
                "replicates": "rep-00, rep-01",
            }
        ]

    def test_another_checks_rows_are_not_listed(self, replicates):
        assert spurious_rows_frame(replicates, check="annotations").empty


class TestPlot:
    def test_one_dot_per_instance_and_customdata_indexes_the_frame(
        self, replicates
    ):
        fig, inst = plot_replicate_mean_scores(replicates, check="scale-bar")
        scatter = next(trace for trace in fig.data if trace.type == "scatter")
        assert len(scatter.customdata) == len(inst) == 4
        assert "rep-01: 0.000 (FN)" in scatter.hovertext[
            list(inst["path"]).index("scale-bar[1].micrograph")
        ]


def test_bars_follow_the_answer_not_the_alphabet(replicates):
    frame = pooled_mean_scores_frame(replicates, check="scale-bar")
    assert list(frame["label"]) == ["panel_label", "micrograph"]


def test_a_nested_rows_fields_stay_together():
    def inst(path):
        return _instance(path, "x", "x", 1.0)

    summary = _replicate(0, [
        inst("scale-bar[0].panel_label"),
        inst("scale-bar[0].units[0].axis"),
        inst("scale-bar[0].units[1].axis"),
        inst("scale-bar[0].units[0].answer"),
        inst("scale-bar[0].units[1].answer"),
        inst("scale-bar[0].decision"),
    ])
    values, _ = panel_comparison(
        [summary], source=FIGURE, row_path="scale-bar[0]"
    )
    assert list(values.index) == [
        "panel_label",
        "decision",
        "units[0].axis",
        "units[0].answer",
        "units[1].axis",
        "units[1].answer",
    ]
