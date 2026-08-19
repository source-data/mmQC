"""DataFrame builders for flat evaluation reporting and drill-down."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd

from soda_mmqc.core.eval_manifest import MatchingMetric
from soda_mmqc.core.evaluation import format_ancestor_context

from soda_mmqc.reporting.aggregate import (
    RunSummary,
    field_order_for_summary,
    leaf_property_tail,
)
from soda_mmqc.reporting.load import FlatRecord, record_source
from soda_mmqc.reporting.navigate import instance_object_path
from soda_mmqc.reporting.styles import (
    LAYER1_OUTLIER_OUTCOMES,
    LAYER2_BINARY_ORDER,
    LAYER2_ERROR_OUTCOMES,
    LAYER2_GRADED_ORDER,
)


def counts_to_frame(
    counts: Mapping[str, int],
    order: Sequence[str],
    label: str,
) -> pd.DataFrame:
    """Single-column outcome counts in a stable order."""
    return pd.DataFrame([{label: key, "count": counts.get(key, 0)} for key in order])


def layer_counts_by_property(
    summary: RunSummary,
    order: Sequence[str],
    attr: str,
) -> pd.DataFrame:
    """Wide table of layer counts per leaf property."""
    rows: list[dict[str, Any]] = []
    keys = field_order_for_summary(summary)
    for leaf_property in keys:
        rollup = summary.by_property[leaf_property]
        counts = (
            rollup.layer1_counts if attr == "layer1_counts" else rollup.layer2_counts
        )
        rows.append(
            {
                "leaf_property": leaf_property,
                "field": leaf_property_tail(leaf_property),
                **{key: counts.get(key, 0) for key in order},
            }
        )
    return pd.DataFrame(rows)


def split_layer2_by_metric(
    summary: RunSummary,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split layer-2 counts by manifest ``matching_metric``.

    Binary polarity → TP/TN/FP/FN chart. Graded string **and** multiclass →
    match/mismatch chart (same Layer-2 labels).
    """
    binary_rows: list[dict[str, Any]] = []
    graded_rows: list[dict[str, Any]] = []

    for leaf_property in field_order_for_summary(summary):
        profile = summary.manifest.profile_for(leaf_property)
        if profile is None:
            continue
        rollup = summary.by_property[leaf_property]
        base = {
            "leaf_property": leaf_property,
            "field": leaf_property_tail(leaf_property),
        }
        if profile.matching_metric == MatchingMetric.BINARY_POLARITY:
            binary_rows.append(
                {
                    **base,
                    **{
                        key: rollup.layer2_counts.get(key, 0)
                        for key in LAYER2_BINARY_ORDER
                    },
                }
            )
        elif profile.matching_metric in (
            MatchingMetric.GRADED_STRING,
            MatchingMetric.MULTICLASS,
        ):
            graded_rows.append(
                {
                    **base,
                    **{
                        key: rollup.layer2_counts.get(key, 0)
                        for key in LAYER2_GRADED_ORDER
                    },
                }
            )

    return pd.DataFrame(binary_rows), pd.DataFrame(graded_rows)


def _instance_table_columns(
    record: FlatRecord,
    instance: Mapping[str, Any],
) -> dict[str, str]:
    """Source, panel path, and leaf field for instance drill-down tables."""
    raw_path = str(instance.get("path") or "")
    raw_leaf = str(instance.get("leaf_property") or "")
    return {
        "source": record_source(record),
        "path": instance_object_path(raw_path),
        "leaf_property": leaf_property_tail(raw_leaf) if raw_leaf else "",
    }


