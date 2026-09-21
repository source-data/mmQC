"""Tests for fig-checklist static report helpers."""

from __future__ import annotations

import json

from soda_mmqc.config import CHECKLIST_DIR
from soda_mmqc.reporting.export_report import (
    ArmScoreRow,
    panel_item_properties,
    schema_field_rows,
    scores_table,
    best_arm_per_property,
)


def test_best_arm_is_reported_per_property():
    """No overall winner: the old line ranked arms by a mean across
    properties, which hides an arm that improves one and degrades
    another. Here that trade is visible."""
    rows = [
        ArmScoreRow("m1", "pinned", 10, {"a": 0.80, "b": 0.95}),
        ArmScoreRow("m1", "micrograph-scale-bar@v2", 10, {"a": 0.91, "b": 0.10}),
    ]
    assert best_arm_per_property(rows) == [
        "m1 / a: micrograph-scale-bar@v2 (0.910)",
        "m1 / b: pinned (0.950)",
    ]


def test_scores_table_is_one_column_per_property():
    """No macro column: a mean across properties is not reported."""
    rows = [
        ArmScoreRow("m1", "pinned", 5, {"decision": 1.0, "is_a_plot": 0.0}),
        ArmScoreRow(
            "m1", "micrograph-scale-bar@v2", 5,
            {"decision": 0.5, "is_a_plot": 1.0},
        ),
    ]
    frame = scores_table(rows)
    assert list(frame.columns) == [
        "model",
        "arm",
        "docs",
        "decision",
        "is_a_plot",
    ]
    assert frame.loc[1, "decision"] == 0.5


def test_schema_field_rows_for_micrograph_scale_bar():
    schema = json.loads(
        (
            CHECKLIST_DIR
            / "fig-checklist"
            / "micrograph-scale-bar"
            / "schema.json"
        ).read_text(encoding="utf-8")
    )
    props = panel_item_properties(schema)
    assert props is not None
    assert "scale_bar_on_image" in props

    rows = schema_field_rows(schema)
    by_field = {row.field: row for row in rows}
    assert "micrograph" in by_field
    assert by_field["micrograph"].allowed == "'yes', 'no'"
    assert "scale bar" in by_field["scale_bar_on_image"].description.lower()


def test_schema_field_rows_flattens_nested_object_arrays():
    schema = json.loads(
        (
            CHECKLIST_DIR / "fig-checklist" / "plot-axis-units" / "schema.json"
        ).read_text(encoding="utf-8")
    )
    fields = {row.field for row in schema_field_rows(schema)}
    assert "units_provided" in fields
    assert "units_provided[].axis" in fields
    assert "units_provided[].answer" in fields
    assert "decision" in fields
