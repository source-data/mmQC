"""Plotly charts for flat evaluation reporting."""

from __future__ import annotations

from typing import Any, Literal, Mapping, Sequence

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from soda_mmqc.core.property_rollup import instance_is_scored
from soda_mmqc.reporting.aggregate import RunSummaries, RunSummary, field_order, leaf_property_tail
from soda_mmqc.reporting.load import record_source
from soda_mmqc.reporting.styles import (
    COMPARISON_SERIES_OPACITIES,
    COMPARISON_SERIES_PATTERNS,
    INSTANCE_SCORE_MARKER_COLOR,
    INSTANCE_SCORE_MARKER_BORDER_COLOR,
    INSTANCE_SCORE_MARKER_BORDER_WIDTH,
    LAYER1_COLORS,
    LAYER1_ORDER,
    LAYER1_TITLE,
    LAYER2_BINARY_COLORS,
    LAYER2_BINARY_ORDER,
    LAYER2_BINARY_TITLE,
    LAYER2_GRADED_COLORS,
    LAYER2_GRADED_ORDER,
    LAYER2_GRADED_TITLE,
    MEAN_SCORE_BAR_COLOR,
    MEAN_SCORE_BAR_SPACING,
    MEAN_SCORE_BAR_WIDTH,
    MEAN_SCORE_JITTER_STDDEV,
    MEAN_SCORE_PLOT_TITLE,
    MEAN_SCORE_Y_MAX,
    LAYER_S_COLORS,
    LAYER_S_ORDER,
    LAYER_S_TITLE,
    PLOTLY_TEMPLATE,
)
from soda_mmqc.reporting.tables import layer_counts_by_property, split_layer2_by_metric

_COMPARISON_SUBPLOT_TITLE_FONT_SIZE = 12
_COMPARISON_SUBPLOT_HORIZONTAL_SPACING = 0.12
_COMPARISON_SUBPLOT_VERTICAL_SPACING = 0.08
_COMPARISON_SUBPLOT_PANEL_WIDTH = 340

_DASHBOARD_LEGEND_LAYOUT = {
    2: dict(
        orientation="h",
        yanchor="bottom",
        y=1.14,
        xanchor="center",
        x=0.36,
        font=dict(size=9),
    ),
    3: dict(
        orientation="h",
        yanchor="bottom",
        y=1.14,
        xanchor="center",
        x=0.61,
        font=dict(size=9),
    ),
    4: dict(
        orientation="h",
        yanchor="bottom",
        y=1.14,
        xanchor="center",
        x=0.86,
        font=dict(size=9),
    ),
}


def _zero_rangemode() -> dict[str, str]:
    return {"rangemode": "tozero"}


def _apply_plot_template(fig: go.Figure) -> go.Figure:
    """Apply the shared Plotly template to a reporting figure."""
    fig.update_layout(template=PLOTLY_TEMPLATE)
    return fig


def mean_scores_frame(summary: RunSummary) -> pd.DataFrame:
    """Per-property mean scores for supplementary bar charts."""
    rows: list[dict[str, Any]] = []
    for leaf_property in field_order(summary.manifest, summary.by_property.keys()):
        rollup = summary.by_property[leaf_property]
        rows.append(
            {
                "leaf_property": leaf_property,
                "field": leaf_property_tail(leaf_property),
                "mean_score": rollup.mean_score,
            }
        )
    return pd.DataFrame(rows)


