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
    ARM_CONTRAST_BAR_COLOR,
    ARM_CONTRAST_PANEL_CHROME,
    ARM_CONTRAST_ROW_GAP,
    ARM_CONTRAST_ROW_HEIGHT,
    ARM_LEVELS_COLORS,
    ARM_CONTRAST_ZERO_LINE_COLOR,
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
    """Per-property mean scores, with the denominator each was taken over.

    ``mean_score`` stays ``None`` where nothing was applicable. Plotly
    renders ``None`` in a ``y`` array as a gap, which is what we want: a
    gap says "nothing to score here", a zero bar says "scored zero", and
    those are different findings.

    ``n_scored`` rides along so a chart can put the denominator in its
    hover text. A layer-2 mean without it is not a reportable number.
    """
    rows: list[dict[str, Any]] = []
    for leaf_property in field_order(summary.manifest, summary.by_property.keys()):
        rollup = summary.by_property[leaf_property]
        rows.append(
            {
                "leaf_property": leaf_property,
                "field": leaf_property_tail(leaf_property),
                "mean_score": rollup.mean_score,
                "n_scored": rollup.n_scored,
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
    compare: Literal["arm", "model"],
    model: str | None = None,
    arm: str | None = None,
) -> tuple[RunSummary, ...]:
    if isinstance(summaries, RunSummaries):
        if compare == "arm":
            if model is None:
                raise ValueError("model is required when compare='arm'")
            selected = summaries.for_model(model)
        else:
            if arm is None:
                raise ValueError("arm is required when compare='model'")
            selected = summaries.for_arm(arm)
    else:
        selected = tuple(summaries)

    if not selected:
        raise ValueError("No summaries selected for comparison plot")
    return selected


def _series_label(summary: RunSummary, *, compare: Literal["arm", "model"]) -> str:
    return summary.arm if compare == "arm" else summary.model


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
    compare: Literal["arm", "model"] | None,
) -> dict[str, Any]:
    marker: dict[str, Any] = {"color": color}
    if compare == "arm":
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
    compare: Literal["arm", "model"] | None,
    title: str,
    series_label: str,
) -> go.Figure:
    """One stacked-bar subplot per leaf field; x = arm or model within each."""
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
    spread: pd.DataFrame | None = None,
    arm: str | None = None,
) -> go.Figure:
    """Per-property mean score bars, with replicate spread when given.

    ``spread`` is a :func:`~soda_mmqc.reporting.aggregate.replicate_spread`
    frame. Once a run has replicates, plotting two arms as bare bars is
    actively misleading -- the reader cannot tell a real difference from
    resampling noise -- so the error bars are the point of passing it.
    Where a property has fewer than two replicates its ``sd`` is NA and
    that bar simply gets no error bar, rather than a zero-length one
    implying perfect reproducibility.

    A property with nothing applicable is a gap, never a zero bar.
    """
    if frame.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return _apply_plot_template(fig)

    # None -> a gap in the bar chart. object dtype keeps None as None;
    # a float column would coerce it to NaN, which plots the same but
    # reads as a number in the data.
    values = [
        None if pd.isna(value) else float(value)
        for value in frame["mean_score"]
    ]
    denominators = (
        list(frame["n_scored"]) if "n_scored" in frame else [None] * len(frame)
    )

    error_y = None
    if spread is not None and not spread.empty:
        by_property = spread
        if arm is not None:
            by_property = by_property[by_property["arm"] == arm]
        sd_by_property = (
            by_property.set_index("property")["sd"].to_dict()
            if not by_property.empty
            else {}
        )
        sds = [
            None
            if pd.isna(sd_by_property.get(key, pd.NA))
            else float(sd_by_property[key])
            for key in frame["leaf_property"]
        ]
        if any(sd is not None for sd in sds):
            error_y = dict(type="data", array=sds, visible=True)

    fig = go.Figure(
        go.Bar(
            x=list(frame["field"]),
            y=values,
            error_y=error_y,
            customdata=denominators,
            hovertemplate=(
                "%{x}<br>mean %{y:.3f}"
                "<br>over %{customdata} scored instance(s)"
                "<extra></extra>"
            ),
        )
    )
    fig.update_layout(
        title=title,
        xaxis_title="leaf field",
        yaxis_title="mean score",
        yaxis=dict(range=[0, 1]),
    )
    return _apply_plot_template(fig)


