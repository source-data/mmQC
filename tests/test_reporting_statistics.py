"""Statistics over runs: one leaf property at a time, two variance axes.

The unit of measurement is one leaf property. Variation comes from where
the example came from and from which replicate measured it, and nothing
here ever pools two properties together.
"""

from __future__ import annotations

import pandas as pd
import pytest

from soda_mmqc.core.applicability_and_matching import Layer1Label
from soda_mmqc.core.eval_manifest import (
    EvalManifest,
    FieldProfile,
    MatchingMetric,
)
from soda_mmqc.reporting.aggregate import (
    SCORES_FRAME_COLUMNS,
    NON_RESPONSE_COLUMNS,
    arm_contrast,
    arm_levels,
    non_response_counts,
    property_path,
    replicate_spread,
    scores_frame,
)
from soda_mmqc.reporting.load import FlatRecord, FlatRun, FlatRuns, RunRef

CHECK = "replication-reporting"
MODEL = "claude-sonnet-5"
APPLICABLE = Layer1Label.CORRECT_APPLICABLE.value
NOT_APPLICABLE = Layer1Label.CORRECT_NA.value


#: Profiled, because that is the case the statistics are about: layer 2
#: is conditional on layer 1, and an unprofiled property has no layer-1
#: label to be conditional on.
_PROFILE = FieldProfile(matching_metric=MatchingMetric.BINARY_POLARITY)


def _manifest(properties=("p1", "p2")) -> EvalManifest:
    return EvalManifest(
        checklist="c",
        defaults=FieldProfile(),
        list_alignment={},
        _fields={name: _PROFILE for name in properties},
        _field_keys={name: frozenset({"matching_metric"}) for name in properties},
    )


def _record(example: str, scores: dict[str, float | None]) -> FlatRecord:
    instances = []
    for leaf_property, score in scores.items():
        instance: dict = {"leaf_property": leaf_property}
        if score is None:
            instance |= {"score": 1.0, "layer1": NOT_APPLICABLE}
        else:
            instance |= {"score": score, "layer1": APPLICABLE}
        instances.append(instance)
    return FlatRecord(
        doc_id=example,
        metadata={"source": example},
        analysis={"instances": instances, "by_list": {}},
    )


def _run(*, arm: str, replicate: int, records) -> FlatRun:
    return FlatRun(
        ref=RunRef(
            checklist="c",
            check=CHECK,
            model=MODEL,
            arm=arm,
            replicate=replicate,
        ),
        records=tuple(records),
        manifest=_manifest(),
    )


