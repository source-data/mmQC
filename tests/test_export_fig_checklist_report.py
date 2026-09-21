"""Tests for fig-checklist static report helpers."""

from __future__ import annotations

import json

from soda_mmqc.config import CHECKLIST_DIR
from soda_mmqc.reporting.export_report import (
    ArmScoreRow,
    panel_item_properties,
    schema_field_rows,
    scores_table,
    winner_lines,
)


def test_winner_lines_picks_highest_macro_per_model():
    rows = [
        ArmScoreRow("m1", "pinned", 10, 0.80, {"a": 0.8}),
        ArmScoreRow("m1", "micrograph-scale-bar@v2", 10, 0.91, {"a": 0.91}),
        ArmScoreRow("m2", "pinned", 10, 0.70, {"a": 0.7}),
        ArmScoreRow("m2", "micrograph-scale-bar@v3", 10, 0.88, {"a": 0.88}),
    ]
    lines = winner_lines(rows)
    assert lines == [
        "Best arm on m1: micrograph-scale-bar@v2 (macro 0.910)",
        "Best arm on m2: micrograph-scale-bar@v3 (macro 0.880)",
    ]


def test_scores_table_includes_macro_and_fields():
    rows = [
        ArmScoreRow("m1", "pinned", 5, 0.5, {"decision": 1.0, "is_a_plot": 0.0}),
        ArmScoreRow("m1", "micrograph-scale-bar@v2", 5, 0.75, {"decision": 0.5, "is_a_plot": 1.0}),
    ]
    frame = scores_table(rows)
    assert list(frame.columns) == [
        "model",
        "arm",
        "docs",
        "macro",
        "decision",
        "is_a_plot",
    ]
    assert frame.loc[0, "macro"] == 0.5
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
