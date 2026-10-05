"""A field in an object nested inside a list row scores as the same field
placed directly in the row.

exp-04's panel-major contract puts each check's fields in an object inside the
panel row (`outputs[].<check>.decision`). The scorer discovered such a leaf but
read only the last segment of its pattern from the row, so every instance came
out absent on both sides -- `correct_NA` whatever the gold and the prediction
said. Found 2026-10-05, before any run depended on it.
"""

from __future__ import annotations

import json
from dataclasses import asdict

from soda_mmqc.core.eval_manifest import parse_eval_manifest
from soda_mmqc.core.evaluation import FlatEvaluator

YES_NO_NA = {"type": "string", "enum": ["yes", "no", "not_applicable"]}
TEXT = {"type": "string"}
DEFAULTS = {"matching_metric": "binary_polarity", "positive_value": "yes",
            "negative_value": "no", "na_values": []}
EXACT = {"matching_metric": "graded_string", "string_compare": "exact", "match_threshold": 1.0}


def _schema(nested: bool) -> dict:
    inner = {"answer": YES_NO_NA, "quote": TEXT}
    row = {"panel_label": TEXT}
    if nested:
        row["chk"] = {"type": "object", "properties": inner,
                      "required": list(inner), "additionalProperties": False}
    else:
        row.update(inner)
    return {"type": "object", "required": ["outputs"], "additionalProperties": False,
            "properties": {"outputs": {"type": "array", "items": {
                "type": "object", "properties": row, "required": list(row),
                "additionalProperties": False}}}}


def _manifest(prefix: str) -> dict:
    return {"checklist": "toy", "defaults": DEFAULTS,
            "list_alignment": {"outputs": ["panel_label"]},
            "fields": {"outputs[].panel_label": EXACT,
                       f"outputs[].{prefix}answer": {"na_values": ["not_applicable"]},
                       f"outputs[].{prefix}quote": EXACT}}


GOLD = [{"panel_label": "A", "answer": "yes", "quote": "x"},
        {"panel_label": "B", "answer": "not_applicable", "quote": ""},
        {"panel_label": "C", "answer": "no", "quote": "y"},
        {"panel_label": "E", "answer": "yes", "quote": ""}]
PRED = [{"panel_label": "A", "answer": "no", "quote": "x"},
        {"panel_label": "B", "answer": "yes", "quote": ""},
        {"panel_label": "D", "answer": "no", "quote": "z"},
        {"panel_label": "E", "answer": "not_applicable", "quote": "q"}]


def _nest(rows):
    return {"outputs": [{"panel_label": r["panel_label"],
                         "chk": {"answer": r["answer"], "quote": r["quote"]}} for r in rows]}


def _score(nested: bool) -> dict:
    evaluator = FlatEvaluator(_schema(nested), parse_eval_manifest(_manifest("chk." if nested else "")))
    gold, pred = (_nest(GOLD), _nest(PRED)) if nested else ({"outputs": GOLD}, {"outputs": PRED})
    return asdict(evaluator.evaluate(gold, pred))


def test_a_nested_field_reads_the_values_in_the_row():
    answers = [i for i in _score(nested=True)["instances"]
               if i["leaf_property"] == "outputs[].chk.answer"]
    assert [(i["exp_value"], i["pred_value"]) for i in answers] == [
        ("yes", "no"), ("not_applicable", "yes"), ("no", None), ("yes", "not_applicable")]
    assert [i["path"] for i in answers][0] == "outputs[0].chk.answer"


def test_nested_and_flat_score_identically():
    flat = json.dumps(_score(nested=False), sort_keys=True, default=str)
    nested = json.dumps(_score(nested=True), sort_keys=True, default=str).replace("chk.", "")
    assert nested == flat
