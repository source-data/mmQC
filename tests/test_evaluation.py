"""Tests for flat evaluation orchestrator (phase 5)."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from soda_mmqc.core.eval_manifest import load_eval_manifest, parse_eval_manifest
from soda_mmqc.core.property_rollup import rollup_by_property
from soda_mmqc.core.evaluation import FlatEvaluator

FIXTURES = Path(__file__).parent / "fixtures"
SCHEMA = json.loads((FIXTURES / "toy_eval_schema.json").read_text())
BASELINE_GOLD = json.loads((FIXTURES / "toy_eval_gold_baseline.json").read_text())
MANIFEST = load_eval_manifest(FIXTURES / "eval_manifest_toy.json")


def _mock_embedder(texts):
    import torch

    dim = 8
    return torch.stack([torch.ones(dim) for _ in texts])


@pytest.fixture
def evaluator() -> FlatEvaluator:
    return FlatEvaluator(SCHEMA, MANIFEST, embedder=_mock_embedder)


def _instance(result, path: str) -> dict:
    for instance in result.instances:
        if instance.path == path:
            return instance.to_dict()
    raise KeyError(path)


def _property_summary(result, leaf_property: str, manifest) -> dict:
    """Roll the result's instances up for one property.

    The evaluator no longer produces this itself: rolling up needs the
    manifest's thresholds, which are tunable, so it happens at read time
    in `core.property_rollup` rather than being stored at scoring time.
    """
    rollup = rollup_by_property(
        [i.to_dict() for i in result.instances], manifest
    )[leaf_property]
    return {
        "mean_score": rollup.mean_score,
        "n_scored": rollup.n_scored,
        "layer1_counts": rollup.layer1_counts,
        "layer2_counts": rollup.layer2_counts,
    }


class TestExampleA:
    """Toy example A — perfect baseline."""

    def test_perfect_match(self, evaluator: FlatEvaluator):
        result = evaluator.evaluate(BASELINE_GOLD, copy.deepcopy(BASELINE_GOLD))

        assert _instance(result, "item.label") == {
            "path": "item.label",
            "leaf_property": "item.label",
            "exp_value": "Panel A",
            "pred_value": "Panel A",
            "score": 1.0,
            "layer1": "correct_applicable",
            "layer2": "match",
        }
        assert _instance(result, "item.status")["layer1"] == "correct_NA"
        assert _instance(result, "panels[0].status")["layer2"] == "TP"
        assert _instance(result, "panels[1].status")["layer1"] == "correct_NA"

        assert result.by_list["panels"]["row_counts"] == {
            "correct_row": 2,
            "missing_row": 0,
            "spurious_row": 0,
        }
        assert len(result.by_list["panels"]["rows"]) == 2
        assert all(
            row["structural"] == "correct_row"
            for row in result.by_list["panels"]["rows"]
        )

        assert _property_summary(result, "item.label", evaluator.manifest) == {
            "mean_score": 1.0,
            "n_scored": 1,
            "layer1_counts": {"correct_applicable": 1},
            "layer2_counts": {"match": 1},
        }
        # Correctly not applicable, so nothing was eligible to score. This
        # asserted `mean_score: 0.0` before -- indistinguishable from a
        # model that answered and got it wrong, and a false zero in every
        # mean taken over this property.
        assert _property_summary(result, "item.status", evaluator.manifest) == {
            "mean_score": None,
            "n_scored": 0,
            "layer1_counts": {"correct_NA": 1},
            "layer2_counts": {},
        }
        assert _property_summary(result, "panels[].status", evaluator.manifest) == {
            "mean_score": 1.0,
            "n_scored": 1,
            "layer1_counts": {"correct_applicable": 1, "correct_NA": 1},
            "layer2_counts": {"TP": 1},
        }
        assert _property_summary(result, "tags", evaluator.manifest)["mean_score"] == 1.0
        assert _property_summary(result, "tags", evaluator.manifest)["layer1_counts"] == {}
        assert result.aggregate_layer1_counts() == {
            "correct_applicable": 6,
            "correct_NA": 2,
        }
        assert result.aggregate_layer2_counts() == {"match": 5, "TP": 1}


class TestExampleB:
    def test_b1_extra_tag_element(self, evaluator: FlatEvaluator):
        pred = copy.deepcopy(BASELINE_GOLD)
        pred["tags"] = ["alpha", "beta", "gamma"]
        result = evaluator.evaluate(BASELINE_GOLD, pred)
        assert _instance(result, "tags")["score"] == pytest.approx(2 / 3)
        assert _property_summary(result, "tags", evaluator.manifest)["mean_score"] == pytest.approx(2 / 3)

    def test_b3_total_mismatch(self, evaluator: FlatEvaluator):
        gold = copy.deepcopy(BASELINE_GOLD)
        pred = copy.deepcopy(BASELINE_GOLD)
        gold["tags"] = ["alpha"]
        pred["tags"] = ["omega"]
        result = evaluator.evaluate(gold, pred)
        assert _instance(result, "tags")["score"] == 0.0


class TestExampleC:
    def test_c1_wrong_item_label(self, evaluator: FlatEvaluator):
        pred = copy.deepcopy(BASELINE_GOLD)
        pred["item"]["label"] = "Panel B"
        result = evaluator.evaluate(BASELINE_GOLD, pred)
        inst = _instance(result, "item.label")
        assert inst["score"] == 0.0
        assert inst["layer2"] == "mismatch"
        assert _property_summary(result, "item.label", evaluator.manifest)["layer2_counts"] == {
            "mismatch": 1
        }

    def test_c2_spurious_status(self, evaluator: FlatEvaluator):
        pred = copy.deepcopy(BASELINE_GOLD)
        pred["item"]["status"] = "yes"
        result = evaluator.evaluate(BASELINE_GOLD, pred)
        assert _instance(result, "item.status")["layer1"] == "spurious_applicable"

    def test_c3_missing_item_label(self, evaluator: FlatEvaluator):
        pred = copy.deepcopy(BASELINE_GOLD)
        del pred["item"]["label"]
        result = evaluator.evaluate(BASELINE_GOLD, pred)
        assert _instance(result, "item.label")["layer1"] == "withheld_applicable"

    def test_c4_wrong_meta_year(self, evaluator: FlatEvaluator):
        pred = copy.deepcopy(BASELINE_GOLD)
        pred["item"]["meta"]["year"] = 1900
        result = evaluator.evaluate(BASELINE_GOLD, pred)
        assert _instance(result, "item.meta.year")["score"] == 0.0
        assert _instance(result, "item.meta.author")["score"] == 1.0


class TestExampleD:
    def test_d2_reordered_panels(self, evaluator: FlatEvaluator):
        pred = copy.deepcopy(BASELINE_GOLD)
        pred["panels"] = [
            {"id": 9, "label": "Fig 2", "status": "", "caption": "Panel two"},
            {"id": 8, "label": "Fig 1", "status": "no", "caption": "Panel one"},
        ]
        result = evaluator.evaluate(BASELINE_GOLD, pred)

        assert result.by_list["panels"]["row_counts"]["correct_row"] == 2
        assert _instance(result, "panels[0].status")["layer2"] == "FN"
        assert _instance(result, "panels[0].id")["score"] == 0.0
        assert _instance(result, "panels[1].label")["layer2"] == "match"
        assert _property_summary(result, "panels[].status", evaluator.manifest)["mean_score"] == pytest.approx(
            0.0
        )

    def test_d3_spurious_panel_status(self, evaluator: FlatEvaluator):
        pred = copy.deepcopy(BASELINE_GOLD)
        pred["panels"][1]["status"] = "yes"
        result = evaluator.evaluate(BASELINE_GOLD, pred)
        assert _instance(result, "panels[1].status")["layer1"] == "spurious_applicable"

    def test_d4_missing_panel(self, evaluator: FlatEvaluator):
        pred = copy.deepcopy(BASELINE_GOLD)
        pred["panels"] = [
            {"id": 1, "label": "Fig 1", "status": "yes", "caption": "Panel one"},
        ]
        result = evaluator.evaluate(BASELINE_GOLD, pred)

        assert result.by_list["panels"]["row_counts"] == {
            "correct_row": 1,
            "missing_row": 1,
            "spurious_row": 0,
        }
        assert _instance(result, "panels[1].label")["layer1"] == "withheld_applicable"
        assert _instance(result, "panels[1].status")["layer1"] == "correct_NA"

    def test_d5_extra_panel(self, evaluator: FlatEvaluator):
        pred = copy.deepcopy(BASELINE_GOLD)
        pred["panels"] = BASELINE_GOLD["panels"] + [
            {"id": 99, "label": "Fig 99", "status": "no", "caption": ""},
        ]
        result = evaluator.evaluate(BASELINE_GOLD, pred)

        assert result.by_list["panels"]["row_counts"] == {
            "correct_row": 2,
            "missing_row": 0,
            "spurious_row": 1,
        }
        assert _instance(result, "panels[0].label")["score"] == 1.0
        assert _instance(result, "panels[1].label")["score"] == 1.0


class TestGoldenSnapshots:
    """Golden JSON snapshots for selected toy examples."""

    @pytest.mark.parametrize(
        "snapshot_name,pred_mutator",
        [
            ("example_a", lambda pred: pred),
            (
                "example_d2",
                lambda pred: pred.update(
                    {
                        "panels": [
                            {
                                "id": 9,
                                "label": "Fig 2",
                                "status": "",
                                "caption": "Panel two",
                            },
                            {
                                "id": 8,
                                "label": "Fig 1",
                                "status": "no",
                                "caption": "Panel one",
                            },
                        ]
                    }
                )
                or pred,
            ),
        ],
    )
    def test_snapshot_by_property_and_by_list(
        self,
        evaluator: FlatEvaluator,
        snapshot_name: str,
        pred_mutator,
    ):
        pred = copy.deepcopy(BASELINE_GOLD)
        pred_mutator(pred)
        result = evaluator.evaluate(BASELINE_GOLD, pred)

        # The snapshot pins what the evaluator *measured*, which is what
        # analysis.json stores. Rollups are derived at read time from the
        # manifest in force then, so pinning them here would pin a
        # threshold-dependent number into a fixture about measurement.
        actual = result.to_dict()

        snapshot_path = FIXTURES / "evaluation_snapshots" / f"{snapshot_name}.json"
        if not snapshot_path.exists():
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(
                json.dumps(actual, indent=2) + "\n", encoding="utf-8"
            )
            pytest.fail(f"Wrote new snapshot at {snapshot_path}; re-run to verify")

        expected = json.loads(snapshot_path.read_text(encoding="utf-8"))
        assert actual == expected


class TestExtendedPrimitiveCompareModes:
    @pytest.fixture
    def flags_evaluator(self) -> FlatEvaluator:
        schema = {
            "type": "object",
            "required": ["flags"],
            "properties": {
                "flags": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["yes", "no"]},
                }
            },
        }
        manifest = parse_eval_manifest(
            {
                "checklist": "flags",
                "fields": {
                    "flags": {"primitive_list_compare": "positional"},
                },
            }
        )
        return FlatEvaluator(schema, manifest)

    def test_positional_via_manifest(self, flags_evaluator: FlatEvaluator):
        gold = {"flags": ["yes", "no"]}
        pred = {"flags": ["no", "yes"]}
        result = flags_evaluator.evaluate(gold, pred)
        assert _instance(result, "flags")["score"] == 0.0

    @pytest.fixture
    def captions_evaluator(self) -> FlatEvaluator:
        schema = {
            "type": "object",
            "required": ["captions"],
            "properties": {
                "captions": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
        }
        manifest = parse_eval_manifest(
            {
                "checklist": "captions",
                "fields": {
                    "captions": {
                        "primitive_list_compare": "join_string",
                        "matching_metric": "graded_string",
                        "string_compare": "exact",
                        "match_threshold": 1.0,
                    }
                },
            }
        )
        return FlatEvaluator(schema, manifest)

    def test_join_string_via_manifest(self, captions_evaluator: FlatEvaluator):
        gold = {"captions": ["arrow", "scale bar"]}
        pred = {"captions": ["scale bar", "arrow"]}
        result = captions_evaluator.evaluate(gold, pred)
        assert _instance(result, "captions")["score"] == 0.0
