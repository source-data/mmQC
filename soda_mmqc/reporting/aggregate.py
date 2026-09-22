"""Aggregate per-doc flat analyses into run-level summaries."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

import pandas as pd

from soda_mmqc.core.eval_manifest import EvalManifest

from soda_mmqc.core.property_rollup import PropertyRollup, rollup_by_property
from soda_mmqc.core.run_layout import BASELINE_ARM
from soda_mmqc.reporting.load import (
    FlatRun,
    FlatRuns,
    RunRef,
    record_source,
)

# `PropertyRollup` is defined in core/property_rollup.py, which owns every
# instances-to-statistics step. It is re-exported here because this module
# is the reporting-facing name for aggregation, but there is one class and
# one implementation.
__all__ = [
    "PropertyRollup",
    "RunSummary",
    "RunSummaries",
    "aggregate_run",
    "summarize_runs",
    "scores_frame",
    "replicate_spread",
    "arm_contrast",
    "arm_levels",
    "non_response_counts",
    "field_order",
    "leaf_property_tail",
    "property_path",
]


@dataclass
class RunSummary:
    """Aggregated reporting for one scored run leaf."""

    ref: RunRef
    manifest: EvalManifest
    records: tuple[Any, ...]
    by_list_row_counts: dict[str, dict[str, int]]
    by_property: dict[str, PropertyRollup]
    #: The leaf this run was read from, for lazily loading gold/pred
    #: payloads. ``None`` for a summary built in memory.
    path: Path | None = None

    # Flat accessors, so consumers read `summary.check` as before.
    @property
    def checklist(self) -> str:
        return self.ref.checklist

    @property
    def check(self) -> str:
        return self.ref.check

    @property
    def model(self) -> str:
        return self.ref.model

    @property
    def arm(self) -> str:
        return self.ref.arm

    @property
    def replicate(self) -> int:
        return self.ref.replicate

    @property
    def by_list_keys(self) -> tuple[str, ...]:
        return tuple(sorted(self.by_list_row_counts))


def leaf_property_tail(leaf_property: str) -> str:
    """Display label for a leaf property pattern."""
    return leaf_property.rsplit(".", maxsplit=1)[-1]


#: Separator between the segments of a :func:`property_path`.
PATH_SEPARATOR = ":"

#: Segments of a :func:`property_path`, in order.
PROPERTY_PATH_SEGMENTS = ("check", "arm", "replicate", "example", "property")


def property_path(
    check: str,
    leaf_property: str,
    *,
    arm: str | None = None,
    replicate: int | None = None,
    example: str | None = None,
) -> str:
    """Locate a measurement: ``check:arm:replicate:example:property``.

    A leaf property does not identify what was measured. In exp-01
    ``outputs[].panel_label`` occurs in all eleven checks and
    ``outputs[].decision`` in six, so a table or a plot keyed on the
    property alone stacks unrelated measurements under one label.

    ``None`` means *pooled over*, and renders as an empty segment, so
    the separator doubles on its own rather than by a special rule. The
    segments stay positional: ``split(":")`` gives five fields whatever
    was pooled, and the second is the arm whether or not it is there.

        >>> property_path("micrograph-scale-bar", "outputs[].panel_label")
        'micrograph-scale-bar::::outputs[].panel_label'

    ``leaf_property`` keeps its within-record JSON path. That path
    carries the same notation one level in -- ``outputs[]`` is a pooling
    over the panels of one example -- and dropping it would collide
    ``outputs[].units_provided[].axis`` with
    ``outputs[].unit_definition_as_provided[].axis`` inside a single
    check, where no prefix can separate them.

    ``model`` is deliberately not a segment: it is constant within a run
    root, so it would only ever add a separator.
    """
    return PATH_SEPARATOR.join(
        (
            check,
            arm or "",
            "" if replicate is None else f"rep-{int(replicate):02d}",
            example or "",
            leaf_property,
        )
    )


def field_order(
    manifest: EvalManifest,
    property_keys: Sequence[str],
) -> list[str]:
    """Order leaf properties: manifest profile order, then remaining sorted."""
    profiled = list(manifest.profiled_leaf_properties())
    profiled_set = set(profiled)
    ordered = [key for key in profiled if key in property_keys]
    remainder = sorted(key for key in property_keys if key not in profiled_set)
    return ordered + remainder


def _merge_row_counts(
    target: dict[str, dict[str, int]],
    by_list: Mapping[str, Any],
) -> None:
    for list_key, payload in by_list.items():
        if not isinstance(payload, dict):
            continue
        row_counts = payload.get("row_counts")
        if not isinstance(row_counts, dict):
            continue
        bucket = target.setdefault(list_key, Counter())
        for outcome, count in row_counts.items():
            if isinstance(outcome, str) and isinstance(count, int):
                bucket[outcome] += count


def _pool_instances(
    records: Sequence[Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]]]:
    """Every instance in the run, plus the pooled layer-S row counts."""
    instances: list[dict[str, Any]] = []
    by_list_counts: dict[str, dict[str, int]] = {}

    for record in records:
        analysis = record.analysis
        record_instances = analysis.get("instances", ())
        if isinstance(record_instances, list):
            instances.extend(
                inst for inst in record_instances if isinstance(inst, dict)
            )

        by_list = analysis.get("by_list", {})
        if isinstance(by_list, dict):
            _merge_row_counts(by_list_counts, by_list)

    return instances, by_list_counts


def aggregate_run(run: FlatRun) -> RunSummary:
    """Pool all leaf instances in a flat run into chart/table rollups.

    The rollup is computed here, from the instances in ``analysis.json``
    and the manifest as loaded now -- never read from the analysis file.
    Thresholds live in the manifest and get tuned, so a rollup stored at
    scoring time would be a cache nothing invalidates.
    """
    instances, by_list_counts = _pool_instances(run.records)
    by_property = rollup_by_property(instances, run.manifest)

    return RunSummary(
        ref=run.ref,
        manifest=run.manifest,
        records=run.records,
        by_list_row_counts={
            key: dict(counts) for key, counts in by_list_counts.items()
        },
        by_property=by_property,
        path=run.path,
    )


class RunSummaries(Mapping[RunRef, RunSummary]):
    """Summaries keyed by :class:`RunRef`.

    The key carries the arm and the replicate, because those are what
    distinguish two runs of one check. Replicates of one arm may be
    pooled -- a replicate is a resample. Arms may never be pooled with
    each other: they are different configurations, and the difference
    between them is the result.
    """

    def __init__(self, summaries: Sequence[RunSummary]) -> None:
        self._by_key = {s.ref: s for s in summaries}
        self._summaries = tuple(summaries)

    def __len__(self) -> int:
        return len(self._by_key)

    def __iter__(self) -> Iterator[RunRef]:
        return iter(self._by_key)

    def __getitem__(self, key: RunRef) -> RunSummary:
        return self._by_key[key]

    def for_model(self, model: str) -> tuple[RunSummary, ...]:
        """Every arm of one model, baseline first then alphabetical.

        Ordered rather than left in load order, so a comparison plot
        puts the control in the first series position every time.
        """
        order = {arm: index for index, arm in enumerate(self.arms)}
        return tuple(
            sorted(
                (s for s in self._summaries if s.model == model),
                key=lambda s: (order.get(s.arm, len(order)), s.replicate),
            )
        )

    def for_arm(self, arm: str) -> tuple[RunSummary, ...]:
        """Every replicate of one arm, in replicate order."""
        return tuple(
            sorted(
                (s for s in self._summaries if s.arm == arm),
                key=lambda s: s.replicate,
            )
        )

    @property
    def models(self) -> tuple[str, ...]:
        return tuple(sorted({s.model for s in self._summaries}))

    @property
    def arms(self) -> tuple[str, ...]:
        """Arms with the baseline first, then the rest alphabetically.

        The baseline is the control every variant is read against, so it
        leads rather than landing wherever its name sorts -- `pinned`
        would otherwise come after `<check>@v2`.
        """
        names = {s.arm for s in self._summaries}
        rest = sorted(names - {BASELINE_ARM})
        return tuple(
            ([BASELINE_ARM] if BASELINE_ARM in names else []) + rest
        )

    @property
    def replicates(self) -> tuple[int, ...]:
        return tuple(sorted({s.replicate for s in self._summaries}))


def summarize_runs(runs: FlatRuns) -> RunSummaries:
    """Build one :class:`RunSummary` per :class:`FlatRun`."""
    return RunSummaries([aggregate_run(run) for run in runs])


#: Columns of :func:`scores_frame`, in order.
SCORES_FRAME_COLUMNS = (
    "check",
    "model",
    "arm",
    "replicate",
    "example",
    "property",
    "path",
    "mean_score",
    "n_scored",
    "n_instances",
)


def scores_frame(runs: FlatRuns) -> pd.DataFrame:
    """One row per (check, arm, replicate, example, property).

    Both axes of variation stay on the frame -- ``example`` and
    ``replicate`` -- and ``property`` is never collapsed into a row.
    Every statistic downstream groups this frame, and none of them may
    group across ``property``: ``panel_label`` and ``micrograph`` measure
    different things, and a number mixing them hides an arm that improves
    one while degrading the other.

    Note this is *not* :func:`aggregate_run` per run. That pools examples
    within a leaf, which throws away the example axis this frame exists
    to keep. Each record is rolled up on its own instead.

    ``mean_score`` is nullable: ``NA`` means the property had nothing
    applicable on that example, which is not a score of zero. Read it
    with ``n_scored``, which is the denominator it was taken over.
    """
    rows: list[dict[str, Any]] = []
    for run in runs:
        for record in run.records:
            instances = record.analysis.get("instances", ())
            if not isinstance(instances, list):
                continue
            rollups = rollup_by_property(
                (inst for inst in instances if isinstance(inst, dict)),
                run.manifest,
            )
            example = record_source(record)
            for leaf_property, rollup in rollups.items():
                rows.append(
                    {
                        "check": run.check,
                        "model": run.model,
                        "arm": run.arm,
                        "replicate": run.replicate,
                        "example": example,
                        "property": leaf_property,
                        "path": property_path(
                            run.check,
                            leaf_property,
                            arm=run.arm,
                            replicate=run.replicate,
                            example=example,
                        ),
                        "mean_score": rollup.mean_score,
                        "n_scored": rollup.n_scored,
                        "n_instances": rollup.n_instances,
                    }
                )

    frame = pd.DataFrame(rows, columns=list(SCORES_FRAME_COLUMNS))
    # Nullable float, so "nothing applicable" stays distinguishable from
    # a genuine zero after any groupby.
    frame["mean_score"] = frame["mean_score"].astype("Float64")
    return frame


#: Columns of :func:`replicate_spread`, in order.
REPLICATE_SPREAD_COLUMNS = (
    "check",
    "model",
    "arm",
    "property",
    "path",
    "mean",
    "sd",
    "n_replicates",
    "n_scored_total",
)

#: Columns of :func:`arm_levels`, in order.
ARM_LEVELS_COLUMNS = (
    "check",
    "property",
    "path",
    "arm",
    "mean",
    "se",
    "n_examples",
)

#: Columns of :func:`arm_contrast`, in order.
ARM_CONTRAST_COLUMNS = (
    "check",
    "property",
    "path",
    "difference",
    "se",
    "n_examples",
    "n_baseline_only",
    "n_variant_only",
    "paired_fraction",
)


def replicate_spread(frame: pd.DataFrame) -> pd.DataFrame:
    """Spread over **replicates**, for one arm and one property.

    The SD answers "how much would this number move if we ran it again",
    not "how much do examples differ": examples are collapsed within a
    replicate first, then the SD is taken over the per-replicate values.
    Saying which axis a spread is over is not optional -- there are two,
    and they mean different things.

    A replicate that scored nothing applicable for this property is
    excluded rather than counted as zero. That is the same rule layer 2
    follows everywhere: it is conditional on layer 1, and a replicate
    that judged the property inapplicable has nothing to say about
    matching quality.

    ``mean`` travels with ``n_replicates`` and ``n_scored_total``
    deliberately. An arm scored on fewer instances is scored on a subset
    it selected, so a layer-2 mean without its denominator is not a
    reportable number.

    One row per ``(check, model, arm, property)``. Arms are never pooled
    with each other -- they are different configurations, and the
    difference between them is the result, not noise.
    """
    if frame.empty:
        return pd.DataFrame(columns=list(REPLICATE_SPREAD_COLUMNS))

    # Collapse examples within a replicate, skipping the ones with
    # nothing applicable: mean() on a Float64 column ignores NA.
    per_replicate = (
        frame.groupby(
            ["check", "model", "arm", "property", "replicate"],
            dropna=False,
            observed=True,
        )
        .agg(
            replicate_mean=("mean_score", "mean"),
            n_scored=("n_scored", "sum"),
        )
        .reset_index()
    )
    # A replicate that scored nothing is not a zero; it is absent.
    scored = per_replicate[per_replicate["n_scored"] > 0]

    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(
        ["check", "model", "arm", "property"], dropna=False, observed=True
    ):
        check, model, arm, leaf_property = key
        live = scored[
            (scored["check"] == check)
            & (scored["model"] == model)
            & (scored["arm"] == arm)
            & (scored["property"] == leaf_property)
        ]
        values = live["replicate_mean"].astype("Float64").dropna()
        n_replicates = int(len(values))
        rows.append(
            {
                "check": check,
                "model": model,
                "arm": arm,
                "property": leaf_property,
                "path": property_path(check, leaf_property, arm=arm),
                "mean": float(values.mean()) if n_replicates else pd.NA,
                # ddof=1: the SD of a single observation is undefined,
                # not zero. Reporting 0.0 there would claim perfect
                # reproducibility from one measurement.
                "sd": (
                    float(values.astype(float).std(ddof=1))
                    if n_replicates > 1
                    else pd.NA
                ),
                "n_replicates": n_replicates,
                "n_scored_total": int(live["n_scored"].sum()),
            }
        )

    result = pd.DataFrame(rows, columns=list(REPLICATE_SPREAD_COLUMNS))
    return result.astype({"mean": "Float64", "sd": "Float64"})


def arm_contrast(
    frame: pd.DataFrame,
    *,
    baseline: str,
    variant: str,
) -> pd.DataFrame:
    """Paired difference between two arms, for one property.

    Pairing is by example: the arms differ in one thing, so the
    comparison is within an example and whatever makes an example hard
    cancels. Replicates are averaged per ``(arm, example)`` first --
    they are resamples of the same measurement, so they reduce its noise
    rather than adding rows to the pairing.

    One row per ``(check, property)``. It never pools properties, and it
    does not test significance: what counts as a real difference is the
    experiment's claim, not this function's.

    ``difference`` is conditional on *both* arms having judged the
    property applicable on the same example, so it is computed on the
    paired set alone. ``paired_fraction`` says how much of the benchmark
    that was, and ``n_baseline_only`` / ``n_variant_only`` say which side
    lost the rest. Read those first: an arm that answers less is scored
    on fewer, self-selected cases, and a difference of zero over one of
    forty examples is not the same finding as a difference of zero over
    forty. In exp-01 a minimal skill returning ``outputs: []`` can earn
    the better layer-2 mean precisely by answering less.

    Unpaired examples are dropped from the difference but counted, never
    dropped silently -- silent dropping is what makes the confound
    invisible.
    """
    present = set(frame["arm"].unique()) if not frame.empty else set()
    for name in (baseline, variant):
        if name not in present:
            raise ValueError(
                f"No arm {name!r} in this frame; it has "
                f"{sorted(present) or 'nothing'}"
            )

    # Average replicates within (arm, example): a resample reduces the
    # noise on one measurement, it does not create another example.
    per_example = (
        frame.groupby(
            ["check", "property", "arm", "example"],
            dropna=False,
            observed=True,
        )["mean_score"]
        .mean()
        .reset_index()
    )

    rows: list[dict[str, Any]] = []
    for key, group in per_example.groupby(
        ["check", "property"], dropna=False, observed=True
    ):
        check, leaf_property = key
        base = group[group["arm"] == baseline].set_index("example")[
            "mean_score"
        ].dropna()
        var = group[group["arm"] == variant].set_index("example")[
            "mean_score"
        ].dropna()

        paired = base.index.intersection(var.index)
        differences = (
            var.loc[paired].astype(float) - base.loc[paired].astype(float)
        )
        n_examples = int(len(differences))
        n_baseline_only = int(len(base.index.difference(var.index)))
        n_variant_only = int(len(var.index.difference(base.index)))
        considered = n_examples + n_baseline_only + n_variant_only

        rows.append(
            {
                "check": check,
                "property": leaf_property,
                "path": property_path(check, leaf_property),
                "difference": (
                    float(differences.mean()) if n_examples else pd.NA
                ),
                "se": (
                    float(differences.std(ddof=1) / (n_examples ** 0.5))
                    if n_examples > 1
                    else pd.NA
                ),
                "n_examples": n_examples,
                "n_baseline_only": n_baseline_only,
                "n_variant_only": n_variant_only,
                "paired_fraction": (
                    n_examples / considered if considered else pd.NA
                ),
            }
        )

    result = pd.DataFrame(rows, columns=list(ARM_CONTRAST_COLUMNS))
    return result.astype(
        {"difference": "Float64", "se": "Float64", "paired_fraction": "Float64"}
    )


def arm_levels(
    frame: pd.DataFrame,
    *,
    baseline: str,
    variant: str,
) -> pd.DataFrame:
    """What each arm actually scored, on the set they can be compared on.

    Two rows per ``(check, property)``, one per arm, for reading beside
    :func:`arm_contrast`: a difference of ``-0.05`` means something
    different at 0.95 than at 0.20, and the contrast alone does not say
    which.

    The mean is taken over the **paired** examples only -- the same
    intersection ``arm_contrast`` uses -- so that

        ``variant mean - baseline mean == arm_contrast difference``

    exactly, for every row. Each arm's mean over its *own* examples would
    not: on exp-01 it disagreed for 17 of 67 contrasts, by as much as
    0.14, and reversed the sign of ``stat-test``'s ``explanation``. Two
    figures side by side that contradict each other are worse than one.

    The price is stated rather than hidden: ``n_examples`` is the paired
    count, and an arm that answered more is not credited here for the
    examples its counterpart skipped. ``arm_contrast``'s
    ``n_baseline_only`` and ``n_variant_only`` are where that goes.

    A property neither arm paired on is absent, not zero.
    """
    present = set(frame["arm"].unique()) if not frame.empty else set()
    for name in (baseline, variant):
        if name not in present:
            raise ValueError(
                f"No arm {name!r} in this frame; it has "
                f"{sorted(present) or 'nothing'}"
            )

    # Replicates average within (arm, example) first, exactly as
    # arm_contrast does -- a resample refines one measurement rather than
    # adding an example to the pairing.
    per_example = (
        frame.groupby(
            ["check", "property", "arm", "example"],
            dropna=False,
            observed=True,
        )["mean_score"]
        .mean()
        .reset_index()
    )

    rows: list[dict[str, Any]] = []
    for key, group in per_example.groupby(
        ["check", "property"], dropna=False, observed=True
    ):
        check, leaf_property = key
        by_arm = {
            arm: group[group["arm"] == arm]
            .set_index("example")["mean_score"]
            .dropna()
            for arm in (baseline, variant)
        }
        paired = by_arm[baseline].index.intersection(by_arm[variant].index)
        if not len(paired):
            continue

        for arm in (baseline, variant):
            values = by_arm[arm].loc[paired].astype(float)
            n_examples = int(len(values))
            rows.append(
                {
                    "check": check,
                    "property": leaf_property,
                    "path": property_path(check, leaf_property, arm=arm),
                    "arm": arm,
                    "mean": float(values.mean()),
                    "se": (
                        float(values.std(ddof=1) / (n_examples ** 0.5))
                        if n_examples > 1
                        else pd.NA
                    ),
                    "n_examples": n_examples,
                }
            )

    result = pd.DataFrame(rows, columns=list(ARM_LEVELS_COLUMNS))
    return result.astype({"mean": "Float64", "se": "Float64"})



#: Columns of :func:`non_response_counts`, in order.
NON_RESPONSE_COLUMNS = (
    "check",
    "model",
    "arm",
    "replicate",
    "example",
    "list_key",
    "path",
    "empty",
    "correct_row",
    "missing_row",
    "spurious_row",
)


def non_response_counts(runs: FlatRuns) -> pd.DataFrame:
    """Per example, whether the session returned an empty answer.

    An empty ``outputs`` scores as a fully missing row set rather than
    being excluded: a skill so thin that the model returns nothing is a
    worse result, not an absent one, and dropping those examples would
    flatter the arm that produced them.

    Count these before reading any mean. Non-response is a layer-S fact
    and it interacts with layer 2 in the direction that misleads: an arm
    that answers nothing has no applicable instances either, so it
    contributes nothing to the layer-2 mean and can appear to score
    *better* by having said less.

    ``empty`` is ``correct_row == 0 and missing_row > 0`` -- nothing
    matched and something was expected. A row set with nothing expected
    and nothing returned is agreement, not silence, and a spurious-only
    answer is a wrong answer rather than no answer; neither counts here.
    """
    rows: list[dict[str, Any]] = []
    for run in runs:
        for record in run.records:
            by_list = record.analysis.get("by_list", {})
            if not isinstance(by_list, dict):
                continue
            example = record_source(record)
            for list_key, payload in sorted(by_list.items()):
                if not isinstance(payload, dict):
                    continue
                counts = payload.get("row_counts")
                if not isinstance(counts, dict):
                    continue
                correct = int(counts.get("correct_row", 0) or 0)
                missing = int(counts.get("missing_row", 0) or 0)
                spurious = int(counts.get("spurious_row", 0) or 0)
                rows.append(
                    {
                        "check": run.check,
                        "model": run.model,
                        "arm": run.arm,
                        "replicate": run.replicate,
                        "example": example,
                        "list_key": list_key,
                        "path": property_path(
                            run.check,
                            f"{list_key}[]",
                            arm=run.arm,
                            replicate=run.replicate,
                            example=example,
                        ),
                        "empty": correct == 0 and missing > 0,
                        "correct_row": correct,
                        "missing_row": missing,
                        "spurious_row": spurious,
                    }
                )

    frame = pd.DataFrame(rows, columns=list(NON_RESPONSE_COLUMNS))
    if not frame.empty:
        frame["empty"] = frame["empty"].astype(bool)
    return frame
