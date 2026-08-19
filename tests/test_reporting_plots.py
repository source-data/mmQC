"""Phase 3 tests for soda_mmqc.reporting.plots."""

from __future__ import annotations

import plotly.io as pio
import pytest

from soda_mmqc.reporting import (
    aggregate_run,
    build_dashboard,
    layer_counts_by_property,
    load_flat_runs,
    plot_comparison_layer1,
    plot_comparison_layer2_binary,
    plot_comparison_layer2_graded,
    plot_layer1_stacked,
    plot_layer2_stacked,
    plot_layer_s_bar,
    plot_mean_score_bars,
    plot_mean_score_with_instances,
    split_layer2_by_metric,
    summarize_runs,
)
from soda_mmqc.reporting.plots import (
    _field_numeric_positions,
    applicable_instance_scores_frame,
    mean_scores_frame,
    plot_comparison_mean_scores,
)
from soda_mmqc.reporting.styles import MEAN_SCORE_BAR_SPACING, PLOTLY_TEMPLATE
from soda_mmqc.reporting.styles import (
    LAYER1_ORDER,
    LAYER1_TITLE,
    LAYER2_BINARY_COLORS,
    LAYER2_BINARY_ORDER,
    LAYER2_BINARY_TITLE,
    LAYER2_GRADED_COLORS,
    LAYER2_GRADED_ORDER,
    LAYER2_GRADED_TITLE,
    LAYER_S_ORDER,
    LAYER_S_TITLE,
)

MODEL_MINI = "gpt-5-mini-2025-08-07"


@pytest.fixture
def prompt1_summary():
    runs = load_flat_runs(
        "fig-checklist",
        "micrograph-scale-bar",
        models=MODEL_MINI,
        prompts="prompt.1",
    )
    return aggregate_run(runs[0])


@pytest.fixture
def summaries_prompt():
    runs = load_flat_runs(
        "fig-checklist",
        "micrograph-scale-bar",
        models=MODEL_MINI,
        prompts=["prompt.1", "prompt.2", "prompt.3"],
    )
    return summarize_runs(runs)


@pytest.fixture
def summaries_model():
    runs = load_flat_runs(
        "fig-checklist",
        "micrograph-scale-bar",
        models=[MODEL_MINI, "gpt-5"],
        prompts="prompt.1",
    )
    return summarize_runs(runs)


class TestSingleRunPlots:
    def test_plot_layer_s_bar(self, prompt1_summary):
        counts = prompt1_summary.by_list_row_counts["outputs"]
        fig = plot_layer_s_bar(counts, title="Layer S test", list_key="outputs")
        assert len(fig.data) == 1
        assert list(fig.data[0].x) == list(LAYER_S_ORDER)

    def test_plot_layer1_stacked(self, prompt1_summary):
        frame = layer_counts_by_property(
            prompt1_summary, LAYER1_ORDER, "layer1_counts"
        )
        fig = plot_layer1_stacked(frame, title="Layer 1 test")
        assert len(fig.data) > 0
        all_fields = {field for trace in fig.data for field in trace.x}
        assert "micrograph" in all_fields
        assert any(trace.text for trace in fig.data if trace.type == "bar")

    def test_plot_layer2_binary_and_graded(self, prompt1_summary):
        binary_df, graded_df = split_layer2_by_metric(prompt1_summary)
        fig_bin = plot_layer2_stacked(
            binary_df,
            LAYER2_BINARY_ORDER,
            LAYER2_BINARY_COLORS,
            title="binary",
        )
        fig_graded = plot_layer2_stacked(
            graded_df,
            LAYER2_GRADED_ORDER,
            LAYER2_GRADED_COLORS,
            title="graded",
        )
        assert len(fig_bin.data) > 0
        assert len(fig_graded.data) > 0

    def test_plot_mean_score_bars(self, prompt1_summary):
        frame = mean_scores_frame(prompt1_summary)
        fig = plot_mean_score_bars(frame)
        assert len(fig.data) == 1
        assert len(fig.data[0].y) == len(frame)

    def test_plot_mean_score_with_instances(self, prompt1_summary):
        frame = mean_scores_frame(prompt1_summary)
        inst = applicable_instance_scores_frame(prompt1_summary)
        fields = frame["field"].tolist()
        field_to_x = _field_numeric_positions(fields, spacing=MEAN_SCORE_BAR_SPACING)
        fig = plot_mean_score_with_instances(prompt1_summary, seed=0)
        assert len(fig.data) == 2
        assert fig.data[0].type == "bar"
        assert fig.data[1].type == "scatter"
        assert fig.data[0].marker.color in ("#000000", "rgb(0, 0, 0)", "#000")
        assert len(fig.data[1].x) == len(inst)
        for x_val, row in zip(fig.data[1].x, inst.itertuples(index=False), strict=True):
            assert abs(x_val - field_to_x[row.field]) <= 0.25
        fig_repeat = plot_mean_score_with_instances(prompt1_summary, seed=0)
        assert list(fig.data[1].x) == list(fig_repeat.data[1].x)

    def test_build_dashboard_layout(self, prompt1_summary):
        fig = build_dashboard(prompt1_summary)
        assert fig.layout.template == pio.templates[PLOTLY_TEMPLATE]
        assert fig.layout.barmode == "stack"
        assert hasattr(fig.layout, "xaxis4")
        assert len(fig.data) >= 4
        assert fig.layout.yaxis.rangemode == "tozero"
        stacked_traces = [trace for trace in fig.data if trace.type == "bar" and trace.name]
        assert stacked_traces
        assert all(getattr(trace, "base", None) in (None, 0) for trace in stacked_traces)
        subplot_titles = [
            annotation.text
            for annotation in fig.layout.annotations
            if annotation.text
        ]
        assert LAYER_S_TITLE in subplot_titles
        assert LAYER1_TITLE in subplot_titles
        assert LAYER2_BINARY_TITLE in subplot_titles
        assert LAYER2_GRADED_TITLE in subplot_titles


