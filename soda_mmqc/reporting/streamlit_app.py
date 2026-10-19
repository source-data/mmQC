"""Streamlit UI: find the panels that pull a check's properties down.

For one check, each property is a bar (its mean score over examples and
replicates) with one dot per panel (that panel's score, averaged over the
replicates that scored it). Clicking a dot shows the figure, its caption,
and the panel's gold against every replicate's prediction.

Launched by ``mmqc report``. With a run root it reads that run::

    mmqc report experiments/runs/<run> --checklist fig-checklist \\
        --check do-fig-checklist-cm

and without one it lists what ``mmqc score`` wrote under
``data/evaluation/``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Literal, Sequence

import pandas as pd
import streamlit as st

from soda_mmqc.reporting.aggregate import RunSummaries, RunSummary, summarize_runs
from soda_mmqc.reporting.context import inspect_source
from soda_mmqc.reporting.display import build_figure_image_plot
from soda_mmqc.reporting.load import (
    EvaluationCheckRef,
    discover_evaluation_checks,
    evaluation_data_cache_key,
    load_run_root,
    run_root_cache_key,
    try_load_run_summaries,
)
from soda_mmqc.reporting.plots import plot_replicate_mean_scores
from soda_mmqc.reporting.replicates import (
    checks_in,
    panel_comparison,
    panel_row_path,
    spurious_rows_frame,
)
from soda_mmqc.reporting.styles import MEAN_SCORE_PLOT_TITLE, PLOTLY_TEMPLATE

CompareMode = Literal["single", "arm", "model"]

FIGURE_HEIGHT = 900
FIGURE_WIDTH = 800


def parse_app_args(argv: Sequence[str]) -> argparse.Namespace:
    """The arguments ``mmqc report`` passes after streamlit's ``--``."""
    parser = argparse.ArgumentParser(prog="mmqc report")
    parser.add_argument("root", nargs="?", type=Path)
    parser.add_argument("--checklist")
    parser.add_argument("--check")
    parser.add_argument("--model", default="")
    args = parser.parse_args(list(argv))
    if args.root is not None and not (args.checklist and args.check):
        parser.error("a run root needs --checklist and --check")
    return args


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
def _load_evaluation_summaries(
    checklist: str,
    check: str,
    _cache_key: str,
) -> tuple[RunSummaries | None, str | None]:
    return try_load_run_summaries(checklist, check)


@st.cache_data(show_spinner="Loading run…")
def _load_root_summaries(
    root: str,
    checklist: str,
    check: str,
    model: str,
    _cache_key: str,
) -> tuple[RunSummaries | None, str | None]:
    try:
        runs = load_run_root(
            Path(root), checklist=checklist, check=check, model=model
        )
    except (FileNotFoundError, OSError, ValueError) as exc:
        return None, str(exc)
    if len(runs) == 0:
        return None, (
            f"No scored replicate under `{root}`: run `mmqc score` on it "
            "first -- predictions alone are not enough."
        )
    return summarize_runs(runs), None


def _check_label(ref: EvaluationCheckRef) -> str:
    label = f"{ref.checklist} / {ref.check}"
    if not ref.has_manifest:
        label += " (no eval-manifest)"
    return label


def _replicates(summaries: RunSummaries, model: str, arm: str) -> list[RunSummary]:
    """Every replicate of one (model, arm) -- the most that may be pooled."""
    return [s for s in summaries.for_model(model) if s.arm == arm]


