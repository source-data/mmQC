"""Tests for per-property rollups.

Aggregation happens here and only here, at read time. See
``tests/test_aggregation_boundary.py`` for the separation this enforces.
"""

from __future__ import annotations

from soda_mmqc.core.applicability_and_matching import Layer1Label
from soda_mmqc.core.property_rollup import (
    instance_is_scored,
    property_mean_score,
    rollup_property,
)

APPLICABLE = Layer1Label.CORRECT_APPLICABLE.value
NOT_APPLICABLE = Layer1Label.CORRECT_NA.value


def test_profiled_mean_excludes_instances_that_were_not_applicable():
    instances = [
        {"score": 1.0, "layer1": NOT_APPLICABLE},
        {"score": 0.0, "layer1": APPLICABLE},
    ]
    assert property_mean_score(instances, profiled=True) == 0.0


def test_no_applicable_instance_is_not_a_score_of_zero():
    """0.0 is a score a model can earn; "nothing to score" is not.

    Conflating them injects a spurious zero into every mean taken over
    this property -- across replicates, across examples, and into every
    bar chart -- which is what both experiment notebooks worked around by
    hand.
    """
    instances = [{"score": 1.0, "layer1": NOT_APPLICABLE}]
    rollup = rollup_property(instances, profiled=True)
    assert rollup.mean_score is None
    assert rollup.n_scored == 0
    assert rollup.n_instances == 1


def test_a_genuine_zero_is_still_zero():
    rollup = rollup_property(
        [{"score": 0.0, "layer1": APPLICABLE}], profiled=True
    )
    assert rollup.mean_score == 0.0
    assert rollup.n_scored == 1


def test_no_instances_at_all_is_also_none():
    rollup = rollup_property([], profiled=True)
    assert rollup.mean_score is None
    assert rollup.n_scored == 0
    assert rollup.n_instances == 0


def test_the_denominator_is_not_a_second_stored_number():
    """n_scored is derived from the layer-1 count, not stored beside it."""
    instances = [
        {"score": 1.0, "layer1": APPLICABLE},
        {"score": 0.0, "layer1": APPLICABLE},
        {"score": 1.0, "layer1": NOT_APPLICABLE},
    ]
    rollup = rollup_property(instances, profiled=True)
    assert rollup.mean_score == 0.5
    assert rollup.n_scored == rollup.layer1_counts[APPLICABLE] == 2
    assert "n_scored" not in vars(rollup), (
        "n_scored must be a derived property, not a field that can drift "
        "from layer1_counts"
    )


def test_an_unprofiled_property_scores_every_instance():
    rollup = rollup_property([{"score": 1.0}, {"score": 0.0}], profiled=False)
    assert rollup.mean_score == 0.5
    assert rollup.layer1_counts == {}
    assert rollup.n_scored == 2


def test_instance_is_scored():
    assert instance_is_scored(
        {"score": 1.0, "layer1": APPLICABLE}, profiled=True
    )
    assert not instance_is_scored(
        {"score": 1.0, "layer1": NOT_APPLICABLE}, profiled=True
    )
    assert instance_is_scored({"score": 0.5}, profiled=False)
