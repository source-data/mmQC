"""Statistics over runs: one leaf property at a time, two variance axes.

The unit of measurement is one leaf property. Variation comes from where
the example came from and from which replicate measured it, and nothing
here ever pools two properties together.
"""

from __future__ import annotations

import pandas as pd

from soda_mmqc.core.applicability_and_matching import Layer1Label
from soda_mmqc.core.eval_manifest import (
    EvalManifest,
    FieldProfile,
    MatchingMetric,
)
from soda_mmqc.reporting.aggregate import SCORES_FRAME_COLUMNS, scores_frame
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