def applicable_instance_scores_frame(summary: RunSummary) -> pd.DataFrame:
    """Eligible instance scores for mean-score scatter overlay."""
    rows: list[dict[str, Any]] = []
    for record in summary.records:
        instances = record.analysis.get("instances", ())
        if not isinstance(instances, list):
            continue
        doc_id = record.doc_id or ""
        source = record_source(record)
        for instance in instances:
            if not isinstance(instance, dict):
                continue
            leaf_property = instance.get("leaf_property")
            if not isinstance(leaf_property, str):
                continue
            profile = summary.manifest.profile_for(leaf_property)
            profiled = profile is not None and profile.is_profiled
            if not instance_is_scored(instance, profiled=profiled):
                continue
            score = instance.get("score")
            if not isinstance(score, (int, float)):
                continue
            layer2 = instance.get("layer2")
            rows.append(
                {
                    "leaf_property": leaf_property,
                    "field": leaf_property_tail(leaf_property),
                    "source": source,
                    "doc_id": doc_id,
                    "path": instance.get("path", ""),
                    "score": float(score),
                    "layer2": layer2 if isinstance(layer2, str) else None,
                }
            )
    return pd.DataFrame(rows)


def _field_numeric_positions(
    fields: Sequence[str],
    *,
    spacing: float = 1.0,
) -> dict[str, float]:
    return {field: float(index) * spacing for index, field in enumerate(fields)}


def plot_mean_score_with_instances(
    summary: RunSummary,
    *,
    title: str | None = None,
    seed: int = 0,
    return_instances: bool = False,
) -> go.Figure | tuple[go.Figure, pd.DataFrame]:
    """Layer 2 mean score bars with jittered applicable instance scores."""
    frame = mean_scores_frame(summary)
    inst = applicable_instance_scores_frame(summary)
    if title is None:
        title = MEAN_SCORE_PLOT_TITLE
    if frame.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        fig = _apply_plot_template(fig)
        return (fig, inst) if return_instances else fig

    fields = frame["field"].tolist()
    field_to_x = _field_numeric_positions(fields, spacing=MEAN_SCORE_BAR_SPACING)
    bar_x = [field_to_x[field] for field in fields]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=bar_x,
            y=frame["mean_score"],
            width=MEAN_SCORE_BAR_WIDTH,
            marker_color=MEAN_SCORE_BAR_COLOR,
            name="mean score",
            hovertext=[
                f"{field}<br>mean: {score:.3f}"
                for field, score in zip(fields, frame["mean_score"], strict=True)
            ],
            hoverinfo="text",
        )
    )

    if not inst.empty:
        rng = np.random.default_rng(seed)
        jitter = rng.normal(0, MEAN_SCORE_JITTER_STDDEV, size=len(inst))
        scatter_x = [
            field_to_x[row.field] + offset
            for row, offset in zip(inst.itertuples(index=False), jitter, strict=True)
        ]
        hover_lines = []
        for row in inst.itertuples(index=False):
            text = f"{row.source}<br>{row.path}<br>score: {row.score:.3f}"
            if row.layer2:
                text += f"<br>{row.layer2}"
            hover_lines.append(text)
        fig.add_trace(
            go.Scatter(
                x=scatter_x,
                y=inst["score"],
                mode="markers",
                name="instance score",
                customdata=np.arange(len(inst)),
                marker=dict(
                    size=8,
                    color=INSTANCE_SCORE_MARKER_COLOR,
                    opacity=0.85,
                    line=dict(
                        width=INSTANCE_SCORE_MARKER_BORDER_WIDTH,
                        color=INSTANCE_SCORE_MARKER_BORDER_COLOR,
                    ),
                ),
                hovertext=hover_lines,
                hoverinfo="text",
            )
        )

    fig.update_layout(
        title=title,
        barmode="overlay",
        xaxis=dict(
            tickmode="array",
            tickvals=bar_x,
            ticktext=fields,
            title="leaf field",
        ),
        yaxis=dict(range=[0, MEAN_SCORE_Y_MAX], title="score"),
    )
    fig = _apply_plot_template(fig)
    return (fig, inst) if return_instances else fig


def _primary_layer_s_counts(summary: RunSummary) -> dict[str, int]:
    if not summary.by_list_row_counts:
        return {}
    list_key = summary.by_list_keys[0]
    return dict(summary.by_list_row_counts.get(list_key, {}))


