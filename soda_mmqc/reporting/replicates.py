"""Instance scores averaged over the replicates of one arm.

A replicate is a resample of the same configuration, so its scores may be
averaged with the others'. What may not be pooled is arms: every function
here takes the replicates of *one* (model, arm) and nothing else.

A dot on the mean-score plot is one panel of one figure for one property,
at its score averaged over the replicates that scored it. Instances line up
across replicates because an instance path indexes the *gold* row
(``micrograph-scale-bar[3].micrograph`` is gold panel 3 in every replicate),
so ``(source, path)`` names the same measurement in each.

A replicate scores an instance only when it judged its applicability
correctly (layer 1); one that did not leaves it unscored, and the dot is the
mean over the replicates that did. The bar is the mean over every scored
``(instance, replicate)`` pair -- across examples and replicates at once.
"""

from __future__ import annotations

import re
from typing import Any, Sequence

import pandas as pd

from soda_mmqc.core.property_rollup import instance_is_scored, rollup_by_property
from soda_mmqc.reporting.aggregate import RunSummary
from soda_mmqc.reporting.load import record_source

_CHECK_RE = re.compile(r"^([^.\[]+)")
_ROW_RE = re.compile(r"^([^.\[]+\[\d+\])")


def property_check(leaf_property: str) -> str:
    """The top-level list a leaf property belongs to.

    In a merged checklist run that list is the check
    (``micrograph-scale-bar[].micrograph`` → ``micrograph-scale-bar``); in a
    single-check run it is the check's own output list (``outputs``).
    """
    match = _CHECK_RE.match(leaf_property)
    return match.group(1) if match else leaf_property


def property_label(leaf_property: str) -> str:
    """The property without its top-level list, for an axis label.

    Not just the last segment: ``units_provided[].answer`` and
    ``unit_definition_as_provided[].answer`` are different properties of
    one check, and the tail alone would stack them under one label.
    """
    prefix = f"{property_check(leaf_property)}[]."
    if leaf_property.startswith(prefix):
        return leaf_property[len(prefix):]
    return leaf_property


def panel_row_path(path: str) -> str:
    """The top-level row an instance belongs to: one panel.

    ``plot-axis-units[0].units_provided[1].answer`` → ``plot-axis-units[0]``.
    """
    match = _ROW_RE.match(path)
    return match.group(1) if match else path


def checks_in(summaries: Sequence[RunSummary]) -> list[str]:
    """Top-level lists across the runs, in the order the answers give them.

    That is the schema's order -- the checklist's -- where the manifest's
    would be alphabetical.
    """
    return list(
        dict.fromkeys(
            property_check(instance["leaf_property"])
            for summary in summaries
            for instance in _instances(summary)
        )
    )


def _instances(summary: RunSummary):
    for record in summary.records:
        instances = record.analysis.get("instances", ())
        if not isinstance(instances, list):
            continue
        for instance in instances:
            if isinstance(instance, dict) and isinstance(
                instance.get("leaf_property"), str
            ):
                yield instance


def _is_scored(summary: RunSummary, instance: dict[str, Any]) -> bool:
    profile = summary.manifest.profile_for(instance["leaf_property"])
    profiled = profile is not None and profile.is_profiled
    return instance_is_scored(instance, profiled=profiled)


def _in_check(leaf_property: str, check: str | None) -> bool:
    return check is None or property_check(leaf_property) == check


def pooled_mean_scores_frame(
    summaries: Sequence[RunSummary],
    *,
    check: str | None = None,
) -> pd.DataFrame:
    """Per property: the mean over every scored (instance, replicate) pair.

    ``mean_score`` is ``None`` where nothing was scored, as in
    :func:`soda_mmqc.reporting.plots.mean_scores_frame`.
    """
    columns = ["leaf_property", "label", "mean_score", "n_scored"]
    if not summaries:
        return pd.DataFrame(columns=columns)
    pooled = [
        instance
        for summary in summaries
        for instance in _instances(summary)
        if _in_check(instance["leaf_property"], check)
    ]
    rollups = rollup_by_property(pooled, summaries[0].manifest)
    rows = [
        {
            "leaf_property": leaf_property,
            "label": property_label(leaf_property),
            "mean_score": rollups[leaf_property].mean_score,
            "n_scored": rollups[leaf_property].n_scored,
        }
        # rollups keeps the instances' order: the answer's, so the bars
        # read panel_label, then each field as the check asks it.
        for leaf_property in rollups
    ]
    return pd.DataFrame(rows, columns=columns)


