"""Aggregate scored leaf instances into per-property rollups.

This is the *only* place instances become statistics, and it runs at read
time, never at scoring time. The division it implements:

* ``core/evaluation.py`` **measures** -- it compares prediction to gold
  under ``eval-manifest.json`` and emits one record per instance carrying
  a score and its layer-1 / layer-2 labels. That is what ``analysis.json``
  stores, and it is raw.
* this module **aggregates** those instances, using the manifest as it is
  when the report is built.

The manifest holds metrics and thresholds, and those are inputs we tune.
Re-tuning one and re-reporting must not require re-running the evaluator,
which is only true if nothing derived from the manifest is stored beside
the measurements. ``by_property`` used to be stored *and* recomputed --
``reporting/tables.py`` read the stored copy while
``reporting/aggregate.py`` recomputed its own, and the two agreed only
until someone moved a threshold.

Vocabulary: layer 1 already names the four applicability outcomes
(:class:`Layer1Label`). A rollup's denominator is the count of
``correct_applicable`` instances -- not a separate quantity with a
separate name.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from soda_mmqc.core.applicability_and_matching import Layer1Label

__all__ = [
    "PropertyRollup",
    "rollup_property",
    "rollup_by_property",
    "instance_is_scored",
]


def _instance_score(instance: Any) -> float | None:
    score = (
        instance.get("score") if isinstance(instance, dict) else instance.score
    )
    if isinstance(score, (int, float)):
        return float(score)
    return None


def _instance_layer1(instance: Any) -> str | None:
    layer1 = (
        instance.get("layer1")
        if isinstance(instance, dict)
        else instance.layer1
    )
    return layer1 if isinstance(layer1, str) else None


def _instance_layer2(instance: Any) -> str | None:
    layer2 = (
        instance.get("layer2")
        if isinstance(instance, dict)
        else instance.layer2
    )
    return layer2 if isinstance(layer2, str) else None


def instance_is_scored(instance: Any, *, profiled: bool) -> bool:
    """Whether this instance contributes to its property's mean score.

    Layer 2 is conditional on layer 1: for a profiled property, only an
    instance the model judged applicable *and* judged so correctly says
    anything about matching quality. Whether it judged applicability
    rightly is layer 1's question, answered by ``layer1_counts``.
    """
    if _instance_score(instance) is None:
        return False
    if profiled:
        return (
            _instance_layer1(instance)
            == Layer1Label.CORRECT_APPLICABLE.value
        )
    return True


@dataclass(frozen=True)
class PropertyRollup:
    """One leaf property's instances, rolled up. Always derived.

    ``mean_score`` is ``None`` when :attr:`n_scored` is 0 -- the property
    had nothing to score here, which is not the same as scoring zero. Read
    the two together: an arm that judges a property inapplicable more often
    is scored on fewer, self-selected cases, so a mean without its
    denominator is not a reportable number.
    """

    mean_score: float | None
    profiled: bool
    n_instances: int
    layer1_counts: dict[str, int]
    layer2_counts: dict[str, int]

    @property
    def n_scored(self) -> int:
        """The mean's denominator.

        Derived rather than stored, because for a profiled property it is
        exactly the ``correct_applicable`` layer-1 count, and two fields
        holding one number drift.
        """
        if self.profiled:
            return self.layer1_counts.get(
                Layer1Label.CORRECT_APPLICABLE.value, 0
            )
        return self.n_instances


def rollup_property(
    instances: Sequence[Any],
    *,
    profiled: bool,
) -> PropertyRollup:
    """Roll one leaf property's instances into a :class:`PropertyRollup`."""
    scores = [
        _instance_score(instance)
        for instance in instances
        if instance_is_scored(instance, profiled=profiled)
    ]
    layer1 = Counter(
        label
        for label in (_instance_layer1(i) for i in instances)
        if label is not None
    )
    layer2 = Counter(
        label
        for label in (_instance_layer2(i) for i in instances)
        if label is not None
    )
    return PropertyRollup(
        mean_score=(sum(scores) / len(scores)) if scores else None,
        profiled=profiled,
        n_instances=len(instances),
        layer1_counts=dict(layer1),
        layer2_counts=dict(layer2),
    )


def rollup_by_property(
    instances: Iterable[Any],
    manifest: Any,
    *,
    leaf_properties: Sequence[str] | None = None,
) -> dict[str, PropertyRollup]:
    """Group instances by leaf property and roll each group up.

    ``manifest`` supplies the profile, so the rollup reflects the
    thresholds in force *now* rather than whenever the run was scored.
    ``leaf_properties`` pins the set of keys when the caller knows which
    properties the schema defines, so one absent from these instances
    still appears with an empty rollup.
    """
    grouped: dict[str, list[Any]] = {}
    for instance in instances:
        key = (
            instance.get("leaf_property")
            if isinstance(instance, dict)
            else instance.leaf_property
        )
        if isinstance(key, str):
            grouped.setdefault(key, []).append(instance)

    keys = list(leaf_properties) if leaf_properties is not None else list(grouped)
    rollups: dict[str, PropertyRollup] = {}
    for key in keys:
        profile = manifest.profile_for(key)
        rollups[key] = rollup_property(
            grouped.get(key, ()),
            profiled=profile is not None and profile.is_profiled,
        )
    return rollups


def property_mean_score(
    instances: Sequence[Any],
    *,
    profiled: bool,
) -> float | None:
    """Mean instance score for one leaf property, or ``None``.

    A thin alias over :func:`rollup_property` for callers that want only
    the mean. Prefer the rollup: the mean without its denominator is not
    a reportable number.
    """
    return rollup_property(instances, profiled=profiled).mean_score
