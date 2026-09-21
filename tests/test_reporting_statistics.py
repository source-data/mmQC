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
    arm_contrast,
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
