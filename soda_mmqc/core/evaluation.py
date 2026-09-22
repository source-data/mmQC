"""Flat leaf evaluation orchestrator."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Optional, Protocol, Sequence

from soda_mmqc.core.applicability_and_matching import report_layers
from soda_mmqc.core.collation import (
    CollationLayout,
    EvalLeafSpec,
    EvalListSpec,
    build_eval_leaf_specs,
    discover_collation_layout,
    validate_manifest_field_patterns,
    validate_manifest_list_alignment,
)
from soda_mmqc.core.eval_manifest import (
    EvalManifest,
    FieldProfile,
    MatchingMetric,
    load_eval_manifest,
)
from soda_mmqc.core.leaves import (
    PrimitiveListCompareMode,
    compare_boolean,
    compare_enum_string,
    compare_exact_strings,
    compare_number,
    compare_primitive_list,
    compare_primitive_list_join,
    compare_primitive_list_positional,
    compare_strings,
    exact_primitive_similarity,
)
from soda_mmqc.core.object_list_pairing import align_object_rows, mapping_rows_only
from soda_mmqc.core.schema_discovery import LeafKind
from soda_mmqc.core.structural_reporting import ByListResult, build_by_list


class RowPairing(Protocol):
    def pred_index_for_gold(self, gold_index: int) -> Optional[int]: ...


@dataclass(frozen=True)
class PositionalPairing:
    """Positional gold[i] ↔ pred[i] join for structural lists."""

    n_pred: int

    def pred_index_for_gold(self, gold_index: int) -> Optional[int]:
        if gold_index < self.n_pred:
            return gold_index
        return None


@dataclass
class LeafInstanceResult:
    """One scored leaf instance."""

    path: str
    leaf_property: str
    exp_value: Any
    pred_value: Any
    score: float
    layer1: Optional[str] = None
    layer2: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "path": self.path,
            "leaf_property": self.leaf_property,
            "exp_value": self.exp_value,
            "pred_value": self.pred_value,
            "score": self.score,
        }
        if self.layer1 is not None:
            payload["layer1"] = self.layer1
        if self.layer2 is not None:
            payload["layer2"] = self.layer2
        return payload


@dataclass
class EvaluationResult:
    """Comparator output for one gold/pred pair: measurements only.

    What this carries is what was *measured* -- one record per leaf
    instance with its score and its layer-1/layer-2 labels, plus the
    layer-S structural outcome per list. It deliberately carries no
    per-property rollup.

    Rolling instances up needs the manifest's profiles, and the manifest
    holds thresholds we tune. Storing a rollup beside the measurements
    makes a cache with no invalidation: adjust a threshold, re-report
    without re-scoring, and the stored number silently disagrees with a
    fresh one. Aggregation therefore happens at read time, in
    :mod:`soda_mmqc.core.property_rollup`.
    """

    instances: tuple[LeafInstanceResult, ...]
    by_list: dict[str, dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {
            "instances": [instance.to_dict() for instance in self.instances],
            "by_list": self.by_list,
        }

    def aggregate_layer1_counts(self) -> dict[str, int]:
        """Layer-1 labels across every instance."""
        return dict(
            Counter(
                instance.layer1
                for instance in self.instances
                if instance.layer1
            )
        )

    def aggregate_layer2_counts(self) -> dict[str, int]:
        """Layer-2 labels across every instance."""
        return dict(
            Counter(
                instance.layer2
                for instance in self.instances
                if instance.layer2
            )
        )

    def layer_s_issues(self, by_list_key: str) -> dict[str, list[dict[str, Any]]]:
        """Missing and spurious row records for one predictive ``by_list`` key."""
        rows = self.by_list[by_list_key]["rows"]
        return {
            "missing": [
                row for row in rows if row["structural"] == "missing_row"
            ],
            "spurious": [
                row for row in rows if row["structural"] == "spurious_row"
            ],
        }


class FlatEvaluator:
    """Compare prediction JSON to gold under schema + eval manifest."""

    def __init__(
        self,
        schema: Mapping[str, Any],
        manifest: EvalManifest,
        *,
        embedder: Optional[Any] = None,
    ) -> None:
        self.schema = schema
        self.manifest = manifest
        self.embedder = embedder

    @classmethod
    def from_paths(
        cls,
        schema_path: str,
        manifest_path: str,
        *,
        embedder: Optional[Any] = None,
    ) -> FlatEvaluator:
        import json
        from pathlib import Path

        schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
        manifest = load_eval_manifest(manifest_path)
        return cls(schema, manifest, embedder=embedder)

    def evaluate(self, exp: Mapping[str, Any], pred: Mapping[str, Any]) -> EvaluationResult:
        """Run the full flat evaluation pipeline."""
        layout = discover_collation_layout(self.schema, exp, pred)
        validate_manifest_list_alignment(self.manifest, self.schema, layout)
        validate_manifest_field_patterns(self.manifest, self.schema, layout)
        leaf_specs = build_eval_leaf_specs(self.schema, layout)

        instances: list[LeafInstanceResult] = []
        by_list: dict[str, dict[str, Any]] = {}
        pairings = self._align_eval_lists(exp, pred, layout, by_list)

        for leaf_spec in leaf_specs:
            if leaf_spec.kind is LeafKind.ROOT_PRIMITIVE_ARRAY:
                instances.append(
                    self._evaluate_extended_primitive(exp, pred, leaf_spec)
                )
            elif leaf_spec.kind is LeafKind.SCALAR:
                instances.append(self._evaluate_scalar(exp, pred, leaf_spec))
            else:
                instances.extend(
                    self._evaluate_row_leaves(exp, pred, leaf_spec, pairings)
                )

        return EvaluationResult(
            instances=tuple(instances),
            by_list=by_list,
        )

    def _align_eval_lists(
        self,
        exp: Mapping[str, Any],
        pred: Mapping[str, Any],
        layout: CollationLayout,
        by_list_out: dict[str, dict[str, Any]],
    ) -> dict[str, dict[tuple[Any, ...], RowPairing]]:
        pairings: dict[str, dict[tuple[Any, ...], RowPairing]] = {}
        for spec in layout.eval_lists:
            for (
                context_key,
                gold_rows,
                pred_rows,
                gold_ancestors,
                pred_ancestors,
            ) in _iter_eval_list_contexts(spec, exp, pred, pairings):
                if spec.is_predictive:
                    assert spec.alignment_list_name is not None
                    pairing = align_object_rows(
                        gold_rows,
                        pred_rows,
                        list_name=spec.alignment_list_name,
                        manifest=self.manifest,
                        embedder=self.embedder,
                    )
                    by_list_result = build_by_list(
                        pairing,
                        n_gold=len(gold_rows),
                        n_pred=len(pred_rows),
                    )
                    pairings.setdefault(spec.by_list_key, {})[context_key] = pairing
                    alignment_keys = self.manifest.alignment_keys_for(
                        spec.alignment_list_name
                    )
                    serialized = _serialize_by_list(
                        by_list_result,
                        list_spec=spec,
                        context_key=context_key,
                        gold_ancestors=gold_ancestors,
                        pred_ancestors=pred_ancestors,
                        gold_rows=gold_rows,
                        pred_rows=pred_rows,
                        alignment_keys=alignment_keys,
                    )
                    _merge_by_list(by_list_out, spec.by_list_key, serialized)
                else:
                    pairings.setdefault(spec.by_list_key, {})[context_key] = (
                        PositionalPairing(n_pred=len(pred_rows))
                    )
        return pairings

    def _evaluate_extended_primitive(
        self,
        exp: Mapping[str, Any],
        pred: Mapping[str, Any],
        leaf_spec: EvalLeafSpec,
    ) -> LeafInstanceResult:
        exp_value = _get_value_at_eval_pattern(exp, leaf_spec.eval_pattern)
        pred_value = _get_value_at_eval_pattern(pred, leaf_spec.eval_pattern)
        exp_list = exp_value if isinstance(exp_value, list) else []
        pred_list = pred_value if isinstance(pred_value, list) else []
        profile = self.manifest.profile_for(leaf_spec.eval_pattern)
        score = _compare_extended_primitive_score(
            pred_list,
            exp_list,
            leaf_spec=leaf_spec,
            profile=profile,
            embedder=self.embedder,
        )
        return self._instance_from_values(
            path=leaf_spec.eval_pattern,
            leaf_property=leaf_spec.eval_pattern,
            exp_value=exp_value,
            pred_value=pred_value,
            score=score,
            profile=profile,
            enum_values=leaf_spec.enum_values,
        )

    def _evaluate_scalar(
        self,
        exp: Mapping[str, Any],
        pred: Mapping[str, Any],
        leaf_spec: EvalLeafSpec,
    ) -> LeafInstanceResult:
        exp_value = _get_value_at_eval_pattern(exp, leaf_spec.eval_pattern)
        pred_value = _get_value_at_eval_pattern(pred, leaf_spec.eval_pattern)
        profile = self.manifest.profile_for(leaf_spec.eval_pattern)
        score = score_leaf_pair(
            pred_value,
            exp_value,
            profile,
            enum_values=leaf_spec.enum_values,
            embedder=self.embedder,
        )
        return self._instance_from_values(
            path=leaf_spec.eval_pattern,
            leaf_property=leaf_spec.eval_pattern,
            exp_value=exp_value,
            pred_value=pred_value,
            score=score,
            profile=profile,
            enum_values=leaf_spec.enum_values,
        )

    def _evaluate_row_leaves(
        self,
        exp: Mapping[str, Any],
        pred: Mapping[str, Any],
        leaf_spec: EvalLeafSpec,
        pairings: dict[str, dict[tuple[Any, ...], RowPairing]],
    ) -> list[LeafInstanceResult]:
        assert leaf_spec.eval_list is not None
        field_name = leaf_spec.eval_pattern.rsplit(".", maxsplit=1)[-1]
        profile = self.manifest.profile_for(leaf_spec.eval_pattern)
        results: list[LeafInstanceResult] = []

        for context_key, gold_rows, pred_rows, _, _ in _iter_eval_list_contexts(
            leaf_spec.eval_list, exp, pred, pairings
        ):
            pairing = pairings[leaf_spec.eval_list.by_list_key][context_key]
            prefix = _instance_prefix_for_context(leaf_spec.eval_list, context_key)
            for gold_index, gold_row in enumerate(gold_rows):
                pred_index = pairing.pred_index_for_gold(gold_index)
                exp_value = gold_row.get(field_name)
                pred_value = (
                    pred_rows[pred_index].get(field_name)
                    if pred_index is not None
                    else None
                )
                path = f"{prefix}[{gold_index}].{field_name}"
                score = self._score_row_leaf_value(
                    pred_value,
                    exp_value,
                    leaf_spec=leaf_spec,
                    profile=profile,
                )
                results.append(
                    self._instance_from_values(
                        path=path,
                        leaf_property=leaf_spec.eval_pattern,
                        exp_value=exp_value,
                        pred_value=pred_value,
                        score=score,
                        profile=profile,
                        enum_values=leaf_spec.enum_values,
                    )
                )
        return results

    def _score_row_leaf_value(
        self,
        pred_value: Any,
        exp_value: Any,
        *,
        leaf_spec: EvalLeafSpec,
        profile: Optional[FieldProfile],
    ) -> float:
        use_primitive_list = isinstance(exp_value, list) or isinstance(
            pred_value, list
        )
        if not use_primitive_list and profile is not None:
            use_primitive_list = profile.primitive_list_compare is not None

        if use_primitive_list:
            exp_list = exp_value if isinstance(exp_value, list) else []
            pred_list = pred_value if isinstance(pred_value, list) else []
            return _compare_extended_primitive_score(
                pred_list,
                exp_list,
                leaf_spec=leaf_spec,
                profile=profile,
                embedder=self.embedder,
            )

        return score_leaf_pair(
            pred_value,
            exp_value,
            profile,
            enum_values=leaf_spec.enum_values,
            embedder=self.embedder,
        )

    def _instance_from_values(
        self,
        *,
        path: str,
        leaf_property: str,
        exp_value: Any,
        pred_value: Any,
        score: float,
        profile: Optional[FieldProfile],
        enum_values: Optional[tuple[str, ...]],
    ) -> LeafInstanceResult:
        layer1: Optional[str] = None
        layer2: Optional[str] = None
        if profile is not None and profile.is_profiled:
            reporting = report_layers(exp_value, pred_value, profile, score)
            layer1 = reporting.layer1.value
            if reporting.layer2 is not None:
                layer2 = reporting.layer2.value
        return LeafInstanceResult(
            path=path,
            leaf_property=leaf_property,
            exp_value=exp_value,
            pred_value=pred_value,
            score=score,
            layer1=layer1,
            layer2=layer2,
        )


def score_leaf_pair(
    pred_value: Any,
    exp_value: Any,
    profile: Optional[FieldProfile],
    *,
    enum_values: Optional[tuple[str, ...]] = None,
    embedder: Optional[Any] = None,
) -> float:
    """Score one leaf value pair using manifest profile and schema hints."""
    if enum_values is not None:
        return compare_enum_string(pred_value, exp_value, enum_values).score

    if profile is not None and profile.is_profiled:
        if profile.matching_metric == MatchingMetric.GRADED_STRING:
            if not isinstance(exp_value, str) or not isinstance(pred_value, str):
                return exact_primitive_similarity(pred_value, exp_value)
            return compare_strings(
                pred_value,
                exp_value,
                mode=profile.string_compare,
                embedder=embedder,
            ).score
        return exact_primitive_similarity(pred_value, exp_value)

    if isinstance(exp_value, bool) or isinstance(pred_value, bool):
        return compare_boolean(pred_value, exp_value).score
    if isinstance(exp_value, (int, float)) or isinstance(pred_value, (int, float)):
        return compare_number(pred_value, exp_value).score
    if isinstance(exp_value, str) or isinstance(pred_value, str):
        return compare_exact_strings(pred_value, exp_value).score
    return exact_primitive_similarity(pred_value, exp_value)


def _iter_eval_list_contexts(
    spec: EvalListSpec,
    exp: Mapping[str, Any],
    pred: Mapping[str, Any],
    pairings: dict[str, dict[tuple[Any, ...], RowPairing]],
    gold_ancestors: tuple[Mapping[str, Any], ...] = (),
    pred_ancestors: tuple[Mapping[str, Any], ...] = (),
):
    """Yield list contexts with ancestor rows for display metadata."""
    if spec.parent is None:
        gold_rows = _rows_at_field(exp, spec.field_name)
        pred_rows = _rows_at_field(pred, spec.field_name)
        yield ((), gold_rows, pred_rows, gold_ancestors, pred_ancestors)
        return

    for (
        context_key,
        parent_gold_rows,
        parent_pred_rows,
        parent_gold_ancestors,
        parent_pred_ancestors,
    ) in _iter_eval_list_contexts(
        spec.parent, exp, pred, pairings
    ):
        parent_pairings = pairings.get(spec.parent.by_list_key, {})
        parent_pairing = parent_pairings.get(context_key)
        for parent_index in range(len(parent_gold_rows)):
            gold_parent_row = parent_gold_rows[parent_index]
            if parent_pairing is not None:
                pred_parent_index = parent_pairing.pred_index_for_gold(parent_index)
            else:
                pred_parent_index = (
                    parent_index if parent_index < len(parent_pred_rows) else None
                )
            pred_parent_row = (
                parent_pred_rows[pred_parent_index]
                if pred_parent_index is not None
                and pred_parent_index < len(parent_pred_rows)
                else {}
            )
            child_context = context_key + (parent_index,)
            gold_rows = _rows_in_parent(gold_parent_row, spec.field_name)
            pred_rows = _rows_in_parent(pred_parent_row, spec.field_name)
            child_gold_ancestors = parent_gold_ancestors + (gold_parent_row,)
            child_pred_ancestors = parent_pred_ancestors + (pred_parent_row,)
            yield (
                child_context,
                gold_rows,
                pred_rows,
                child_gold_ancestors,
                child_pred_ancestors,
            )


def _rows_at_field(doc: Mapping[str, Any], field_name: str) -> list[Mapping[str, Any]]:
    rows = doc.get(field_name)
    if not isinstance(rows, list):
        return []
    return list(mapping_rows_only(rows))


def _rows_in_parent(parent_row: Mapping[str, Any], field: str) -> list[Mapping[str, Any]]:
    rows = parent_row.get(field)
    if not isinstance(rows, list):
        return []
    return list(mapping_rows_only(rows))


def _get_value_at_eval_pattern(doc: Mapping[str, Any], pattern: str) -> Any:
    if "[]." in pattern:
        raise ValueError(
            f"document-level read unsupported for row pattern {pattern!r}"
        )
    current: Any = doc
    for segment in pattern.split("."):
        if current is None:
            return None
        if not isinstance(current, Mapping) or segment not in current:
            return None
        current = current[segment]
    return current


def _instance_prefix_for_context(
    spec: EvalListSpec, context_key: tuple[Any, ...]
) -> str:
    """Path to a list slice before indexing rows (e.g. ``papers[0].figures[2].outputs``)."""
    ancestors = _ancestor_spec_chain(spec)
    if not ancestors and not context_key:
        return spec.field_name
    parts = [
        f"{ancestors[index].field_name}[{context_key[index]}]"
        for index in range(len(context_key))
    ]
    parts.append(spec.field_name)
    return ".".join(parts)


def _ancestor_row_path(
    spec: EvalListSpec,
    context_key: tuple[Any, ...],
    depth: int,
) -> str:
    """Path to one structural ancestor row (no predictive list suffix)."""
    ancestors = _ancestor_spec_chain(spec)
    parts = [
        f"{ancestors[index].field_name}[{context_key[index]}]"
        for index in range(depth + 1)
    ]
    return ".".join(parts)


def _ancestor_spec_chain(spec: EvalListSpec) -> tuple[EvalListSpec, ...]:
    """Structural ancestor specs from root to immediate parent of ``spec``."""
    chain: list[EvalListSpec] = []
    current = spec.parent
    while current is not None:
        chain.append(current)
        current = current.parent
    return tuple(reversed(chain))


def _row_scalar_fields(row: Mapping[str, Any]) -> dict[str, Any]:
    """Non-list fields on a structural ancestor row (exclude nested object lists)."""
    return {key: value for key, value in row.items() if not isinstance(value, list)}


def _ancestor_context(
    spec: EvalListSpec,
    context_key: tuple[Any, ...],
    gold_ancestors: Sequence[Mapping[str, Any]],
    pred_ancestors: Sequence[Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Path-indexed scalar fields for each structural ancestor row."""
    gold_entries: list[dict[str, Any]] = []
    pred_entries: list[dict[str, Any]] = []
    for depth in range(len(_ancestor_spec_chain(spec))):
        path = _ancestor_row_path(spec, context_key, depth)
        gold_entries.append(
            {"path": path, "fields": _row_scalar_fields(gold_ancestors[depth])}
        )
        if depth < len(pred_ancestors):
            pred_entries.append(
                {
                    "path": path,
                    "fields": _row_scalar_fields(pred_ancestors[depth]),
                }
            )
    return {"ancestor_gold": gold_entries, "ancestor_pred": pred_entries}


