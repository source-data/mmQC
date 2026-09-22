"""Comparison workflow: overlay charts and drill-down tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Sequence

import pandas as pd
import plotly.graph_objects as go

from soda_mmqc.reporting.aggregate import RunSummaries, RunSummary
from soda_mmqc.reporting.display import (
    comparison_errors_table,
    show_comparison_errors,
)
from soda_mmqc.reporting.plots import (
    _comparison_summaries,
    plot_comparison_layer1,
    plot_comparison_layer2_binary,
    plot_comparison_layer2_graded,
    plot_comparison_layer_s,
)


@dataclass
class ComparisonReport:
    """Overlay figures and error table for an arm or model contrast."""

    compare: Literal["arm", "model"]
    anchor: str
    summaries: tuple[RunSummary, ...]
    layer_s_figure: go.Figure | None
    layer1_figure: go.Figure
    layer2_binary_figure: go.Figure
    layer2_graded_figure: go.Figure
    errors_table: pd.DataFrame

    @property
    def series_labels(self) -> tuple[str, ...]:
        if self.compare == "arm":
            return tuple(summary.arm for summary in self.summaries)
        return tuple(summary.model for summary in self.summaries)


def build_comparison_report(
    summaries: RunSummaries | Sequence[RunSummary],
    *,
    compare: Literal["arm", "model"] = "arm",
    model: str | None = None,
    arm: str | None = None,
) -> ComparisonReport:
    """Build overlay Layer S / 1 / 2 figures and a long-form error table."""
    selected = _comparison_summaries(
        summaries,
        compare=compare,
        model=model,
        arm=arm,
    )
    if compare == "arm":
        if model is None:
            raise ValueError("model is required when compare='arm'")
        anchor = model
    else:
        if arm is None:
            raise ValueError("arm is required when compare='model'")
        anchor = arm

    errors_table = comparison_errors_table(
        summaries,
        compare=compare,
        model=model,
        arm=arm,
    )
    return ComparisonReport(
        compare=compare,
        anchor=anchor,
        summaries=selected,
        layer_s_figure=plot_comparison_layer_s(
            summaries,
            compare=compare,
            model=model,
            arm=arm,
        ),
        layer1_figure=plot_comparison_layer1(
            summaries,
            compare=compare,
            model=model,
            arm=arm,
        ),
        layer2_binary_figure=plot_comparison_layer2_binary(
            summaries,
            compare=compare,
            model=model,
            arm=arm,
        ),
        layer2_graded_figure=plot_comparison_layer2_graded(
            summaries,
            compare=compare,
            model=model,
            arm=arm,
        ),
        errors_table=errors_table,
    )


def show_comparison_report(
    summaries: RunSummaries | Sequence[RunSummary],
    *,
    compare: Literal["arm", "model"] = "arm",
    model: str | None = None,
    arm: str | None = None,
    show_errors_table: bool = True,
) -> ComparisonReport:
    """Display comparison overlay charts and optional error table."""
    report = build_comparison_report(
        summaries,
        compare=compare,
        model=model,
        arm=arm,
    )
    if report.layer_s_figure is not None:
        report.layer_s_figure.show()
    report.layer1_figure.show()
    report.layer2_binary_figure.show()
    report.layer2_graded_figure.show()
    if show_errors_table:
        show_comparison_errors(
            summaries,
            compare=compare,
            model=model,
            arm=arm,
        )
    return report
