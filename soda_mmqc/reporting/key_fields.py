"""Key-field summary: curated leaf scores by check × role (binary/semantic/extraction)."""

from __future__ import annotations

from typing import Mapping, Sequence

import pandas as pd

from soda_mmqc.reporting.aggregate import (
    RunSummaries,
    RunSummary,
    field_order_for_summary,
    leaf_property_tail,
)

KEY_FIELD_ROLES = ("binary", "semantic", "extraction")

# (check, {role: leaf tails under outputs[].…})
# Mapped from the curation table: check × binary / semantic / extraction.
FIG_KEY_FIELD_SUMMARY: tuple[tuple[str, dict[str, tuple[str, ...]]], ...] = (
    (
        "error-bars-defined",
        {
            "binary": ("error_bar_defined_in_caption",),
            "semantic": ("Decision_and_explanation",),
            "extraction": ("from_the_caption",),
        },
    ),
    (
        "image-annotation-defined",
        {
            "binary": ("annotation_defined_in_caption",),
            "extraction": ("from_the_caption",),
        },
    ),
    (
        "individual-data-points",
        {
            "binary": ("decision",),
            "semantic": ("explanation",),
        },
    ),
    (
        "individual-data-points-D-E",
        {
            "binary": ("decision",),
            "semantic": ("explanation",),
        },
    ),
    (
        "micrograph-scale-bar",
        {
            "extraction": ("from_the_caption", "from_the_image"),
        },
    ),
    (
        "plot-axis-units",
        {
            "binary": ("decision",),
            "semantic": ("explanation[].explanation",),
            "extraction": ("unit_definition_as_provided[].definition",),
        },
    ),
    (
        "plot-gap-labeling",
        {
            "binary": ("decision",),
            "semantic": ("explanation",),
        },
    ),
    (
        "replication-reporting",
        {
            "binary": ("decision",),
            "semantic": ("explanation",),
            "extraction": ("replicate_statements",),
        },
    ),
    (
        "single-channel-for-overlay",
        {
            "binary": ("all_channels_shown_separately",),
        },
    ),
    (
        "stat-significance-level",
        {
            "binary": ("decision",),
            "semantic": ("explanation",),
            "extraction": ("symbol_definition",),
        },
    ),
    (
        "stat-test",
        {
            "binary": ("decision",),
            "semantic": ("explanation",),
            "extraction": ("from_the_caption",),
        },
    ),
)


def _macro_mean(summary: RunSummary) -> float:
    order = field_order_for_summary(summary)
    scores = [
        summary.by_property[key].mean_score
        for key in order
        if key in summary.by_property
    ]
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def best_prompt_summary(summaries: RunSummaries, *, model: str) -> RunSummary | None:
    """Prompt with highest macro mean for ``model``."""
    candidates = list(summaries.for_model(model))
    if not candidates:
        return None
    return max(candidates, key=_macro_mean)


def role_field_label(fields: Sequence[str]) -> str:
    """Compact field-name label for axis ticks / hover."""
    return ", ".join(fields)


def checks_for_role(
    role: str,
    *,
    mapping: Sequence[tuple[str, Mapping[str, Sequence[str]]]] = FIG_KEY_FIELD_SUMMARY,
) -> list[tuple[str, str]]:
    """Ordered ``(check, fields_label)`` pairs that define ``role``."""
    out: list[tuple[str, str]] = []
    for check, role_fields in mapping:
        fields = tuple(role_fields.get(role, ()))
        if fields:
            out.append((check, role_field_label(fields)))
    return out


def key_field_role_means_frame(
    check_summaries: Mapping[str, RunSummaries],
    *,
    models: Sequence[str],
    mapping: Sequence[tuple[str, Mapping[str, Sequence[str]]]] = FIG_KEY_FIELD_SUMMARY,
) -> pd.DataFrame:
    """Per check × model × role mean of mapped leaf mean_scores (best prompt)."""
    rows: list[dict[str, object]] = []
    for check, role_fields in mapping:
        summaries = check_summaries.get(check)
        if summaries is None:
            continue
        for model in models:
            best = best_prompt_summary(summaries, model=model)
            if best is None:
                continue
            by_tail = {
                leaf_property_tail(key): rollup.mean_score
                for key, rollup in best.by_property.items()
            }
            for role in KEY_FIELD_ROLES:
                fields = tuple(role_fields.get(role, ()))
                if not fields:
                    continue
                scores = [by_tail[tail] for tail in fields if tail in by_tail]
                if not scores:
                    continue
                rows.append(
                    {
                        "check": check,
                        "model": model,
                        "prompt": best.prompt,
                        "role": role,
                        "fields": role_field_label(fields),
                        "mean_score": sum(scores) / len(scores),
                    }
                )
    return pd.DataFrame(rows)
