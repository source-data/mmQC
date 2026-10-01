"""Tests for schema leaf / object-list discovery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from soda_mmqc.core.schema_discovery import (
    LeafKind,
    SchemaTypingError,
    discover_object_lists,
    discover_schema,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_toy_schema_leaves():
    schema = json.loads((FIXTURES / "toy_eval_schema.json").read_text())
    leaves = discover_schema(schema)
    patterns = [leaf.pattern for leaf in leaves]
    assert patterns == [
        "tags",
        "item.id",
        "item.label",
        "item.status",
        "item.meta.author",
        "item.meta.year",
        "panels[].id",
        "panels[].label",
        "panels[].status",
        "panels[].caption",
    ]
    assert leaves[0].kind is LeafKind.ROOT_PRIMITIVE_ARRAY
    assert leaves[1].kind is LeafKind.SCALAR
    assert leaves[6].kind is LeafKind.ROW
    assert leaves[6].object_list_name == "panels"


def test_row_nested_primitive_array_is_row_kind():
    schema = {
        "type": "object",
        "properties": {
            "outputs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "panel_label": {"type": "string"},
                        "symbols": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                },
            }
        },
    }
    leaves = discover_schema(schema)
    symbols = next(leaf for leaf in leaves if leaf.pattern == "outputs[].symbols")
    assert symbols.kind is LeafKind.ROW
    assert symbols.object_list_name == "outputs"

    tags_only = discover_schema(
        {
            "type": "object",
            "properties": {
                "tags": {"type": "array", "items": {"type": "string"}},
            },
        }
    )
    assert tags_only[0].kind is LeafKind.ROOT_PRIMITIVE_ARRAY
    assert tags_only[0].object_list_name is None


def test_toy_schema_object_lists():
    schema = json.loads((FIXTURES / "toy_eval_schema.json").read_text())
    lists = discover_object_lists(schema)
    assert len(lists) == 1
    assert lists[0].list_name == "panels"
    assert lists[0].by_list_key == "panels"


# --- unions and untyped nodes -------------------------------------------------
#
# `replication-reporting · n_value_min` is typed only through `anyOf` -- an
# integer, or one of two string tokens -- and discovery used to skip it without
# a word, so it was never scored. These pin down that a union of primitives is a
# leaf, that it carries no enum values (which would force enum comparison onto
# its integers), and that a node discovery cannot type is refused, not skipped.


def _row_schema(field: dict) -> dict:
    return {
        "type": "object",
        "properties": {
            "outputs": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"panel_label": {"type": "string"}, "n": field},
                },
            }
        },
    }


INTEGER_OR_TOKEN = {
    "anyOf": [
        {"type": "integer", "minimum": 0},
        {"type": "string", "enum": ["not_reported", "not_applicable"]},
    ]
}


def test_a_union_of_primitives_is_a_leaf():
    leaves = discover_schema(_row_schema(INTEGER_OR_TOKEN))
    n = next(leaf for leaf in leaves if leaf.pattern == "outputs[].n")
    assert n.kind is LeafKind.ROW
    assert n.object_list_name == "outputs"


def test_a_union_leaf_carries_no_enum_values():
    """Enum values would send its integers through enum string comparison."""
    leaves = discover_schema(_row_schema(INTEGER_OR_TOKEN))
    n = next(leaf for leaf in leaves if leaf.pattern == "outputs[].n")
    assert n.enum_values is None


def test_a_union_leaf_scores_both_of_its_alternatives():
    from soda_mmqc.core.evaluation import score_leaf_pair

    n = next(
        leaf for leaf in discover_schema(_row_schema(INTEGER_OR_TOKEN))
        if leaf.pattern == "outputs[].n"
    )
    assert score_leaf_pair(3, 3, None, enum_values=n.enum_values) == 1.0
    assert score_leaf_pair(3, 4, None, enum_values=n.enum_values) < 1.0
    assert score_leaf_pair(
        "not_reported", "not_reported", None, enum_values=n.enum_values
    ) == 1.0


def test_oneof_is_read_like_anyof():
    field = {"oneOf": [{"type": "integer"}, {"type": "null"}]}
    patterns = [leaf.pattern for leaf in discover_schema(_row_schema(field))]
    assert "outputs[].n" in patterns


def test_an_untyped_node_is_refused_not_skipped():
    with pytest.raises(SchemaTypingError, match=r"outputs\[\]\.n"):
        discover_schema(_row_schema({"description": "no type at all"}))


def test_a_union_mixing_primitives_and_containers_is_refused():
    field = {"anyOf": [{"type": "integer"}, {"type": "array", "items": {"type": "string"}}]}
    with pytest.raises(SchemaTypingError, match=r"outputs\[\]\.n"):
        discover_schema(_row_schema(field))


def test_every_committed_schema_is_fully_typed():
    """No contract in the repository has a field the scorer cannot see."""
    root = Path(__file__).resolve().parents[1] / "soda_mmqc" / "data" / "checklist"
    schemas = sorted(root.glob("*/*/schema.json"))
    assert schemas
    for path in schemas:
        envelope = json.loads(path.read_text())
        discover_schema(envelope.get("format", {}).get("schema", envelope))
