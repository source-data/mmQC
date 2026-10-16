"""Row pairing for list-of-objects properties.

Pairs pred rows to gold rows using manifest ``list_alignment`` keys before
per-field leaf scoring. Layer S structural reporting is built separately
(see ``structural_reporting.py``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

import numpy as np

from soda_mmqc.core.eval_manifest import EvalManifest, FieldProfile, MatchingMetric
from soda_mmqc.core.leaves import (
    StringCompareMode,
    compare_strings,
    exact_primitive_similarity,
)
from soda_mmqc.core.matching import (
    MatchedPair,
    hungarian_match_pairs,
    pairs_at_threshold,
)


def mapping_rows_only(rows: Sequence[Any]) -> tuple[Mapping[str, Any], ...]:
    """Keep only mapping rows from a list-of-objects property."""
    return tuple(row for row in rows if isinstance(row, Mapping))


@dataclass(frozen=True)
class ObjectListPairingResult:
    """Row pairing outcome for one list-of-objects property."""

    gold_to_pred: tuple[tuple[int, int], ...]
    match_threshold: float
    pair_similarities: tuple[MatchedPair, ...]

    def pred_index_for_gold(self, gold_index: int) -> Optional[int]:
        for gold, pred in self.gold_to_pred:
            if gold == gold_index:
                return pred
        return None


def align_object_rows(
    exp_rows: Sequence[Mapping[str, Any]],
    pred_rows: Sequence[Mapping[str, Any]],
    *,
    list_name: str,
    manifest: EvalManifest,
    embedder: Optional[Any] = None,
) -> ObjectListPairingResult:
    """Pair object-list rows using manifest ``list_alignment`` keys.

    Row similarity ``s(i,j)`` is the mean leaf score over alignment keys.
    Each key uses the ``fields`` profile for ``{list_name}[].{key}``.
    ``gold_to_pred`` contains only pairs with ``s(i,j) >= match_threshold``.
    """
    exp_rows = mapping_rows_only(exp_rows)
    pred_rows = mapping_rows_only(pred_rows)
    alignment_keys = manifest.alignment_keys_for(list_name)
    if not alignment_keys:
        raise ValueError(
            f"list_alignment[{list_name!r}] is required for object list pairing"
        )

    key_profiles = _alignment_key_profiles(list_name, alignment_keys, manifest)
    match_threshold = _row_match_threshold(key_profiles)

    if not exp_rows and not pred_rows:
        return ObjectListPairingResult(
            gold_to_pred=(),
            match_threshold=match_threshold,
            pair_similarities=(),
        )

    matrix = build_object_similarity_matrix(
        exp_rows,
        pred_rows,
        alignment_keys,
        key_profiles,
        embedder=embedder,
    )
    pairs = hungarian_match_pairs(matrix)
    accepted = pairs_at_threshold(pairs, match_threshold)
    gold_to_pred = tuple((gold, pred) for gold, pred, _ in accepted)

    return ObjectListPairingResult(
        gold_to_pred=gold_to_pred,
        match_threshold=match_threshold,
        pair_similarities=pairs,
    )


def build_object_similarity_matrix(
    exp_rows: Sequence[Mapping[str, Any]],
    pred_rows: Sequence[Mapping[str, Any]],
    alignment_keys: Sequence[str],
    key_profiles: Sequence[FieldProfile],
    *,
    embedder: Optional[Any] = None,
) -> np.ndarray:
    """Row similarity matrix for list-of-objects pairing."""
    if not exp_rows or not pred_rows:
        return np.zeros((len(exp_rows), len(pred_rows)), dtype=float)
    return np.array(
        [
            [
                row_similarity(
                    exp_rows[i],
                    pred_rows[j],
                    alignment_keys,
                    key_profiles,
                    embedder=embedder,
                )
                for j in range(len(pred_rows))
            ]
            for i in range(len(exp_rows))
        ],
        dtype=float,
    )


def row_similarity(
    exp_row: Mapping[str, Any],
    pred_row: Mapping[str, Any],
    alignment_keys: Sequence[str],
    key_profiles: Sequence[FieldProfile],
    *,
    embedder: Optional[Any] = None,
) -> float:
    """Mean alignment-key score between two object rows."""
    if not isinstance(exp_row, Mapping) or not isinstance(pred_row, Mapping):
        return 0.0
    if not alignment_keys:
        return 0.0
    scores = [
        score_alignment_key(
            exp_row.get(key),
            pred_row.get(key),
            profile,
            embedder=embedder,
        )
        for key, profile in zip(alignment_keys, key_profiles)
    ]
    return sum(scores) / len(scores)


def score_alignment_key(
    exp_value: Any,
    pred_value: Any,
    profile: FieldProfile,
    *,
    embedder: Optional[Any] = None,
) -> float:
    """Leaf score for one alignment key using its manifest field profile."""
    if profile.matching_metric == MatchingMetric.GRADED_STRING:
        if profile.string_compare is None:
            raise ValueError("graded_string alignment key requires string_compare")
        if not isinstance(exp_value, str) or not isinstance(pred_value, str):
            return exact_primitive_similarity(pred_value, exp_value)
        return compare_strings(
            pred_value,
            exp_value,
            mode=profile.string_compare,
            embedder=embedder,
        ).score

    if isinstance(exp_value, str) and isinstance(pred_value, str):
        return compare_strings(
            pred_value,
            exp_value,
            mode=StringCompareMode.EXACT,
        ).score

    return exact_primitive_similarity(pred_value, exp_value)


def leaf_property_for_alignment_key(list_name: str, field_name: str) -> str:
    """Manifest path pattern for a row alignment field."""
    return f"{list_name}[].{field_name}"


def _alignment_key_profiles(
    list_name: str,
    alignment_keys: Sequence[str],
    manifest: EvalManifest,
) -> tuple[FieldProfile, ...]:
    profiles: list[FieldProfile] = []
    for key in alignment_keys:
        path = leaf_property_for_alignment_key(list_name, key)
        profile = manifest.profile_for(path)
        if profile is None:
            profiles.append(FieldProfile())
        else:
            profiles.append(profile)
    return tuple(profiles)


def _row_match_threshold(key_profiles: Sequence[FieldProfile]) -> float:
    thresholds: list[float] = []
    for profile in key_profiles:
        if profile.matching_metric == MatchingMetric.GRADED_STRING:
            if profile.match_threshold is None:
                raise ValueError("graded_string alignment key requires match_threshold")
            thresholds.append(profile.match_threshold)
        else:
            thresholds.append(1.0)
    if not thresholds:
        return 1.0
    return sum(thresholds) / len(thresholds)
