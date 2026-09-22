"""Phase 3 tests for soda_mmqc.reporting.plots."""

from __future__ import annotations

import plotly.io as pio
import pytest

from soda_mmqc.reporting import (
    aggregate_run,
    build_dashboard,
    layer_counts_by_property,
    load_evaluation_dir,
    plot_comparison_layer1,
    plot_comparison_layer2_binary,
    plot_comparison_layer2_graded,
    plot_layer1_stacked,
    plot_layer2_stacked,
    plot_layer_s_bar,
    plot_mean_score_bars,
    plot_arm_contrast_by_check,
    plot_mean_score_with_instances,
    split_layer2_by_metric,
    summarize_runs,
)
from soda_mmqc.reporting.plots import (
    _field_numeric_positions,
    applicable_instance_scores_frame,
    mean_scores_frame,
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

from pathlib import Path


# The committed snapshot these tests read instead of soda_mmqc/data/evaluation.
# Reading the live corpus meant asserting whichever evaluation runs happened to
# be committed -- a statement about data, not about the reporting code -- so the
# tests broke whenever that corpus was regenerated or removed.
FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/reporting_snapshots"


@pytest.fixture(autouse=True)
def _use_fixture_corpus(monkeypatch):
    """Point the loader at the committed snapshot, not the live corpus."""
    monkeypatch.setattr("soda_mmqc.reporting.load.EVALUATION_DIR", FIXTURES)


MODEL_A = "model-a"


@pytest.fixture
def arm1_summary():
    runs = load_evaluation_dir(
        "fig-checklist",
        "micrograph-scale-bar",
        models=MODEL_A,
        arms="pinned",
    )
    return aggregate_run(runs[0])


@pytest.fixture
def summaries_arm():
    runs = load_evaluation_dir(
        "fig-checklist",
        "micrograph-scale-bar",
        models=MODEL_A,
        arms=["pinned", "micrograph-scale-bar@v2", "micrograph-scale-bar@v3"],
    )
    return summarize_runs(runs)


@pytest.fixture
def summaries_model():
    runs = load_evaluation_dir(
        "fig-checklist",
        "micrograph-scale-bar",
        models=[MODEL_A, "model-b"],
        arms="pinned",
    )
    return summarize_runs(runs)


class TestSingleRunPlots:
    def test_plot_layer_s_bar(self, arm1_summary):
        counts = arm1_summary.by_list_row_counts["outputs"]
        fig = plot_layer_s_bar(counts, title="Layer S test", list_key="outputs")
        assert len(fig.data) == 1
        assert list(fig.data[0].x) == list(LAYER_S_ORDER)

    def test_plot_layer1_stacked(self, arm1_summary):
        frame = layer_counts_by_property(
            arm1_summary, LAYER1_ORDER, "layer1_counts"
        )
        fig = plot_layer1_stacked(frame, title="Layer 1 test")
        assert len(fig.data) > 0
        all_fields = {field for trace in fig.data for field in trace.x}
        assert "micrograph" in all_fields

    def test_plot_layer2_binary_and_graded(self, arm1_summary):
        binary_df, graded_df = split_layer2_by_metric(arm1_summary)
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

    def test_plot_mean_score_bars(self, arm1_summary):
        frame = mean_scores_frame(arm1_summary)
        fig = plot_mean_score_bars(frame)
        assert len(fig.data) == 1
        assert len(fig.data[0].y) == len(frame)

    def test_plot_mean_score_with_instances(self, arm1_summary):
        frame = mean_scores_frame(arm1_summary)
        inst = applicable_instance_scores_frame(arm1_summary)
        fields = frame["field"].tolist()
        field_to_x = _field_numeric_positions(fields, spacing=MEAN_SCORE_BAR_SPACING)
        fig = plot_mean_score_with_instances(arm1_summary, seed=0)
        assert len(fig.data) == 2
        assert fig.data[0].type == "bar"
        assert fig.data[1].type == "scatter"
        assert fig.data[0].marker.color in ("#000000", "rgb(0, 0, 0)", "#000")
        assert len(fig.data[1].x) == len(inst)
        for x_val, row in zip(fig.data[1].x, inst.itertuples(index=False), strict=True):
            assert abs(x_val - field_to_x[row.field]) <= 0.25
        fig_repeat = plot_mean_score_with_instances(arm1_summary, seed=0)
        assert list(fig.data[1].x) == list(fig_repeat.data[1].x)

    def test_build_dashboard_layout(self, arm1_summary):
        fig = build_dashboard(arm1_summary)
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
    def test_arm_contrast_layer1_series_count(self, summaries_arm):
        fig = plot_comparison_layer1(
            summaries_arm,
            compare="arm",
            model=MODEL_A,
        )
        assert len(fig.data) > 0
        assert fig.layout.barmode == "stack"
        series = {
            row[1]
            for trace in fig.data
            if trace.customdata is not None
            for row in trace.customdata
        }
        assert series == {"pinned", "micrograph-scale-bar@v2", "micrograph-scale-bar@v3"}
        assert set(fig.data[0].x) == {"pinned", "micrograph-scale-bar@v2", "micrograph-scale-bar@v3"}
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
            arm="pinned",
        )
        series = {
            row[1]
            for trace in fig.data
            if trace.customdata is not None
            for row in trace.customdata
        }
        assert series == {MODEL_A, "model-b"}
        patterns = set()
        for trace in fig.data:
            shape = trace.marker.pattern.shape
            if isinstance(shape, (list, tuple)):
                patterns.update(shape)
            elif shape:
                patterns.add(shape)
        assert "/" in patterns

    def test_comparison_layer2_binary(self, summaries_arm):
        fig = plot_comparison_layer2_binary(
            summaries_arm,
            compare="arm",
            model=MODEL_A,
        )
        assert len(fig.data) > 0

    def test_comparison_layer2_graded(self, summaries_arm):
        fig = plot_comparison_layer2_graded(
            summaries_arm,
            compare="arm",
            model=MODEL_A,
        )
        assert len(fig.data) > 0

    def test_comparison_requires_selector(self, summaries_arm):
        with pytest.raises(ValueError, match="model is required"):
            plot_comparison_layer1(summaries_arm, compare="arm")


