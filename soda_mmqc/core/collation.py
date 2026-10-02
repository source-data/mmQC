"""Collation layout: embed model schema in evaluation documents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from soda_mmqc.core.eval_manifest import EvalManifest
from soda_mmqc.core.schema_discovery import (
    LeafKind,
    LeafPropertySpec,
    ObjectListSpec,
    discover_object_lists,
    discover_schema,
    list_name_to_by_list_key,
)


@dataclass(frozen=True)
class PredictiveListBinding:
    """Schema predictive list at its resolved path in the eval document."""

    schema_list_name: str
    by_list_key: str
    alignment_list_name: str


@dataclass(frozen=True)
class EvalListSpec:
    """One object list in the evaluation document traversal tree."""

    by_list_key: str
    field_name: str
    is_predictive: bool
    alignment_list_name: Optional[str]
    parent: Optional[EvalListSpec] = None
    schema_list_name: Optional[str] = None


@dataclass(frozen=True)
class CollationLayout:
    """How a model schema embeds in an evaluation gold/pred document."""

    embedding_prefix: tuple[str, ...]
    predictive_lists: tuple[PredictiveListBinding, ...]
    eval_lists: tuple[EvalListSpec, ...]


@dataclass(frozen=True)
class EvalLeafSpec:
    """One leaf to score in evaluation path space."""

    eval_pattern: str
    kind: LeafKind
    enum_values: Optional[tuple[str, ...]] = None
    eval_list: Optional[EvalListSpec] = None
    schema_pattern: Optional[str] = None


def discover_collation_layout(
    schema: Mapping[str, Any],
    exp: Mapping[str, Any],
    pred: Mapping[str, Any],
) -> CollationLayout:
    """Locate schema embedding and derive structural vs predictive eval lists."""
    exp_prefix = _find_embedding_prefix(schema, exp)
    pred_prefix = _find_embedding_prefix(schema, pred)
    if exp_prefix != pred_prefix:
        raise ValueError(
            "gold and pred use different collation embeddings: "
            f"{_prefix_label(exp_prefix)!r} vs {_prefix_label(pred_prefix)!r}"
        )

    schema_lists = discover_object_lists(schema)
    predictive = tuple(
        _binding_for_schema_list(spec.list_name, exp_prefix) for spec in schema_lists
    )
    eval_lists = _build_eval_list_tree(exp_prefix, schema_lists)
    return CollationLayout(
        embedding_prefix=exp_prefix,
        predictive_lists=predictive,
        eval_lists=eval_lists,
    )


def build_eval_leaf_specs(
    schema: Mapping[str, Any],
    layout: CollationLayout,
) -> tuple[EvalLeafSpec, ...]:
    """Schema leaves remapped to eval paths (predictive model output only)."""
    prefix = _eval_pattern_prefix(layout.embedding_prefix)
    specs: list[EvalLeafSpec] = []

    for leaf in discover_schema(schema):
        eval_pattern = _remap_schema_pattern(leaf.pattern, prefix)
        eval_list = _eval_list_for_schema_list(
            layout, leaf.object_list_name
        )
        specs.append(
            EvalLeafSpec(
                eval_pattern=eval_pattern,
                kind=leaf.kind,
                enum_values=leaf.enum_values,
                eval_list=eval_list,
                schema_pattern=leaf.pattern,
            )
        )

    return tuple(specs)


def validate_manifest_field_patterns(
    manifest: EvalManifest,
    schema: Mapping[str, Any],
    layout: CollationLayout,
) -> None:
    """Reject ``fields`` entries on structural-only eval paths."""
    prefix = _eval_pattern_prefix(layout.embedding_prefix)
    schema_eval_patterns = {
        _remap_schema_pattern(leaf.pattern, prefix)
        for leaf in discover_schema(schema)
    }
    forbidden = sorted(
        pattern
        for pattern in (*manifest.field_patterns(), *manifest.unscored_leaf_properties())
        if pattern not in schema_eval_patterns
    )
    if forbidden:
        raise ValueError(
            "fields entries on non-schema (structural) paths are forbidden: "
            + ", ".join(forbidden)
        )


def validate_manifest_list_alignment(
    manifest: EvalManifest,
    schema: Mapping[str, Any],
    layout: CollationLayout,
) -> None:
    """Ensure ``list_alignment`` matches schema predictive lists at eval paths."""
    expected = {
        binding.by_list_key: binding for binding in layout.predictive_lists
    }
    manifest_keys = set(manifest.list_alignment)

    missing = set(expected) - manifest_keys
    if missing:
        raise ValueError(
            "list_alignment missing keys for schema predictive lists: "
            + ", ".join(sorted(missing))
        )

    extra = manifest_keys - set(expected)
    if extra:
        raise ValueError(
            "list_alignment keys not in schema predictive set: "
            + ", ".join(sorted(extra))
        )

    row_properties = _schema_row_properties(schema)
    for binding in layout.predictive_lists:
        keys = manifest.alignment_keys_for(binding.alignment_list_name)
        assert keys is not None
        row_props = row_properties.get(binding.schema_list_name, frozenset())
        unknown = [key for key in keys if key not in row_props]
        if unknown:
            raise ValueError(
                f"list_alignment[{binding.by_list_key!r}] keys {unknown!r} "
                f"not in schema row properties for {binding.schema_list_name!r}"
            )


def alignment_list_name_to_by_list_key(alignment_list_name: str) -> str:
    """``figures[].panels`` → ``figures.panels``."""
    return list_name_to_by_list_key(alignment_list_name)


def _binding_for_schema_list(
    schema_list_name: str,
    embedding_prefix: tuple[str, ...],
) -> PredictiveListBinding:
    by_list_key = _resolved_by_list_key(schema_list_name, embedding_prefix)
    alignment_list_name = _resolved_alignment_list_name(
        schema_list_name, embedding_prefix
    )
    return PredictiveListBinding(
        schema_list_name=schema_list_name,
        by_list_key=by_list_key,
        alignment_list_name=alignment_list_name,
    )


def _build_eval_list_tree(
    embedding_prefix: tuple[str, ...],
    schema_lists: Sequence[ObjectListSpec],
) -> tuple[EvalListSpec, ...]:
    specs: list[EvalListSpec] = []
    structural_nodes: dict[tuple[str, ...], EvalListSpec] = {}

    for index, field in enumerate(embedding_prefix):
        prefix = embedding_prefix[: index + 1]
        parent_prefix = embedding_prefix[:index]
        parent = structural_nodes.get(parent_prefix)
        node = EvalListSpec(
            by_list_key=".".join(prefix),
            field_name=field,
            is_predictive=False,
            alignment_list_name=None,
            parent=parent,
        )
        structural_nodes[prefix] = node
        specs.append(node)

    predictive_nodes: dict[str, EvalListSpec] = {}

    for schema_list in schema_lists:
        parent: Optional[EvalListSpec] = None
        if schema_list.parent is not None:
            parent = predictive_nodes.get(schema_list.parent.list_name)
        if parent is None:
            parent = structural_nodes.get(embedding_prefix)
        field = _terminal_field_name(schema_list.list_name)
        by_list_key = _resolved_by_list_key(schema_list.list_name, embedding_prefix)
        alignment_list_name = _resolved_alignment_list_name(
            schema_list.list_name, embedding_prefix
        )
        node = EvalListSpec(
            by_list_key=by_list_key,
            field_name=field,
            is_predictive=True,
            alignment_list_name=alignment_list_name,
            parent=parent,
            schema_list_name=schema_list.list_name,
        )
        predictive_nodes[schema_list.list_name] = node
        specs.append(node)

    return tuple(specs)


def _find_embedding_prefix(
    schema: Mapping[str, Any],
    doc: Mapping[str, Any],
) -> tuple[str, ...]:
    if _doc_matches_schema_root(schema, doc):
        return ()
    found = _search_embedding_prefix(schema, doc, prefix=())
    if found is None:
        raise ValueError("evaluation document does not embed the model schema")
    return found


def _search_embedding_prefix(
    schema: Mapping[str, Any],
    doc: Any,
    *,
    prefix: tuple[str, ...],
) -> Optional[tuple[str, ...]]:
    if isinstance(doc, Mapping) and _doc_matches_schema_root(schema, doc):
        return prefix
    if not isinstance(doc, Mapping):
        return None
    schema_keys = set(_schema_root_properties(schema))
    for key, value in doc.items():
        if key in schema_keys:
            continue
        if isinstance(value, list):
            sample = _first_mapping_row(value)
            if sample is None:
                continue
            found = _search_embedding_prefix(
                schema, sample, prefix=prefix + (key,)
            )
            if found is not None:
                return found
    return None


def _doc_matches_schema_root(schema: Mapping[str, Any], doc: Mapping[str, Any]) -> bool:
    properties = _schema_root_properties(schema)
    if not properties:
        return False
    for name, prop_schema in properties.items():
        if name not in doc:
            return False
        if not _value_matches_property(doc[name], prop_schema):
            return False
    return True


def _value_matches_property(value: Any, prop_schema: Mapping[str, Any]) -> bool:
    prop_type = _primary_type(prop_schema)
    if prop_type == "array":
        return isinstance(value, list)
    if prop_type == "object":
        return isinstance(value, Mapping)
    if prop_type == "string":
        return isinstance(value, str)
    if prop_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if prop_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if prop_type == "boolean":
        return isinstance(value, bool)
    return True


def _schema_root_properties(schema: Mapping[str, Any]) -> Mapping[str, Any]:
    return schema.get("properties", {})


def _primary_type(node: Mapping[str, Any]) -> Optional[str]:
    raw = node.get("type")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        for candidate in raw:
            if candidate != "null":
                return candidate
    return None


def _first_mapping_row(rows: Sequence[Any]) -> Optional[Mapping[str, Any]]:
    for row in rows:
        if isinstance(row, Mapping):
            return row
    return None


def _eval_pattern_prefix(embedding_prefix: tuple[str, ...]) -> str:
    if not embedding_prefix:
        return ""
    return "[].".join(embedding_prefix) + "[]."


def _remap_schema_pattern(pattern: str, eval_prefix: str) -> str:
    if not eval_prefix:
        return pattern
    return f"{eval_prefix}{pattern}"


def _resolved_by_list_key(
    schema_list_name: str, embedding_prefix: tuple[str, ...]
) -> str:
    field = _terminal_field_name(schema_list_name)
    if not embedding_prefix:
        return field
    return ".".join((*embedding_prefix, field))


def _resolved_alignment_list_name(
    schema_list_name: str, embedding_prefix: tuple[str, ...]
) -> str:
    field = _terminal_field_name(schema_list_name)
    if not embedding_prefix:
        return field
    return "[].".join((*embedding_prefix, field))


def _terminal_field_name(schema_list_name: str) -> str:
    if "[]." in schema_list_name:
        return schema_list_name.rsplit("[].", maxsplit=1)[-1]
    return schema_list_name


def _prefix_label(prefix: tuple[str, ...]) -> str:
    if not prefix:
        return "<root>"
    return "[].".join(prefix)


def _eval_list_for_schema_list(
    layout: CollationLayout, schema_list_name: Optional[str]
) -> Optional[EvalListSpec]:
    if schema_list_name is None:
        return None
    for spec in layout.eval_lists:
        if spec.is_predictive and spec.schema_list_name == schema_list_name:
            return spec
    return None


def _schema_row_properties(schema: Mapping[str, Any]) -> dict[str, frozenset[str]]:
    result: dict[str, frozenset[str]] = {}

    def walk(node: Mapping[str, Any], prefix: str) -> None:
        if _primary_type(node) == "object":
            for name, child in node.get("properties", {}).items():
                walk(child, f"{prefix}.{name}" if prefix else name)
            return
        if _primary_type(node) != "array":
            return
        items = node.get("items", {})
        if _primary_type(items) != "object":
            return
        list_name = prefix
        result[list_name] = frozenset(items.get("properties", {}))
        for name, child in items.get("properties", {}).items():
            child_prefix = f"{list_name}[].{name}"
            walk(child, child_prefix)

    walk(schema, "")
    return result
