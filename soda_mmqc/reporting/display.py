"""Interactive notebook display for flat evaluation drill-down tables."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence, overload

import pandas as pd

from soda_mmqc import logger
from soda_mmqc.reporting.aggregate import RunSummaries, RunSummary
from soda_mmqc.reporting.context import ExampleContext, inspect_instance, inspect_source
from soda_mmqc.reporting.tables import (
    filter_by_doc,
    filter_by_field,
    filter_by_source,
    layer1_instance_table,
    layer2_instance_table,
    layer_s_issues_table,
)

_ITABLES_INITIALIZED = False


def _itables_available() -> bool:
    try:
        import itables  # noqa: F401
    except ImportError:
        return False
    return True


def _ensure_itables_notebook_mode() -> None:
    global _ITABLES_INITIALIZED
    if _ITABLES_INITIALIZED:
        return
    try:
        from itables import init_notebook_mode

        init_notebook_mode(all_interactive=False)
    except Exception as exc:
        logger.debug("itables init_notebook_mode skipped: %s", exc)
    _ITABLES_INITIALIZED = True


def _column_search_cols(
    frame: pd.DataFrame,
    column_search: Mapping[str, str],
) -> list[dict[str, str] | None]:
    """DataTables ``searchCols`` entries aligned with ``frame`` columns."""
    return [
        {"search": column_search[column]} if column in column_search else None
        for column in frame.columns
    ]


def _column_order(
    frame: pd.DataFrame,
    default_sort: Sequence[str] | None,
) -> list[list[int | str]]:
    if not default_sort:
        return []
    order: list[list[int | str]] = []
    for column in default_sort:
        if column in frame.columns:
            order.append([int(frame.columns.get_loc(column)), "asc"])
    return order


def sort_frame(
    frame: pd.DataFrame,
    default_sort: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Return a copy sorted by ``default_sort`` columns when present."""
    if frame.empty or not default_sort:
        return frame.copy()
    columns = [col for col in default_sort if col in frame.columns]
    if not columns:
        return frame.copy()
    return frame.sort_values(columns, kind="stable").reset_index(drop=True)


def show_table(
    frame: pd.DataFrame,
    *,
    caption: str | None = None,
    default_sort: Sequence[str] | None = None,
    column_filters: Literal["header", "footer"] | None = "footer",
    column_search: Mapping[str, str] | None = None,
    length_menu: Sequence[int] = (10, 25, 50, 100),
) -> Any:
    """Display a DataFrame with itables (sort, search, column filters).

    Falls back to plain ``IPython.display.display`` when itables is missing.
    Returns the itables widget when available, else the sorted DataFrame.
    """
    prepared = sort_frame(frame, default_sort)

    if _itables_available():
        from itables import show

        _ensure_itables_notebook_mode()
        show_kwargs: dict[str, Any] = {
            "caption": caption,
            "order": _column_order(prepared, default_sort),
            "column_filters": column_filters,
            "lengthMenu": list(length_menu),
            "layout": {"topStart": "pageLength", "topEnd": "search"},
        }
        if column_search:
            show_kwargs["searchCols"] = _column_search_cols(prepared, column_search)
        return show(prepared, **show_kwargs)

    logger.warning(
        "itables is not installed; falling back to plain display. "
        "Install with: pip install itables"
    )
    try:
        from IPython.display import display

        if caption:
            display(caption)
        display(prepared)
    except ImportError:
        if caption:
            print(caption)
        print(prepared.to_string())
    return prepared


def show_issues_table(
    summary: RunSummary,
    *,
    caption: str | None = None,
) -> Any:
    """Layer S missing and spurious rows."""
    frame = layer_s_issues_table(summary)
    title = caption or (
        f"Layer S issues — {summary.check} / {summary.model} / {summary.arm}"
    )
    return show_table(
        frame,
        caption=title,
        default_sort=("source", "list_key", "structural"),
    )


def show_layer1_errors(
    summary: RunSummary,
    *,
    field: str | None = None,
    source: str | None = None,
    layer1: str | None = None,
    caption: str | None = None,
) -> Any:
    """Layer-1 applicability outliers."""
    frame = layer1_instance_table(summary)
    if source is not None:
        frame = filter_by_source(frame, source)
    if field is not None:
        frame = filter_by_field(frame, field)
    title = caption or (
        f"Layer 1 outliers — {summary.check} / {summary.model} / {summary.arm}"
    )
    column_search = {"layer1": layer1} if layer1 is not None else None
    return show_table(
        frame,
        caption=title,
        default_sort=("source", "leaf_property", "path"),
        column_search=column_search,
    )


