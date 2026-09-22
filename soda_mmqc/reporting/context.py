"""Build example context for on-demand drill-down inspection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from soda_mmqc import logger
from soda_mmqc.core.examples import EXAMPLE_FACTORY
from soda_mmqc.reporting.aggregate import RunSummary
from soda_mmqc.reporting.load import ensure_record_payloads, find_record, record_source
from soda_mmqc.reporting.navigate import (
    PathStep,
    get_at_steps,
    get_at_steps_optional,
    instance_navigation_path,
    layer_s_row_steps,
    parent_row_steps,
    path_string_to_steps,
)


@dataclass(frozen=True)
class InstanceRef:
    """Locate one eval subtree inside a benchmark example."""

    source: str
    doc_id: str
    steps: tuple[PathStep, ...]


@dataclass(frozen=True)
class ExamplePreview:
    """On-disk example assets (figure image, caption, …)."""

    example_type: str
    source: str
    caption: str | None = None
    image_path: Path | None = None


@dataclass
class ExampleContext:
    """Gold/pred content at ``ref.steps`` plus optional figure preview."""

    ref: InstanceRef
    checklist: str
    check: str
    model: str
    arm: str
    steps: tuple[PathStep, ...]
    exp_subtree: Any
    pred_subtree: Any | None
    exp_value: Any
    pred_value: Any | None
    exp_row: dict[str, Any] | None
    pred_row: dict[str, Any] | None
    metadata: dict[str, Any]
    expected_output: dict[str, Any]
    model_output: dict[str, Any]
    example_preview: ExamplePreview | None = None
    pred_missing: bool = False


def _load_example_preview(
    metadata: Mapping[str, Any],
    *,
    include_example_assets: bool,
) -> ExamplePreview | None:
    if not include_example_assets:
        return None
    source = metadata.get("source")
    if not isinstance(source, str) or not source:
        return None
    example_type = metadata.get("example_type")
    if not isinstance(example_type, str) or not example_type:
        return None
    try:
        example = EXAMPLE_FACTORY.create(source, example_type)
    except Exception as exc:
        logger.warning("Could not load example preview for %s: %s", source, exc)
        return None

    image_path = getattr(example, "image_path", None)
    return ExamplePreview(
        example_type=example_type,
        source=source,
        caption=getattr(example, "caption", None),
        image_path=image_path if isinstance(image_path, Path) else None,
    )


def _resolve_rows(
    expected_output: Mapping[str, Any],
    model_output: Mapping[str, Any] | None,
    steps: Sequence[PathStep],
    *,
    source: str,
    pred_missing: bool,
) -> tuple[Any, Any | None, Any, Any | None, dict[str, Any] | None, dict[str, Any] | None]:
    exp_subtree = get_at_steps(
        expected_output,
        steps,
        side="gold",
        doc_id=source,
    )
    pred_subtree = (
        None
        if pred_missing or model_output is None
        else get_at_steps_optional(
            model_output,
            steps,
            side="pred",
            doc_id=source,
        )
    )

    row_steps = parent_row_steps(steps)
    exp_row: dict[str, Any] | None = None
    pred_row: dict[str, Any] | None = None
    if row_steps is not None:
        row_value = get_at_steps(
            expected_output,
            row_steps,
            side="gold",
            doc_id=source,
        )
        if isinstance(row_value, dict):
            exp_row = dict(row_value)
        if not pred_missing and model_output is not None:
            pred_row_value = get_at_steps_optional(
                model_output,
                row_steps,
                side="pred",
                doc_id=source,
            )
            if isinstance(pred_row_value, dict):
                pred_row = dict(pred_row_value)

    exp_value = exp_subtree
    pred_value = pred_subtree
    if steps and isinstance(steps[-1], str):
        field = steps[-1]
        if isinstance(exp_row, dict):
            exp_value = exp_row.get(field, exp_subtree)
        if isinstance(pred_row, dict):
            pred_value = pred_row.get(field, pred_subtree)

    return exp_subtree, pred_subtree, exp_value, pred_value, exp_row, pred_row


def _build_example_context(
    summary: RunSummary,
    record: Any,
    *,
    steps: tuple[PathStep, ...],
    include_example_assets: bool,
    pred_missing: bool,
) -> ExampleContext:
    source = record_source(record)
    expected_output, model_output = ensure_record_payloads(
        record, leaf_path=summary.path
    )
    doc_id = record.doc_id or ""
    ref = InstanceRef(source=source, doc_id=doc_id, steps=steps)
    (
        exp_subtree,
        pred_subtree,
        exp_value,
        pred_value,
        exp_row,
        pred_row,
    ) = _resolve_rows(
        expected_output,
        model_output,
        steps,
        source=source,
        pred_missing=pred_missing,
    )
    return ExampleContext(
        ref=ref,
        checklist=summary.checklist,
        check=summary.check,
        model=summary.model,
        arm=summary.arm,
        steps=steps,
        exp_subtree=exp_subtree,
        pred_subtree=pred_subtree,
        exp_value=exp_value,
        pred_value=pred_value,
        exp_row=exp_row,
        pred_row=pred_row,
        metadata=dict(record.metadata),
        expected_output=expected_output,
        model_output=model_output,
        example_preview=_load_example_preview(
            record.metadata,
            include_example_assets=include_example_assets,
        ),
        pred_missing=pred_missing,
    )


def inspect_source(
    summary: RunSummary,
    *,
    source: str,
    include_example_assets: bool = True,
) -> ExampleContext:
    """Resolve full gold/pred JSON for one model-call source."""
    record = find_record(summary.records, source=source)
    return _build_example_context(
        summary,
        record,
        steps=(),
        include_example_assets=include_example_assets,
        pred_missing=False,
    )


def inspect_instance(
    summary: RunSummary,
    *,
    source: str,
    steps: Sequence[PathStep] | None = None,
    object_path: str | None = None,
    leaf: str | None = None,
    include_example_assets: bool = True,
    pred_missing: bool = False,
) -> ExampleContext:
    """Resolve gold/pred content for one leaf instance within a source.

    Pass either explicit ``steps`` or table-style ``object_path`` and ``leaf``
    (from culprits columns ``path`` and ``leaf_property``).
    """
    if steps is not None:
        if object_path is not None or leaf is not None:
            raise ValueError("pass either steps or (object_path, leaf), not both")
        step_tuple = tuple(steps)
    elif object_path is not None and leaf is not None:
        nav_path = instance_navigation_path(object_path, leaf)
        step_tuple = path_string_to_steps(nav_path)
    else:
        raise ValueError("either steps or (object_path, leaf) is required")

    record = find_record(summary.records, source=source)
    return _build_example_context(
        summary,
        record,
        steps=step_tuple,
        include_example_assets=include_example_assets,
        pred_missing=pred_missing,
    )


def inspect_layer_s_row(
    summary: RunSummary,
    *,
    source: str,
    list_key: str,
    gold_index: int | None = None,
    pred_index: int | None = None,
    context_path: str | None = None,
    structural: str | None = None,
    include_example_assets: bool = True,
) -> ExampleContext:
    """Inspect the gold and/or pred row behind a Layer S alignment record."""
    if structural == "missing_row":
        steps = layer_s_row_steps(
            list_key=list_key,
            context_path=context_path,
            index=gold_index,
        )
        if steps is None:
            raise ValueError("missing_row requires gold_index")
        return inspect_instance(
            summary,
            source=source,
            steps=steps,
            include_example_assets=include_example_assets,
            pred_missing=True,
        )
    if structural == "spurious_row":
        steps = layer_s_row_steps(
            list_key=list_key,
            context_path=context_path,
            index=pred_index,
        )
        if steps is None:
            raise ValueError("spurious_row requires pred_index")
        return inspect_instance(
            summary,
            source=source,
            steps=steps,
            include_example_assets=include_example_assets,
            pred_missing=False,
        )

    index = gold_index if gold_index is not None else pred_index
    steps = layer_s_row_steps(
        list_key=list_key,
        context_path=context_path,
        index=index,
    )
    if steps is None:
        raise ValueError("Layer S row requires gold_index or pred_index")
    return inspect_instance(
        summary,
        source=source,
        steps=steps,
        include_example_assets=include_example_assets,
    )
