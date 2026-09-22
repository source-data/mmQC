"""Export a static HTML snapshot of fig-checklist evaluation reporting."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd
import plotly.graph_objects as go

from soda_mmqc.config import CHECKLIST_DIR
from soda_mmqc.reporting.aggregate import (
    RunSummaries,
    RunSummary,
    field_order,
    leaf_property_tail,
    summarize_runs,
)
from soda_mmqc.reporting.compare import build_comparison_report
from soda_mmqc.reporting.load import (
    discover_evaluation_checks,
    load_evaluation_dir,
)
from soda_mmqc.reporting.plots import plot_comparison_mean_scores


@dataclass(frozen=True)
class ArmScoreRow:
    """One model x arm score row for tables and winners."""

    model: str
    arm: str
    n_docs: int
    field_scores: dict[str, float | None]


@dataclass(frozen=True)
class CheckReportSummary:
    """Per-check export summary for the index page."""

    check: str
    models: tuple[str, ...]
    winners: tuple[str, ...]
    score_rows: tuple[ArmScoreRow, ...]
    relative_page: str
    skipped_reason: str | None = None


@dataclass(frozen=True)
class SchemaFieldRow:
    """One output-field row for the schema legend on a check page."""

    field: str
    type_label: str
    allowed: str
    description: str


def score_rows_for_summaries(summaries: RunSummaries) -> list[ArmScoreRow]:
    """Build sorted model/arm score rows from run summaries."""
    rows: list[ArmScoreRow] = []
    # Iterate the summaries rather than the cross product of models and
    # arms: a RunRef also carries a replicate, so there is no key to
    # build from (model, arm) alone.
    for summary in summaries.values():
        order = field_order(summary.manifest, summary.by_property.keys())
        field_scores = {
            leaf_property_tail(key): summary.by_property[key].mean_score
            for key in order
            if key in summary.by_property
        }
        rows.append(
            ArmScoreRow(
                model=summary.model,
                arm=summary.arm,
                n_docs=len(summary.records),
                field_scores=field_scores,
            )
        )
    rows.sort(key=lambda row: (row.model, row.arm))
    return rows


def best_arm_per_property(
    rows: Sequence[ArmScoreRow],
) -> list[str]:
    """Which arm scored highest on each property, per model.

    This replaces `winner_lines`, which ranked arms by a mean across
    properties. That number mixed measurements of different things: an
    arm that improved `panel_label` and degraded `micrograph` came out
    looking unchanged, and the one line hid both movements.

    There is deliberately no overall winner. Whether a set of
    per-property movements adds up to a better arm is the experiment's
    claim, and it belongs in the experiment's note where the reasoning
    is visible -- not in a library default that picks for you.
    """
    lines: list[str] = []
    for model in sorted({row.model for row in rows}):
        model_rows = [row for row in rows if row.model == model]
        properties = sorted(
            {name for row in model_rows for name in row.field_scores}
        )
        for name in properties:
            scored = [
                (row.arm, row.field_scores[name])
                for row in model_rows
                if row.field_scores.get(name) is not None
            ]
            if not scored:
                lines.append(
                    f"{model} / {name}: nothing applicable in any arm"
                )
                continue
            arm, value = max(scored, key=lambda pair: pair[1])
            lines.append(f"{model} / {name}: {arm} ({value:.3f})")
    return lines


def scores_table(rows: Sequence[ArmScoreRow]) -> pd.DataFrame:
    """Wide table: model, arm, docs, then one column per property.

    No summary column. A mean across properties mixes measurements of
    different things, so the table reports each property and leaves the
    judgement to the reader.
    """
    field_names: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for field in row.field_scores:
            if field not in seen:
                seen.add(field)
                field_names.append(field)

    records: list[dict[str, object]] = []
    for row in rows:
        record: dict[str, object] = {
            "model": row.model,
            "arm": row.arm,
            "docs": row.n_docs,
        }
        for field in field_names:
            value = row.field_scores.get(field)
            record[field] = round(value, 3) if value is not None else None
        records.append(record)
    return pd.DataFrame(records)


def _figure_html(fig: go.Figure | None, *, include_js: bool) -> str:
    if fig is None:
        return "<p><em>No chart for this section.</em></p>"
    return fig.to_html(
        full_html=False,
        include_plotlyjs="cdn" if include_js else False,
        config={"displayModeBar": True},
    )


def _df_html(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "<p><em>No scores available.</em></p>"
    return frame.to_html(
        index=False,
        classes="scores",
        border=0,
        float_format=lambda value: f"{value:.3f}",
        na_rep="—",
    )


def load_check_schema(checklist: str, check: str) -> dict[str, Any] | None:
    """Load ``schema.json`` for a checklist check, if present."""
    path = CHECKLIST_DIR / checklist / check / "schema.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def panel_item_properties(schema: Mapping[str, Any]) -> dict[str, Any] | None:
    """Return the per-panel ``properties`` object from a check schema."""
    try:
        props = schema["format"]["schema"]["properties"]["outputs"]["items"]["properties"]
    except (KeyError, TypeError):
        return None
    return props if isinstance(props, dict) else None


def _format_type_label(spec: Mapping[str, Any]) -> str:
    type_name = spec.get("type")
    if isinstance(type_name, list):
        type_name = " | ".join(str(part) for part in type_name)
    if type_name == "array":
        items = spec.get("items")
        if isinstance(items, dict):
            item_type = items.get("type", "any")
            if item_type == "object":
                return "array<object>"
            if isinstance(item_type, list):
                item_type = " | ".join(str(part) for part in item_type)
            return f"array<{item_type}>"
        return "array"
    if type_name:
        return str(type_name)
    return "—"


def _format_allowed(spec: Mapping[str, Any]) -> str:
    enum_values = spec.get("enum")
    if isinstance(enum_values, list) and enum_values:
        return ", ".join(repr(value) for value in enum_values)
    return "—"


def schema_field_rows(schema: Mapping[str, Any]) -> list[SchemaFieldRow]:
    """Flatten panel output fields (including nested object array leaves)."""
    properties = panel_item_properties(schema)
    if not properties:
        return []

    rows: list[SchemaFieldRow] = []
    for field_name, raw_spec in properties.items():
        if not isinstance(raw_spec, dict):
            continue
        rows.append(
            SchemaFieldRow(
                field=field_name,
                type_label=_format_type_label(raw_spec),
                allowed=_format_allowed(raw_spec),
                description=str(raw_spec.get("description") or ""),
            )
        )
        if raw_spec.get("type") != "array":
            continue
        items = raw_spec.get("items")
        if not isinstance(items, dict) or items.get("type") != "object":
            continue
        nested = items.get("properties")
        if not isinstance(nested, dict):
            continue
        for nested_name, nested_spec in nested.items():
            if not isinstance(nested_spec, dict):
                continue
            rows.append(
                SchemaFieldRow(
                    field=f"{field_name}[].{nested_name}",
                    type_label=_format_type_label(nested_spec),
                    allowed=_format_allowed(nested_spec),
                    description=str(nested_spec.get("description") or ""),
                )
            )
    return rows


def _schema_section_html(schema: Mapping[str, Any] | None) -> str:
    """HTML block explaining panel output fields from the check schema."""
    if schema is None:
        return (
            "<h2>Output fields (schema)</h2>"
            "<p><em>No schema.json found for this check.</em></p>"
        )

    rows = schema_field_rows(schema)
    properties = panel_item_properties(schema)
    parts: list[str] = [
        "<h2>Output fields (schema)</h2>",
        "<p class='meta'>Panel-level fields from <code>schema.json</code> "
        "(what each scored column means).</p>",
    ]
    if not rows:
        parts.append("<p><em>Could not read panel field definitions from schema.</em></p>")
        return "\n".join(parts)

    parts.append(
        "<table class='scores schema'>"
        "<thead><tr>"
        "<th>Field</th><th>Type</th><th>Allowed values</th><th>Description</th>"
        "</tr></thead><tbody>"
    )
    for row in rows:
        parts.append(
            "<tr>"
            f"<td><code>{html.escape(row.field)}</code></td>"
            f"<td>{html.escape(row.type_label)}</td>"
            f"<td>{html.escape(row.allowed)}</td>"
            f"<td>{html.escape(row.description)}</td>"
            "</tr>"
        )
    parts.append("</tbody></table>")

    if properties is not None:
        pretty = json.dumps(properties, indent=2, ensure_ascii=False)
        parts.append("<details><summary>Schema fragment (panel properties)</summary>")
        parts.append(f"<pre class='schema-json'>{html.escape(pretty)}</pre>")
        parts.append("</details>")
    return "\n".join(parts)


def render_check_html(
    *,
    checklist: str,
    check: str,
    summaries: RunSummaries,
    models: Sequence[str],
    include_comparison: bool,
    schema: Mapping[str, Any] | None = None,
) -> str:
    """Render one check report page (HTML string)."""
    rows = score_rows_for_summaries(summaries)
    winners = best_arm_per_property(rows)
    table = scores_table(rows)
    if schema is None:
        schema = load_check_schema(checklist, check)

    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>{html.escape(check)} — fig-checklist report</title>",
        "<style>",
        "body{font-family:system-ui,sans-serif;max-width:1100px;margin:1.5rem auto;padding:0 1rem;color:#1f2937;}",
        "h1{font-size:1.5rem;} h2{font-size:1.2rem;margin-top:2rem;} h3{font-size:1.05rem;margin-top:1.5rem;}",
        ".meta{color:#6b7280;font-size:0.9rem;margin-bottom:1.25rem;}",
        ".winners{background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:0.75rem 1rem;}",
        ".winners li{margin:0.25rem 0;}",
        "table.scores{border-collapse:collapse;width:100%;font-size:0.9rem;margin:1rem 0;}",
        "table.scores th,table.scores td{border-bottom:1px solid #e5e7eb;padding:0.4rem 0.55rem;text-align:left;vertical-align:top;}",
        "table.scores th{background:#f3f4f6;}",
        "table.schema td:nth-child(1),table.schema td:nth-child(2){white-space:nowrap;}",
        "details{margin:0.75rem 0 1.25rem;} summary{cursor:pointer;color:#2563eb;}",
        "pre.schema-json{background:#f8fafc;border:1px solid #e5e7eb;border-radius:8px;"
        "padding:0.75rem 1rem;overflow:auto;font-size:0.82rem;}",
        ".chart{margin:1rem 0 1.5rem;}",
        "a{color:#2563eb;}",
        "</style></head><body>",
        f"<p class='meta'><a href='../index.html'>← All checks</a> · {html.escape(checklist)} / {html.escape(check)}</p>",
        f"<h1>{html.escape(check)}</h1>",
    ]

    parts.append(_schema_section_html(schema))

    parts.append("<h2>Winners</h2><ul class='winners'>")
    if winners:
        for line in winners:
            parts.append(f"<li>{html.escape(line)}</li>")
    else:
        parts.append("<li><em>No arm scores available.</em></li>")
    parts.append("</ul>")

    parts.append("<h2>Scores by arm</h2>")
    parts.append(_df_html(table))

    include_js = True
    for model in models:
        model_summaries = summaries.for_model(model)
        if not model_summaries:
            continue
        parts.append(f"<h2>Model: {html.escape(model)}</h2>")
        parts.append("<h3>Mean scores per field (arms compared)</h3>")
        mean_fig = plot_comparison_mean_scores(
            summaries,
            compare="arm",
            model=model,
            title=f"Mean scores by field — {check} / {model}",
        )
        parts.append(f"<div class='chart'>{_figure_html(mean_fig, include_js=include_js)}</div>")
        include_js = False

        if include_comparison and len(model_summaries) >= 2:
            report = build_comparison_report(
                summaries,
                compare="arm",
                model=model,
            )
            parts.append("<h3>Layer comparison overlays</h3>")
            for label, fig in (
                ("Structure (Layer S)", report.layer_s_figure),
                ("Applicability (Layer 1)", report.layer1_figure),
                ("Matching-binary (Layer 2)", report.layer2_binary_figure),
                ("Matching-graded (Layer 2)", report.layer2_graded_figure),
            ):
                parts.append(f"<h4>{html.escape(label)}</h4>")
                parts.append(
                    f"<div class='chart'>{_figure_html(fig, include_js=False)}</div>"
                )
        elif include_comparison:
            parts.append(
                "<p><em>Layer overlays skipped (need at least two arms).</em></p>"
            )

    parts.append("</body></html>")
    return "\n".join(parts)


def render_index_html(
    *,
    checklist: str,
    report_date: str,
    check_summaries: Sequence[CheckReportSummary],
) -> str:
    """Render the top-level index page."""
    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>{html.escape(checklist)} evaluation report — {html.escape(report_date)}</title>",
        "<style>",
        "body{font-family:system-ui,sans-serif;max-width:1000px;margin:1.5rem auto;padding:0 1rem;color:#1f2937;}",
        "h1{font-size:1.6rem;} table{border-collapse:collapse;width:100%;font-size:0.95rem;}",
        "th,td{border-bottom:1px solid #e5e7eb;padding:0.5rem 0.6rem;text-align:left;vertical-align:top;}",
        "th{background:#f3f4f6;} .skip{color:#6b7280;font-style:italic;}",
        "a{color:#2563eb;}",
        "</style></head><body>",
        f"<h1>{html.escape(checklist)} evaluation report</h1>",
        f"<p>Snapshot date: <strong>{html.escape(report_date)}</strong></p>",
        "<table><thead><tr><th>Check</th><th>Models</th><th>Winners</th><th>Status</th></tr></thead><tbody>",
    ]
    for item in check_summaries:
        if item.skipped_reason:
            parts.append(
                "<tr>"
                f"<td>{html.escape(item.check)}</td>"
                "<td>—</td><td>—</td>"
                f"<td class='skip'>{html.escape(item.skipped_reason)}</td>"
                "</tr>"
            )
            continue
        winners_html = "<br>".join(html.escape(line) for line in item.winners) or "—"
        models_html = ", ".join(html.escape(model) for model in item.models) or "—"
        parts.append(
            "<tr>"
            f"<td><a href='{html.escape(item.relative_page)}'>{html.escape(item.check)}</a></td>"
            f"<td>{models_html}</td>"
            f"<td>{winners_html}</td>"
            "<td>ok</td>"
            "</tr>"
        )
    parts.append("</tbody></table></body></html>")
    return "\n".join(parts)


def export_fig_checklist_report(
    *,
    out_dir: Path,
    models: Sequence[str] | None = None,
    checks: Sequence[str] | None = None,
    include_comparison: bool = True,
    report_date: str | None = None,
) -> list[CheckReportSummary]:
    """Write HTML report + summary CSV for fig-checklist evaluations.

    Returns per-check summaries (including skipped checks).
    """
    checklist = "fig-checklist"
    stamp = report_date or date.today().isoformat()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    refs = [
        ref
        for ref in discover_evaluation_checks()
        if ref.checklist == checklist
    ]
    if checks:
        wanted = set(checks)
        refs = [ref for ref in refs if ref.check in wanted]

    check_summaries: list[CheckReportSummary] = []
    summary_frames: list[pd.DataFrame] = []

    for ref in refs:
        relative_page = f"{ref.check}/index.html"
        if not ref.has_manifest:
            check_summaries.append(
                CheckReportSummary(
                    check=ref.check,
                    models=(),
                    winners=(),
                    score_rows=(),
                    relative_page=relative_page,
                    skipped_reason="No eval-manifest.json",
                )
            )
            continue

        try:
            runs = load_evaluation_dir(
                ref.checklist,
                ref.check,
                models=list(models) if models else None,
            )
        except (OSError, ValueError) as exc:
            check_summaries.append(
                CheckReportSummary(
                    check=ref.check,
                    models=(),
                    winners=(),
                    score_rows=(),
                    relative_page=relative_page,
                    skipped_reason=str(exc),
                )
            )
            continue

        if len(runs) == 0:
            check_summaries.append(
                CheckReportSummary(
                    check=ref.check,
                    models=(),
                    winners=(),
                    score_rows=(),
                    relative_page=relative_page,
                    skipped_reason="No flat evaluation runs",
                )
            )
            continue

        summaries = summarize_runs(runs)
        model_list = list(summaries.models)
        if models:
            # Preserve user-requested order when filtering.
            model_list = [model for model in models if model in summaries.models]
        if not model_list:
            check_summaries.append(
                CheckReportSummary(
                    check=ref.check,
                    models=(),
                    winners=(),
                    score_rows=(),
                    relative_page=relative_page,
                    skipped_reason="No matching models",
                )
            )
            continue

        rows = score_rows_for_summaries(summaries)
        rows = [row for row in rows if row.model in set(model_list)]
        winners = best_arm_per_property(rows)
        table = scores_table(rows)
        if not table.empty:
            table = table.copy()
            table.insert(0, "check", ref.check)
            summary_frames.append(table)

        check_dir = out_dir / ref.check
        check_dir.mkdir(parents=True, exist_ok=True)
        page = render_check_html(
            checklist=checklist,
            check=ref.check,
            summaries=summaries,
            models=model_list,
            include_comparison=include_comparison,
        )
        (check_dir / "index.html").write_text(page, encoding="utf-8")

        check_summaries.append(
            CheckReportSummary(
                check=ref.check,
                models=tuple(model_list),
                winners=tuple(winners),
                score_rows=tuple(rows),
                relative_page=relative_page,
            )
        )

    index = render_index_html(
        checklist=checklist,
        report_date=stamp,
        check_summaries=check_summaries,
    )
    (out_dir / "index.html").write_text(index, encoding="utf-8")

    if summary_frames:
        combined = pd.concat(summary_frames, ignore_index=True)
        combined.to_csv(out_dir / "summary.csv", index=False)
    else:
        pd.DataFrame().to_csv(out_dir / "summary.csv", index=False)

    return check_summaries