class TestScoresFrame:
    def test_one_row_per_property_per_replicate_per_example(self):
        """The tidy frame both experiment notebooks built by hand.

        Keeping property on the row -- never collapsed into it -- is what
        makes every downstream statistic per-property by construction.
        """
        runs = FlatRuns(
            [
                _run(
                    arm="pinned",
                    replicate=0,
                    records=[_record("doc-a", {"p1": 1.0, "p2": 0.5})],
                ),
                _run(
                    arm="pinned",
                    replicate=1,
                    records=[_record("doc-a", {"p1": 0.0, "p2": 0.5})],
                ),
            ]
        )

        frame = scores_frame(runs)

        assert len(frame) == 4
        assert list(frame.columns) == list(SCORES_FRAME_COLUMNS)
        panel = frame[frame["property"] == "p1"]
        assert sorted(panel["mean_score"].dropna()) == [0.0, 1.0]
        assert set(panel["replicate"]) == {0, 1}

    def test_the_example_axis_survives(self):
        """aggregate_run pools examples; this frame must not."""
        runs = FlatRuns(
            [
                _run(
                    arm="pinned",
                    replicate=0,
                    records=[
                        _record("doc-a", {"p1": 1.0}),
                        _record("doc-b", {"p1": 0.0}),
                    ],
                )
            ]
        )

        frame = scores_frame(runs)

        assert set(frame["example"]) == {"doc-a", "doc-b"}
        assert sorted(frame["mean_score"]) == [0.0, 1.0]

    def test_an_inapplicable_property_is_a_row_with_a_null_score(self):
        """Absent is not zero, and the row must still exist.

        Dropping it would make the property look unmeasured; writing 0.0
        would make it look wrong. The row carries NA with n_scored 0.
        """
        runs = FlatRuns(
            [
                _run(
                    arm="pinned",
                    replicate=0,
                    records=[_record("doc-a", {"p1": None})],
                )
            ]
        )

        frame = scores_frame(runs)
        row = frame.iloc[0]

        assert pd.isna(row["mean_score"])
        assert row["n_scored"] == 0
        assert row["n_instances"] == 1

    def test_a_null_score_survives_a_groupby(self):
        """Float64 rather than float64: a mean must not see a false zero."""
        runs = FlatRuns(
            [
                _run(
                    arm="pinned",
                    replicate=0,
                    records=[_record("doc-a", {"p1": None})],
                ),
                _run(
                    arm="pinned",
                    replicate=1,
                    records=[_record("doc-a", {"p1": 1.0})],
                ),
            ]
        )

        frame = scores_frame(runs)
        pooled = frame.groupby("property")["mean_score"].mean()

        assert pooled["p1"] == 1.0, (
            "the inapplicable replicate must be skipped, not averaged in "
            "as a zero"
        )

    def test_it_never_collapses_two_properties(self):
        runs = FlatRuns(
            [
                _run(
                    arm="pinned",
                    replicate=0,
                    records=[_record("doc-a", {"p1": 1.0, "p2": 0.0})],
                )
            ]
        )
        frame = scores_frame(runs)
        assert set(frame["property"]) == {"p1", "p2"}
        assert len(frame) == 2

    def test_arms_stay_distinct(self):
        runs = FlatRuns(
            [
                _run(
                    arm="pinned",
                    replicate=0,
                    records=[_record("doc-a", {"p1": 1.0})],
                ),
                _run(
                    arm=f"{CHECK}@v2",
                    replicate=0,
                    records=[_record("doc-a", {"p1": 0.0})],
                ),
            ]
        )
        frame = scores_frame(runs)
        by_arm = frame.set_index("arm")["mean_score"]
        assert by_arm["pinned"] == 1.0
        assert by_arm[f"{CHECK}@v2"] == 0.0

    def test_an_empty_run_set_still_has_the_columns(self):
        frame = scores_frame(FlatRuns([]))
        assert list(frame.columns) == list(SCORES_FRAME_COLUMNS)
        assert frame.empty


def _frame(rows) -> pd.DataFrame:
    """A scores_frame-shaped table from (arm, rep, example, prop, mean, n)."""
    return pd.DataFrame(
        [
            {
                "check": CHECK,
                "model": MODEL,
                "arm": arm,
                "replicate": replicate,
                "example": example,
                "property": leaf_property,
                "mean_score": mean_score,
                "n_scored": n_scored,
                "n_instances": max(n_scored, 1),
            }
            for arm, replicate, example, leaf_property, mean_score, n_scored
            in rows
        ],
        columns=list(SCORES_FRAME_COLUMNS),
    ).astype({"mean_score": "Float64"})


