"""Discover leaf properties and object lists from a JSON Schema."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional


class LeafKind(str, Enum):
    """Evaluator dispatch kind from schema placement (not full value typing).

    ``ROOT_PRIMITIVE_ARRAY`` — primitive array at document root (e.g. ``tags``);
    one instance, document-level read. Row-nested primitive arrays (e.g.
    ``outputs[].symbols``) are ``ROW`` — same extended-primitive *compare*
    rules, but scored per gold row after ``list_alignment`` pairing.
    """

    SCALAR = "scalar"
    ROOT_PRIMITIVE_ARRAY = "root_primitive_array"
    ROW = "row"


PRIMITIVE_TYPES = frozenset({"string", "number", "integer", "boolean"})


class SchemaTypingError(ValueError):
    """A schema node the scorer cannot type, and so cannot score.

    Raised rather than skipped. A silently skipped node is a field that is never
    scored and that nothing reports: `replication-reporting · n_value_min`,
    typed only through ``anyOf``, went unscored that way from the day its
    manifest was generated until the contract audit of 2026-09-30.
    """


@dataclass(frozen=True)
class LeafPropertySpec:
    """One leaf property pattern from schema traversal."""

    pattern: str
    kind: LeafKind
    enum_values: Optional[tuple[str, ...]] = None
    object_list_name: Optional[str] = None


@dataclass(frozen=True)
class ObjectListSpec:
    """One list-of-objects property requiring row alignment."""

    list_name: str
    by_list_key: str
    parent: Optional[ObjectListSpec] = None
    parent_field: Optional[str] = None


def discover_schema(schema: Mapping[str, Any]) -> tuple[LeafPropertySpec, ...]:
    """Return all leaf property specs in stable order."""
    leaves: list[LeafPropertySpec] = []
    _walk_node(schema, prefix="", leaves=leaves)
    return tuple(leaves)


def discover_object_lists(schema: Mapping[str, Any]) -> tuple[ObjectListSpec, ...]:
    """Return object-list specs in root-to-leaf order."""
    lists: list[ObjectListSpec] = []
    _walk_object_lists(schema, prefix="", parent=None, parent_field=None, lists=lists)
    return tuple(lists)


def list_name_to_by_list_key(list_name: str) -> str:
    """Map alignment list name to ``by_list`` output key (no ``[]``)."""
    return list_name.replace("[].", ".")


def _walk_node(
    node: Mapping[str, Any],
    *,
    prefix: str,
    leaves: list[LeafPropertySpec],
    object_list_name: Optional[str] = None,
) -> None:
    node_type = _primary_type(node)
    if node_type == "object":
        for name, child in node.get("properties", {}).items():
            child_prefix = f"{prefix}.{name}" if prefix else name
            _walk_node(
                child,
                prefix=child_prefix,
                leaves=leaves,
                object_list_name=object_list_name,
            )
        return

    if node_type == "array":
        items = node.get("items", {})
        items_type = _primary_type(items)
        if items_type in PRIMITIVE_TYPES:
            leaves.append(
                LeafPropertySpec(
                    pattern=prefix,
                    kind=(
                        LeafKind.ROW
                        if object_list_name
                        else LeafKind.ROOT_PRIMITIVE_ARRAY
                    ),
                    enum_values=_enum_values(items),
                    object_list_name=object_list_name,
                )
            )
            return

        if items_type == "object":
            list_name = prefix
            for name, child in items.get("properties", {}).items():
                row_pattern = f"{list_name}[].{name}"
                _walk_node(
                    child,
                    prefix=row_pattern,
                    leaves=leaves,
                    object_list_name=list_name,
                )
            return

    if node_type in PRIMITIVE_TYPES:
        leaves.append(
            LeafPropertySpec(
                pattern=prefix,
                kind=LeafKind.ROW if object_list_name else LeafKind.SCALAR,
                enum_values=_enum_values(node),
                object_list_name=object_list_name,
            )
        )
        return

    raise SchemaTypingError(
        f"Cannot type the schema node at {prefix or '<root>'!r}: give it a "
        f"'type', or an 'anyOf' / 'oneOf' of primitive types. Found keys "
        f"{sorted(node)}."
    )


def _walk_object_lists(
    node: Mapping[str, Any],
    *,
    prefix: str,
    parent: Optional[ObjectListSpec],
    parent_field: Optional[str],
    lists: list[ObjectListSpec],
) -> None:
    node_type = _primary_type(node)
    if node_type == "object":
        for name, child in node.get("properties", {}).items():
            child_prefix = f"{prefix}.{name}" if prefix else name
            _walk_object_lists(
                child,
                prefix=child_prefix,
                parent=parent,
                parent_field=parent_field,
                lists=lists,
            )
        return

    if node_type != "array":
        return

    items = node.get("items", {})
    if _primary_type(items) != "object":
        return

    list_name = prefix
    spec = ObjectListSpec(
        list_name=list_name,
        by_list_key=list_name_to_by_list_key(list_name),
        parent=parent,
        parent_field=parent_field,
    )
    lists.append(spec)

    for name, child in items.get("properties", {}).items():
        child_prefix = f"{list_name}[].{name}"
        _walk_object_lists(
            child,
            prefix=child_prefix,
            parent=spec,
            parent_field=name,
            lists=lists,
        )


def _primary_type(node: Mapping[str, Any]) -> Optional[str]:
    """The node's type, reading ``anyOf`` / ``oneOf`` unions of primitives.

    A union of primitives -- an integer, or one of two string tokens -- is a
    primitive leaf. It is reported as ``string`` when any alternative is a
    string, which is only a placement decision: such a leaf carries no
    ``enum_values`` (see :func:`_enum_values`), so it is scored by its
    manifest profile, which handles integers and strings alike. A union
    mixing primitives with objects or arrays has no single placement and is
    left untyped, for the walker to refuse.
    """
    raw = node.get("type")
    if isinstance(raw, str):
        return raw
    if isinstance(raw, list):
        for candidate in raw:
            if candidate != "null":
                return candidate
    alternatives = node.get("anyOf") or node.get("oneOf")
    if isinstance(alternatives, list) and alternatives:
        kinds = [_primary_type(alt) for alt in alternatives if isinstance(alt, Mapping)]
        kinds = [kind for kind in kinds if kind and kind != "null"]
        if kinds and all(kind in PRIMITIVE_TYPES for kind in kinds):
            return "string" if "string" in kinds else kinds[0]
    return None


def _enum_values(node: Mapping[str, Any]) -> Optional[tuple[str, ...]]:
    raw = node.get("enum")
    if not isinstance(raw, list) or not raw:
        return None
    if not all(isinstance(value, str) for value in raw):
        return None
    return tuple(raw)
