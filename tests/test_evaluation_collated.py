"""Collated evaluation tests (phase 5.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from soda_mmqc.core.eval_manifest import load_eval_manifest
from soda_mmqc.core.evaluation import FlatEvaluator, format_ancestor_context

FIXTURES = Path(__file__).parent / "fixtures"
PANEL_SCHEMA = json.loads(
    (FIXTURES / "panel_segmentation_schema.json").read_text()
)
COLLATED_GOLD = json.loads((FIXTURES / "collated_eval_gold.json").read_text())
COLLATED_PRED = json.loads((FIXTURES / "collated_eval_pred.json").read_text())
COLLATED_MANIFEST = load_eval_manifest(FIXTURES / "eval_manifest_collated.json")


@pytest.fixture
def collated_evaluator() -> FlatEvaluator:
    return FlatEvaluator(PANEL_SCHEMA, COLLATED_MANIFEST)


def _instance(result, path: str):
    for instance in result.instances:
        if instance.path == path:
            return instance
    raise KeyError(path)


class TestCollatedEvaluation:
    def test_perfect_first_figure(self, collated_evaluator: FlatEvaluator):
        pred = json.loads(json.dumps(COLLATED_GOLD))
        result = collated_evaluator.evaluate(COLLATED_GOLD, pred)
        assert _instance(result, "figures[0].panels[0].label").score == 1.0
        assert "figures.panels" in result.by_list
        assert "figures" not in result.by_list

    def test_reordered_panels_in_second_figure(self, collated_evaluator: FlatEvaluator):
        result = collated_evaluator.evaluate(COLLATED_GOLD, COLLATED_PRED)
        assert _instance(result, "figures[1].panels[0].is_micrograph").layer2 == "FN"
        assert result.by_list["figures.panels"]["row_counts"]["correct_row"] == 4

    def test_layer_s_issues_include_context(self, collated_evaluator: FlatEvaluator):
        result = collated_evaluator.evaluate(COLLATED_GOLD, COLLATED_PRED)
        issues = result.layer_s_issues("figures.panels")
        assert issues["missing"] == []
        assert issues["spurious"] == []
        first_row = result.by_list["figures.panels"]["rows"][0]
        assert first_row["context_path"] == "figures[0].panels"
        assert first_row["gold_alignment"] == "1A"
        assert first_row["pred_alignment"] == "1A"
        assert first_row["ancestor_gold"] == [
            {
                "path": "figures[0]",
                "fields": {"figure_label": "Figure 1"},
            }
        ]
        assert first_row["ancestor_pred"] == [
            {
                "path": "figures[0]",
                "fields": {"figure_label": "Figure 1"},
            }
        ]

    def test_demo_collation_ancestor_paths(self):
        demo_dir = Path(__file__).resolve().parents[1] / "tests/fixtures/flat_eval_demo"
        evaluator = FlatEvaluator.from_paths(
            str(demo_dir / "schema.json"),
            str(demo_dir / "manifest.json"),
        )
        gold = json.loads((demo_dir / "gold.json").read_text())
        pred = json.loads((demo_dir / "pred.json").read_text())
        missing = evaluator.evaluate(gold, pred).layer_s_issues(
            "papers.figures.outputs"
        )["missing"][0]
        assert missing["ancestor_gold"] == [
            {"path": "papers[0]", "fields": {"paper_id": "smith2024"}},
            {
                "path": "papers[0].figures[2]",
                "fields": {"figure_label": "Figure 3"},
            },
        ]
        assert missing["gold_alignment"] == "3B"
        assert "smith2024" in format_ancestor_context(missing["ancestor_gold"])
        assert "Figure 3" in format_ancestor_context(missing["ancestor_gold"])

    def test_toy_manifest_rejected_for_collated_layout(self):
        toy_manifest = load_eval_manifest(FIXTURES / "eval_manifest_toy.json")
        evaluator = FlatEvaluator(PANEL_SCHEMA, toy_manifest)
        with pytest.raises(ValueError, match="missing keys"):
            evaluator.evaluate(COLLATED_GOLD, COLLATED_PRED)
