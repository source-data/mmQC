"""Tests for layer S structural reporting (phase 4.4)."""

from __future__ import annotations

from pathlib import Path


from soda_mmqc.core.eval_manifest import load_eval_manifest
from soda_mmqc.core.object_list_pairing import align_object_rows
from soda_mmqc.core.structural_reporting import (
    StructuralOutcome,
    build_by_list,
)

FIXTURES = Path(__file__).parent / "fixtures"
TOY_MANIFEST = load_eval_manifest(FIXTURES / "eval_manifest_toy.json")

BASELINE_GOLD_PANELS = [
    {"id": 1, "label": "Fig 1", "status": "yes"},
    {"id": 2, "label": "Fig 2", "status": ""},
]


def _by_list(gold_rows, pred_rows):
    pairing = align_object_rows(
        gold_rows,
        pred_rows,
        list_name="panels",
        manifest=TOY_MANIFEST,
    )
    return build_by_list(
        pairing,
        n_gold=len(gold_rows),
        n_pred=len(pred_rows),
    )


class TestBuildByList:
    def test_a_perfect_panels(self):
        result = _by_list(BASELINE_GOLD_PANELS, BASELINE_GOLD_PANELS)
        assert result.row_counts.correct_row == 2
        assert result.row_counts.missing_row == 0
        assert result.row_counts.spurious_row == 0
        assert len(result.rows) == 2
        assert all(r.structural is StructuralOutcome.CORRECT_ROW for r in result.rows)
        assert result.rows[0].gold_index == 0
        assert result.rows[0].pred_index == 0
        assert result.rows[0].similarity == 1.0

    def test_d2_reordered_rows(self):
        pred = [
            {"id": 9, "label": "Fig 2", "status": ""},
            {"id": 8, "label": "Fig 1", "status": "no"},
        ]
        result = _by_list(BASELINE_GOLD_PANELS, pred)
        assert result.row_counts.correct_row == 2
        assert result.row_counts.missing_row == 0
        assert result.row_counts.spurious_row == 0

        by_gold = {
            row.gold_index: row
            for row in result.rows
            if row.structural is StructuralOutcome.CORRECT_ROW
        }
        assert by_gold[0].pred_index == 1
        assert by_gold[0].similarity == 1.0
        assert by_gold[1].pred_index == 0
        assert by_gold[1].similarity == 1.0

    def test_d4_missing_panel(self):
        pred = [{"id": 1, "label": "Fig 1", "status": "yes"}]
        result = _by_list(BASELINE_GOLD_PANELS, pred)
        assert result.row_counts.correct_row == 1
        assert result.row_counts.missing_row == 1
        assert result.row_counts.spurious_row == 0

        correct = [r for r in result.rows if r.structural is StructuralOutcome.CORRECT_ROW]
        missing = [r for r in result.rows if r.structural is StructuralOutcome.MISSING_ROW]
        assert len(correct) == 1
        assert correct[0].gold_index == 0
        assert correct[0].pred_index == 0
        assert len(missing) == 1
        assert missing[0].gold_index == 1
        assert missing[0].pred_index is None
        assert missing[0].similarity is None

    def test_d5_extra_panel(self):
        pred = BASELINE_GOLD_PANELS + [
            {"id": 99, "label": "Fig 99", "status": "no"},
        ]
        result = _by_list(BASELINE_GOLD_PANELS, pred)
        assert result.row_counts.correct_row == 2
        assert result.row_counts.missing_row == 0
        assert result.row_counts.spurious_row == 1

        spurious = [r for r in result.rows if r.structural is StructuralOutcome.SPURIOUS_ROW]
        assert len(spurious) == 1
        assert spurious[0].gold_index is None
        assert spurious[0].pred_index == 2
        assert spurious[0].similarity is None

    def test_both_empty(self):
        pairing = align_object_rows([], [], list_name="panels", manifest=TOY_MANIFEST)
        result = build_by_list(pairing, n_gold=0, n_pred=0)
        assert result.row_counts.correct_row == 0
        assert result.row_counts.missing_row == 0
        assert result.row_counts.spurious_row == 0
        assert result.rows == ()

    def test_below_threshold_emits_missing_and_spurious(self):
        """Hungarian pair below τ → missing_row + spurious_row, not correct_row."""
        gold = [{"label": "Fig 1"}]
        pred = [{"label": "Fig 99"}]
        pairing = align_object_rows(
            gold,
            pred,
            list_name="panels",
            manifest=TOY_MANIFEST,
        )
        result = build_by_list(pairing, n_gold=1, n_pred=1)
        assert result.row_counts.correct_row == 0
        assert result.row_counts.missing_row == 1
        assert result.row_counts.spurious_row == 1
        assert len(result.rows) == 2