class TestComparisonPlots:
    def test_prompt_contrast_layer1_series_count(self, summaries_prompt):
        fig = plot_comparison_layer1(
            summaries_prompt,
            compare="prompt",
            model=MODEL_MINI,
        )
        assert len(fig.data) > 0
        assert fig.layout.barmode == "stack"
        series = {
            row[1]
            for trace in fig.data
            if trace.customdata is not None
            for row in trace.customdata
        }
        assert series == {"prompt.1", "prompt.2", "prompt.3"}
        assert set(fig.data[0].x) == {"prompt.1", "prompt.2", "prompt.3"}
        assert fig.data[0].orientation in (None, "v")
        subplot_titles = [annotation.text for annotation in fig.layout.annotations]
        assert len(subplot_titles) == 7
        legend_outcomes = {
            trace.name for trace in fig.data if trace.showlegend
        }
        assert legend_outcomes == {
            "correct_NA",
            "correct_applicable",
            "spurious_applicable",
        }
        opacities = set()
        for trace in fig.data:
            opacity = trace.marker.opacity
            if isinstance(opacity, (list, tuple)):
                opacities.update(opacity)
            else:
                opacities.add(opacity)
        assert len(opacities) == 3

    def test_model_contrast_layer1_series_count(self, summaries_model):
        fig = plot_comparison_layer1(
            summaries_model,
            compare="model",
            prompt="prompt.1",
        )
        series = {
            row[1]
            for trace in fig.data
            if trace.customdata is not None
            for row in trace.customdata
        }
        assert series == {MODEL_MINI, "gpt-5"}
        patterns = set()
        for trace in fig.data:
            shape = trace.marker.pattern.shape
            if isinstance(shape, (list, tuple)):
                patterns.update(shape)
            elif shape:
                patterns.add(shape)
        assert "/" in patterns

    def test_comparison_layer2_binary(self, summaries_prompt):
        fig = plot_comparison_layer2_binary(
            summaries_prompt,
            compare="prompt",
            model=MODEL_MINI,
        )
        assert len(fig.data) > 0

    def test_comparison_layer2_graded(self, summaries_prompt):
        fig = plot_comparison_layer2_graded(
            summaries_prompt,
            compare="prompt",
            model=MODEL_MINI,
        )
        assert len(fig.data) > 0
        assert any(trace.text for trace in fig.data if trace.type == "bar")

    def test_comparison_mean_scores_with_instances(self, summaries_prompt):
        fig = plot_comparison_mean_scores(
            summaries_prompt,
            compare="prompt",
            model=MODEL_MINI,
            show_instances=True,
        )
        trace_types = [trace.type for trace in fig.data]
        assert "box" in trace_types
        assert "scatter" in trace_types
        assert "bar" not in trace_types
        assert "violin" not in trace_types
        scatter = next(trace for trace in fig.data if trace.type == "scatter")
        assert scatter.marker.size == 5
        assert scatter.marker.opacity == 0.4
        box = next(trace for trace in fig.data if trace.type == "box")
        assert box.width is not None
        assert box.width > 0.1

    def test_comparison_mean_scores_compact_packs_fields(self, summaries_prompt):
        wide = plot_comparison_mean_scores(
            summaries_prompt,
            compare="prompt",
            model=MODEL_MINI,
            show_instances=True,
            compact=False,
        )
        compact = plot_comparison_mean_scores(
            summaries_prompt,
            compare="prompt",
            model=MODEL_MINI,
            show_instances=True,
            compact=True,
        )
        wide_span = wide.layout.xaxis.range[1] - wide.layout.xaxis.range[0]
        compact_span = compact.layout.xaxis.range[1] - compact.layout.xaxis.range[0]
        assert compact_span < wide_span
        assert compact.layout.xaxis.tickangle == -35

    def test_comparison_requires_selector(self, summaries_prompt):
        with pytest.raises(ValueError, match="model is required"):
            plot_comparison_layer1(summaries_prompt, compare="prompt")
