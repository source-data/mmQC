"""A manifest field declared `"scored": false` is skipped by the evaluator.

Without the declaration a field missing from the manifest inherits the
default metric, so an explanation beside an enum decision could not be left
unscored (contract cleanup, C3 and C5).
"""

from __future__ import annotations

import pytest

from soda_mmqc.core.eval_manifest import parse_eval_manifest
from soda_mmqc.core.evaluation import FlatEvaluator

SCHEMA = {"type": "object", "properties": {"outputs": {"type": "array", "items": {
    "type": "object", "properties": {
        "panel_label": {"type": "string"},
        "decision": {"type": "string", "enum": ["PASS", "FAIL", "not_applicable"]},
        "explanation": {"type": "string"}}}}}}


def _manifest(explanation):
    return parse_eval_manifest({
        "checklist": "toy",
        "defaults": {"matching_metric": "binary_polarity", "positive_value": "yes",
                     "negative_value": "no", "na_values": []},
        "list_alignment": {"outputs": ["panel_label"]},
        "fields": {"outputs[].panel_label": {"matching_metric": "graded_string",
                                             "string_compare": "exact",
                                             "match_threshold": 1.0},
                   "outputs[].decision": {"matching_metric": "multiclass",
                                          "na_values": ["not_applicable"]},
                   "outputs[].explanation": explanation}})


GOLD = {"outputs": [{"panel_label": "A", "decision": "not_applicable", "explanation": ""}]}
PRED = {"outputs": [{"panel_label": "A", "decision": "not_applicable",
                     "explanation": "a micrograph, so no error bars"}]}


def test_an_unscored_field_produces_no_instances():
    result = FlatEvaluator(SCHEMA, _manifest({"scored": False})).evaluate(GOLD, PRED)
    props = {i.leaf_property for i in result.instances}
    assert "outputs[].explanation" not in props
    assert "outputs[].decision" in props


def test_the_same_field_scored_is_a_spurious_applicable_answer():
    """Why C3 needs it: explaining a not-applicable panel would be penalised."""
    result = FlatEvaluator(SCHEMA, _manifest({"matching_metric": "graded_string",
                                              "string_compare": "semantic",
                                              "match_threshold": 0.8,
                                              "na_values": [""]})).evaluate(GOLD, PRED)
    (inst,) = [i for i in result.instances if i.leaf_property == "outputs[].explanation"]
    assert inst.layer1 == "spurious_applicable"


def test_unscored_takes_no_other_keys():
    with pytest.raises(ValueError, match="no other keys"):
        _manifest({"scored": False, "matching_metric": "graded_string"})


def test_scored_must_be_a_boolean():
    with pytest.raises(ValueError, match="true or false"):
        _manifest({"scored": "no"})


def test_an_alignment_key_cannot_be_unscored():
    with pytest.raises(ValueError, match="aligns rows"):
        parse_eval_manifest({"checklist": "toy", "defaults": {},
                             "list_alignment": {"outputs": ["panel_label"]},
                             "fields": {"outputs[].panel_label": {"scored": False}}})


def test_an_unscored_path_outside_the_schema_is_rejected():
    import dataclasses
    manifest = _manifest({"scored": False})
    manifest = dataclasses.replace(
        manifest, _unscored=manifest._unscored | {"outputs[].no_such_field"})
    with pytest.raises(ValueError, match="non-schema"):
        FlatEvaluator(SCHEMA, manifest).evaluate(GOLD, PRED)