class TestArmContrastByCheck:
    """One panel per check, because a difference only means something
    against the other properties of the same check.

    A single axis over all 62 exp-01 contrasts stacked eleven unrelated
    checks into one column of bars, and the tick labels had to carry the
    whole property path to stay unambiguous.
    """

    @pytest.fixture
    def contrast(self):
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "check": "micrograph-scale-bar",
                    "property": "outputs[].panel_label",
                    "path": "micrograph-scale-bar::::outputs[].panel_label",
                    "difference": -0.20,
                    "se": 0.04,
                    "n_examples": 38,
                    "paired_fraction": 1.0,
                },
                {
                    "check": "micrograph-scale-bar",
                    "property": "outputs[].micrograph",
                    "path": "micrograph-scale-bar::::outputs[].micrograph",
                    "difference": 0.05,
                    "se": 0.01,
                    "n_examples": 38,
                    "paired_fraction": 1.0,
                },
                {
                    "check": "plot-axis-units",
                    "property": "outputs[].units_provided[].axis",
                    "path": "plot-axis-units::::outputs[].units_provided[].axis",
                    "difference": 0.002,
                    "se": 0.005,
                    "n_examples": 28,
                    "paired_fraction": 0.95,
                },
                {
                    "check": "plot-axis-units",
                    "property": "outputs[].unit_definition_as_provided[].axis",
                    "path": (
                        "plot-axis-units::::outputs[]."
                        "unit_definition_as_provided[].axis"
                    ),
                    "difference": -0.01,
                    "se": 0.006,
                    "n_examples": 28,
                    "paired_fraction": 0.95,
                },
            ]
        )

    def test_one_panel_per_check(self, contrast):
        fig = plot_arm_contrast_by_check(contrast)
        titles = [annotation.text for annotation in fig.layout.annotations]
        assert titles == ["micrograph-scale-bar", "plot-axis-units"]

    def test_a_tick_drops_the_path_root_but_stays_unambiguous(self, contrast):
        """The panel title carries the check, so the tick need not -- and
        nor need it carry the `outputs[]` root every property shares.

        What distinguishes two properties must survive: plot-axis-units
        has two tailing in `axis`, and they share one panel.
        """
        fig = plot_arm_contrast_by_check(contrast)
        labels = {y for trace in fig.data for y in (trace.y or ())}
        assert "units_provided[].axis" in labels
        assert "unit_definition_as_provided[].axis" in labels
        assert not any(label.startswith("plot-axis-units:") for label in labels)
        assert not any(label.startswith("outputs[]") for label in labels)

    def test_the_x_axis_is_shared_so_panels_compare(self, contrast):
        """Per-panel autoscaling would make a 0.002 difference look like
        a 0.2 one."""
        fig = plot_arm_contrast_by_check(contrast)
        layout = fig.layout.to_plotly_json()
        ranges = {
            tuple(value["range"])
            for key, value in layout.items()
            if key.startswith("xaxis") and value.get("range")
        }
        assert len(ranges) == 1

    def test_every_bar_carries_its_standard_error(self, contrast):
        fig = plot_arm_contrast_by_check(contrast)
        seen = set()
        for trace in fig.data:
            if trace.error_x is not None and trace.error_x.array is not None:
                seen.update(round(v, 4) for v in trace.error_x.array)
        assert seen == {0.04, 0.01, 0.005, 0.006}

    def test_an_empty_contrast_is_not_a_crash(self):
        import pandas as pd

        fig = plot_arm_contrast_by_check(
            pd.DataFrame(
                columns=["check", "property", "path", "difference", "se"]
            )
        )
        assert fig.data == ()