def format_ancestor_context(
    entries: Sequence[Mapping[str, Any]],
) -> str:
    """Compact human-readable summary of ``ancestor_gold`` / ``ancestor_pred``."""
    parts: list[str] = []
    for entry in entries:
        path = entry["path"]
        fields = entry.get("fields") or {}
        if not fields:
            parts.append(path)
            continue
        field_text = ", ".join(f"{key}={value!r}" for key, value in fields.items())
        parts.append(f"{path} ({field_text})")
    return " → ".join(parts)


def _merge_by_list(
    by_list_out: dict[str, dict[str, Any]],
    by_list_key: str,
    serialized: dict[str, Any],
) -> None:
    if by_list_key not in by_list_out:
        by_list_out[by_list_key] = serialized
        return

    existing = by_list_out[by_list_key]
    for outcome, count in serialized["row_counts"].items():
        existing["row_counts"][outcome] = (
            existing["row_counts"].get(outcome, 0) + count
        )
    existing["rows"].extend(serialized["rows"])


def _row_alignment_label(
    rows: Sequence[Mapping[str, Any]],
    index: Optional[int],
    alignment_keys: Sequence[str],
) -> Optional[str]:
    if index is None or index >= len(rows):
        return None
    row = rows[index]
    parts = [str(row[key]) for key in alignment_keys if key in row]
    return " / ".join(parts) if parts else None