def _comparison_summaries(
    summaries: RunSummaries | Sequence[RunSummary],
    *,
    compare: Literal["prompt", "model"],
    model: str | None = None,
    prompt: str | None = None,
) -> tuple[RunSummary, ...]:
    if isinstance(summaries, RunSummaries):
        if compare == "prompt":
            if model is None:
                raise ValueError("model is required when compare='prompt'")
            selected = summaries.for_model(model)
        else:
            if prompt is None:
                raise ValueError("prompt is required when compare='model'")
            selected = summaries.for_prompt(prompt)
    else:
        selected = tuple(summaries)

    if not selected:
        raise ValueError("No summaries selected for comparison plot")
    return selected


def _series_label(summary: RunSummary, *, compare: Literal["prompt", "model"]) -> str:
    return summary.prompt if compare == "prompt" else summary.model


def _comparison_series_opacity(series_index: int, series_count: int) -> float:
    """Fade later comparison series so grouped bars stay distinguishable."""
    if series_index < len(COMPARISON_SERIES_OPACITIES):
        return COMPARISON_SERIES_OPACITIES[series_index]
    if series_count <= 1:
        return 1.0
    return max(0.25, 1.0 - series_index * (0.75 / (series_count - 1)))


def _comparison_series_pattern(series_index: int) -> str:
    """Return a Plotly hatch pattern for model comparison series."""
    if series_index < len(COMPARISON_SERIES_PATTERNS):
        return COMPARISON_SERIES_PATTERNS[series_index]
    return COMPARISON_SERIES_PATTERNS[series_index % len(COMPARISON_SERIES_PATTERNS)]


def _comparison_outcome_value(
    series_frames: Mapping[str, pd.DataFrame],
    *,
    field: str,
    series: str,
    outcome: str,
) -> int:
    frame = series_frames[series]
    if frame.empty or field not in frame["field"].values:
        return 0
    row = frame.loc[frame["field"] == field].iloc[0]
    return int(row[outcome]) if outcome in row and pd.notna(row[outcome]) else 0


def _comparison_subplot_grid(panel_count: int) -> tuple[int, int]:
    if panel_count <= 1:
        return 1, 1
    cols = min(4, panel_count)
    rows = (panel_count + cols - 1) // cols
    return rows, cols


def _comparison_marker_for_points(
    color: str,
    *,
    series_indices: Sequence[int],
    series_count: int,
    compare: Literal["prompt", "model"] | None,
) -> dict[str, Any]:
    marker: dict[str, Any] = {"color": color}
    if compare == "prompt":
        marker["opacity"] = [
            _comparison_series_opacity(index, series_count) for index in series_indices
        ]
    elif compare == "model":
        marker["pattern"] = {
            "shape": [
                _comparison_series_pattern(index) for index in series_indices
            ],
            "solidity": 0.35,
            "fgcolor": "#ffffff",
        }
    return marker


