"""Phase 2b tests for example context drill-down."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from unittest.mock import patch

from soda_mmqc.core.evaluation import FlatEvaluator
from soda_mmqc.reporting.aggregate import aggregate_run
from soda_mmqc.reporting.context import inspect_instance, inspect_layer_s_row, inspect_source
from soda_mmqc.reporting.display import _display_figure_image, show_instance_context
from soda_mmqc.reporting.load import (
    FlatRecord,
    FlatRun,
    RunRef,
    load_evaluation_dir,
    load_record_payloads,
    record_source,
)
from soda_mmqc.reporting.navigate import (
    NavigationError,
    get_at_steps,
    layer_s_row_steps,
    parent_row_steps,
    instance_navigation_path,
    instance_object_path,
    path_string_to_steps,
)


# The committed snapshot these tests read instead of soda_mmqc/data/evaluation.
# Reading the live corpus meant asserting whichever evaluation runs happened to
# be committed -- a statement about data, not about the reporting code -- so the
# tests broke whenever that corpus was regenerated or removed.
FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/reporting_snapshots"


@pytest.fixture(autouse=True)
def _use_fixture_corpus(monkeypatch):
    """Point the loader at the committed snapshot, not the live corpus."""
    monkeypatch.setattr("soda_mmqc.reporting.load.EVALUATION_DIR", FIXTURES)


DEMO_DIR = Path(__file__).resolve().parents[1] / "tests/fixtures/flat_eval_demo"
MICROGRAPH = "micrograph-scale-bar"
MODEL_A = "model-a"
FIGURE1_SOURCE = "10.1038_s44318-026-00715-1/content/1"
# A record whose `scale_bar_on_image` is actually populated. Asserting a leaf
# resolves to "" proves little -- an empty string is also what a failed lookup
# returns -- so the leaf-addressing tests below use a non-empty value.
FIGURE3_SOURCE = "10.1038_s44318-026-00715-1/content/3"


class TestNavigate:
    def test_instance_object_path_strips_leaf(self):
        assert instance_object_path("outputs[7].scale_bar_on_image") == "outputs[7]"
        assert instance_object_path("outputs[7]") == "outputs[7]"

    def test_instance_navigation_path_recombines(self):
        assert instance_navigation_path("outputs[7]", "scale_bar_on_image") == (
            "outputs[7].scale_bar_on_image"
        )
        assert path_string_to_steps(
            instance_navigation_path("outputs[7]", "scale_bar_on_image")
        ) == ("outputs", 7, "scale_bar_on_image")

    def test_path_string_to_steps_leaf(self):
        assert path_string_to_steps("outputs[7].scale_bar_on_image") == (
            "outputs",
            7,
            "scale_bar_on_image",
        )

    def test_path_string_to_steps_collated_context(self):
        assert path_string_to_steps("papers[0].figures[2].outputs") == (
            "papers",
            0,
            "figures",
            2,
            "outputs",
        )

    def test_get_at_steps_flat_row(self):
        doc = {"outputs": [{"panel_label": "A", "micrograph": "no"}]}
        row = get_at_steps(doc, ["outputs", 0])
        assert row == {"panel_label": "A", "micrograph": "no"}
        assert get_at_steps(doc, ["outputs", 0, "micrograph"]) == "no"

    def test_get_at_steps_raises_with_context(self):
        doc = {"outputs": []}
        with pytest.raises(NavigationError, match="doc_id='fig-1'"):
            get_at_steps(doc, ["outputs", 3], doc_id="fig-1", side="gold")

    def test_parent_row_steps(self):
        assert parent_row_steps(["outputs", 2, "micrograph"]) == ("outputs", 2)
        assert parent_row_steps(["outputs", 2]) is None

    def test_layer_s_row_steps_simple_context(self):
        assert layer_s_row_steps(list_key="outputs", context_path="outputs", index=3) == (
            "outputs",
            3,
        )


class TestLoadRecordPayloads:
    def test_lazy_load_micrograph_payloads(self):
        leaf = (
            FIXTURES / "fig-checklist" / MICROGRAPH / MODEL_A
            / "micrograph-scale-bar@v2" / "rep-00"
        )
        expected, model = load_record_payloads(leaf, FIGURE1_SOURCE)
        assert "outputs" in expected
        assert "outputs" in model

    def test_load_flat_runs_without_payloads_by_default(self):
        runs = load_evaluation_dir(
            "fig-checklist",
            MICROGRAPH,
            models=MODEL_A,
            arms="micrograph-scale-bar@v2",
        )
        record = runs[0].records[0]
        assert not record.has_payloads
        assert record_source(record)

    def test_load_flat_runs_with_payloads(self):
        runs = load_evaluation_dir(
            "fig-checklist",
            MICROGRAPH,
            models=MODEL_A,
            arms="micrograph-scale-bar@v2",
            include_payloads=True,
        )
        assert runs[0].records[0].has_payloads


@pytest.fixture
def demo_summary():
    evaluator = FlatEvaluator.from_paths(
        str(DEMO_DIR / "schema.json"),
        str(DEMO_DIR / "manifest.json"),
    )
    gold = json.loads((DEMO_DIR / "gold.json").read_text())
    pred = json.loads((DEMO_DIR / "pred.json").read_text())
    result = evaluator.evaluate(gold, pred)
    record = FlatRecord(
        doc_id="demo-doc",
        metadata={"example_type": "figure", "source": "unused/for/test"},
        analysis=result.to_dict(),
        expected_output=gold,
        model_output=pred,
    )
    run = FlatRun(
        ref=RunRef(
            checklist="fig-checklist",
            check="demo",
            model="test-model",
            arm="pinned",
            replicate=0,
        ),
        records=(record,),
        manifest=evaluator.manifest,
    )
    return aggregate_run(run)


class TestInspectInstance:
    @pytest.fixture
    def summary_p2(self):
        runs = load_evaluation_dir(
            "fig-checklist",
            MICROGRAPH,
            models=MODEL_A,
            arms="micrograph-scale-bar@v2",
        )
        return aggregate_run(runs[0])

    def test_inspect_requires_steps_or_object_path_and_leaf(self, summary_p2):
        with pytest.raises(ValueError, match="either steps or"):
            inspect_instance(
                summary_p2,
                source=FIGURE1_SOURCE,
            )
        with pytest.raises(ValueError, match="not both"):
            inspect_instance(
                summary_p2,
                source=FIGURE1_SOURCE,
                steps=["outputs", 0],
                object_path="outputs[0]",
                leaf="scale_bar_on_image",
            )

    def test_inspect_leaf_via_object_path_and_leaf(self, summary_p2):
        ctx = inspect_instance(
            summary_p2,
            source=FIGURE3_SOURCE,
            object_path="outputs[0]",
            leaf="scale_bar_on_image",
            include_example_assets=False,
        )
        assert ctx.exp_value == "no"
        assert ctx.pred_value == "no"
        assert ctx.steps == ("outputs", 0, "scale_bar_on_image")
        assert ctx.ref.source == FIGURE3_SOURCE

    def test_lazy_payload_inspect_leaf(self, summary_p2):
        ctx = inspect_instance(
            summary_p2,
            source=FIGURE3_SOURCE,
            steps=["outputs", 0, "scale_bar_on_image"],
            include_example_assets=False,
        )
        assert ctx.exp_value == "no"
        assert ctx.pred_value == "no"
        assert ctx.exp_row is not None
        assert ctx.pred_row is not None

    def test_inspect_panel_row(self, summary_p2):
        ctx = inspect_instance(
            summary_p2,
            source=FIGURE1_SOURCE,
            steps=["outputs", 0],
            include_example_assets=False,
        )
        assert ctx.exp_subtree["panel_label"] == "A"
        assert ctx.pred_subtree["panel_label"] == "A"

    def test_figure_preview_when_assets_available(self, summary_p2):
        ctx = inspect_instance(
            summary_p2,
            source=FIGURE1_SOURCE,
            steps=["outputs", 0],
        )
        preview = ctx.example_preview
        assert preview is not None
        assert preview.example_type == "figure"
        assert preview.caption
        assert preview.image_path is not None
        assert preview.image_path.is_file()

    def test_inspect_source_returns_full_payload(self, summary_p2):
        ctx = inspect_source(summary_p2, source=FIGURE1_SOURCE, include_example_assets=False)
        assert ctx.steps == ()
        assert "outputs" in ctx.expected_output
        assert ctx.exp_subtree == ctx.expected_output
        assert ctx.pred_subtree == ctx.model_output


class TestShowInstanceContext:
    @pytest.fixture
    def summary_p2(self):
        runs = load_evaluation_dir(
            "fig-checklist",
            MICROGRAPH,
            models=MODEL_A,
            arms="micrograph-scale-bar@v2",
        )
        return aggregate_run(runs[0])

    def test_requires_source_with_summary(self, summary_p2):
        with pytest.raises(ValueError, match="source is required"):
            show_instance_context(summary_p2)

    def test_zoomable_figure_preview(self, summary_p2):
        with patch(
            "soda_mmqc.reporting.display._display_figure_image"
        ) as mock_image, patch(
            "soda_mmqc.reporting.display._display_markdown"
        ), patch(
            "soda_mmqc.reporting.display._display_side_by_side"
        ):
            show_instance_context(
                summary_p2,
                source=FIGURE1_SOURCE,
                figure_height=360,
                figure_width=480,
            )
        mock_image.assert_called_once()
        assert mock_image.call_args.kwargs == {
            "height": 360,
            "width": 480,
            "zoomable": True,
        }


class TestInspectLayerS:
    def test_missing_row_gold_only(self, demo_summary):
        ctx = inspect_layer_s_row(
            demo_summary,
            source="unused/for/test",
            list_key="papers.figures.outputs",
            context_path="papers[0].figures[2].outputs",
            gold_index=1,
            structural="missing_row",
            include_example_assets=False,
        )
        assert ctx.pred_missing is True
        assert ctx.pred_subtree is None
        assert ctx.exp_subtree["label"] == "3B"

    def test_spurious_row_pred_side(self, demo_summary):
        ctx = inspect_layer_s_row(
            demo_summary,
            source="unused/for/test",
            list_key="papers.figures.outputs",
            context_path="papers[0].figures[2].outputs",
            pred_index=1,
            structural="spurious_row",
            include_example_assets=False,
        )
        assert ctx.pred_missing is False
        assert ctx.pred_subtree["label"] == "3C"
