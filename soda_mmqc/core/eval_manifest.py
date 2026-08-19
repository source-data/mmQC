"""Load and query evaluation manifests (eval-manifest.json)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Mapping, Optional

from soda_mmqc.core.leaves import PrimitiveListCompareMode, StringCompareMode

_INDEX_RE = re.compile(r"^(\w+)\[(\d+)\]$")

_COMPARE_ONLY_KEYS = frozenset(
    {"primitive_list_compare", "join_separator", "sort_before_join"}
)
DEFAULT_JOIN_SEPARATOR = ", "


class MatchingMetric(str, Enum):
    """Layer 2 reporting shape for a profiled leaf property."""

    BINARY_POLARITY = "binary_polarity"
    MULTICLASS = "multiclass"
    GRADED_STRING = "graded_string"


@dataclass(frozen=True)
class FieldProfile:
    """Resolved metric profile for one leaf property."""

    matching_metric: Optional[MatchingMetric] = None
    na_values: tuple[str, ...] = ()
    positive_value: Optional[str] = None
    negative_value: Optional[str] = None
    string_compare: Optional[StringCompareMode] = None
    match_threshold: Optional[float] = None
    primitive_list_compare: Optional[PrimitiveListCompareMode] = None
    join_separator: str = DEFAULT_JOIN_SEPARATOR
    sort_before_join: bool = False

    @property
    def is_profiled(self) -> bool:
        return self.matching_metric is not None

    def effective_primitive_list_compare(self) -> PrimitiveListCompareMode:
        """Resolved extended-primitive compare mode (default ``align``)."""
        if self.primitive_list_compare is None:
            return PrimitiveListCompareMode.ALIGN
        return self.primitive_list_compare


@dataclass(frozen=True)
class EvalManifest:
    """Parsed eval-manifest.json."""

    checklist: str
    defaults: FieldProfile
    list_alignment: dict[str, tuple[str, ...]]
    _fields: dict[str, FieldProfile]
    _field_keys: dict[str, frozenset[str]]

    def profile_for(self, leaf_property: str) -> Optional[FieldProfile]:
        """Return merged defaults + field override, or None if unprofiled."""
        override = self._fields.get(leaf_property)
        if override is None:
            return None
        override_keys = self._field_keys[leaf_property]
        return _merge_profiles(self.defaults, override, override_keys=override_keys)

    def alignment_keys_for(self, list_name: str) -> Optional[tuple[str, ...]]:
        """Look up alignment keys by list name or ``by_list`` key."""
        if list_name in self.list_alignment:
            return self.list_alignment[list_name]
        normalized = list_name.replace("[].", ".")
        return self.list_alignment.get(normalized)

    def profiled_leaf_properties(self) -> tuple[str, ...]:
        return tuple(self._fields)

    def field_patterns(self) -> tuple[str, ...]:
        """All manifest ``fields`` path keys (schema / insertion order)."""
        return tuple(self._fields)


def load_eval_manifest(path: Path | str) -> EvalManifest:
    """Load and parse an eval-manifest.json file."""
    manifest_path = Path(path)
    with manifest_path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return parse_eval_manifest(data)


def parse_eval_manifest(data: Mapping[str, Any]) -> EvalManifest:
    """Parse manifest data from a JSON object."""
    checklist = _require_str(data, "checklist")
    defaults_raw = data.get("defaults", {})
    if not isinstance(defaults_raw, dict):
        raise ValueError("defaults must be an object")

    defaults = _profile_from_raw(defaults_raw, context="defaults")
    _validate_defaults(defaults_raw)

    list_alignment_raw = data.get("list_alignment", {})
    if not isinstance(list_alignment_raw, dict):
        raise ValueError("list_alignment must be an object")
    list_alignment = _parse_list_alignment(list_alignment_raw)

    fields_raw = data.get("fields", {})
    if not isinstance(fields_raw, dict):
        raise ValueError("fields must be an object")

    fields: dict[str, FieldProfile] = {}
    field_keys: dict[str, frozenset[str]] = {}
    for path_key, field_raw in fields_raw.items():
        if not isinstance(field_raw, dict):
            raise ValueError(f"fields[{path_key!r}] must be an object")
        profile = _profile_from_raw(field_raw, context=f"fields[{path_key!r}]")
        merged = _merge_profiles(
            defaults, profile, override_keys=frozenset(field_raw)
        )
        if _is_compare_only_override(frozenset(field_raw)):
            _validate_compare_only_field(path_key, merged)
        else:
            _validate_field_profile(path_key, merged)
        fields[path_key] = profile
        field_keys[path_key] = frozenset(field_raw)

    return EvalManifest(
        checklist=checklist,
        defaults=defaults,
        list_alignment=list_alignment,
        _fields=fields,
        _field_keys=field_keys,
    )


def instance_to_leaf_property(instance_path: str) -> str:
    """Map a concrete path to its manifest pattern (e.g. ``panels[1].status``)."""
    segments: list[str] = []
    for segment in instance_path.split("."):
        match = _INDEX_RE.match(segment)
        if match:
            segments.append(f"{match.group(1)}[]")
        else:
            segments.append(segment)
    return ".".join(segments)


def path_matches_pattern(pattern: str, instance_path: str) -> bool:
    """True when ``instance_path`` is an instance of manifest pattern ``pattern``."""
    return instance_to_leaf_property(instance_path) == pattern


def _parse_list_alignment(raw: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for list_name, keys in raw.items():
        if not isinstance(list_name, str):
            raise ValueError("list_alignment keys must be strings")
        if not isinstance(keys, list) or not keys:
            raise ValueError(
                f"list_alignment[{list_name!r}] must be a non-empty array"
            )
        if not all(isinstance(key, str) and key for key in keys):
            raise ValueError(
                f"list_alignment[{list_name!r}] must contain non-empty strings"
            )
        result[list_name] = tuple(keys)
    return result


def _profile_from_raw(raw: Mapping[str, Any], *, context: str) -> FieldProfile:
    matching_metric = _parse_matching_metric(raw.get("matching_metric"), context=context)
    na_values = _parse_na_values(raw.get("na_values"), context=context)
    positive_value = _optional_str(raw.get("positive_value"), field="positive_value")
    negative_value = _optional_str(raw.get("negative_value"), field="negative_value")
    string_compare = _parse_string_compare(
        raw.get("string_compare"), context=context
    )
    match_threshold = _parse_match_threshold(
        raw.get("match_threshold"), context=context
    )
    primitive_list_compare = _parse_primitive_list_compare(
        raw.get("primitive_list_compare"), context=context
    )
    join_separator = _parse_join_separator(raw.get("join_separator"), context=context)
    sort_before_join = _parse_sort_before_join(
        raw.get("sort_before_join"), context=context
    )
    return FieldProfile(
        matching_metric=matching_metric,
        na_values=na_values,
        positive_value=positive_value,
        negative_value=negative_value,
        string_compare=string_compare,
        match_threshold=match_threshold,
        primitive_list_compare=primitive_list_compare,
        join_separator=join_separator,
        sort_before_join=sort_before_join,
    )


def _merge_profiles(
    defaults: FieldProfile,
    override: FieldProfile,
    *,
    override_keys: frozenset[str],
) -> FieldProfile:
    if _is_compare_only_override(override_keys):
        return override
    return FieldProfile(
        matching_metric=(
            override.matching_metric
            if "matching_metric" in override_keys
            else defaults.matching_metric
        ),
        na_values=(
            override.na_values
            if "na_values" in override_keys
            else defaults.na_values
        ),
        positive_value=(
            override.positive_value
            if "positive_value" in override_keys
            else defaults.positive_value
        ),
        negative_value=(
            override.negative_value
            if "negative_value" in override_keys
            else defaults.negative_value
        ),
        string_compare=(
            override.string_compare
            if "string_compare" in override_keys
            else defaults.string_compare
        ),
        match_threshold=(
            override.match_threshold
            if "match_threshold" in override_keys
            else defaults.match_threshold
        ),
        primitive_list_compare=(
            override.primitive_list_compare
            if "primitive_list_compare" in override_keys
            else defaults.primitive_list_compare
        ),
        join_separator=(
            override.join_separator
            if "join_separator" in override_keys
            else defaults.join_separator
        ),
        sort_before_join=(
            override.sort_before_join
            if "sort_before_join" in override_keys
            else defaults.sort_before_join
        ),
    )


def _validate_defaults(raw: Mapping[str, Any]) -> None:
    if "string_compare" in raw:
        raise ValueError("string_compare must not appear in defaults")
    if "match_threshold" in raw:
        raise ValueError("match_threshold must not appear in defaults")
    if "primitive_list_compare" in raw:
        raise ValueError("primitive_list_compare must not appear in defaults")
    if "join_separator" in raw:
        raise ValueError("join_separator must not appear in defaults")
    if "sort_before_join" in raw:
        raise ValueError("sort_before_join must not appear in defaults")


def _is_compare_only_override(override_keys: frozenset[str]) -> bool:
    return bool(override_keys) and override_keys <= _COMPARE_ONLY_KEYS


def _validate_compare_only_field(path_key: str, merged: FieldProfile) -> None:
    if merged.primitive_list_compare is None:
        raise ValueError(
            f"fields[{path_key!r}] compare-only entry requires primitive_list_compare"
        )
    if merged.primitive_list_compare == PrimitiveListCompareMode.JOIN_STRING:
        raise ValueError(
            f"fields[{path_key!r}] join_string requires matching_metric "
            "graded_string in the same field"
        )


def _validate_field_profile(path_key: str, merged: FieldProfile) -> None:
    if merged.matching_metric is None:
        if merged.primitive_list_compare is not None:
            _validate_compare_only_field(path_key, merged)
            return
        raise ValueError(f"fields[{path_key!r}] must set matching_metric")

    if merged.matching_metric == MatchingMetric.GRADED_STRING:
        if merged.string_compare is None:
            raise ValueError(
                f"fields[{path_key!r}] graded_string requires string_compare"
            )
        if merged.match_threshold is None:
            raise ValueError(
                f"fields[{path_key!r}] graded_string requires match_threshold"
            )

    if merged.matching_metric == MatchingMetric.BINARY_POLARITY:
        if merged.positive_value is None or merged.negative_value is None:
            raise ValueError(
                f"fields[{path_key!r}] binary_polarity requires "
                "positive_value and negative_value (field or defaults)"
            )

    if merged.primitive_list_compare == PrimitiveListCompareMode.JOIN_STRING:
        if merged.matching_metric != MatchingMetric.GRADED_STRING:
            raise ValueError(
                f"fields[{path_key!r}] join_string requires "
                "matching_metric graded_string"
            )


def _parse_matching_metric(
    value: Any, *, context: str
) -> Optional[MatchingMetric]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{context}.matching_metric must be a string")
    try:
        return MatchingMetric(value)
    except ValueError as exc:
        allowed = ", ".join(metric.value for metric in MatchingMetric)
        raise ValueError(
            f"{context}.matching_metric must be one of: {allowed}"
        ) from exc


def _parse_string_compare(
    value: Any, *, context: str
) -> Optional[StringCompareMode]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{context}.string_compare must be a string")
    try:
        return StringCompareMode(value)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in StringCompareMode)
        raise ValueError(
            f"{context}.string_compare must be one of: {allowed}"
        ) from exc


def _parse_match_threshold(value: Any, *, context: str) -> Optional[float]:
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        raise ValueError(f"{context}.match_threshold must be a number")
    threshold = float(value)
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"{context}.match_threshold must be in [0, 1]")
    return threshold


def _parse_na_values(value: Any, *, context: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{context}.na_values must be an array")
    for item in value:
        if not isinstance(item, str):
            raise ValueError(f"{context}.na_values must contain strings only")
    return tuple(value)


def _parse_primitive_list_compare(
    value: Any, *, context: str
) -> Optional[PrimitiveListCompareMode]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{context}.primitive_list_compare must be a string")
    try:
        return PrimitiveListCompareMode(value)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in PrimitiveListCompareMode)
        raise ValueError(
            f"{context}.primitive_list_compare must be one of: {allowed}"
        ) from exc


def _parse_join_separator(value: Any, *, context: str) -> str:
    if value is None:
        return DEFAULT_JOIN_SEPARATOR
    if not isinstance(value, str):
        raise ValueError(f"{context}.join_separator must be a string")
    return value


def _parse_sort_before_join(value: Any, *, context: str) -> bool:
    if value is None:
        return False
    if not isinstance(value, bool):
        raise ValueError(f"{context}.sort_before_join must be a boolean")
    return value


def _require_str(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _optional_str(value: Any, *, field: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    return value