def _plot_comparison_stacked(
    *,
    fields: Sequence[str],
    series_frames: Mapping[str, pd.DataFrame],
    order: Sequence[str],
    color_map: Mapping[str, str],
    compare: Literal["prompt", "model"] | None,
    title: str,
    series_label: str,
) -> go.Figure:
    """One stacked-bar subplot per leaf field; x = prompt or model within each."""
    series_order = list(series_frames.keys())
    if not fields or not series_order:
        fig = go.Figure()
        fig.update_layout(title=title)
        return _apply_plot_template(fig)

    rows, cols = _comparison_subplot_grid(len(fields))
    fig = make_subplots(
        rows=rows,
        cols=cols,
        subplot_titles=list(fields),
        shared_xaxes=True,
        shared_yaxes=True,
        vertical_spacing=_COMPARISON_SUBPLOT_VERTICAL_SPACING,
        horizontal_spacing=_COMPARISON_SUBPLOT_HORIZONTAL_SPACING,
    )

    series_count = len(series_order)
    series_indices = list(range(series_count))
    legend_shown: set[str] = set()
    for panel_index, field in enumerate(fields):
        row = panel_index // cols + 1
        col = panel_index % cols + 1
        for outcome in order:
            values = [
                _comparison_outcome_value(
                    series_frames,
                    field=field,
                    series=series,
                    outcome=outcome,
                )
                for series in series_order
            ]
            if sum(values) == 0:
                continue
            show_legend = outcome not in legend_shown
            if show_legend:
                legend_shown.add(outcome)
            fig.add_trace(
                go.Bar(
                    x=list(series_order),
                    y=values,
                    name=outcome,
                    marker=_comparison_marker_for_points(
                        color_map[outcome],
                        series_indices=series_indices,
                        series_count=series_count,
                        compare=compare,
                    ),
                    legendgroup=outcome,
                    showlegend=show_legend,
                    customdata=[[field, series] for series in series_order],
                    hovertemplate=(
                        "field=%{customdata[0]}<br>"
                        f"{series_label}=%{{customdata[1]}}<br>"
                        f"{outcome}=%{{y}}<extra></extra>"
                    ),
                ),
                row=row,
                col=col,
            )

    if not fig.data:
        fig.update_layout(title=title)
        return _apply_plot_template(fig)

    fig.update_layout(
        title=title,
        barmode="stack",
        height=max(280, 220 * rows),
        width=max(720, _COMPARISON_SUBPLOT_PANEL_WIDTH * cols),
    )
    fig.update_annotations(
        font_size=_COMPARISON_SUBPLOT_TITLE_FONT_SIZE,
        xanchor="center",
        align="center",
    )
    fig.update_yaxes(rangemode="tozero", title_text="count", col=1)
    fig.update_xaxes(title_text=series_label, tickangle=-25, row=rows)
    return _apply_plot_template(fig)


def plot_layer_s_bar(
    counts: Mapping[str, int],
    *,
    title: str,
    list_key: str | None = None,
) -> go.Figure:
    """Single-run structural row outcomes."""
    labels = list(LAYER_S_ORDER)
    values = [counts.get(label, 0) for label in labels]
    colors = [LAYER_S_COLORS[label] for label in labels]
    fig = go.Figure(go.Bar(x=labels, y=values, marker_color=colors))
    subtitle = f" ({list_key})" if list_key else ""
    fig.update_layout(
        title=f"{title}{subtitle}",
        xaxis_title="structural outcome",
        yaxis_title="count",
        yaxis=_zero_rangemode(),
    )
    return _apply_plot_template(fig)


def plot_layer1_stacked(
    frame: pd.DataFrame,
    *,
    title: str,
) -> go.Figure:
    """Layer-1 applicability counts stacked by field tail."""
    return _plot_property_stacked(
        frame,
        order=LAYER1_ORDER,
        color_map=LAYER1_COLORS,
        title=title,
        outcome_label="layer 1 outcome",
    )


def plot_layer2_stacked(
    frame: pd.DataFrame,
    order: Sequence[str],
    color_map: Mapping[str, str],
    *,
    title: str,
) -> go.Figure:
    """Layer-2 counts stacked by field tail (binary or graded)."""
    return _plot_property_stacked(
        frame,
        order=order,
        color_map=color_map,
        title=title,
        outcome_label="layer 2 outcome",
    )


def _plot_property_stacked(
    frame: pd.DataFrame,
    *,
    order: Sequence[str],
    color_map: Mapping[str, str],
    title: str,
    outcome_label: str,
) -> go.Figure:
    if frame.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return _apply_plot_template(fig)

    melted = frame.melt(
        id_vars=["leaf_property", "field"],
        value_vars=list(order),
        var_name="outcome",
        value_name="count",
    )
    melted = melted[melted["count"] > 0]
    field_order_list = frame["field"].tolist()
    fig = px.bar(
        melted,
        x="field",
        y="count",
        color="outcome",
        barmode="stack",
        category_orders={"outcome": list(order), "field": field_order_list},
        color_discrete_map=dict(color_map),
        title=title,
        labels={"field": "leaf field", "outcome": outcome_label},
    )
    fig.update_layout(yaxis=_zero_rangemode())
    return _apply_plot_template(fig)