def show_layer2_errors(
    summary: RunSummary,
    *,
    field: str | None = None,
    source: str | None = None,
    caption: str | None = None,
) -> Any:
    """Layer-2 matching errors only (FP, FN, mismatch)."""
    frame = layer2_instance_table(summary)
    if source is not None:
        frame = filter_by_source(frame, source)
    if field is not None:
        frame = filter_by_field(frame, field)
    title = caption or (
        f"Layer 2 errors — {summary.check} / {summary.model} / {summary.arm}"
    )
    return show_table(
        frame,
        caption=title,
        default_sort=("source", "leaf_property", "path"),
    )


def comparison_errors_table(
    summaries: RunSummaries,
    *,
    compare: Literal["arm", "model"] = "arm",
    model: str | None = None,
    arm: str | None = None,
) -> pd.DataFrame:
    """Long-form layer-2 errors across arms or models."""
    if compare == "arm":
        if model is None:
            raise ValueError("model is required when compare='arm'")
        selected = summaries.for_model(model)
        series_col = "arm"
    else:
        if arm is None:
            raise ValueError("arm is required when compare='model'")
        selected = summaries.for_arm(arm)
        series_col = "model"

    frames: list[pd.DataFrame] = []
    for summary in selected:
        frame = layer2_instance_table(summary)
        if frame.empty:
            continue
        tagged = frame.copy()
        tagged["model"] = summary.model
        tagged["arm"] = summary.arm
        frames.append(tagged)

    if not frames:
        return pd.DataFrame(
            columns=[
                "source",
                "path",
                "leaf_property",
                "layer2",
                "score",
                "exp_value",
                "pred_value",
                "model",
                "arm",
            ]
        )

    combined = pd.concat(frames, ignore_index=True)
    sort_cols = [series_col, "source", "leaf_property", "path"]
    return combined.sort_values(
        [col for col in sort_cols if col in combined.columns],
        kind="stable",
    ).reset_index(drop=True)


def show_comparison_errors(
    summaries: RunSummaries,
    *,
    compare: Literal["arm", "model"] = "arm",
    model: str | None = None,
    arm: str | None = None,
    caption: str | None = None,
) -> Any:
    """Interactive layer-2 error table across arms or models."""
    frame = comparison_errors_table(
        summaries,
        compare=compare,
        model=model,
        arm=arm,
    )
    if compare == "arm":
        title = caption or f"Layer 2 comparison — model={model}"
        default_sort = ("arm", "source", "leaf_property", "path")
    else:
        title = caption or f"Layer 2 comparison — arm={arm}"
        default_sort = ("model", "source", "leaf_property", "path")
    return show_table(frame, caption=title, default_sort=default_sort)


def _format_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return repr(value)


def _display_markdown(text: str) -> None:
    try:
        from IPython.display import Markdown, display

        display(Markdown(text))
    except ImportError:
        print(text)


def _display_side_by_side(
    left_title: str,
    left_value: Any,
    right_title: str,
    right_value: Any,
) -> None:
    frame = pd.DataFrame(
        {
            left_title: [_format_value(left_value)],
            right_title: [_format_value(right_value)],
        }
    )
    try:
        from IPython.display import display

        display(frame)
    except ImportError:
        print(frame.to_string())


def build_figure_image_plot(
    image_path: Path | str,
    *,
    height: int = 420,
    width: int | None = None,
) -> Any | None:
    """Plotly figure for a zoomable/pannable figure image (``px.imshow``)."""
    path = Path(image_path)
    if not path.is_file():
        return None
    try:
        import plotly.express as px
        from PIL import Image
    except ImportError:
        return None

    with Image.open(path) as img:
        pixel_width, pixel_height = img.size
        layout_width = width
        if layout_width is None:
            layout_width = max(240, int(height * pixel_width / pixel_height))
        fig = px.imshow(img)
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            height=height,
            width=layout_width,
            dragmode="zoom",
        )
        fig.update_xaxes(visible=False, constrain="domain")
        fig.update_yaxes(
            visible=False,
            scaleanchor="x",
            scaleratio=1,
            autorange="reversed",
        )
        return fig


def _display_figure_image(
    image_path: Path | str,
    *,
    height: int = 420,
    width: int | None = None,
    zoomable: bool = True,
) -> None:
    """Show a figure image in the notebook; Plotly enables zoom/pan when available."""
    path = Path(image_path)
    if not path.is_file():
        logger.warning("Figure image not found: %s", path)
        return

    if zoomable:
        try:
            fig = build_figure_image_plot(path, height=height, width=width)
            if fig is not None:
                fig.show(config={"scrollZoom": True})
                return
        except Exception as exc:
            logger.debug("Plotly figure preview failed, falling back: %s", exc)

    try:
        from IPython.display import Image, display

        display(Image(filename=str(path)))
    except ImportError:
        logger.info("Figure image at %s", path)