class TestReplicateSpread:
    def test_spread_is_computed_within_a_property_never_across(self):
        frame = _frame([
            ("pinned", 0, "doc-a", "p1", 1.0, 2),
            ("pinned", 1, "doc-a", "p1", 0.0, 2),
            ("pinned", 0, "doc-a", "p2", 0.5, 2),
            ("pinned", 1, "doc-a", "p2", 0.5, 2),
        ])
        spread = replicate_spread(frame).set_index("property")

        assert spread.loc["p1", "mean"] == 0.5
        assert spread.loc["p1", "sd"] == pytest.approx(0.7071, rel=1e-3)
        assert spread.loc["p2", "sd"] == 0.0
        assert len(spread) == 2, "one row per property; never a pooled row"

    def test_a_replicate_with_nothing_applicable_is_not_a_zero(self):
        """The Task 1 defect, on the replicate axis.

        rep-01 scored nothing for this property. Treating that as 0.0
        would halve the mean and manufacture a spread out of nothing.
        """
        frame = _frame([
            ("pinned", 0, "doc-a", "p1", 1.0, 3),
            ("pinned", 1, "doc-a", "p1", None, 0),
        ])
        spread = replicate_spread(frame).iloc[0]

        assert spread["mean"] == 1.0
        assert spread["n_replicates"] == 1
        assert pd.isna(spread["sd"]), "one replicate has no spread"

    def test_sd_is_na_with_a_single_replicate(self):
        frame = _frame([("pinned", 0, "doc-a", "p1", 1.0, 1)])
        assert pd.isna(replicate_spread(frame).iloc[0]["sd"])

    def test_spread_reports_the_denominator_it_used(self):
        """A layer-2 mean without its scored count is not reportable."""
        frame = _frame([
            ("pinned", 0, "doc-a", "p1", 1.0, 4),
            ("pinned", 1, "doc-a", "p1", 1.0, 2),
            ("pinned", 2, "doc-a", "p1", None, 0),
        ])
        row = replicate_spread(frame).iloc[0]
        assert row["n_replicates"] == 2
        assert row["n_scored_total"] == 6

    def test_examples_are_collapsed_before_replicates(self):
        """The SD is over replicates, not over examples.

        Two examples per replicate, each replicate internally consistent:
        the spread across replicates is zero even though examples differ.
        """
        frame = _frame([
            ("pinned", 0, "doc-a", "p1", 1.0, 1),
            ("pinned", 0, "doc-b", "p1", 0.0, 1),
            ("pinned", 1, "doc-a", "p1", 1.0, 1),
            ("pinned", 1, "doc-b", "p1", 0.0, 1),
        ])
        row = replicate_spread(frame).iloc[0]
        assert row["mean"] == 0.5
        assert row["sd"] == 0.0

    def test_arms_are_never_pooled_with_each_other(self):
        frame = _frame([
            ("pinned", 0, "doc-a", "p1", 1.0, 1),
            ("v2", 0, "doc-a", "p1", 0.0, 1),
        ])
        spread = replicate_spread(frame).set_index("arm")
        assert len(spread) == 2
        assert spread.loc["pinned", "mean"] == 1.0
        assert spread.loc["v2", "mean"] == 0.0