def pooled_instance_scores_frame(
    summaries: Sequence[RunSummary],
    *,
    check: str | None = None,
) -> pd.DataFrame:
    """One row per (source, path) scored in at least one replicate.

    ``score`` is the mean over the replicates that scored the instance.
    ``replicates`` lists every replicate's outcome for it, scored or not,
    as ``(replicate, score or None, layer1, layer2)``, so a reader can tell
    a panel that is always mediocre from one that failed once.
    """
    columns = [
        "leaf_property",
        "label",
        "source",
        "path",
        "score",
        "n_scored",
        "replicates",
    ]
    outcomes: dict[tuple[str, str], dict[str, Any]] = {}
    for summary in summaries:
        for record in summary.records:
            source = record_source(record)
            instances = record.analysis.get("instances", ())
            if not isinstance(instances, list):
                continue
            for instance in instances:
                if not isinstance(instance, dict):
                    continue
                leaf_property = instance.get("leaf_property")
                if not isinstance(leaf_property, str):
                    continue
                if not _in_check(leaf_property, check):
                    continue
                key = (source, str(instance.get("path", "")))
                entry = outcomes.setdefault(
                    key, {"leaf_property": leaf_property, "replicates": []}
                )
                score = (
                    float(instance["score"])
                    if _is_scored(summary, instance)
                    else None
                )
                entry["replicates"].append(
                    (
                        summary.replicate,
                        score,
                        instance.get("layer1"),
                        instance.get("layer2"),
                    )
                )

    rows: list[dict[str, Any]] = []
    for (source, path), entry in outcomes.items():
        scores = [score for _, score, _, _ in entry["replicates"] if score is not None]
        if not scores:
            continue
        rows.append(
            {
                "leaf_property": entry["leaf_property"],
                "label": property_label(entry["leaf_property"]),
                "source": source,
                "path": path,
                "score": sum(scores) / len(scores),
                "n_scored": len(scores),
                "replicates": sorted(entry["replicates"], key=lambda r: r[0]),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def panel_comparison(
    summaries: Sequence[RunSummary],
    *,
    source: str,
    row_path: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Gold against each replicate's prediction, for one panel.

    Read from the scored instances rather than by indexing the prediction,
    because the instance carries the prediction *paired* with that gold
    row; the prediction's own list may be in another order or miss panels.

    Returns ``(values, scores)``, both indexed by the field path below the
    panel (``micrograph``, ``units_provided[1].answer``): ``values`` has a
    ``gold`` column and one ``rep-NN`` column per replicate; ``scores``
    has the same ``rep-NN`` columns, missing (NaN) where the replicate left
    the instance unscored.
    """
    prefix = f"{row_path}."
    gold: dict[str, Any] = {}
    preds: dict[str, dict[str, Any]] = {}
    scores: dict[str, dict[str, Any]] = {}
    for summary in sorted(summaries, key=lambda s: s.replicate):
        column = f"rep-{summary.replicate:02d}"
        preds[column] = {}
        scores[column] = {}
        for record in summary.records:
            if record_source(record) != source:
                continue
            for instance in record.analysis.get("instances", ()):
                if not isinstance(instance, dict):
                    continue
                path = str(instance.get("path", ""))
                if not path.startswith(prefix):
                    continue
                field = path[len(prefix):]
                gold.setdefault(field, instance.get("exp_value"))
                preds[column][field] = instance.get("pred_value")
                scores[column][field] = (
                    float(instance["score"])
                    if isinstance(instance.get("leaf_property"), str)
                    and _is_scored(summary, instance)
                    else None
                )

    # Instances come field by field; a reader wants a nested row's fields
    # together: units_provided[0].axis, units_provided[0].answer, then [1].
    rank = {
        name: index
        for index, name in enumerate(
            dict.fromkeys(f.rsplit(".", 1)[-1] for f in gold)
        )
    }
    fields = sorted(
        gold,
        key=lambda f: (
            f.rsplit(".", 1)[0] if "." in f else "",
            rank[f.rsplit(".", 1)[-1]],
        ),
    )
    values = pd.DataFrame(
        {"gold": [gold[f] for f in fields]}
        | {
            column: [by_field.get(f) for f in fields]
            for column, by_field in preds.items()
        },
        index=fields,
    )
    score_frame = pd.DataFrame(
        {
            column: [by_field.get(f) for f in fields]
            for column, by_field in scores.items()
        },
        index=fields,
    )
    return values, score_frame


def spurious_rows_frame(
    summaries: Sequence[RunSummary],
    *,
    check: str | None = None,
) -> pd.DataFrame:
    """Rows a prediction has and the gold does not, with their replicates.

    A spurious row has no gold row, so no instance path and no dot; it is
    listed instead, keyed by where it sits and the label it was given.
    """
    columns = ["source", "context_path", "label", "replicates"]
    seen: dict[tuple[str, str, str], list[int]] = {}
    for summary in summaries:
        for record in summary.records:
            source = record_source(record)
            by_list = record.analysis.get("by_list", {})
            if not isinstance(by_list, dict):
                continue
            for list_key, payload in by_list.items():
                if not isinstance(payload, dict):
                    continue
                for row in payload.get("rows", ()):
                    if not isinstance(row, dict):
                        continue
                    if row.get("structural") != "spurious_row":
                        continue
                    context_path = str(row.get("context_path") or list_key)
                    if not _in_check(context_path, check):
                        continue
                    key = (source, context_path, str(row.get("pred_alignment")))
                    seen.setdefault(key, []).append(summary.replicate)
    rows = [
        {
            "source": source,
            "context_path": context_path,
            "label": label,
            "replicates": ", ".join(f"rep-{r:02d}" for r in sorted(reps)),
        }
        for (source, context_path, label), reps in sorted(seen.items())
    ]
    return pd.DataFrame(rows, columns=columns)
