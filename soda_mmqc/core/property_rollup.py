"""Shared rollups for ``by_property`` summaries."""

from __future__ import annotations

from typing import Any, Sequence

LAYER1_MEAN_SCORE_ELIGIBLE = "correct_applicable"


def _instance_score(instance: Any) -> float | None:
    score = instance.get("score") if isinstance(instance, dict) else instance.score
    if isinstance(score, (int, float)):
        return float(score)
    return None


def _instance_layer1(instance: Any) -> str | None:
    layer1 = instance.get("layer1") if isinstance(instance, dict) else instance.layer1
    return layer1 if isinstance(layer1, str) else None


def _eligible_scores(
    instances: Sequence[Any],
    *,
    profiled: bool,
) -> list[float]:
    """The instance scores this property's mean is taken over.

    Layer 2 is conditional on layer 1: when a property is profiled, only
    instances the model judged applicable *and* judged so correctly say
    anything about matching quality. Whether it judged applicability right
    is layer 1's question, reported there.
    """
    scores: list[float] = []
    for instance in instances:
        score = _instance_score(instance)
        if score is None:
            continue
        if profiled and _instance_layer1(instance) != LAYER1_MEAN_SCORE_ELIGIBLE:
            continue
        scores.append(score)
    return scores


def eligible_instance_count(
    instances: Sequence[Any],
    *,
    profiled: bool,
) -> int:
    """How many instances this property's mean was taken over.

    Carried beside the mean because a mean over zero instances is not a
    score at all, and a mean over one is not comparable to a mean over
    forty. An arm that judges a property inapplicable more often is scored
    on fewer, self-selected cases, so no layer-2 mean should be read
    without this number next to it.
    """
    return len(_eligible_scores(instances, profiled=profiled))


def property_mean_score(
    instances: Sequence[Any],
    *,
    profiled: bool,
) -> float | None:
    """Mean instance score for one leaf property, or ``None``.

    ``None`` means no instance was eligible -- the property had nothing to
    score here. It is deliberately not ``0.0``: that is a score a model can
    earn, and returning it for "not applicable" puts a false zero into
    every mean taken over this property, on every axis.
    """
    scores = _eligible_scores(instances, profiled=profiled)
    if not scores:
        return None
    return sum(scores) / len(scores)


def instance_eligible_for_mean_score(
    instance: dict[str, Any],
    *,
    profiled: bool,
) -> bool:
    """Whether an instance contributes to ``mean_score`` and score scatter plots."""
    if _instance_score(instance) is None:
        return False
    if profiled:
        return instance.get("layer1") == LAYER1_MEAN_SCORE_ELIGIBLE
    return True
