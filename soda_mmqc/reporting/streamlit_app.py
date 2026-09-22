"""Streamlit UI for Layer 2 mean scores and instance drill-down."""

from __future__ import annotations

import json
from typing import Any, Literal

import pandas as pd
import streamlit as st

from soda_mmqc.reporting.aggregate import RunSummary, RunSummaries
from soda_mmqc.reporting.context import ExampleContext, inspect_instance
from soda_mmqc.reporting.display import build_figure_image_plot
from soda_mmqc.reporting.load import (
    EvaluationCheckRef,
    discover_evaluation_checks,
    evaluation_data_cache_key,
    try_load_run_summaries,
)
from soda_mmqc.reporting.navigate import instance_object_path
from soda_mmqc.reporting.plots import plot_mean_score_with_instances
from soda_mmqc.reporting.styles import MEAN_SCORE_PLOT_TITLE, PLOTLY_TEMPLATE
from soda_mmqc.reporting.tables import layer2_instance_table

CompareMode = Literal["single", "arm", "model"]

# Match comparative-reporting.ipynb drill-down defaults
INSTANCE_FIGURE_HEIGHT = 1200
INSTANCE_FIGURE_WIDTH = 800


def _format_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return repr(value)


def render_instance_context(
    ctx: ExampleContext,
    *,
    figure_height: int = INSTANCE_FIGURE_HEIGHT,
    figure_width: int | None = INSTANCE_FIGURE_WIDTH,
) -> None:
    """Render gold/pred drill-down (Streamlit backend)."""
    st.subheader("Selected instance")
    st.caption(
        f"`{ctx.checklist}` / `{ctx.check}` / `{ctx.model}` / `{ctx.arm}` · "
        f"`source={ctx.ref.source}`"
    )
    if ctx.steps:
        st.write("Path:", f"`{'.'.join(str(step) for step in ctx.steps)}`")
    if ctx.pred_missing:
        st.warning("Prediction row missing for this instance.")

    preview = ctx.example_preview
    if preview is not None:
        if preview.caption:
            st.markdown(f"**Caption**  \n{preview.caption}")
        if preview.image_path is not None and preview.image_path.is_file():
            fig = build_figure_image_plot(
                preview.image_path,
                height=figure_height,
                width=figure_width,
            )
            if fig is not None:
                st.plotly_chart(
                    fig,
                    width="stretch",
                    height=figure_height,
                    config={
                        "scrollZoom": True,
                        "displayModeBar": True,
                        "modeBarButtonsToRemove": ["select2d", "lasso2d"],
                    },
                )
            else:
                st.image(str(preview.image_path))

    pred_label = "pred (missing)" if ctx.pred_missing else "pred"
    leaf_name = ctx.steps[-1] if ctx.steps and isinstance(ctx.steps[-1], str) else None

    if not ctx.steps:
        col_gold, col_pred = st.columns(2)
        with col_gold:
            st.markdown("**Gold (full model output)**")
            st.code(_format_value(ctx.expected_output), language="json")
        with col_pred:
            st.markdown(f"**{pred_label.title()} (full model output)**")
            st.code(_format_value(ctx.model_output), language="json")
    elif leaf_name is not None and ctx.exp_row is not None:
        col_gold, col_pred = st.columns(2)
        with col_gold:
            st.markdown("**Gold row**")
            st.code(_format_value(ctx.exp_row), language="json")
        with col_pred:
            st.markdown(f"**{pred_label.title()} row**")
            st.code(_format_value(ctx.pred_row), language="json")
        col_gold, col_pred = st.columns(2)
        with col_gold:
            st.markdown(f"**Gold `{leaf_name}`**")
            st.code(_format_value(ctx.exp_value), language="json")
        with col_pred:
            st.markdown(f"**{pred_label.title()} `{leaf_name}`**")
            st.code(_format_value(ctx.pred_value), language="json")
    else:
        col_gold, col_pred = st.columns(2)
        with col_gold:
            st.markdown("**Gold at path**")
            st.code(_format_value(ctx.exp_subtree), language="json")
        with col_pred:
            st.markdown(f"**{pred_label.title()} at path**")
            st.code(_format_value(ctx.pred_subtree), language="json")


def _selected_instance_index(selection: Any) -> int | None:
    if selection is None or not getattr(selection, "points", None):
        return None
    points = selection.points
    if not points:
        return None
    point = points[0]
    customdata = point.get("customdata")
    if customdata is None:
        return None
    if isinstance(customdata, (list, tuple)):
        return int(customdata[0])
    return int(customdata)


@st.cache_data(show_spinner="Loading evaluation runs…")
def _load_summaries(
    checklist: str,
    check: str,
    _cache_key: str,
) -> tuple[RunSummaries | None, str | None]:
    return try_load_run_summaries(checklist, check)


def _check_label(ref: EvaluationCheckRef) -> str:
    label = f"{ref.checklist} / {ref.check}"
    if not ref.has_manifest:
        label += " (no eval-manifest)"
    return label