class TestArmContrast:
    def test_it_pairs_by_example_within_a_property(self):
        """Pairing cancels whatever is common to both arms."""
        frame = _frame([
            ("pinned", 0, "doc-a", "p1", 1.0, 1),
            ("pinned", 0, "doc-b", "p1", 0.0, 1),
            ("v2", 0, "doc-a", "p1", 0.5, 1),
            ("v2", 0, "doc-b", "p1", 0.0, 1),
        ])
        contrast = arm_contrast(frame, baseline="pinned", variant="v2").iloc[0]

        assert contrast["property"] == "p1"
        assert contrast["difference"] == pytest.approx(-0.25)
        assert contrast["n_examples"] == 2

    def test_it_drops_an_example_only_one_arm_scored(self):
        frame = _frame([
            ("pinned", 0, "doc-a", "p1", 1.0, 1),
            ("pinned", 0, "doc-b", "p1", 1.0, 1),
            ("v2", 0, "doc-a", "p1", 0.0, 1),
        ])
        contrast = arm_contrast(frame, baseline="pinned", variant="v2").iloc[0]
        assert contrast["n_examples"] == 1
        assert contrast["difference"] == pytest.approx(-1.0)

    def test_a_shrunken_pairing_announces_itself(self):
        """The conditioning confound, made visible.

        Each arm's layer-2 mean is over its own applicable set. An arm
        that judges a property inapplicable more often is scored on a
        subset it selected -- plausibly the easy cases -- so a difference
        computed on a shrunken paired set must say how shrunken it is.
        """
        frame = _frame([
            ("pinned", 0, "doc-a", "p1", 1.0, 1),
            ("pinned", 0, "doc-b", "p1", 1.0, 1),
            ("pinned", 0, "doc-c", "p1", 1.0, 1),
            ("v2", 0, "doc-a", "p1", 1.0, 1),
            ("v2", 0, "doc-b", "p1", None, 0),
            ("v2", 0, "doc-c", "p1", None, 0),
        ])
        contrast = arm_contrast(frame, baseline="pinned", variant="v2").iloc[0]

        assert contrast["difference"] == 0.0, (
            "on the one example both arms scored they agree -- which is "
            "exactly the misleading reading this row must qualify"
        )
        assert contrast["n_examples"] == 1
        assert contrast["n_baseline_only"] == 2
        assert contrast["n_variant_only"] == 0
        assert contrast["paired_fraction"] == pytest.approx(1 / 3)

    def test_replicates_are_averaged_before_pairing(self):
        """Replicates are resamples: they reduce noise, not add rows."""
        frame = _frame([
            ("pinned", 0, "doc-a", "p1", 1.0, 1),
            ("pinned", 1, "doc-a", "p1", 0.0, 1),
            ("v2", 0, "doc-a", "p1", 1.0, 1),
            ("v2", 1, "doc-a", "p1", 1.0, 1),
        ])
        contrast = arm_contrast(frame, baseline="pinned", variant="v2").iloc[0]
        assert contrast["n_examples"] == 1, "one example, not four rows"
        assert contrast["difference"] == pytest.approx(0.5)

    def test_se_needs_two_examples(self):
        frame = _frame([
            ("pinned", 0, "doc-a", "p1", 1.0, 1),
            ("v2", 0, "doc-a", "p1", 0.0, 1),
        ])
        contrast = arm_contrast(frame, baseline="pinned", variant="v2").iloc[0]
        assert contrast["n_examples"] == 1
        assert pd.isna(contrast["se"])

    def test_it_never_pools_properties(self):
        frame = _frame([
            ("pinned", 0, "doc-a", "p1", 1.0, 1),
            ("pinned", 0, "doc-a", "p2", 0.0, 1),
            ("v2", 0, "doc-a", "p1", 0.0, 1),
            ("v2", 0, "doc-a", "p2", 1.0, 1),
        ])
        contrast = arm_contrast(
            frame, baseline="pinned", variant="v2"
        ).set_index("property")

        assert len(contrast) == 2
        assert contrast.loc["p1", "difference"] == pytest.approx(-1.0)
        assert contrast.loc["p2", "difference"] == pytest.approx(1.0)

    def test_an_unknown_arm_is_named(self):
        frame = _frame([("pinned", 0, "doc-a", "p1", 1.0, 1)])
        with pytest.raises(ValueError, match="no-such-arm"):
            arm_contrast(frame, baseline="pinned", variant="no-such-arm")


def _record_with_rows(
    example: str, correct: int, missing: int, spurious: int
) -> FlatRecord:
    """A record whose layer-S row counts say what the session returned."""
    return FlatRecord(
        doc_id=example,
        metadata={"source": example},
        analysis={
            "instances": [],
            "by_list": {
                "outputs": {
                    "row_counts": {
                        "correct_row": correct,
                        "missing_row": missing,
                        "spurious_row": spurious,
                    },
                    "rows": [],
                }
            },
        },
    )


