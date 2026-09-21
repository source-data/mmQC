"""Tests for property-level mean score rollups."""

from __future__ import annotations

from soda_mmqc.core.property_rollup import (
    LAYER1_MEAN_SCORE_ELIGIBLE,
    eligible_instance_count,
    instance_eligible_for_mean_score,
    property_mean_score,
)


def test_property_mean_score_profiled_excludes_na():
    instances = [
        {"score": 1.0, "layer1": "correct_NA"},
        {"score": 0.0, "layer1": LAYER1_MEAN_SCORE_ELIGIBLE},
    ]
    assert property_mean_score(instances, profiled=True) == 0.0


def test_no_eligible_instance_is_not_a_score_of_zero():
    """0.0 is a score a model can earn; "nothing to score" is not.

    This test previously asserted 0.0. Conflating the two injects a
    spurious zero into every mean taken over this property -- across
    replicates, across examples, and into every bar chart -- which is what
    both experiment notebooks had to work around by hand.
    """
    instances = [{"score": 1.0, "layer1": "correct_NA"}]
    assert property_mean_score(instances, profiled=True) is None
    assert eligible_instance_count(instances, profiled=True) == 0


def test_a_genuine_zero_is_still_zero():
    instances = [{"score": 0.0, "layer1": LAYER1_MEAN_SCORE_ELIGIBLE}]
    assert property_mean_score(instances, profiled=True) == 0.0
    assert eligible_instance_count(instances, profiled=True) == 1


def test_no_instances_at_all_is_also_none():
    assert property_mean_score([], profiled=True) is None
    assert eligible_instance_count([], profiled=True) == 0


def test_eligible_counts_only_what_the_mean_used():
    instances = [
        {"score": 1.0, "layer1": LAYER1_MEAN_SCORE_ELIGIBLE},
        {"score": 0.0, "layer1": LAYER1_MEAN_SCORE_ELIGIBLE},
        {"score": 1.0, "layer1": "correct_NA"},
        {"score": None, "layer1": LAYER1_MEAN_SCORE_ELIGIBLE},
    ]
    assert eligible_instance_count(instances, profiled=True) == 2
    assert property_mean_score(instances, profiled=True) == 0.5


def test_an_unprofiled_property_counts_every_scored_instance():
    instances = [{"score": 1.0}, {"score": 0.0}]
    assert eligible_instance_count(instances, profiled=False) == 2
    assert property_mean_score(instances, profiled=False) == 0.5


def test_property_mean_score_unprofiled_includes_all():
    instances = [
        {"score": 1.0},
        {"score": 0.0},
    ]
    assert property_mean_score(instances, profiled=False) == 0.5


def test_instance_eligible_for_mean_score():
    assert instance_eligible_for_mean_score(
        {"score": 1.0, "layer1": LAYER1_MEAN_SCORE_ELIGIBLE},
        profiled=True,
    )
    assert not instance_eligible_for_mean_score(
        {"score": 1.0, "layer1": "correct_NA"},
        profiled=True,
    )
    assert instance_eligible_for_mean_score({"score": 0.5}, profiled=False)


def test_macro_mean_survives_an_ineligible_property():
    """The None path was not exercised by any existing test.

    A green suite after the semantics change proved only that nothing else
    broke -- every fixture had eligible instances. macro_mean summed the
    scores, so a single None would have raised TypeError the first time a
    real check reported a property as correctly not applicable.

    It is skipped rather than zeroed here, and the function is scheduled
    for deletion: it averages across leaf properties, which is the one
    aggregate this codebase must not produce.
    """
    from soda_mmqc.core.eval_manifest import EvalManifest, FieldProfile
    from soda_mmqc.reporting.aggregate import PropertyRollup, RunSummary
    from soda_mmqc.reporting.export_report import macro_mean

    manifest = EvalManifest(
        checklist="c",
        defaults=FieldProfile(),
        list_alignment={},
        _fields={},
        _field_keys={},
    )
    summary = RunSummary(
        checklist="c",
        check="k",
        model="m",
        prompt="p",
        manifest=manifest,
        records=(),
        by_list_row_counts={},
        by_property={
            "a": PropertyRollup(
                mean_score=1.0, eligible=2, layer1_counts={}, layer2_counts={}
            ),
            "b": PropertyRollup(
                mean_score=None, eligible=0,
                layer1_counts={"correct_NA": 1}, layer2_counts={},
            ),
        },
    )

    assert macro_mean(summary) == 1.0
