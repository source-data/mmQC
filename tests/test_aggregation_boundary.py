"""Measuring and aggregating are separate concerns, in separate places.

`eval-manifest.json` carries the metrics and thresholds. Those are inputs
we adjust: re-tuning a threshold and re-reporting is a normal thing to do,
and it must not require re-running the evaluator.

So the split is:

* **Measure** -- `core/evaluation.py` compares prediction to gold under the
  manifest and emits one record per instance: layer-S structural outcome,
  layer-1 applicability label, layer-2 matching label, score. That is what
  `analysis.json` stores.
* **Aggregate** -- `core/property_rollup.py` turns those instances into
  per-property rollups, at read time, from the manifest as it is *now*.

Before this split, `by_property` was computed at scoring time and stored,
while `reporting/aggregate.py` recomputed the same thing from `instances`
and ignored the stored copy -- and `tables.py` read the stored copy. Two
live paths to the same number, agreeing only for as long as nobody touched
a threshold.
"""

from __future__ import annotations

import json
from pathlib import Path

from soda_mmqc.core.applicability_and_matching import Layer1Label

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def test_analysis_json_stores_measurements_not_aggregates():
    """`by_property` must not be in the serialized analysis.

    It is derived from `instances` plus the manifest. Storing it makes a
    cache with no invalidation: change a threshold, re-report without
    re-scoring, and the stored rollup silently disagrees with a fresh one.
    """
    for snapshot in sorted((FIXTURES / "evaluation_snapshots").glob("*.json")):
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
        assert "by_property" not in payload, (
            f"{snapshot.name} still stores a derived rollup; aggregation "
            "belongs at read time, in core/property_rollup.py"
        )
        assert "instances" in payload
        assert "by_list" in payload


def test_the_evaluator_emits_no_property_rollup():
    import soda_mmqc.core.evaluation as evaluation

    assert not hasattr(evaluation, "PropertySummary"), (
        "PropertySummary was the scoring-time rollup; aggregation moved to "
        "core/property_rollup.py, which runs at read time"
    )


def test_there_is_one_name_for_a_scorable_instance():
    """`eligible` was a fifth word for an existing layer-1 label.

    Layer 1 already names the four applicability outcomes. A rollup's
    denominator is the count of `correct_applicable`, not a separately
    stored number that duplicates it.
    """
    import soda_mmqc.core.property_rollup as rollup

    assert not hasattr(rollup, "eligible_instance_count"), (
        "the denominator is layer1_counts[correct_applicable]"
    )
    source = Path(rollup.__file__).read_text(encoding="utf-8")
    assert "LAYER1_MEAN_SCORE_ELIGIBLE" not in source, (
        "use Layer1Label.CORRECT_APPLICABLE rather than a second constant "
        "naming the same label"
    )


def test_the_denominator_is_the_layer1_count():
    from soda_mmqc.core.property_rollup import rollup_property

    instances = [
        {"score": 1.0, "layer1": Layer1Label.CORRECT_APPLICABLE.value},
        {"score": 0.0, "layer1": Layer1Label.CORRECT_APPLICABLE.value},
        {"score": 1.0, "layer1": Layer1Label.CORRECT_NA.value},
    ]
    result = rollup_property(instances, profiled=True)

    assert result.mean_score == 0.5
    assert result.n_scored == 2
    assert result.n_scored == result.layer1_counts[
        Layer1Label.CORRECT_APPLICABLE.value
    ], "the denominator is not a second number; it is the layer-1 count"
    assert result.n_instances == 3


def test_an_unprofiled_property_scores_every_instance():
    """With no layer-1 labels there is no correct_applicable to count."""
    from soda_mmqc.core.property_rollup import rollup_property

    result = rollup_property(
        [{"score": 1.0}, {"score": 0.0}], profiled=False
    )
    assert result.mean_score == 0.5
    assert result.layer1_counts == {}
    assert result.n_scored == 2
    assert result.n_instances == 2


def test_nothing_applicable_is_not_a_score_of_zero():
    from soda_mmqc.core.property_rollup import rollup_property

    result = rollup_property(
        [{"score": 1.0, "layer1": Layer1Label.CORRECT_NA.value}],
        profiled=True,
    )
    assert result.mean_score is None
    assert result.n_scored == 0
    assert result.n_instances == 1