def _cell(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _score_style(score: Any) -> str:
    if score is None or score != score:
        return "color: #888"
    if score < 1.0:
        alpha = 0.15 + 0.5 * (1.0 - float(score))
        return f"background-color: rgba(220, 60, 60, {alpha:.2f})"
    return ""


def render_panel(
    replicates: Sequence[RunSummary],
    row: pd.Series,
) -> None:
    """The figure, its caption, and one panel's gold against each replicate."""
    source = str(row["source"])
    path = str(row["path"])
    row_path = panel_row_path(path)
    field = path[len(row_path) + 1:]

    st.subheader(f"{source} · {row_path}")
    st.caption(
        f"`{row['leaf_property']}` · mean {row['score']:.3f} over "
        f"{row['n_scored']} of {len(replicates)} replicate(s)"
    )

    try:
        preview = inspect_source(replicates[0], source=source).example_preview
    except (FileNotFoundError, KeyError, OSError) as exc:
        st.warning(f"Could not load the example: {exc}")
        preview = None

    col_figure, col_panel = st.columns([3, 2])
    with col_figure:
        if preview is not None and preview.image_path is not None:
            fig = build_figure_image_plot(
                preview.image_path, height=FIGURE_HEIGHT, width=FIGURE_WIDTH
            )
            if fig is not None:
                st.plotly_chart(
                    fig,
                    width="stretch",
                    config={
                        "scrollZoom": True,
                        "displayModeBar": True,
                        "modeBarButtonsToRemove": ["select2d", "lasso2d"],
                    },
                )
            else:
                st.image(str(preview.image_path))
    with col_panel:
        values, scores = panel_comparison(
            replicates, source=source, row_path=row_path
        )
        st.markdown("**Gold vs prediction**")
        st.caption(
            "Red: scored below 1 (darker is lower). Grey: not scored in that "
            "replicate. The selected field is marked ▶."
        )
        shown = values.map(_cell)
        shown.index = [
            f"▶ {name}" if name == field else name for name in shown.index
        ]
        styled = shown.style.apply(
            lambda column: [
                ""
                if column.name == "gold"
                else _score_style(scores[column.name].iloc[i])
                for i in range(len(column))
            ],
            axis=0,
        )
        st.dataframe(styled, width="stretch")
        if preview is not None and preview.caption:
            st.markdown("**Caption**")
            st.markdown(preview.caption)


def _render_check(
    replicates: Sequence[RunSummary],
    *,
    check: str | None,
    title: str,
    chart_key: str,
) -> None:
    fig, inst = plot_replicate_mean_scores(
        replicates, check=check, title=title, seed=0
    )
    fig.update_layout(template=PLOTLY_TEMPLATE, height=450)
    if inst.empty:
        st.plotly_chart(fig, width="stretch", key=chart_key)
        return
    event = st.plotly_chart(
        fig,
        width="stretch",
        on_select="rerun",
        selection_mode="points",
        key=chart_key,
    )
    spurious = spurious_rows_frame(replicates, check=check)
    if not spurious.empty:
        with st.expander(
            f"{len(spurious)} predicted row(s) with no gold row (no dot)"
        ):
            st.dataframe(spurious, width="stretch", hide_index=True)

    idx = _selected_instance_index(getattr(event, "selection", None))
    if idx is not None and 0 <= idx < len(inst):
        render_panel(replicates, inst.iloc[idx])


def main() -> None:
    st.set_page_config(page_title="mmQC report", layout="wide")
    args = parse_app_args(sys.argv[1:])

    with st.sidebar:
        if args.root is not None:
            checklist, check = args.checklist, args.check
            st.markdown(f"**Run** `{args.root}`  \n`{checklist}` / `{check}`")
            summaries, load_error = _load_root_summaries(
                str(args.root),
                checklist,
                check,
                args.model,
                run_root_cache_key(args.root, checklist, check),
            )
        else:
            refs = discover_evaluation_checks()
            if not refs:
                st.warning(
                    "No scored runs under `data/evaluation/`. Pass a run "
                    "root: `mmqc report <root> --checklist … --check …`."
                )
                return
            labels = [_check_label(ref) for ref in refs]
            ref = refs[labels.index(st.selectbox("Check", labels))]
            checklist, check = ref.checklist, ref.check
            summaries, load_error = _load_evaluation_summaries(
                checklist, check, evaluation_data_cache_key(checklist, check)
            )

    if load_error or summaries is None or len(summaries) == 0:
        st.error(load_error or "No runs loaded.")
        return

    with st.sidebar:
        lists = checks_in(list(summaries.values()))
        selected_list = (
            st.selectbox("Check within the run", lists)
            if len(lists) > 1
            else None
        )
        compare_mode: CompareMode = st.radio(
            "Contrast by",
            options=("single", "arm", "model"),
            format_func=lambda value: {
                "single": "Single arm",
                "arm": "Arm",
                "model": "Model",
            }[value],
            horizontal=True,
        )
        models, arms = summaries.models, summaries.arms
        if compare_mode == "single":
            model = st.selectbox("Model", models) if len(models) > 1 else models[0]
            arm = st.selectbox("Arm", arms) if len(arms) > 1 else arms[0]
            panels = [(f"{arm}", _replicates(summaries, model, arm))]
        elif compare_mode == "arm":
            model = st.selectbox("Model (fixed)", models)
            panels = [(arm, _replicates(summaries, model, arm)) for arm in arms]
        else:
            arm = st.selectbox("Arm (fixed)", arms)
            panels = [
                (model, _replicates(summaries, model, arm)) for model in models
            ]
        panels = [(label, reps) for label, reps in panels if reps]

    shown_check = selected_list or check
    st.title(shown_check)
    st.caption(
        "Bars: mean score over examples and replicates. Dots: one panel each, "
        "its score averaged over the replicates that scored it. Click a dot "
        "to see the figure, its caption, and gold against each prediction."
    )

    def title_for(label: str, reps: Sequence[RunSummary]) -> str:
        return (
            f"{shown_check} — {label} — {len(reps)} replicate(s) — "
            f"{MEAN_SCORE_PLOT_TITLE}"
        )

    if len(panels) == 1:
        label, reps = panels[0]
        _render_check(
            reps,
            check=selected_list,
            title=title_for(label, reps),
            chart_key=f"mean_score_{label}_{selected_list}",
        )
        return
    for tab, (label, reps) in zip(
        st.tabs([label for label, _ in panels]), panels, strict=True
    ):
        with tab:
            _render_check(
                reps,
                check=selected_list,
                title=title_for(label, reps),
                chart_key=f"mean_score_{compare_mode}_{label}_{selected_list}",
            )


if __name__ == "__main__":
    main()