def plot_mean_score_bars(
    frame: pd.DataFrame,
    *,
    title: str = "Mean score by leaf field",
) -> go.Figure:
    """Supplementary per-property mean score bars."""
    if frame.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return _apply_plot_template(fig)
    fig = px.bar(
        frame,
        x="field",
        y="mean_score",
        category_orders={"field": frame["field"].tolist()},
        title=title,
        labels={"field": "leaf field", "mean_score": "mean score"},
    )
    fig.update_layout(yaxis=dict(range=[0, 1]))
    return _apply_plot_template(fig)


def plot_comparison_mean_scores(
    summaries: RunSummaries | Sequence[RunSummary],
    *,
    compare: Literal["prompt", "model"] = "prompt",
    model: str | None = None,
    prompt: str | None = None,
    title: str | None = None,
) -> go.Figure:
    """Grouped mean-score bars across prompts (or models) per leaf field."""
    selected = _comparison_summaries(
        summaries,
        compare=compare,
        model=model,
        prompt=prompt,
    )
    field_order_keys: list[str] = []
    seen: set[str] = set()
    for summary in selected:
        for leaf_property in field_order(
            summary.manifest, summary.by_property.keys()
        ):
            if leaf_property not in seen:
                seen.add(leaf_property)
                field_order_keys.append(leaf_property)
    field_labels = [leaf_property_tail(key) for key in field_order_keys]

    fig = go.Figure()
    series_count = len(selected)
    for series_index, summary in enumerate(selected):
        label = _series_label(summary, compare=compare)
        scores = [
            summary.by_property[key].mean_score
            if key in summary.by_property
            else None
            for key in field_order_keys
        ]
        fig.add_trace(
            go.Bar(
                name=label,
                x=field_labels,
                y=scores,
                marker_opacity=_comparison_series_opacity(series_index, series_count),
                legendgroup=label,
                showlegend=True,
                hovertemplate=(
                    f"{label}<br>%{{x}}<br>mean: %{{y:.3f}}<extra></extra>"
                ),
            )
        )

    if title is None:
        if compare == "prompt":
            title = f"Mean scores by field — model={model}"
        else:
            title = f"Mean scores by field — prompt={prompt}"
    fig.update_layout(
        title=title,
        barmode="group",
        xaxis_title="leaf field",
        yaxis=dict(range=[0, MEAN_SCORE_Y_MAX], title="mean score"),
    )
    return _apply_plot_template(fig)


def plot_comparison_layer_s(
    summaries: RunSummaries | Sequence[RunSummary],
    *,
    compare: Literal["prompt", "model"] = "prompt",
    model: str | None = None,
    prompt: str | None = None,
    title: str | None = None,
) -> go.Figure | None:
    """Grouped structural row counts across prompts or models."""
    selected = _comparison_summaries(
        summaries,
        compare=compare,
        model=model,
        prompt=prompt,
    )
    traces_added = False
    fig = go.Figure()
    list_key = selected[0].by_list_keys[0] if selected[0].by_list_keys else None
    series_count = len(selected)
    for series_index, summary in enumerate(selected):
        counts = _primary_layer_s_counts(summary)
        if not counts:
            continue
        label = _series_label(summary, compare=compare)
        values = [counts.get(key, 0) for key in LAYER_S_ORDER]
        colors = [LAYER_S_COLORS[key] for key in LAYER_S_ORDER]
        fig.add_trace(
            go.Bar(
                name=label,
                x=list(LAYER_S_ORDER),
                y=values,
                marker_color=colors,
                marker_opacity=_comparison_series_opacity(series_index, series_count),
                legendgroup=label,
                showlegend=True,
            )
        )
        traces_added = True
    if not traces_added:
        return None
    if title is None:
        if compare == "prompt":
            title = f"{LAYER_S_TITLE} comparison — model={model}"
        else:
            title = f"{LAYER_S_TITLE} comparison — prompt={prompt}"
        if list_key:
            title = f"{title} ({list_key})"
    fig.update_layout(
        title=title,
        barmode="group",
        xaxis_title="structural outcome",
        yaxis_title="count",
        yaxis=_zero_rangemode(),
    )
    return _apply_plot_template(fig)