def _render_instance_context(
    ctx: ExampleContext,
    *,
    show_full_eval: bool = False,
    figure_height: int = 420,
    figure_width: int | None = None,
    zoomable_figure: bool = True,
) -> None:
    """Display gold/pred content and optional figure preview for one instance."""
    header = (
        f"**Example context** — `{ctx.checklist}` / `{ctx.check}` / "
        f"`{ctx.model}` / `{ctx.arm}`  \n"
        f"`source={ctx.ref.source}`"
    )
    if ctx.steps:
        header += f" · `steps={list(ctx.steps)}`"
    if ctx.pred_missing:
        header += " · *pred row missing*"
    _display_markdown(header)

    preview = ctx.example_preview
    if preview is not None:
        caption = preview.caption or ""
        _display_markdown(f"**Caption**  \n{caption}")
        if preview.image_path is not None and preview.image_path.is_file():
            _display_figure_image(
                preview.image_path,
                height=figure_height,
                width=figure_width,
                zoomable=zoomable_figure,
            )

    pred_label = "pred (missing)" if ctx.pred_missing else "pred"
    leaf_name = ctx.steps[-1] if ctx.steps and isinstance(ctx.steps[-1], str) else None

    if not ctx.steps:
        _display_markdown("**Model output (gold vs pred)**")
        _display_side_by_side("gold", ctx.expected_output, pred_label, ctx.model_output)
    elif leaf_name is not None and ctx.exp_row is not None:
        _display_markdown("**Panel row (gold vs pred)**")
        _display_side_by_side(
            "gold row",
            ctx.exp_row,
            f"{pred_label} row",
            ctx.pred_row,
        )
        _display_markdown(f"**`{leaf_name}` (gold vs pred)**")
        _display_side_by_side("gold", ctx.exp_value, pred_label, ctx.pred_value)
    else:
        _display_markdown("**At steps (gold vs pred)**")
        _display_side_by_side("gold", ctx.exp_subtree, pred_label, ctx.pred_subtree)

    if show_full_eval:
        _display_markdown("**Full expected_output**")
        _display_side_by_side("expected_output", ctx.expected_output, "—", "—")
        _display_markdown("**Full model_output**")
        _display_side_by_side("model_output", ctx.model_output, "—", "—")


@overload
def show_instance_context(
    ctx: ExampleContext,
    *,
    show_full_eval: bool = False,
    figure_height: int = 420,
    figure_width: int | None = None,
    zoomable_figure: bool = True,
    source: None = None,
    object_path: None = None,
    leaf: None = None,
    include_example_assets: bool = True,
) -> None: ...


@overload
def show_instance_context(
    summary: RunSummary,
    *,
    source: str,
    object_path: None = None,
    leaf: None = None,
    show_full_eval: bool = False,
    figure_height: int = 420,
    figure_width: int | None = None,
    zoomable_figure: bool = True,
    include_example_assets: bool = True,
) -> None: ...


@overload
def show_instance_context(
    summary: RunSummary,
    *,
    source: str,
    object_path: str,
    leaf: str,
    show_full_eval: bool = False,
    figure_height: int = 420,
    figure_width: int | None = None,
    zoomable_figure: bool = True,
    include_example_assets: bool = True,
) -> None: ...


def show_instance_context(
    ctx: ExampleContext | RunSummary,
    *,
    source: str | None = None,
    object_path: str | None = None,
    leaf: str | None = None,
    show_full_eval: bool = False,
    figure_height: int = 420,
    figure_width: int | None = None,
    zoomable_figure: bool = True,
    include_example_assets: bool = True,
) -> None:
    """Display gold/pred content for one model-call source.

    Pass a pre-built :class:`ExampleContext`, or a :class:`RunSummary` with
    ``source`` to show the full model output for that example. Optionally pass
    ``object_path`` and ``leaf`` from a culprits table row for one leaf field.

    Figure images use a Plotly widget (zoom/pan via toolbar; scroll to zoom when
    enabled). Set ``zoomable_figure=False`` to fall back to a static image.
    Resize the initial viewport with ``figure_height`` / ``figure_width``.
    """
    if isinstance(ctx, ExampleContext):
        _render_instance_context(
            ctx,
            show_full_eval=show_full_eval,
            figure_height=figure_height,
            figure_width=figure_width,
            zoomable_figure=zoomable_figure,
        )
        return

    if source is None:
        raise ValueError("source is required when passing RunSummary")

    if object_path is None and leaf is None:
        resolved = inspect_source(
            ctx,
            source=source,
            include_example_assets=include_example_assets,
        )
    elif object_path is not None and leaf is not None:
        resolved = inspect_instance(
            ctx,
            source=source,
            object_path=object_path,
            leaf=leaf,
            include_example_assets=include_example_assets,
        )
    else:
        raise ValueError("pass both object_path and leaf, or neither")
    _render_instance_context(
        resolved,
        show_full_eval=show_full_eval,
        figure_height=figure_height,
        figure_width=figure_width,
        zoomable_figure=zoomable_figure,
    )
