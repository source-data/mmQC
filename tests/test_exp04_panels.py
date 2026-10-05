"""exp-04's spurious-panel count: one panel per figure, whatever the shape."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[1] / "experiments" / "exp-04-panel-major" / "panels.py"
_spec = importlib.util.spec_from_file_location("exp04_panels", _PATH)
panels = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(panels)

GOLD = ["A", "B", "C"]


def _cm(**lists):
    return {check: [{"panel_label": label} for label in lists.get(check.replace("-", "_"), [])]
            for check in panels.CHECKS}


def _pm(labels):
    return {"outputs": [{"panel_label": label} for label in labels]}


def test_a_panel_invented_in_every_list_is_one_spurious_panel():
    answer = _cm(micrograph_scale_bar=["A", "B", "C", "Z"],
                 individual_data_points=["A", "B", "C", "Z"],
                 error_bars_defined=["A", "B", "C", "Z"])
    assert panels.panel_counts(GOLD, answer, "cm")["spurious_panels"] == 1


def test_the_same_panel_in_a_pm_answer_counts_the_same():
    assert panels.panel_counts(GOLD, _pm(["A", "B", "C", "Z"]), "pm")["spurious_panels"] == 1


def test_cm_lists_that_disagree():
    answer = _cm(micrograph_scale_bar=["A", "B", "Y"],
                 individual_data_points=["A", "C", "Z"],
                 error_bars_defined=["A", "B"])
    assert panels.panel_counts(GOLD, answer, "cm") == {
        "gold_panels": 3, "spurious_panels": 2, "missing_panels": 0,
        "partly_missing_panels": 2}


def test_a_panel_no_list_carries_is_missing():
    assert panels.panel_counts(GOLD, _pm(["A", "B"]), "pm") == {
        "gold_panels": 3, "spurious_panels": 0, "missing_panels": 1,
        "partly_missing_panels": 0}


@pytest.mark.parametrize("answer", [None, {}, {"outputs": []}])
def test_no_answer_states_no_panels(answer):
    counts = panels.panel_counts(GOLD, answer, "pm")
    assert (counts["spurious_panels"], counts["missing_panels"]) == (0, 3)


def test_labels_are_compared_exactly_as_layer_s_aligns_them():
    assert panels.panel_counts(GOLD, _pm(["A", "B ", "C"]), "pm")["spurious_panels"] == 1


def test_an_unknown_shape_is_refused():
    with pytest.raises(ValueError):
        panels.labels_per_check(_pm(GOLD), "row-major")
