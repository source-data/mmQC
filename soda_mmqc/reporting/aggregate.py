"""Aggregate per-doc flat analyses into run-level summaries."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Sequence

from soda_mmqc.core.eval_manifest import EvalManifest

from soda_mmqc.core.property_rollup import PropertyRollup, rollup_by_property
from soda_mmqc.reporting.load import FlatRun, FlatRuns

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
    """Aggregated reporting for one (model, prompt) flat run."""

    checklist: str
    check: str
    model: str
    prompt: str
    manifest: EvalManifest
    records: tuple[Any, ...]
    by_list_row_counts: dict[str, dict[str, int]]
    by_property: dict[str, PropertyRollup]

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
        checklist=run.checklist,
        check=run.check,
        model=run.model,
        prompt=run.prompt,
        manifest=run.manifest,
        records=run.records,
        by_list_row_counts={
            key: dict(counts) for key, counts in by_list_counts.items()
        },
        by_property=by_property,
    )


class RunSummaries(Mapping[tuple[str, str], RunSummary]):
    """Summaries keyed by ``(model, prompt)``."""

    def __init__(self, summaries: Sequence[RunSummary]) -> None:
        self._by_key = {(s.model, s.prompt): s for s in summaries}
        self._summaries = tuple(summaries)

    def __len__(self) -> int:
        return len(self._by_key)

    def __iter__(self) -> Iterator[tuple[str, str]]:
        return iter(self._by_key)

    def __getitem__(self, key: tuple[str, str]) -> RunSummary:
        return self._by_key[key]

    def for_model(self, model: str) -> tuple[RunSummary, ...]:
        return tuple(s for s in self._summaries if s.model == model)

    def for_prompt(self, prompt: str) -> tuple[RunSummary, ...]:
        return tuple(s for s in self._summaries if s.prompt == prompt)

    @property
    def models(self) -> tuple[str, ...]:
        return tuple(sorted({s.model for s in self._summaries}))

    @property
    def prompts(self) -> tuple[str, ...]:
        return tuple(sorted({s.prompt for s in self._summaries}))


def summarize_runs(runs: FlatRuns) -> RunSummaries:
    """Build one :class:`RunSummary` per :class:`FlatRun`."""
    return RunSummaries([aggregate_run(run) for run in runs])