class TestNonResponse:
    def test_an_empty_answer_is_counted_not_excluded(self):
        """A skill so thin the model returns nothing is a result, not a gap.

        Dropping these would make the failing arm look better.
        """
        runs = FlatRuns([
            _run(arm="v2", replicate=0, records=[
                _record_with_rows("doc-a", 0, 4, 0),
                _record_with_rows("doc-b", 3, 1, 0),
            ]),
        ])
        counts = non_response_counts(runs)

        assert counts["empty"].sum() == 1
        assert bool(
            counts.loc[counts["example"] == "doc-a", "empty"].item()
        ) is True
        assert bool(
            counts.loc[counts["example"] == "doc-b", "empty"].item()
        ) is False

    def test_it_is_reported_per_arm_and_replicate(self):
        runs = FlatRuns([
            _run(arm="pinned", replicate=0,
                 records=[_record_with_rows("doc-a", 4, 0, 0)]),
            _run(arm="v2", replicate=0,
                 records=[_record_with_rows("doc-a", 0, 4, 0)]),
        ])
        counts = non_response_counts(runs)
        by_arm = counts.groupby("arm")["empty"].sum()

        assert by_arm["pinned"] == 0
        assert by_arm["v2"] == 1
        assert set(counts["replicate"]) == {0}

    def test_a_genuinely_empty_benchmark_row_is_not_non_response(self):
        """Nothing expected and nothing returned is not a failure.

        correct_row 0 with missing_row 0 means the gold had no rows
        either -- the session agreed there was nothing to report.
        """
        runs = FlatRuns([
            _run(arm="pinned", replicate=0,
                 records=[_record_with_rows("doc-a", 0, 0, 0)]),
        ])
        counts = non_response_counts(runs)
        assert bool(counts.iloc[0]["empty"]) is False

    def test_a_spurious_only_answer_is_not_non_response(self):
        """The model answered, just wrongly. That is a layer-S error."""
        runs = FlatRuns([
            _run(arm="pinned", replicate=0,
                 records=[_record_with_rows("doc-a", 0, 0, 3)]),
        ])
        counts = non_response_counts(runs)
        row = counts.iloc[0]
        assert bool(row["empty"]) is False
        assert row["spurious_row"] == 3

    def test_the_row_counts_travel_with_the_flag(self):
        """So a reader can see how much was missed, not just that it was."""
        runs = FlatRuns([
            _run(arm="v2", replicate=0,
                 records=[_record_with_rows("doc-a", 0, 7, 0)]),
        ])
        row = non_response_counts(runs).iloc[0]
        assert row["correct_row"] == 0
        assert row["missing_row"] == 7
        assert row["list_key"] == "outputs"

    def test_an_empty_run_set_still_has_the_columns(self):
        counts = non_response_counts(FlatRuns([]))
        assert list(counts.columns) == list(NON_RESPONSE_COLUMNS)
        assert counts.empty


class TestNoCrossPropertySummary:
    """The constraint, asserted against the module that broke it."""

    def test_macro_mean_is_gone(self):
        """It averaged mean_score over properties and ranked arms by it.

        panel_label and micrograph measure different things; a number
        mixing them hides an arm that improves one and degrades the
        other.
        """
        from soda_mmqc.reporting import export_report

        assert not hasattr(export_report, "macro_mean")
        assert not hasattr(export_report, "winner_lines")

    def test_the_scores_table_has_no_summary_column(self):
        from soda_mmqc.reporting.export_report import ArmScoreRow, scores_table

        rows = [
            ArmScoreRow("m1", "pinned", 10, {"a": 0.8, "b": 0.2}),
            ArmScoreRow("m1", "c@v2", 10, {"a": 0.9, "b": 0.1}),
        ]
        table = scores_table(rows)

        assert "macro" not in table.columns
        assert {"model", "arm", "docs", "a", "b"} <= set(table.columns)

    def test_the_winner_is_reported_per_property(self):
        """An arm that improves one property and degrades another.

        The old single line called this a winner. Per property it is
        visibly a trade, which is the finding.
        """
        from soda_mmqc.reporting.export_report import (
            ArmScoreRow,
            best_arm_per_property,
        )

        rows = [
            ArmScoreRow("m1", "pinned", 10, {"a": 0.8, "b": 0.9}),
            ArmScoreRow("m1", "c@v2", 10, {"a": 0.9, "b": 0.1}),
        ]
        lines = best_arm_per_property(rows)

        assert lines == [
            "m1 / a: c@v2 (0.900)",
            "m1 / b: pinned (0.900)",
        ]

    def test_a_property_nothing_scored_says_so(self):
        from soda_mmqc.reporting.export_report import (
            ArmScoreRow,
            best_arm_per_property,
        )

        rows = [ArmScoreRow("m1", "pinned", 10, {"a": None})]
        assert best_arm_per_property(rows) == [
            "m1 / a: nothing applicable in any arm"
        ]