def plot_comparison_layer1(
    summaries: RunSummaries | Sequence[RunSummary],
    *,
    compare: Literal["prompt", "model"] = "prompt",
    model: str | None = None,
    prompt: str | None = None,
    title: str | None = None,
) -> go.Figure:
    """Grouped stacked Layer-1 bars across prompts or models."""
    selected = _comparison_summaries(
        summaries,
        compare=compare,
        model=model,
        prompt=prompt,
    )
    fields = sorted(
        {
            field
            for summary in selected
            for field in layer_counts_by_property(
                summary, LAYER1_ORDER, "layer1_counts"
            )["field"].tolist()
        },
        key=str,
    )
    series_frames = {
        _series_label(summary, compare=compare): layer_counts_by_property(
            summary, LAYER1_ORDER, "layer1_counts"
        )
        for summary in selected
    }
    if title is None:
        if compare == "prompt":
            title = f"{LAYER1_TITLE} comparison — model={model}"
        else:
            title = f"{LAYER1_TITLE} comparison — prompt={prompt}"
    return _plot_comparison_stacked(
        fields=fields,
        series_frames=series_frames,
        order=LAYER1_ORDER,
        color_map=LAYER1_COLORS,
        compare=compare,
        title=title,
        series_label="prompt" if compare == "prompt" else "model",
    )


def plot_comparison_layer2_binary(
    summaries: RunSummaries | Sequence[RunSummary],
    *,
    compare: Literal["prompt", "model"] = "prompt",
    model: str | None = None,
    prompt: str | None = None,
    title: str | None = None,
) -> go.Figure:
    """Grouped stacked binary Layer-2 bars across prompts or models."""
    return _plot_comparison_layer2(
        summaries,
        compare=compare,
        model=model,
        prompt=prompt,
        title=title,
        metric="binary",
    )


def plot_comparison_layer2_graded(
    summaries: RunSummaries | Sequence[RunSummary],
    *,
    compare: Literal["prompt", "model"] = "prompt",
    model: str | None = None,
    prompt: str | None = None,
    title: str | None = None,
) -> go.Figure:
    """Grouped stacked graded Layer-2 bars across prompts or models."""
    return _plot_comparison_layer2(
        summaries,
        compare=compare,
        model=model,
        prompt=prompt,
        title=title,
        metric="graded",
    )


def _plot_comparison_layer2(
    summaries: RunSummaries | Sequence[RunSummary],
    *,
    compare: Literal["prompt", "model"],
    model: str | None,
    prompt: str | None,
    title: str | None,
    metric: Literal["binary", "graded"],
) -> go.Figure:
    selected = _comparison_summaries(
        summaries,
        compare=compare,
        model=model,
        prompt=prompt,
    )
    if metric == "binary":
        order = LAYER2_BINARY_ORDER
        colors = LAYER2_BINARY_COLORS
        default_title = f"{LAYER2_BINARY_TITLE} comparison"
    else:
        order = LAYER2_GRADED_ORDER
        colors = LAYER2_GRADED_COLORS
        default_title = f"{LAYER2_GRADED_TITLE} comparison"

    series_frames: dict[str, pd.DataFrame] = {}
    fields: set[str] = set()
    for summary in selected:
        binary_df, graded_df = split_layer2_by_metric(summary)
        frame = binary_df if metric == "binary" else graded_df
        label = _series_label(summary, compare=compare)
        series_frames[label] = frame
        fields.update(frame["field"].tolist())

    if title is None:
        if compare == "prompt":
            title = f"{default_title} — model={model}"
        else:
            title = f"{default_title} — prompt={prompt}"
    return _plot_comparison_stacked(
        fields=sorted(fields),
        series_frames=series_frames,
        order=order,
        color_map=colors,
        compare=compare,
        title=title,
        series_label="prompt" if compare == "prompt" else "model",
    )