def _serialize_by_list(
    result: ByListResult,
    *,
    list_spec: EvalListSpec,
    context_key: tuple[Any, ...],
    gold_ancestors: Sequence[Mapping[str, Any]],
    pred_ancestors: Sequence[Mapping[str, Any]],
    gold_rows: Sequence[Mapping[str, Any]],
    pred_rows: Sequence[Mapping[str, Any]],
    alignment_keys: Sequence[str],
) -> dict[str, Any]:
    context_path = _instance_prefix_for_context(list_spec, context_key)
    ancestor_context = _ancestor_context(
        list_spec, context_key, gold_ancestors, pred_ancestors
    )
    return {
        "row_counts": asdict(result.row_counts),
        "rows": [
            {
                "context_path": context_path,
                **ancestor_context,
                "gold_index": row.gold_index,
                "pred_index": row.pred_index,
                "structural": row.structural.value,
                "similarity": row.similarity,
                "gold_alignment": _row_alignment_label(
                    gold_rows, row.gold_index, alignment_keys
                ),
                "pred_alignment": _row_alignment_label(
                    pred_rows, row.pred_index, alignment_keys
                ),
            }
            for row in result.rows
        ],
    }


def _compare_extended_primitive_score(
    pred_list: list[Any],
    exp_list: list[Any],
    *,
    leaf_spec: EvalLeafSpec,
    profile: Optional[FieldProfile],
    embedder: Optional[Any],
) -> float:
    compare_mode = (
        profile.effective_primitive_list_compare()
        if profile is not None
        else PrimitiveListCompareMode.ALIGN
    )
    if compare_mode == PrimitiveListCompareMode.JOIN_STRING:
        if profile is None or profile.string_compare is None:
            raise ValueError("join_string extended primitive requires string_compare")
        return compare_primitive_list_join(
            pred_list,
            exp_list,
            join_separator=profile.join_separator,
            sort_before_join=profile.sort_before_join,
            string_compare=profile.string_compare,
            embedder=embedder,
        ).score

    threshold = _primitive_list_threshold(profile)
    element_similarity = _element_similarity_fn(
        leaf_spec,
        profile,
        embedder=embedder,
    )
    if compare_mode == PrimitiveListCompareMode.POSITIONAL:
        return compare_primitive_list_positional(
            pred_list,
            exp_list,
            element_similarity=element_similarity,
            match_threshold=threshold,
        ).score
    return compare_primitive_list(
        pred_list,
        exp_list,
        element_similarity=element_similarity,
        match_threshold=threshold,
    ).score


def _primitive_list_threshold(profile: Optional[FieldProfile]) -> float:
    if profile is None or not profile.is_profiled:
        return 1.0
    if profile.matching_metric == MatchingMetric.GRADED_STRING:
        if profile.match_threshold is None:
            raise ValueError("graded_string extended primitive requires match_threshold")
        return profile.match_threshold
    return 1.0


def _element_similarity_fn(
    leaf_spec: EvalLeafSpec,
    profile: Optional[FieldProfile],
    *,
    embedder: Optional[Any],
):
    if leaf_spec.enum_values is not None:
        allowed = leaf_spec.enum_values

        def _enum_similarity(pred: Any, exp: Any) -> float:
            return compare_enum_string(pred, exp, allowed).score

        return _enum_similarity

    if profile is not None and profile.is_profiled:
        if profile.matching_metric == MatchingMetric.GRADED_STRING:

            def _graded_similarity(pred: Any, exp: Any) -> float:
                if not isinstance(pred, str) or not isinstance(exp, str):
                    return exact_primitive_similarity(pred, exp)
                return compare_strings(
                    pred,
                    exp,
                    mode=profile.string_compare,
                    embedder=embedder,
                ).score

            return _graded_similarity

    return exact_primitive_similarity