class TestArmContrastLayout:
    """Horizontal bars with long tick labels need width, not columns.

    `_comparison_subplot_grid` packs four across, which suits vertical
    bars over short categories. A property label runs to 49 characters
    (`outputs[].unit_definition_as_provided[].definition`), so at a
    quarter width the label crowds out the bar.
    """

    @staticmethod
    def _frame(checks_and_counts):
        import pandas as pd

        rows = []
        for check, count in checks_and_counts:
            for i in range(count):
                rows.append(
                    {
                        "check": check,
                        "property": f"outputs[].p{i}",
                        "path": f"{check}::::outputs[].p{i}",
                        "difference": 0.01 * i,
                        "se": 0.001,
                    }
                )
        return pd.DataFrame(rows)

    def _column_count(self, fig):
        layout = fig.layout.to_plotly_json()
        starts = {
            round(value["domain"][0], 4)
            for key, value in layout.items()
            if key.startswith("xaxis") and value.get("domain")
        }
        return len(starts)

    def test_one_column_by_default(self):
        """Plotly hangs y tick labels outside the panel, into whatever is
        to its left. At two columns the right panel's labels landed on
        the left panel's bars; a 40-character label needs the full width.
        """
        fig = plot_arm_contrast_by_check(
            self._frame([("a", 2), ("b", 2), ("c", 2), ("d", 2)])
        )
        assert self._column_count(fig) == 1

    def test_the_caller_can_pack_it_tighter(self):
        fig = plot_arm_contrast_by_check(
            self._frame([("a", 2), ("b", 2), ("c", 2), ("d", 2)]), columns=2
        )
        assert self._column_count(fig) == 2

    def test_a_row_is_only_as_tall_as_its_tallest_panel(self):
        """A row holding a 2-bar panel should not be sized for an 8-bar one."""
        lopsided = plot_arm_contrast_by_check(
            self._frame([("a", 8), ("b", 8), ("c", 2), ("d", 2)])
        )
        uniform = plot_arm_contrast_by_check(
            self._frame([("a", 8), ("b", 8), ("c", 8), ("d", 8)])
        )
        assert lopsided.layout.height < uniform.layout.height


