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
    load_evaluation_dir,
    split_layer2_by_metric,
    summarize_runs,
)
from soda_mmqc.reporting.styles import LAYER1_ORDER, LAYER2_BINARY_ORDER

DEMO_DIR = Path(__file__).resolve().parents[1] / "tests/fixtures/flat_eval_demo"
FIXTURES = Path(__file__).resolve().parents[1] / "tests/fixtures/reporting_snapshots"

# EVAL_ROOT used to point at soda_mmqc/data/evaluation, and these tests read
# whatever evaluation runs happened to be committed: they asserted a corpus,
# not the reporting code, and broke when the corpus was regenerated or
# removed. FIXTURES is a committed snapshot in the same on-disk format --
# two models, three arms, three records each -- so the assertions below
# describe the fixture and stay true whatever the real corpus holds.


@pytest.fixture(autouse=True)
def _use_fixture_corpus(monkeypatch):
    """Point the loader at the committed snapshot, not the live corpus."""
    monkeypatch.setattr("soda_mmqc.reporting.load.EVALUATION_DIR", FIXTURES)


class TestLoadFlatRuns:
    def test_load_micrograph_models_and_arms(self):
        runs = load_evaluation_dir(
            "fig-checklist",
            "micrograph-scale-bar",
            models=["model-a", "model-b"],
        )
        assert len(runs) == 6
        models = {run.model for run in runs}
        arms = {run.arm for run in runs}
        assert models == {"model-a", "model-b"}
        assert arms == {"pinned", "micrograph-scale-bar@v2", "micrograph-scale-bar@v3"}
        for run in runs:
            assert len(run.records) == 3

    def test_model_contrast_filter(self):
        runs = load_evaluation_dir(
            "fig-checklist",
            "micrograph-scale-bar",
            models=["model-a", "model-b"],
            arms="pinned",
        )
        assert len(runs) == 2
        assert {run.model for run in runs} == {
            "model-a",
            "model-b",
        }


class TestAggregateRun:
    def test_pools_instances_not_doc_means(self):
        runs = load_evaluation_dir(
            "fig-checklist",
            "micrograph-scale-bar",
            models="model-a",
            arms="pinned",
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
        assert total_instances > len(runs[0].records)
        # Every instance must land in exactly one layer-2 bucket. Summing the
        # buckets (rather than TN + TP alone) is what makes this a statement
        # about pooling: the old form silently assumed the data contained no
        # FP or FN, which held for one corpus and nothing more.
        assert sum(micrograph.layer2_counts.values()) == total_instances

    def test_summarize_runs_indexing(self):
        runs = load_evaluation_dir(
            "fig-checklist",
            "micrograph-scale-bar",
            models=["model-a", "model-b"],
            arms="pinned",
        )
        summaries = summarize_runs(runs)
        assert {(s.model, s.arm) for s in summaries.values()} == {
            ("model-a", "pinned"),
            ("model-b", "pinned"),
        }
        assert all(ref.replicate == 0 for ref in summaries)
        assert len(summaries.for_model("model-b")) == 1


class TestTables:
    @pytest.fixture
    def arm1_summary(self):
        runs = load_evaluation_dir(
            "fig-checklist",
            "micrograph-scale-bar",
            models="model-a",
            arms="pinned",
        )
        return aggregate_run(runs[0])

    @pytest.fixture
    def arm2_summary(self):
        runs = load_evaluation_dir(
            "fig-checklist",
            "micrograph-scale-bar",
            models="model-a",
            arms="micrograph-scale-bar@v2",
        )
        return aggregate_run(runs[0])

    def test_split_layer2_by_metric(self, arm1_summary):
        binary_df, graded_df = split_layer2_by_metric(arm1_summary)
        assert "micrograph" in binary_df["field"].tolist()
        assert "from_the_caption" in graded_df["field"].tolist()
        micrograph_row = binary_df.loc[binary_df["field"] == "micrograph"].iloc[0]
        profile = arm1_summary.manifest.profile_for("outputs[].micrograph")
        assert profile is not None
        assert profile.matching_metric == MatchingMetric.BINARY_POLARITY
        assert micrograph_row["TP"] + micrograph_row["TN"] > 0

    def test_layer_counts_by_property(self, arm1_summary):
        frame = layer_counts_by_property(
            arm1_summary, LAYER1_ORDER, "layer1_counts"
        )
        assert list(frame.columns) == [
            "leaf_property",
            "field",
            *LAYER1_ORDER,
        ]

    def test_second_arm_has_layer1_outliers(self, arm2_summary):
        frame = layer1_instance_table(arm2_summary)
        assert not frame.empty
        assert "spurious_applicable" in frame["layer1"].unique()
        assert "scale_bar" in "".join(frame["leaf_property"].tolist())
        assert frame["path"].str.fullmatch(r"outputs\[\d+\]").all()
        assert "outputs[]" not in frame["leaf_property"].iloc[0]
        assert frame["source"].str.contains("/content/").all()

    def test_layer2_errors_empty_on_perfect_baseline_arm(self, arm1_summary):
        frame = layer2_instance_table(arm1_summary)
        assert frame.empty or frame["layer2"].isin({"FP", "FN", "mismatch"}).all()

    def test_layer_s_issues_table_columns(self, arm1_summary):
        frame = layer_s_issues_table(arm1_summary)
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
        from soda_mmqc.reporting.load import FlatRecord, FlatRun, RunRef
        from soda_mmqc.core.eval_manifest import load_eval_manifest

        manifest = load_eval_manifest(DEMO_DIR / "manifest.json")
        record = FlatRecord(
            doc_id="demo",
            metadata={},
            analysis=result.to_dict(),
        )
        run = FlatRun(
            ref=RunRef(
                checklist="demo",
                check="demo",
                model="demo",
                arm="pinned",
                replicate=0,
            ),
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