def _render_mean_score_panel(
    summary: RunSummary,
    *,
    chart_key: str,
    enable_selection: bool,
) -> pd.Series | None:
    title = (
        f"{summary.check} — {summary.model} / {summary.arm} — "
        f"{MEAN_SCORE_PLOT_TITLE}"
    )
    fig, inst = plot_mean_score_with_instances(
        summary,
        title=title,
        seed=0,
        return_instances=True,
    )
    fig.update_layout(template=PLOTLY_TEMPLATE, height=450)

    if enable_selection and not inst.empty:
        event = st.plotly_chart(
            fig,
            width="stretch",
            on_select="rerun",
            selection_mode="points",
            key=chart_key,
        )
        idx = _selected_instance_index(getattr(event, "selection", None))
        if idx is not None and 0 <= idx < len(inst):
            return inst.iloc[idx]
    else:
        st.plotly_chart(fig, width="stretch", key=chart_key)
    return None


def _render_culprit(summary: RunSummary, row: pd.Series) -> None:
    path = str(row["path"])
    leaf = str(row["field"])
    source = str(row["source"])
    st.markdown("**Instance row**")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "source": source,
                    "path": path,
                    "leaf": leaf,
                    "score": row.get("score"),
                    "layer2": row.get("layer2"),
                }
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    errors = layer2_instance_table(summary)
    if not errors.empty:
        match = errors[(errors["source"] == source) & (errors["path"] == path)]
        if not match.empty:
            st.markdown("**Layer 2 error record**")
            st.dataframe(match, width="stretch", hide_index=True)

    ctx = inspect_instance(
        summary,
        source=source,
        object_path=instance_object_path(path),
        leaf=leaf,
    )
    try:
        render_instance_context(ctx)
    except (FileNotFoundError, KeyError, OSError) as exc:
        st.warning(f"Could not load full example context: {exc}")


def main() -> None:
    st.set_page_config(
        page_title="MMQC evaluation reporting",
        layout="wide",
    )
    st.title("Layer 2 mean scores")
    st.caption(
        "Mean score per leaf field (applicable instances only). "
        "Click a red dot to inspect gold vs pred."
    )

    checks = discover_evaluation_checks()
    if not checks:
        st.warning(
            "No evaluation results found under `data/evaluation/`. "
            "Run `evaluate` first."
        )
        return

    compare_mode: CompareMode = "single"
    active_summaries: list[tuple[str, RunSummary]] = []
    summaries: RunSummaries | None = None
    load_error: str | None = None

    with st.sidebar:
        check_labels = [_check_label(ref) for ref in checks]
        selected_label = st.selectbox("Check", check_labels)
        ref = checks[check_labels.index(selected_label)]

        compare_mode = st.radio(
            "Contrast by",
            options=("single", "arm", "model"),
            format_func=lambda value: {
                "single": "Single run",
                "arm": "Arm",
                "model": "Model",
            }[value],
            horizontal=True,
        )

        summaries, load_error = _load_summaries(
            ref.checklist,
            ref.check,
            evaluation_data_cache_key(ref.checklist, ref.check),
        )

        if load_error:
            st.error("Cannot load")
        elif summaries is not None and len(summaries) == 0:
            st.warning("No runs loaded")
        elif summaries is not None:
            models = summaries.models
            arms = summaries.arms

            def _pick(model: str, arm: str) -> list:
                """Every replicate of one (model, arm), in order.

                A RunRef carries a replicate too, so one (model, arm)
                can name several runs. They are listed rather than
                pooled: pooling replicates is a statistic, and this
                selector only chooses what to show.
                """
                return [
                    summary
                    for summary in summaries.for_model(model)
                    if summary.arm == arm
                ]

            def _label(summary) -> str:
                reps = summaries.replicates
                suffix = f" rep-{summary.replicate:02d}" if len(reps) > 1 else ""
                return f"{summary.arm}{suffix}"

            if compare_mode == "single":
                model = st.selectbox("Model", models)
                arm = st.selectbox("Arm", arms)
                active_summaries = [
                    (f"{model} / {_label(summary)}", summary)
                    for summary in _pick(model, arm)
                ]
            elif compare_mode == "arm":
                model = st.selectbox("Model (fixed)", models)
                active_summaries = [
                    (_label(summary), summary)
                    for arm in arms
                    for summary in _pick(model, arm)
                ]
            else:
                arm = st.selectbox("Arm (fixed)", arms)
                active_summaries = [
                    (model, summary)
                    for model in models
                    for summary in _pick(model, arm)
                ]

    if load_error or not active_summaries:
        if load_error:
            st.error("Cannot load this check")
            st.markdown(load_error)
            if not ref.has_manifest:
                st.info(
                    "Checks need an `eval-manifest.json` beside `schema.json` before "
                    "reporting can aggregate results."
                )
        elif summaries is not None and len(summaries) == 0:
            st.warning("No runs loaded for this check.")
        return

    if compare_mode == "single":
        _, summary = active_summaries[0]
        selected = _render_mean_score_panel(
            summary,
            chart_key="mean_score_single",
            enable_selection=True,
        )
        if selected is not None:
            _render_culprit(summary, selected)
    else:
        tabs = st.tabs([label for label, _ in active_summaries])
        for tab, (label, summary) in zip(tabs, active_summaries, strict=True):
            with tab:
                selected = _render_mean_score_panel(
                    summary,
                    chart_key=f"mean_score_{compare_mode}_{label}",
                    enable_selection=True,
                )
                if selected is not None:
                    _render_culprit(summary, selected)


if __name__ == "__main__":
    main()
