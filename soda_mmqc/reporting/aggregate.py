"""Aggregate per-doc flat analyses into run-level summaries."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from soda_mmqc.core.eval_manifest import EvalManifest

from soda_mmqc.core.property_rollup import PropertyRollup, rollup_by_property
from soda_mmqc.core.run_layout import BASELINE_ARM
from soda_mmqc.reporting.load import FlatRun, FlatRuns, RunRef

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
    "field_order",
    "leaf_property_tail",
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