def _add_dashboard_stacked_column(
    fig: go.Figure,
    *,
    col: int,
    frame: pd.DataFrame,
    order: Sequence[str],
    color_map: Mapping[str, str],
) -> None:
    if frame.empty:
        return
    fields = frame["field"].tolist()
    legend_name = f"legend{col}"
    for outcome in order:
        if outcome not in frame.columns:
            continue
        values = frame[outcome].tolist()
        if sum(values) == 0:
            continue
        fig.add_trace(
            go.Bar(
                x=fields,
                y=values,
                name=outcome,
                marker_color=color_map[outcome],
                legend=legend_name,
                showlegend=True,
                legendgroup=legend_name,
            ),
            row=1,
            col=col,
        )


def build_dashboard(
    summary: RunSummary,
    *,
    title: str | None = None,
) -> go.Figure:
    """Four-column dashboard: Layer S, Layer 1, Layer 2 binary, Layer 2 graded."""
    layer1_df = layer_counts_by_property(summary, LAYER1_ORDER, "layer1_counts")
    layer2_binary_df, layer2_graded_df = split_layer2_by_metric(summary)
    layer_s_counts = _primary_layer_s_counts(summary)

    subplot_titles = (
        LAYER_S_TITLE,
        LAYER1_TITLE,
        LAYER2_BINARY_TITLE,
        LAYER2_GRADED_TITLE,
    )
    fig = make_subplots(
        rows=1,
        cols=4,
        subplot_titles=subplot_titles,
    )

    if layer_s_counts:
        layer_s_labels = list(LAYER_S_ORDER)
        layer_s_values = [layer_s_counts.get(label, 0) for label in layer_s_labels]
        layer_s_bar_colors = [LAYER_S_COLORS[label] for label in layer_s_labels]
        fig.add_trace(
            go.Bar(
                x=layer_s_labels,
                y=layer_s_values,
                marker_color=layer_s_bar_colors,
                showlegend=False,
            ),
            row=1,
            col=1,
        )

    _add_dashboard_stacked_column(
        fig,
        col=2,
        frame=layer1_df,
        order=LAYER1_ORDER,
        color_map=LAYER1_COLORS,
    )
    _add_dashboard_stacked_column(
        fig,
        col=3,
        frame=layer2_binary_df,
        order=LAYER2_BINARY_ORDER,
        color_map=LAYER2_BINARY_COLORS,
    )
    _add_dashboard_stacked_column(
        fig,
        col=4,
        frame=layer2_graded_df,
        order=LAYER2_GRADED_ORDER,
        color_map=LAYER2_GRADED_COLORS,
    )
    
    fig.update_annotations(
        font_size=12,
        xanchor="center",
        yanchor="middle",
        y=1,
        align="center",
    )

    if title is None:
        title = (
            f"{summary.check} — {summary.model} / {summary.prompt}"
        )
        
    layout_kwargs: dict[str, Any] = {
        "title_text": title,
        "title_x": 0.5,
        "title_y": 0.95,
        "title_font_size": 16,
        "height": 460,
        "barmode": "stack",
        "showlegend": False,
        "yaxis": _zero_rangemode(),
        "yaxis2": _zero_rangemode(),
        "yaxis3": _zero_rangemode(),
        "yaxis4": _zero_rangemode(),
    }
    for col, legend_layout in _DASHBOARD_LEGEND_LAYOUT.items():
        layout_kwargs[f"legend{col}"] = legend_layout
    fig.update_layout(**layout_kwargs)
    return _apply_plot_template(fig)