def _iter_instances(records: Sequence[FlatRecord]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        instances = record.analysis.get("instances", [])
        if not isinstance(instances, list):
            continue
        for instance in instances:
            if isinstance(instance, dict):
                rows.append(
                    {
                        **instance,
                        **_instance_table_columns(record, instance),
                    }
                )
    return rows


_LAYER_S_ISSUE_COLUMNS = [
    "source",
    "list_key",
    "structural",
    "location",
    "alignment",
    "context_path",
    "gold_index",
    "pred_index",
]


def layer_s_issues_table(summary: RunSummary) -> pd.DataFrame:
    """Missing and spurious predictive rows with location context."""
    rows: list[dict[str, Any]] = []
    for record in summary.records:
        by_list = record.analysis.get("by_list", {})
        if not isinstance(by_list, dict):
            continue
        for list_key, payload in by_list.items():
            if not isinstance(payload, dict):
                continue
            for row in payload.get("rows", []):
                if not isinstance(row, dict):
                    continue
                structural = row.get("structural")
                if structural not in {"missing_row", "spurious_row"}:
                    continue
                side = "gold" if structural == "missing_row" else "pred"
                ancestor_col = f"ancestor_{side}"
                alignment_col = f"{side}_alignment"
                rows.append(
                    {
                        "source": record_source(record),
                        "list_key": list_key,
                        "structural": structural,
                        "location": format_ancestor_context(
                            row.get(ancestor_col, [])
                        ),
                        "alignment": row.get(alignment_col),
                        "context_path": row.get("context_path"),
                        "gold_index": row.get("gold_index"),
                        "pred_index": row.get("pred_index"),
                    }
                )
    if not rows:
        return pd.DataFrame(columns=_LAYER_S_ISSUE_COLUMNS)
    return pd.DataFrame(rows)


def layer1_instance_table(summary: RunSummary) -> pd.DataFrame:
    """Instances with non-default layer-1 applicability outcomes."""
    rows: list[dict[str, Any]] = []
    for instance in _iter_instances(summary.records):
        layer1 = instance.get("layer1")
        if layer1 not in LAYER1_OUTLIER_OUTCOMES:
            continue
        rows.append(
            {
                "source": instance.get("source"),
                "path": instance.get("path"),
                "leaf_property": instance.get("leaf_property"),
                "layer1": layer1,
                "exp_value": instance.get("exp_value"),
                "pred_value": instance.get("pred_value"),
            }
        )
    return pd.DataFrame(rows)


def layer2_instance_table(summary: RunSummary) -> pd.DataFrame:
    """Instances with layer-2 errors (FP, FN, mismatch)."""
    rows: list[dict[str, Any]] = []
    for instance in _iter_instances(summary.records):
        layer2 = instance.get("layer2")
        if layer2 not in LAYER2_ERROR_OUTCOMES:
            continue
        rows.append(
            {
                "source": instance.get("source"),
                "path": instance.get("path"),
                "leaf_property": instance.get("leaf_property"),
                "layer2": layer2,
                "score": instance.get("score"),
                "exp_value": instance.get("exp_value"),
                "pred_value": instance.get("pred_value"),
            }
        )
    return pd.DataFrame(rows)


def instance_culprits_table(summary: RunSummary) -> pd.DataFrame:
    """Instances with layer-1 outliers or layer-2 errors."""
    rows: list[dict[str, Any]] = []
    for instance in _iter_instances(summary.records):
        layer1 = instance.get("layer1")
        layer2 = instance.get("layer2")
        if layer1 not in LAYER1_OUTLIER_OUTCOMES and layer2 not in LAYER2_ERROR_OUTCOMES:
            continue
        rows.append(
            {
                "source": instance.get("source"),
                "path": instance.get("path"),
                "leaf_property": instance.get("leaf_property"),
                "layer1": layer1,
                "layer2": layer2,
                "score": instance.get("score"),
                "exp_value": instance.get("exp_value"),
                "pred_value": instance.get("pred_value"),
            }
        )
    return pd.DataFrame(rows)


def per_doc_property_table(summary: RunSummary) -> pd.DataFrame:
    """Per (doc, leaf property) mean scores from per-doc ``by_property``."""
    rows: list[dict[str, Any]] = []
    for record in summary.records:
        by_property = record.analysis.get("by_property", {})
        if not isinstance(by_property, dict):
            continue
        for leaf_property, payload in by_property.items():
            if not isinstance(payload, dict):
                continue
            rows.append(
                {
                    "doc_id": record.doc_id,
                    "leaf_property": leaf_property,
                    "field": leaf_property_tail(leaf_property),
                    "mean_score": payload.get("mean_score"),
                    "layer1_counts": payload.get("layer1_counts", {}),
                    "layer2_counts": payload.get("layer2_counts", {}),
                }
            )
    return pd.DataFrame(rows)


def worst_docs_table(summary: RunSummary) -> pd.DataFrame:
    """Rank documents by layer S / layer-1 / layer-2 error counts."""
    layer_s_errors: dict[str | None, int] = {}
    layer1_errors: dict[str | None, int] = {}
    layer2_errors: dict[str | None, int] = {}

    for record in summary.records:
        doc_id = record.doc_id
        layer_s_errors.setdefault(doc_id, 0)
        layer1_errors.setdefault(doc_id, 0)
        layer2_errors.setdefault(doc_id, 0)

        by_list = record.analysis.get("by_list", {})
        if isinstance(by_list, dict):
            for payload in by_list.values():
                if not isinstance(payload, dict):
                    continue
                counts = payload.get("row_counts", {})
                if isinstance(counts, dict):
                    layer_s_errors[doc_id] += counts.get("missing_row", 0)
                    layer_s_errors[doc_id] += counts.get("spurious_row", 0)

        instances = record.analysis.get("instances", [])
        if isinstance(instances, list):
            for instance in instances:
                if not isinstance(instance, dict):
                    continue
                if instance.get("layer1") in LAYER1_OUTLIER_OUTCOMES:
                    layer1_errors[doc_id] += 1
                if instance.get("layer2") in LAYER2_ERROR_OUTCOMES:
                    layer2_errors[doc_id] += 1

    rows = [
        {
            "doc_id": doc_id,
            "layer_s_errors": layer_s_errors.get(doc_id, 0),
            "layer1_errors": layer1_errors.get(doc_id, 0),
            "layer2_errors": layer2_errors.get(doc_id, 0),
            "total_errors": (
                layer_s_errors.get(doc_id, 0)
                + layer1_errors.get(doc_id, 0)
                + layer2_errors.get(doc_id, 0)
            ),
        }
        for doc_id in layer_s_errors
    ]
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    return frame.sort_values(
        ["total_errors", "layer2_errors", "layer1_errors", "layer_s_errors"],
        ascending=False,
    ).reset_index(drop=True)


def filter_by_doc(frame: pd.DataFrame, doc_id: str) -> pd.DataFrame:
    if frame.empty or "doc_id" not in frame.columns:
        return frame
    return frame.loc[frame["doc_id"] == doc_id].reset_index(drop=True)


def filter_by_source(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    if frame.empty or "source" not in frame.columns:
        return frame
    return frame.loc[frame["source"] == source].reset_index(drop=True)


def filter_by_field(frame: pd.DataFrame, field: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    if "leaf_property" in frame.columns:
        return frame.loc[frame["leaf_property"] == field].reset_index(drop=True)
    if "field" in frame.columns:
        return frame.loc[frame["field"] == field].reset_index(drop=True)
    return frame


def filter_by_layer_outcome(frame: pd.DataFrame, column: str, outcome: str) -> pd.DataFrame:
    if frame.empty or column not in frame.columns:
        return frame
    return frame.loc[frame[column] == outcome].reset_index(drop=True)
