"""Tests for fig-checklist static report helpers."""

from __future__ import annotations

import json
from pathlib import Path

from soda_mmqc.config import CHECKLIST_DIR
from soda_mmqc.reporting.aggregate import summarize_runs
from soda_mmqc.reporting.export_report import (
    CheckMeanScoreCharts,
    KEY_FIELDS_PAGE,
    MEAN_SCORES_PAGE,
    PromptScoreRow,
    export_fig_checklist_report,
    overview_model_columns,
    panel_item_properties,
    render_mean_scores_overview_html,
    schema_field_rows,
    scores_table,
    winner_lines,
)
from soda_mmqc.reporting.load import load_flat_runs


def test_winner_lines_picks_highest_macro_per_model():
    rows = [
        PromptScoreRow("m1", "prompt.1", 10, 0.80, {"a": 0.8}),
        PromptScoreRow("m1", "prompt.2", 10, 0.91, {"a": 0.91}),
        PromptScoreRow("m2", "prompt.1", 10, 0.70, {"a": 0.7}),
        PromptScoreRow("m2", "prompt.3", 10, 0.88, {"a": 0.88}),
    ]
    lines = winner_lines(rows)
    assert lines == [
        "Best prompt on m1: prompt.2 (macro 0.910)",
        "Best prompt on m2: prompt.3 (macro 0.880)",
    ]


def test_scores_table_includes_macro_and_fields():
    rows = [
        PromptScoreRow("m1", "prompt.1", 5, 0.5, {"decision": 1.0, "is_a_plot": 0.0}),
        PromptScoreRow("m1", "prompt.2", 5, 0.75, {"decision": 0.5, "is_a_plot": 1.0}),
    ]
    frame = scores_table(rows)
    assert list(frame.columns) == [
        "model",
        "prompt",
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


def test_overview_model_columns_respects_preferred_order():
    runs = load_flat_runs(
        "fig-checklist",
        "stat-significance-level",
        models=["gpt-5.4", "gpt-5-mini-2025-08-07"],
    )
    summaries = summarize_runs(runs)
    rows = [
        CheckMeanScoreCharts(
            check="stat-significance-level",
            summaries=summaries,
            models=tuple(summaries.models),
            relative_page="stat-significance-level/index.html",
        )
    ]
    cols = overview_model_columns(
        rows,
        preferred=["gpt-5-mini-2025-08-07", "gpt-5.4", "missing-model"],
    )
    assert cols == ["gpt-5-mini-2025-08-07", "gpt-5.4"]


def test_render_mean_scores_overview_html_grid(tmp_path: Path):
    runs = load_flat_runs(
        "fig-checklist",
        "stat-significance-level",
        models=["gpt-5-mini-2025-08-07", "gpt-5.4"],
    )
    summaries = summarize_runs(runs)
    model_list = ["gpt-5-mini-2025-08-07", "gpt-5.4"]
    chart_rows = [
        CheckMeanScoreCharts(
            check="stat-significance-level",
            summaries=summaries,
            models=tuple(model_list),
            relative_page="stat-significance-level/index.html",
        )
    ]
    page = render_mean_scores_overview_html(
        checklist="fig-checklist",
        report_date="2026-08-12",
        chart_rows=chart_rows,
        model_columns=model_list,
    )
    assert "mean scores overview" in page
    assert "stat-significance-level" in page
    assert "gpt-5-mini-2025-08-07" in page
    assert "gpt-5.4" in page
    assert "table class='overview'" in page
    assert "table-layout:fixed" in page
    assert "width:6.5rem" in page
    assert page.index("gpt-5-mini-2025-08-07") < page.index("gpt-5.4")


def test_schema_leaf_property_patterns_follow_schema_order():
    from soda_mmqc.reporting.aggregate import (
        field_order_for_summary,
        load_check_schema_dict,
        schema_leaf_property_patterns,
    )
    from soda_mmqc.reporting.aggregate import summarize_runs
    from soda_mmqc.reporting.load import load_flat_runs

    schema = load_check_schema_dict("fig-checklist", "stat-significance-level")
    assert schema_leaf_property_patterns(schema) == [
        "outputs[].panel_label",
        "outputs[].is_a_plot",
        "outputs[].significance_level_symbols_on_image",
        "outputs[].symbols_defined",
        "outputs[].symbol_definition",
        "outputs[].decision",
        "outputs[].explanation",
    ]

    nested = load_check_schema_dict("fig-checklist", "plot-axis-units")
    assert schema_leaf_property_patterns(nested)[:5] == [
        "outputs[].panel_label",
        "outputs[].is_a_plot",
        "outputs[].units_provided[].axis",
        "outputs[].units_provided[].answer",
        "outputs[].unit_definition_as_provided[].axis",
    ]

    runs = load_flat_runs(
        "fig-checklist",
        "stat-significance-level",
        models="gpt-5-mini-2025-08-07",
        prompts="prompt.1",
    )
    summary = summarize_runs(runs)[("gpt-5-mini-2025-08-07", "prompt.1")]
    ordered = field_order_for_summary(summary)
    assert ordered[0] == "outputs[].panel_label"
    assert ordered[-1] == "outputs[].explanation"
    assert "outputs[].decision" in ordered
    assert ordered.index("outputs[].is_a_plot") < ordered.index("outputs[].decision")


def test_export_writes_mean_scores_overview(tmp_path: Path):
    out = tmp_path / "report"
    summaries = export_fig_checklist_report(
        out_dir=out,
        models=["gpt-5-mini-2025-08-07", "gpt-5.4"],
        checks=["stat-significance-level"],
        include_comparison=False,
        report_date="2026-08-12",
    )
    assert len(summaries) == 1
    assert summaries[0].skipped_reason is None
    overview = out / MEAN_SCORES_PAGE
    index = out / "index.html"
    assert overview.is_file()
    assert "Mean scores overview" in index.read_text(encoding="utf-8")
    text = overview.read_text(encoding="utf-8")
    assert "stat-significance-level" in text
    assert "gpt-5-mini-2025-08-07" in text
    assert "gpt-5.4" in text
    assert "plotly" in text.lower()