def plot_comparison_mean_scores(
    summaries: RunSummaries | Sequence[RunSummary],
    *,
    compare: Literal["arm", "model"] = "arm",
    model: str | None = None,
    arm: str | None = None,
    title: str | None = None,
) -> go.Figure:
    """Grouped mean-score bars across arms (or models) per leaf field."""
    selected = _comparison_summaries(
        summaries,
        compare=compare,
        model=model,
        arm=arm,
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
        if compare == "arm":
            title = f"Mean scores by field — model={model}"
        else:
            title = f"Mean scores by field — arm={arm}"
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
    compare: Literal["arm", "model"] = "arm",
    model: str | None = None,
    arm: str | None = None,
    title: str | None = None,
) -> go.Figure | None:
    """Grouped structural row counts across arms or models."""
    selected = _comparison_summaries(
        summaries,
        compare=compare,
        model=model,
        arm=arm,
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
        if compare == "arm":
            title = f"{LAYER_S_TITLE} comparison — model={model}"
        else:
            title = f"{LAYER_S_TITLE} comparison — arm={arm}"
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
    compare: Literal["arm", "model"] = "arm",
    model: str | None = None,
    arm: str | None = None,
    title: str | None = None,
) -> go.Figure:
    """Grouped stacked Layer-1 bars across arms or models."""
    selected = _comparison_summaries(
        summaries,
        compare=compare,
        model=model,
        arm=arm,
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
        if compare == "arm":
            title = f"{LAYER1_TITLE} comparison — model={model}"
        else:
            title = f"{LAYER1_TITLE} comparison — arm={arm}"
    return _plot_comparison_stacked(
        fields=fields,
        series_frames=series_frames,
        order=LAYER1_ORDER,
        color_map=LAYER1_COLORS,
        compare=compare,
        title=title,
        series_label="arm" if compare == "arm" else "model",
    )


def plot_comparison_layer2_binary(
    summaries: RunSummaries | Sequence[RunSummary],
    *,
    compare: Literal["arm", "model"] = "arm",
    model: str | None = None,
    arm: str | None = None,
    title: str | None = None,
) -> go.Figure:
    """Grouped stacked binary Layer-2 bars across arms or models."""
    return _plot_comparison_layer2(
        summaries,
        compare=compare,
        model=model,
        arm=arm,
        title=title,
        metric="binary",
    )


def plot_comparison_layer2_graded(
    summaries: RunSummaries | Sequence[RunSummary],
    *,
    compare: Literal["arm", "model"] = "arm",
    model: str | None = None,
    arm: str | None = None,
    title: str | None = None,
) -> go.Figure:
    """Grouped stacked graded Layer-2 bars across arms or models."""
    return _plot_comparison_layer2(
        summaries,
        compare=compare,
        model=model,
        arm=arm,
        title=title,
        metric="graded",
    )


def _plot_comparison_layer2(
    summaries: RunSummaries | Sequence[RunSummary],
    *,
    compare: Literal["arm", "model"],
    model: str | None,
    arm: str | None,
    title: str | None,
    metric: Literal["binary", "graded"],
) -> go.Figure:
    selected = _comparison_summaries(
        summaries,
        compare=compare,
        model=model,
        arm=arm,
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
        if compare == "arm":
            title = f"{default_title} — model={model}"
        else:
            title = f"{default_title} — arm={arm}"
    return _plot_comparison_stacked(
        fields=sorted(fields),
        series_frames=series_frames,
        order=order,
        color_map=colors,
        compare=compare,
        title=title,
        series_label="arm" if compare == "arm" else "model",
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
            f"{summary.check} — {summary.model} / {summary.arm}"
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


def _check_panel_grid(
    checks: Sequence[str],
    bars_per_check: Mapping[str, int],
    *,
    columns: int,
) -> tuple[go.Figure, int, int, int]:
    """An empty per-check panel grid, sized for the bars it will hold.

    Each row is sized for its own tallest panel, so a row holding a
    two-property check beside an eight-property one does not carry six
    rows of blank space.

    ``vertical_spacing`` is a fraction of the whole figure applied
    between every pair of rows, so a constant one does not survive being
    stacked: ten gaps at 0.08 leave the panels a fifth of the height.
    The gap is fixed in pixels and the fraction derived from the height
    it produces.
    """
    cols = max(1, int(columns))
    rows = (len(checks) + cols - 1) // cols
    row_heights = [
        ARM_CONTRAST_PANEL_CHROME
        + ARM_CONTRAST_ROW_HEIGHT
        * max(
            int(bars_per_check[check])
            for check in checks[index * cols:(index + 1) * cols]
        )
        for index in range(rows)
    ]
    gap = ARM_CONTRAST_ROW_GAP if rows > 1 else 0
    total_height = sum(row_heights) + gap * (rows - 1)
    fig = make_subplots(
        rows=rows,
        cols=cols,
        subplot_titles=list(checks),
        shared_xaxes=False,
        shared_yaxes=False,
        row_heights=row_heights,
        vertical_spacing=(gap / total_height) if rows > 1 else 0.0,
        horizontal_spacing=_COMPARISON_SUBPLOT_HORIZONTAL_SPACING,
    )
    return fig, rows, cols, total_height


def _finish_check_panels(
    fig: go.Figure,
    *,
    n_checks: int,
    rows: int,
    cols: int,
    total_height: int,
    title: str,
    xlabel: str,
    span: tuple[float, float] | None,
    showlegend: bool = False,
) -> go.Figure:
    """Shared range on every panel, one axis title per column.

    ``span`` of ``None`` leaves each panel to scale itself, which is
    right when the panels hold quantities of different magnitude and
    wrong when they hold the same one.
    """
    if span is not None:
        fig.update_xaxes(range=list(span))
    fig.update_yaxes(autorange="reversed")
    for col in range(1, cols + 1):
        # A trailing column can hold no panel at all -- three categories
        # across two columns leaves the second column of the last row
        # empty -- and naming an axis that is not there raises.
        occupied = [
            row
            for row in range(1, rows + 1)
            if (row - 1) * cols + (col - 1) < n_checks
        ]
        if not occupied:
            continue
        fig.update_xaxes(title_text=xlabel, row=max(occupied), col=col)
    fig.update_layout(
        title_text=title, height=total_height, showlegend=showlegend
    )
    return _apply_plot_template(fig)


def _strip_shared_list_root(properties: Sequence[str]) -> list[str]:
    """Drop the list root shared by every property of one panel.

    A per-check panel's properties all hang off the same output list, so
    every tick read ``outputs[].something``. The root is what the panel
    title already implies, and ten characters of it on a 49-character
    label is the difference between a panel with room for its bars and
    one whose labels overflow into its neighbour.

    Only a root shared by *all* of them is dropped, and never the whole
    label: a check with two lists would otherwise collide ``a[].name``
    with ``b[].name``. What remains keeps any deeper path, so
    ``units_provided[].axis`` stays apart from
    ``unit_definition_as_provided[].axis``.
    """
    if not properties:
        return []
    candidates: list[str] = []
    first = properties[0]
    index = first.find("[].")
    while index != -1:
        candidates.append(first[: index + 3])
        index = first.find("[].", index + 1)
    for prefix in reversed(candidates):
        if all(
            prop.startswith(prefix) and len(prop) > len(prefix)
            for prop in properties
        ):
            return [prop[len(prefix):] for prop in properties]
    return list(properties)


def plot_arm_contrast_by_check(
    contrast: pd.DataFrame,
    *,
    columns: int = 1,
    title: str = "Paired arm contrast, per property",
    xlabel: str = "difference in mean_score",
) -> go.Figure:
    """One panel per check; within a panel, one bar per leaf property.

    A difference is only interpretable against the other properties of
    the same check. Pooled into one axis, the eleven exp-01 checks became
    a single column of 62 bars whose labels had to carry the whole
    property path to stay apart -- so the panel takes over that job and
    the tick keeps only the within-record path.

    The x axis is shared across panels. Letting each autoscale would draw
    a 0.002 difference the same width as a 0.2 one, which is the one
    reading this figure exists to prevent.

    Nothing here decides whether a difference is real. ``se`` is drawn
    because a difference without it is not a number, and the bars are one
    neutral colour because which direction counts as better is the
    experiment's claim.

    One column by default, not the four ``_comparison_subplot_grid``
    packs. That grid suits vertical bars over short categories; here
    plotly hangs each y tick label outside its panel and into whatever
    sits to the left, so at two columns the right panel's labels were
    drawn across the left panel's bars and the two titles ran together.
    A 40-character label needs the full width. ``columns`` raises it for
    a check set with shorter names.
    """
    if contrast.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return _apply_plot_template(fig)

    checks = sorted(contrast["check"].unique())
    fig, rows, cols, total_height = _check_panel_grid(
        checks, contrast["check"].value_counts(), columns=columns
    )

    for panel_index, check in enumerate(checks):
        row = panel_index // cols + 1
        col = panel_index % cols + 1
        panel = contrast[contrast["check"] == check].sort_values(
            "difference", ascending=True, kind="stable"
        )
        errors = (
            panel["se"].astype(float).fillna(0.0).tolist()
            if "se" in panel
            else None
        )
        fig.add_trace(
            go.Bar(
                x=panel["difference"].astype(float).tolist(),
                y=_strip_shared_list_root(panel["property"].tolist()),
                orientation="h",
                marker_color=ARM_CONTRAST_BAR_COLOR,
                error_x=(
                    {"type": "data", "array": errors, "visible": True}
                    if errors is not None
                    else None
                ),
                customdata=panel[["path"]].to_numpy(),
                hovertemplate="%{customdata[0]}<br>%{x:.4f}<extra></extra>",
                showlegend=False,
            ),
            row=row,
            col=col,
        )
        fig.add_vline(
            x=0,
            line_width=1,
            line_color=ARM_CONTRAST_ZERO_LINE_COLOR,
            row=row,
            col=col,
        )

    # One explicit range on every panel: `shared_xaxes` only links pan and
    # zoom, and a reader comparing panels needs them equal before touching
    # anything.
    return _finish_check_panels(
        fig,
        n_checks=len(checks),
        rows=rows,
        cols=cols,
        total_height=total_height,
        title=title,
        xlabel=xlabel,
        span=_arm_contrast_x_range(contrast),
    )


def _arm_contrast_x_range(contrast: pd.DataFrame) -> tuple[float, float]:
    """Symmetric-enough bounds covering every bar and its error bar."""
    differences = contrast["difference"].astype(float)
    errors = (
        contrast["se"].astype(float).fillna(0.0)
        if "se" in contrast
        else pd.Series(0.0, index=contrast.index)
    )
    low = float((differences - errors).min())
    high = float((differences + errors).max())
    # Always show zero: a panel of small same-signed differences would
    # otherwise be drawn without the line they are differences from.
    low, high = min(low, 0.0), max(high, 0.0)
    pad = (high - low) * 0.08 or 0.01
    return low - pad, high + pad


def plot_arm_levels_by_check(
    levels: pd.DataFrame,
    *,
    series: str = "arm",
    columns: int = 1,
    title: str = "Arm scores, per property",
    xlabel: str = "mean_score (paired examples)",
) -> go.Figure:
    """Both arms' scores side by side, one panel per check.

    The contrast figure says how far apart the arms are; this says where
    on the scale they were. A difference of -0.05 is a different finding
    at 0.95 than at 0.20, and the contrast alone cannot tell them apart.

    Takes :func:`arm_levels`, whose means are over the paired examples,
    so the gap a reader measures between a pair of bars is exactly the
    difference the other figure plots.

    The axis spans the whole of ``mean_score``. Autoscaling to the data
    would stretch 0.88 against 0.90 across the panel and invite a reading
    the numbers do not support.

    ``series`` names the column the legend groups on. It defaults to the
    raw ``arm``, but every check has its own variant arm name, so an
    eleven-check figure would carry twelve legend entries; pass a column
    holding a shared label instead.
    """
    if levels.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return _apply_plot_template(fig)

    checks = sorted(levels["check"].unique())
    fig, rows, cols, total_height = _check_panel_grid(
        checks, levels["check"].value_counts(), columns=columns
    )

    names = list(dict.fromkeys(levels[series]))
    palette = _arm_levels_palette(names)
    legend_shown: set[str] = set()

    for panel_index, check in enumerate(checks):
        row = panel_index // cols + 1
        col = panel_index % cols + 1
        panel = levels[levels["check"] == check]

        # One shared property order per panel, or the grouped bars would
        # not line up: sorted by the first series' score, so the panel
        # reads worst-first like the contrast panel beside it.
        first = panel[panel[series] == names[0]].set_index("property")["mean"]
        order = list(first.sort_values().index) or sorted(panel["property"].unique())
        labels = _strip_shared_list_root(order)

        for name in names:
            arm_rows = panel[panel[series] == name].set_index("property")
            if arm_rows.empty:
                continue
            show_legend = name not in legend_shown
            legend_shown.add(name)
            errors = arm_rows.reindex(order)["se"].astype(float).fillna(0.0)
            fig.add_trace(
                go.Bar(
                    x=arm_rows.reindex(order)["mean"].astype(float).tolist(),
                    y=labels,
                    orientation="h",
                    name=str(name),
                    legendgroup=str(name),
                    showlegend=show_legend,
                    marker_color=palette[name],
                    error_x={
                        "type": "data",
                        "array": errors.tolist(),
                        "visible": True,
                    },
                    customdata=arm_rows.reindex(order)[["path"]].to_numpy(),
                    hovertemplate=(
                        "%{customdata[0]}<br>%{x:.4f}<extra></extra>"
                    ),
                ),
                row=row,
                col=col,
            )

    span = _arm_levels_x_range(levels)
    fig.update_layout(barmode="group")
    return _finish_check_panels(
        fig,
        n_checks=len(checks),
        rows=rows,
        cols=cols,
        total_height=total_height,
        title=title,
        xlabel=xlabel,
        span=span,
        showlegend=True,
    )


def _arm_levels_palette(names: Sequence[Any]) -> dict[Any, str]:
    """Two arms are two categories, not a scale from bad to good."""
    return {
        name: ARM_LEVELS_COLORS[index % len(ARM_LEVELS_COLORS)]
        for index, name in enumerate(names)
    }


def _arm_levels_x_range(levels: pd.DataFrame) -> tuple[float, float]:
    """The full score range, widened only if an error bar runs past it."""
    means = levels["mean"].astype(float)
    errors = levels["se"].astype(float).fillna(0.0)
    return min(0.0, float((means - errors).min())), max(
        1.0, float((means + errors).max())
    )


def plot_grouped_counts(
    counts: pd.DataFrame,
    *,
    group: str,
    category: str,
    series: str = "arm",
    order: Sequence[str] | None = None,
    series_order: Sequence[Any] | None = None,
    columns: int = 1,
    title: str = "Counts by arm",
    xlabel: str = "count",
) -> go.Figure:
    """One panel per ``category``, ``group`` on the y axis, a bar per arm.

    The obvious layout is the other way round -- a panel per check, the
    outcomes stacked on its y axis -- and for counts it does not work.
    ``correct_applicable`` outweighs ``withheld_applicable`` by 14x to
    208x depending on the check, and ``correct_row`` outweighs
    ``spurious_row`` by roughly 200:1, so a panel would hold one long bar
    and three invisible ones. A panel per outcome gives each its own
    scale, which is why the ranges here are deliberately *not* shared.

    They do all start at zero. Bar length has to stay proportional to the
    count, which is also why this is not a log axis.

    Everything not named by ``group``, ``category`` or ``series`` is
    summed over -- replicates included, so a count is over the whole run
    rather than per replicate. A group with no rows in a category is
    drawn at zero: for a count, nothing observed is a result.

    ``series_order`` fixes the legend and the colours. Without it they
    follow whatever order the rows happened to arrive in, and the same
    two arms swap colour between one figure and the next; the default is
    sorted, which is at least stable.

    One column by default, as elsewhere: plotly hangs a y tick label
    outside its panel, and a layer-S group label reaches 45 characters
    (``plot-axis-units - unit_definition_as_provided``).
    """
    if counts.empty:
        fig = go.Figure()
        fig.update_layout(title=title)
        return _apply_plot_template(fig)

    totals = (
        counts.groupby([group, category, series], dropna=False, observed=True)[
            "count"
        ]
        .sum()
        .reset_index()
    )
    categories = (
        [value for value in order if value in set(totals[category])]
        if order is not None
        else sorted(totals[category].unique())
    )
    groups = sorted(totals[group].unique())
    present = set(totals[series])
    names = (
        [name for name in series_order if name in present]
        if series_order is not None
        else sorted(present)
    )
    palette = _arm_levels_palette(names)

    fig, rows, cols, total_height = _check_panel_grid(
        categories,
        {value: len(groups) * len(names) for value in categories},
        columns=columns,
    )

    legend_shown: set[str] = set()
    for panel_index, value in enumerate(categories):
        row = panel_index // cols + 1
        col = panel_index % cols + 1
        panel = totals[totals[category] == value]
        for name in names:
            values = (
                panel[panel[series] == name]
                .set_index(group)["count"]
                .reindex(groups)
                .fillna(0)
            )
            show_legend = name not in legend_shown
            legend_shown.add(name)
            fig.add_trace(
                go.Bar(
                    x=values.tolist(),
                    y=groups,
                    orientation="h",
                    name=str(name),
                    legendgroup=str(name),
                    showlegend=show_legend,
                    marker_color=palette[name],
                    hovertemplate="%{y}<br>%{x:,}<extra></extra>",
                ),
                row=row,
                col=col,
            )

    fig.update_layout(barmode="group")
    fig.update_xaxes(rangemode="tozero")
    return _finish_check_panels(
        fig,
        n_checks=len(categories),
        rows=rows,
        cols=cols,
        total_height=total_height,
        title=title,
        xlabel=xlabel,
        span=None,
        showlegend=True,
    )


def plot_check_layers(
    *,
    layer_s: pd.DataFrame,
    layer1: pd.DataFrame,
    layer2: pd.DataFrame,
    series: str = "arm",
    series_order: Sequence[Any] | None = None,
    title: str = "Three layers, one check",
) -> go.Figure:
    """One check across all three layers, arms side by side in each panel.

    Layer 2 is conditional on layer 1, which is conditional on there
    being a row at all, so the three read together: an arm that returns
    fewer rows has fewer applicability calls to make, and an arm that
    withholds more has fewer instances left for layer 2 to score. Put
    them on separate pages and the reader has to hold three figures in
    mind to notice that.

    Layer S and layer 1 stack their outcomes, because those partition
    everything that happened. Layer 2 does not: ``mean_score`` has
    nothing to stack, and two arms' means stacked would read as their
    sum, which is not a quantity.

    Plotly has no ``barmode="group+stack"``. Distinct ``offsetgroup``
    values under ``barmode="stack"`` put one arm's stack beside the
    other's, which is what makes a grouped stack possible at all.

    In the stacked panels colour belongs to the outcome, so an arm can
    only be opacity -- the convention the other comparison plots use. In
    layer 2 there is no outcome and colour is free, so the arm takes it:
    1.0 against 0.6 of one hue is not a difference a reader sees. The
    legend swatches use those colours.
    """
    names = _series_names(
        pd.concat([layer_s[[series]], layer1[[series]], layer2[[series]]]),
        series,
        series_order,
    )
    fig = make_subplots(
        rows=1,
        cols=3,
        subplot_titles=("Layer S", "Layer 1", "Layer 2"),
        horizontal_spacing=0.07,
    )

    _stacked_layer_panel(
        fig, layer_s, col=1, x="list_key", stack="outcome",
        order=LAYER_S_ORDER, colors=LAYER_S_COLORS,
        series=series, names=names, strip_root=False,
    )
    _stacked_layer_panel(
        fig, layer1, col=2, x="property", stack="layer1",
        order=LAYER1_ORDER, colors=LAYER1_COLORS,
        series=series, names=names, strip_root=True,
    )
    _mean_layer_panel(fig, layer2, col=3, series=series, names=names)

    # Which arm is which needs saying: in the stacked panels it is only
    # opacity, which no legend can show well. The swatch carries the
    # layer-2 colour instead, where the arm *is* the colour.
    for index, name in enumerate(names):
        fig.add_trace(
            go.Bar(
                x=[None], y=[None], name=str(name),
                marker={"color": _arm_color(index)},
                showlegend=True, legendgroup=f"arm::{name}",
            ),
            row=1, col=1,
        )

    fig.update_layout(barmode="stack", title_text=title, height=520)
    fig.update_yaxes(title_text="rows", row=1, col=1)
    fig.update_yaxes(title_text="instances", row=1, col=2)
    fig.update_yaxes(title_text="mean_score", range=[0, 1], row=1, col=3)
    return _apply_plot_template(fig)


def _arm_color(index: int) -> str:
    return ARM_LEVELS_COLORS[index % len(ARM_LEVELS_COLORS)]


def _series_names(
    frame: pd.DataFrame, series: str, series_order: Sequence[Any] | None
) -> list[Any]:
    present = set(frame[series])
    if series_order is None:
        return sorted(present)
    return [name for name in series_order if name in present]


def _stacked_layer_panel(
    fig: go.Figure,
    frame: pd.DataFrame,
    *,
    col: int,
    x: str,
    stack: str,
    order: Sequence[str],
    colors: Mapping[str, str],
    series: str,
    names: Sequence[Any],
    strip_root: bool,
) -> None:
    totals = frame.groupby([x, stack, series], observed=True)["count"].sum()
    categories = sorted({value for value, _, _ in totals.index})
    labels = (
        _strip_shared_list_root(categories) if strip_root else list(categories)
    )
    outcomes = [o for o in order if o in {value for _, value, _ in totals.index}]

    for index, name in enumerate(names):
        opacity = _comparison_series_opacity(index, len(names))
        for outcome in outcomes:
            fig.add_trace(
                go.Bar(
                    x=labels,
                    y=[
                        float(totals.get((category, outcome, name), 0))
                        for category in categories
                    ],
                    name=outcome,
                    legendgroup=outcome,
                    showlegend=index == 0,
                    offsetgroup=str(name),
                    marker={"color": colors[outcome], "opacity": opacity},
                    hovertemplate=(
                        f"{name}<br>%{{x}}<br>{outcome}: %{{y:,}}<extra></extra>"
                    ),
                ),
                row=1,
                col=col,
            )


def _mean_layer_panel(
    fig: go.Figure,
    frame: pd.DataFrame,
    *,
    col: int,
    series: str,
    names: Sequence[Any],
) -> None:
    categories = sorted(frame["property"].unique())
    labels = _strip_shared_list_root(categories)
    for index, name in enumerate(names):
        rows = frame[frame[series] == name].set_index("property").reindex(categories)
        fig.add_trace(
            go.Bar(
                x=labels,
                y=rows["mean"].astype(float).tolist(),
                name=str(name),
                legendgroup=f"arm::{name}",
                showlegend=False,
                offsetgroup=str(name),
                marker={"color": _arm_color(index)},
                error_y={
                    "type": "data",
                    "array": rows["sd"].astype(float).fillna(0.0).tolist(),
                    "visible": True,
                },
                hovertemplate=f"{name}<br>%{{x}}<br>%{{y:.4f}}<extra></extra>",
            ),
            row=1,
            col=col,
        )