class TestArmContrastTickLabels:
    """Inside a per-check panel, the list root is redundant.

    Every property of a check hangs off the same output list, so every
    tick began `outputs[].`. Ten wasted characters on a 49-character
    label is the difference between a panel that has room for its bars
    and one whose labels overflow into the panel beside it.
    """

    @staticmethod
    def _frame(check, properties):
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "check": check,
                    "property": prop,
                    "path": f"{check}::::{prop}",
                    "difference": 0.01,
                    "se": 0.001,
                }
                for prop in properties
            ]
        )

    def _labels(self, fig):
        return {y for trace in fig.data for y in (trace.y or ())}

    def test_the_shared_list_root_goes(self):
        fig = plot_arm_contrast_by_check(
            self._frame("stat-test", ["outputs[].panel_label", "outputs[].is_a_plot"])
        )
        assert self._labels(fig) == {"panel_label", "is_a_plot"}

    def test_a_deeper_path_keeps_what_distinguishes_it(self):
        """plot-axis-units' two `axis` properties must stay apart."""
        fig = plot_arm_contrast_by_check(
            self._frame(
                "plot-axis-units",
                [
                    "outputs[].decision",
                    "outputs[].units_provided[].axis",
                    "outputs[].unit_definition_as_provided[].axis",
                ],
            )
        )
        assert self._labels(fig) == {
            "decision",
            "units_provided[].axis",
            "unit_definition_as_provided[].axis",
        }

    def test_a_root_not_shared_by_every_property_stays(self):
        """Two lists in one check: stripping either would collide them."""
        fig = plot_arm_contrast_by_check(
            self._frame("two-lists", ["a[].name", "b[].name"])
        )
        assert self._labels(fig) == {"a[].name", "b[].name"}

    def test_the_full_path_is_still_in_the_hover(self):
        fig = plot_arm_contrast_by_check(
            self._frame("stat-test", ["outputs[].panel_label"])
        )
        assert fig.data[0].customdata[0][0] == (
            "stat-test::::outputs[].panel_label"
        )


class TestArmContrastVerticalBudget:
    """Spacing is a fraction of the whole figure, so it must shrink as
    panels are added.

    `vertical_spacing` is applied between every pair of rows. At the
    0.08 the comparison grids use, eleven stacked checks spent ten gaps
    x 0.08 = 80% of the figure on whitespace, leaving the panels a fifth
    of the height and plotly dropping every other tick label.
    """

    @staticmethod
    def _frame(n_checks, bars=3):
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "check": f"check-{c:02d}",
                    "property": f"outputs[].p{i}",
                    "path": f"check-{c:02d}::::outputs[].p{i}",
                    "difference": 0.01,
                    "se": 0.001,
                }
                for c in range(n_checks)
                for i in range(bars)
            ]
        )

    def test_panels_keep_most_of_the_figure(self):
        fig = plot_arm_contrast_by_check(self._frame(11))
        layout = fig.layout.to_plotly_json()
        used = sum(
            value["domain"][1] - value["domain"][0]
            for key, value in layout.items()
            if key.startswith("yaxis") and value.get("domain")
        )
        assert used > 0.7, (
            f"panels got {used:.0%} of the height; the rest went to gaps"
        )

    def test_only_the_bottom_panel_labels_the_x_axis(self):
        """Eleven copies of 'difference in mean_score' is noise."""
        fig = plot_arm_contrast_by_check(self._frame(11))
        layout = fig.layout.to_plotly_json()
        titled = [
            key
            for key, value in layout.items()
            if key.startswith("xaxis") and (value.get("title") or {}).get("text")
        ]
        assert len(titled) == 1
