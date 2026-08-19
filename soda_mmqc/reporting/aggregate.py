"""Aggregate per-doc flat analyses into run-level summaries."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Sequence

from soda_mmqc.core.eval_manifest import EvalManifest

from soda_mmqc.core.property_rollup import property_mean_score
from soda_mmqc.reporting.load import FlatRun, FlatRuns


@dataclass(frozen=True)
class PropertyRollup:
    """Pooled summary for one leaf property across a run."""

    mean_score: float
    layer1_counts: dict[str, int]
    layer2_counts: dict[str, int]


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
    """Display label for a leaf property pattern (schema-relative when possible)."""
    prefix = "outputs[]."
    if leaf_property.startswith(prefix):
        return leaf_property[len(prefix) :]
    return leaf_property.rsplit(".", maxsplit=1)[-1]


def schema_leaf_property_patterns(schema: Mapping[str, Any] | None) -> list[str]:
    """Leaf ``outputs[].…`` patterns in ``schema.json`` panel-property order.

    Nested object arrays expand to ``outputs[].parent[].child`` leaves (the
    container itself is not a leaf). Primitive arrays stay as one leaf.
    """
    if not schema:
        return []
    try:
        properties = schema["format"]["schema"]["properties"]["outputs"]["items"][
            "properties"
        ]
    except (KeyError, TypeError):
        return []
    if not isinstance(properties, dict):
        return []

    ordered: list[str] = []
    for field_name, raw_spec in properties.items():
        if not isinstance(raw_spec, dict):
            continue
        if raw_spec.get("type") == "array":
            items = raw_spec.get("items")
            if isinstance(items, dict) and items.get("type") == "object":
                nested = items.get("properties")
                if isinstance(nested, dict):
                    for nested_name in nested:
                        ordered.append(f"outputs[].{field_name}[].{nested_name}")
                    continue
            ordered.append(f"outputs[].{field_name}")
            continue
        ordered.append(f"outputs[].{field_name}")
    return ordered


def load_check_schema_dict(checklist: str, check: str) -> dict[str, Any] | None:
    """Load checklist ``schema.json`` as a dict, if present."""
    import json

    from soda_mmqc.config import CHECKLIST_DIR

    path = CHECKLIST_DIR / checklist / check / "schema.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def field_order(
    manifest: EvalManifest,
    property_keys: Sequence[str],
    *,
    preferred: Sequence[str] | None = None,
) -> list[str]:
    """Order leaf properties: preferred (schema), then manifest, then sorted rest."""
    keys = set(property_keys)
    ordered: list[str] = []
    seen: set[str] = set()
    for key in preferred or ():
        if key in keys and key not in seen:
            ordered.append(key)
            seen.add(key)
    for key in manifest.field_patterns():
        if key in keys and key not in seen:
            ordered.append(key)
            seen.add(key)
    remainder = sorted(key for key in keys if key not in seen)
    return ordered + remainder


def field_order_for_summary(summary: RunSummary) -> list[str]:
    """Order a run's leaf properties using that check's ``schema.json``."""
    schema = load_check_schema_dict(summary.checklist, summary.check)
    return field_order(
        summary.manifest,
        summary.by_property.keys(),
        preferred=schema_leaf_property_patterns(schema),
    )


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
) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, int]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_list_counts: dict[str, dict[str, int]] = {}

    for record in records:
        analysis = record.analysis
        instances = analysis.get("instances", ())
        if isinstance(instances, list):
            for instance in instances:
                if not isinstance(instance, dict):
                    continue
                leaf_property = instance.get("leaf_property")
                if isinstance(leaf_property, str):
                    grouped[leaf_property].append(instance)

        by_list = analysis.get("by_list", {})
        if isinstance(by_list, dict):
            _merge_row_counts(by_list_counts, by_list)

    return grouped, by_list_counts


def aggregate_run(run: FlatRun) -> RunSummary:
    """Pool all leaf instances in a flat run into chart/table rollups."""
    grouped, by_list_counts = _pool_instances(run.records)

    by_property: dict[str, PropertyRollup] = {}
    for leaf_property, instances in grouped.items():
        profile = run.manifest.profile_for(leaf_property)
        profiled = profile is not None and profile.is_profiled
        mean_score = property_mean_score(instances, profiled=profiled)
        layer1 = Counter(
            inst["layer1"]
            for inst in instances
            if isinstance(inst.get("layer1"), str)
        )
        layer2 = Counter(
            inst["layer2"]
            for inst in instances
            if isinstance(inst.get("layer2"), str)
        )
        by_property[leaf_property] = PropertyRollup(
            mean_score=mean_score,
            layer1_counts=dict(layer1),
            layer2_counts=dict(layer2),
        )

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
