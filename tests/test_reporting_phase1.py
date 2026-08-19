"""Phase 1 tests for soda_mmqc.reporting."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from soda_mmqc.core.eval_manifest import MatchingMetric
from soda_mmqc.core.evaluation import FlatEvaluator
from soda_mmqc.reporting import (
    aggregate_run,
    layer1_instance_table,
    layer2_instance_table,
    layer_counts_by_property,
    layer_s_issues_table,
    load_flat_runs,
    normalize_prompt_name,
    split_layer2_by_metric,
    summarize_runs,
)
from soda_mmqc.reporting.styles import LAYER1_ORDER, LAYER2_BINARY_ORDER

EVAL_ROOT = (
    Path(__file__).resolve().parents[1]
    / "soda_mmqc/data/evaluation/fig-checklist/micrograph-scale-bar"
)
DEMO_DIR = Path(__file__).resolve().parents[1] / "notebooks/fixtures/flat-eval-demo"
FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/reporting_snapshots"


class TestNormalizePromptName:
    def test_local_prompt_key(self):
        assert (
            normalize_prompt_name("micrograph-scale-bar::local::prompt.2")
            == "prompt.2"
        )

    def test_already_normalized(self):
        assert normalize_prompt_name("prompt.1") == "prompt.1"


class TestLoadFlatRuns:
    def test_load_micrograph_models_and_prompts(self):
        runs = load_flat_runs(
            "fig-checklist",
            "micrograph-scale-bar",
            models=["gpt-5-mini-2025-08-07", "gpt-5"],
        )
        assert len(runs) == 6
        models = {run.model for run in runs}
        prompts = {run.prompt for run in runs}
        assert models == {"gpt-5-mini-2025-08-07", "gpt-5"}
        assert prompts == {"prompt.1", "prompt.2", "prompt.3"}
        for run in runs:
            assert len(run.records) == 14

    def test_model_contrast_filter(self):
        runs = load_flat_runs(
            "fig-checklist",
            "micrograph-scale-bar",
            models=["gpt-5-mini-2025-08-07", "gpt-5"],
            prompts="prompt.1",
        )
        assert len(runs) == 2
        assert {run.model for run in runs} == {
            "gpt-5-mini-2025-08-07",
            "gpt-5",
        }


class TestAggregateRun:
    def test_pools_instances_not_doc_means(self):
        runs = load_flat_runs(
            "fig-checklist",
            "micrograph-scale-bar",
            models="gpt-5-mini-2025-08-07",
            prompts="prompt.1",
        )
        summary = aggregate_run(runs[0])
        micrograph = summary.by_property["outputs[].micrograph"]
        total_instances = sum(
            len(
                [
                    inst
                    for inst in record.analysis.get("instances", [])
                    if inst.get("leaf_property") == "outputs[].micrograph"
                ]
            )
            for record in runs[0].records
        )
        assert total_instances > 14
        assert micrograph.layer2_counts.get("TN", 0) + micrograph.layer2_counts.get(
            "TP", 0
        ) == total_instances

    def test_summarize_runs_indexing(self):
        runs = load_flat_runs(
            "fig-checklist",
            "micrograph-scale-bar",
            models=["gpt-5-mini-2025-08-07", "gpt-5"],
            prompts="prompt.1",
        )
        summaries = summarize_runs(runs)
        assert ("gpt-5-mini-2025-08-07", "prompt.1") in summaries
        assert ("gpt-5", "prompt.1") in summaries
        assert len(summaries.for_model("gpt-5")) == 1


class TestTables:
    @pytest.fixture
    def prompt1_summary(self):
        runs = load_flat_runs(
            "fig-checklist",
            "micrograph-scale-bar",
            models="gpt-5-mini-2025-08-07",
            prompts="prompt.1",
        )
        return aggregate_run(runs[0])

    @pytest.fixture
    def prompt2_summary(self):
        runs = load_flat_runs(
            "fig-checklist",
            "micrograph-scale-bar",
            models="gpt-5-mini-2025-08-07",
            prompts="prompt.2",
        )
        return aggregate_run(runs[0])

    def test_split_layer2_by_metric(self, prompt1_summary):
        binary_df, graded_df = split_layer2_by_metric(prompt1_summary)
        assert "micrograph" in binary_df["field"].tolist()
        assert "from_the_caption" in graded_df["field"].tolist()
        micrograph_row = binary_df.loc[binary_df["field"] == "micrograph"].iloc[0]
        profile = prompt1_summary.manifest.profile_for("outputs[].micrograph")
        assert profile is not None
        assert profile.matching_metric == MatchingMetric.BINARY_POLARITY
        assert micrograph_row["TP"] + micrograph_row["TN"] > 0

    def test_split_layer2_includes_multiclass_with_graded(self):
        runs = load_flat_runs(
            "fig-checklist",
            "stat-significance-level",
            models="gpt-5.4",
            prompts="prompt.2",
        )
        assert runs
        summary = aggregate_run(runs[0])
        profile = summary.manifest.profile_for("outputs[].decision")
        assert profile is not None
        assert profile.matching_metric == MatchingMetric.MULTICLASS
        _, graded_df = split_layer2_by_metric(summary)
        assert "decision" in graded_df["field"].tolist()
        decision_row = graded_df.loc[graded_df["field"] == "decision"].iloc[0]
        assert decision_row["match"] + decision_row["mismatch"] > 0

    def test_layer_counts_by_property(self, prompt1_summary):
        frame = layer_counts_by_property(
            prompt1_summary, LAYER1_ORDER, "layer1_counts"
        )
        assert list(frame.columns) == [
            "leaf_property",
            "field",
            *LAYER1_ORDER,
        ]

    def test_prompt2_has_layer1_outliers(self, prompt2_summary):
        frame = layer1_instance_table(prompt2_summary)
        assert not frame.empty
        assert "spurious_applicable" in frame["layer1"].unique()
        assert "scale_bar" in "".join(frame["leaf_property"].tolist())
        assert frame["path"].str.fullmatch(r"outputs\[\d+\]").all()
        assert "outputs[]" not in frame["leaf_property"].iloc[0]
        assert frame["source"].str.contains("/content/").all()

    def test_layer2_errors_empty_on_perfect_prompt1(self, prompt1_summary):
        frame = layer2_instance_table(prompt1_summary)
        assert frame.empty or frame["layer2"].isin({"FP", "FN", "mismatch"}).all()

    def test_layer_s_issues_table_columns(self, prompt1_summary):
        frame = layer_s_issues_table(prompt1_summary)
        assert list(frame.columns) == [
            "source",
            "list_key",
            "structural",
            "location",
            "alignment",
            "context_path",
            "gold_index",
            "pred_index",
        ]


class TestCollatedLayerSIssues:
    def test_demo_missing_row_has_location(self):
        evaluator = FlatEvaluator.from_paths(
            str(DEMO_DIR / "schema.json"),
            str(DEMO_DIR / "manifest.json"),
        )
        gold = json.loads((DEMO_DIR / "gold.json").read_text())
        pred = json.loads((DEMO_DIR / "pred.json").read_text())
        result = evaluator.evaluate(gold, pred)

        from soda_mmqc.reporting.aggregate import RunSummary
        from soda_mmqc.reporting.load import FlatRecord, FlatRun
        from soda_mmqc.core.eval_manifest import load_eval_manifest

        manifest = load_eval_manifest(DEMO_DIR / "manifest.json")
        record = FlatRecord(
            doc_id="demo",
            metadata={},
            analysis=result.to_dict(),
        )
        run = FlatRun(
            checklist="demo",
            check="demo",
            model="demo",
            prompt="prompt.1",
            records=(record,),
            manifest=manifest,
        )
        summary = aggregate_run(run)
        issues = layer_s_issues_table(summary)
        if issues.empty:
            missing = result.layer_s_issues("papers.figures.outputs")["missing"]
            assert missing
            row = missing[0]
            assert row["ancestor_gold"]
        else:
            assert (issues["structural"] == "missing_row").any()
            assert issues["location"].str.len().gt(0).any()