class TestMeanScoreBars:
    def _summary_frame(self):
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "leaf_property": "p1",
                    "field": "p1",
                    "mean_score": 0.5,
                    "n_scored": 4,
                },
                {
                    "leaf_property": "p2",
                    "field": "p2",
                    "mean_score": None,
                    "n_scored": 0,
                },
            ]
        )

    def test_a_bar_with_nothing_applicable_is_a_gap_not_a_zero(self):
        from soda_mmqc.reporting.plots import plot_mean_score_bars

        fig = plot_mean_score_bars(self._summary_frame())
        values = list(fig.data[0].y)

        assert values[0] == 0.5
        assert values[1] is None, (
            "a gap says 'nothing to score here'; a zero bar says "
            "'scored zero'"
        )

    def test_the_denominator_is_in_the_hover(self):
        from soda_mmqc.reporting.plots import plot_mean_score_bars

        fig = plot_mean_score_bars(self._summary_frame())
        assert list(fig.data[0].customdata) == [4, 0]
        assert "scored instance" in fig.data[0].hovertemplate

    def test_error_bars_come_from_replicate_spread(self):
        import pandas as pd

        from soda_mmqc.reporting.plots import plot_mean_score_bars

        spread = pd.DataFrame(
            [
                {"arm": "pinned", "property": "p1", "sd": 0.25},
                {"arm": "pinned", "property": "p2", "sd": pd.NA},
            ]
        )
        fig = plot_mean_score_bars(
            self._summary_frame(), spread=spread, arm="pinned"
        )

        assert fig.data[0].error_y.array is not None, (
            "two arms plotted without spread, once replicates exist, is "
            "actively misleading"
        )
        assert list(fig.data[0].error_y.array) == [0.25, None]

    def test_no_spread_means_no_error_bars(self):
        from soda_mmqc.reporting.plots import plot_mean_score_bars

        fig = plot_mean_score_bars(self._summary_frame())
        assert fig.data[0].error_y.array is None

    def test_a_single_replicate_gets_no_error_bar(self):
        """sd is NA below two replicates; a zero bar would claim
        perfect reproducibility from one measurement."""
        import pandas as pd

        from soda_mmqc.reporting.plots import plot_mean_score_bars

        spread = pd.DataFrame(
            [{"arm": "pinned", "property": "p1", "sd": pd.NA}]
        )
        fig = plot_mean_score_bars(
            self._summary_frame(), spread=spread, arm="pinned"
        )
        assert fig.data[0].error_y.array is None


class TestPropertyPath:
    """A property's label says where it came from, not just what it is.

    `outputs[].panel_label` appears in all eleven exp-01 checks, so a
    table or a plot keyed on the property alone puts eleven different
    measurements under one name. The path prefixes the axes that locate
    it, and writes a pooled axis as an empty segment so the delimiter
    doubles: position is preserved, and `split(":")` always gives five
    fields back.
    """

    def test_every_axis_present(self):
        assert property_path(
            "micrograph-scale-bar",
            "outputs[].panel_label",
            arm="pinned",
            replicate=0,
            example="10.1038_x/content/1",
        ) == (
            "micrograph-scale-bar:pinned:rep-00:10.1038_x/content/1"
            ":outputs[].panel_label"
        )

    def test_a_pooled_axis_is_an_empty_segment(self):
        assert property_path(
            "micrograph-scale-bar",
            "outputs[].panel_label",
            arm="pinned",
        ) == "micrograph-scale-bar:pinned:::outputs[].panel_label"

    def test_everything_pooled_but_the_check(self):
        assert property_path(
            "micrograph-scale-bar", "outputs[].panel_label"
        ) == "micrograph-scale-bar::::outputs[].panel_label"

    def test_it_round_trips_to_five_fields(self):
        """Positional, so a reader can always say which axis is missing."""
        path = property_path(
            "micrograph-scale-bar", "outputs[].panel_label", arm="pinned"
        )
        check, arm, replicate, example, leaf_property = path.split(":")
        assert check == "micrograph-scale-bar"
        assert arm == "pinned"
        assert (replicate, example) == ("", "")
        assert leaf_property == "outputs[].panel_label"

    def test_the_property_keeps_its_json_path(self):
        """plot-axis-units has two distinct properties tailing in `axis`.

        Stripping the within-record path would collide them inside a
        single check, which no amount of prefix can disambiguate.
        """
        first = property_path("plot-axis-units", "outputs[].units_provided[].axis")
        second = property_path(
            "plot-axis-units", "outputs[].unit_definition_as_provided[].axis"
        )
        assert first != second


