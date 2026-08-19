"""Tests for curated key-field role score frames and boxplots."""

from __future__ import annotations

from soda_mmqc.reporting.aggregate import summarize_runs
from soda_mmqc.reporting.key_fields import (
    FIG_KEY_FIELD_SUMMARY,
    checks_for_role,
    key_field_role_means_frame,
)
from soda_mmqc.reporting.load import load_flat_runs
from soda_mmqc.reporting.plots import (
    key_field_role_instance_frame,
    plot_key_field_role_scores,
)

MODEL_MINI = "gpt-5-mini-2025-08-07"
MODEL_54 = "gpt-5.4"


def test_key_field_role_means_and_instances():
    check_map = {}
    for check, _ in FIG_KEY_FIELD_SUMMARY[:3]:
        runs = load_flat_runs(
            "fig-checklist",
            check,
            models=[MODEL_MINI, MODEL_54],
        )
        check_map[check] = summarize_runs(runs)

    means = key_field_role_means_frame(
        check_map,
        models=[MODEL_MINI, MODEL_54],
    )
    assert not means.empty
    assert set(means["role"]) <= {"binary", "semantic", "extraction"}
    assert set(means["model"]) <= {MODEL_MINI, MODEL_54}

    idp = means.loc[means["check"] == "individual-data-points"]
    assert set(idp["role"]) == {"binary", "semantic"}
    assert (idp.loc[idp["role"] == "binary", "fields"] == "decision").all()

    binary_inst = key_field_role_instance_frame(
        check_map,
        models=[MODEL_MINI],
        role="binary",
    )
    assert not binary_inst.empty
    assert (binary_inst["role"] == "binary").all()
    assert "score" in binary_inst.columns


def test_key_field_role_plots_build():
    check_map = {}
    for check in ("stat-significance-level", "error-bars-defined"):
        runs = load_flat_runs(
            "fig-checklist",
            check,
            models=MODEL_MINI,
        )
        check_map[check] = summarize_runs(runs)

    for role in ("binary", "semantic", "extraction"):
        check_fields = [
            pair
            for pair in checks_for_role(role)
            if pair[0] in check_map
        ]
        if not check_fields:
            continue
        frame = key_field_role_instance_frame(
            check_map,
            models=[MODEL_MINI],
            role=role,
        )
        fig = plot_key_field_role_scores(
            frame,
            role=role,
            models=[MODEL_MINI],
            check_fields=check_fields,
            title=f"{role} test",
        )
        types = {trace.type for trace in fig.data}
        assert "box" in types
        assert "scatter" in types