class TestFramesCarryThePath:
    def test_scores_frame_pools_nothing(self):
        runs = FlatRuns(
            [_run(arm="pinned", replicate=0, records=[_record("doc-a", {"p1": 1.0})])]
        )

        frame = scores_frame(runs)

        assert frame["path"].tolist() == [f"{CHECK}:pinned:rep-00:doc-a:p1"]

    def test_replicate_spread_pools_replicate_and_example(self):
        runs = FlatRuns(
            [
                _run(arm="pinned", replicate=r, records=[_record("doc-a", {"p1": 1.0})])
                for r in (0, 1)
            ]
        )

        spread = replicate_spread(scores_frame(runs))

        assert spread["path"].tolist() == [f"{CHECK}:pinned:::p1"]

    def test_arm_contrast_pools_arm_replicate_and_example(self):
        runs = FlatRuns(
            [
                _run(arm="pinned", replicate=0, records=[_record("doc-a", {"p1": 1.0})]),
                _run(arm="v2", replicate=0, records=[_record("doc-a", {"p1": 0.5})]),
            ]
        )

        contrast = arm_contrast(scores_frame(runs), baseline="pinned", variant="v2")

        assert contrast["path"].tolist() == [f"{CHECK}::::p1"]


class TestArmLevels:
    """The absolute score each arm earned on the set they can be compared on.

    A grouped bar chart of the two arms sits beside the difference chart,
    so the gap a reader measures between the bars has to be the number
    the other chart plots. Taking each arm's mean over its own examples
    does not give that: on exp-01 it disagreed for 17 of 67 contrasts, by
    up to 0.14, and flipped the sign of stat-test's `explanation`.
    """

    @staticmethod
    def _runs_with_incomplete_pairing():
        """`v2` judged p1 inapplicable on doc-b, so only doc-a pairs.

        Own-set means: pinned (1.0 + 0.0) / 2 = 0.5, v2 = 0.5, so a naive
        difference is 0.0. Paired on doc-a alone it is 0.5 - 1.0 = -0.5.
        """
        return FlatRuns(
            [
                _run(
                    arm="pinned",
                    replicate=0,
                    records=[
                        _record("doc-a", {"p1": 1.0}),
                        _record("doc-b", {"p1": 0.0}),
                    ],
                ),
                _run(
                    arm="v2",
                    replicate=0,
                    records=[
                        _record("doc-a", {"p1": 0.5}),
                        _record("doc-b", {"p1": None}),
                    ],
                ),
            ]
        )

    def test_one_row_per_arm_per_property(self):
        frame = scores_frame(self._runs_with_incomplete_pairing())
        levels = arm_levels(frame, baseline="pinned", variant="v2")
        assert sorted(levels["arm"]) == ["pinned", "v2"]
        assert set(levels["property"]) == {"p1"}

    def test_the_gap_between_the_bars_is_the_plotted_difference(self):
        """The invariant the whole function exists for."""
        frame = scores_frame(self._runs_with_incomplete_pairing())
        levels = arm_levels(frame, baseline="pinned", variant="v2").set_index("arm")
        contrast = arm_contrast(frame, baseline="pinned", variant="v2")

        gap = float(levels.loc["v2", "mean"]) - float(levels.loc["pinned", "mean"])
        assert gap == pytest.approx(float(contrast.loc[0, "difference"]))

    def test_it_is_the_paired_mean_not_the_arm_s_own(self):
        frame = scores_frame(self._runs_with_incomplete_pairing())
        levels = arm_levels(frame, baseline="pinned", variant="v2").set_index("arm")
        assert float(levels.loc["pinned", "mean"]) == pytest.approx(1.0)
        assert float(levels.loc["v2", "mean"]) == pytest.approx(0.5)
        assert set(levels["n_examples"]) == {1}

    def test_a_property_with_no_pairing_at_all_is_absent(self):
        runs = FlatRuns(
            [
                _run(arm="pinned", replicate=0, records=[_record("doc-a", {"p1": 1.0})]),
                _run(arm="v2", replicate=0, records=[_record("doc-b", {"p1": 0.5})]),
            ]
        )
        levels = arm_levels(scores_frame(runs), baseline="pinned", variant="v2")
        assert levels.empty

    def test_it_refuses_an_arm_that_is_not_there(self):
        frame = scores_frame(self._runs_with_incomplete_pairing())
        with pytest.raises(ValueError, match="nope"):
            arm_levels(frame, baseline="pinned", variant="nope")
