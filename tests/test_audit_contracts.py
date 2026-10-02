"""Tests for the contract audit: each rule fires on the defect it names, and a
contract that follows the conventions (C1-C5) produces no finding at all."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from soda_mmqc.scripts.audit_contracts import Finding, audit_check


def _contract(tmp_path: Path, fields: dict, manifest_fields: dict, *,
              gold_rows: list | None = None, check: str = "toy-check",
              manifest: bool = True) -> tuple[Path, Path]:
    """Write a one-list contract, and optionally gold, under ``tmp_path``."""
    check_dir = tmp_path / "checklist" / check
    check_dir.mkdir(parents=True)
    schema = {"format": {"type": "json_schema", "name": check, "strict": True, "schema": {
        "type": "object", "required": ["outputs"], "additionalProperties": False,
        "properties": {"outputs": {"type": "array", "items": {
            "type": "object", "additionalProperties": False,
            "properties": {"panel_label": {"type": "string"}, **fields},
            "required": ["panel_label", *fields]}}}}}}
    (check_dir / "schema.json").write_text(json.dumps(schema))
    if manifest:
        (check_dir / "eval-manifest.json").write_text(json.dumps({
            "checklist": check,
            "defaults": {"matching_metric": "binary_polarity", "positive_value": "yes",
                         "negative_value": "no", "na_values": []},
            "list_alignment": {"outputs": ["panel_label"]},
            "fields": {"outputs[].panel_label": {"matching_metric": "graded_string",
                                                 "string_compare": "exact"},
                       **manifest_fields},
        }))
    gold_root = tmp_path / "examples"
    if gold_rows is not None:
        gold = gold_root / "fig" / "content" / "1" / "checks" / check
        gold.mkdir(parents=True)
        (gold / "expected_output.json").write_text(json.dumps({"outputs": gold_rows}))
    else:
        gold_root.mkdir()
    return check_dir, gold_root


def _rules(findings: list[Finding]) -> set[str]:
    return {f.rule for f in findings}


def test_a_contract_following_the_conventions_is_clean(tmp_path):
    check_dir, gold = _contract(
        tmp_path,
        {"decision": {"type": "string", "enum": ["PASS", "FAIL", "not_applicable"]},
         "explanation": {"type": "string"},
         "on_figure": {"type": "string", "enum": ["yes", "no", "not_applicable"]}},
        {"outputs[].decision": {"matching_metric": "multiclass", "na_values": ["not_applicable"]},
         "outputs[].explanation": {"matching_metric": "graded_string",
                                   "string_compare": "semantic", "match_threshold": 0.8},
         "outputs[].on_figure": {"matching_metric": "binary_polarity",
                                 "na_values": ["not_applicable"]}},
        gold_rows=[{"panel_label": "A", "decision": "not_applicable", "explanation": "",
                    "on_figure": "not_applicable"}],
    )
    assert audit_check("toy", check_dir, gold) == []


def test_no_manifest(tmp_path):
    check_dir, gold = _contract(tmp_path, {}, {}, manifest=False)
    assert _rules(audit_check("toy", check_dir, gold)) == {"no-manifest"}


def test_untyped_field(tmp_path):
    check_dir, gold = _contract(tmp_path, {"n": {"description": "no type"}}, {})
    assert "untyped" in _rules(audit_check("toy", check_dir, gold))


def test_a_union_inheriting_the_default_polarity(tmp_path):
    """The n_value_min case: typed, but scored by a default nobody chose."""
    field = {"anyOf": [{"type": "integer"},
                       {"type": "string", "enum": ["not_reported", "not_applicable"]}]}
    check_dir, gold = _contract(tmp_path, {"n": field}, {})
    assert "default" in _rules(audit_check("toy", check_dir, gold))


def test_na_token_in_free_text(tmp_path):
    """The error-bars-defined case."""
    check_dir, gold = _contract(
        tmp_path, {"decision_and_explanation": {"type": "string"}},
        {"outputs[].decision_and_explanation": {
            "matching_metric": "graded_string", "string_compare": "semantic",
            "na_values": ["not_applicable"]}})
    assert "na-text" in _rules(audit_check("toy", check_dir, gold))


def test_polarity_on_free_text(tmp_path):
    check_dir, gold = _contract(tmp_path, {"present": {"type": "string"}},
                                {"outputs[].present": {"matching_metric": "binary_polarity"}})
    assert "polar-text" in _rules(audit_check("toy", check_dir, gold))


def test_na_enum_value_scored_as_a_class(tmp_path):
    """The N/A-in-decision case."""
    check_dir, gold = _contract(
        tmp_path, {"decision": {"type": "string", "enum": ["PASS", "FAIL", "N/A"]}},
        {"outputs[].decision": {"matching_metric": "multiclass"}})
    assert "enum-na" in _rules(audit_check("toy", check_dir, gold))


def test_enum_missing_a_scored_token(tmp_path):
    check_dir, gold = _contract(
        tmp_path, {"present": {"type": "string", "enum": ["yes", "no"]}},
        {"outputs[].present": {"matching_metric": "binary_polarity",
                               "na_values": ["not_applicable"]}})
    assert "enum-gap" in _rules(audit_check("toy", check_dir, gold))


@pytest.mark.parametrize("token", ["not needed", "not_needed", "N/A", "n/a", "not a plot"])
def test_legacy_not_applicable_spellings(tmp_path, token):
    check_dir, gold = _contract(
        tmp_path, {"present": {"type": "string", "enum": ["yes", "no", token]}},
        {"outputs[].present": {"matching_metric": "binary_polarity", "na_values": [token]}})
    found = [f for f in audit_check("toy", check_dir, gold) if f.rule == "legacy-token"]
    assert found and repr(token) in found[0].detail


def test_legacy_spelling_in_gold_alone_is_found(tmp_path):
    check_dir, gold = _contract(
        tmp_path, {"present": {"type": "string", "enum": ["yes", "no", "not_applicable"]}},
        {"outputs[].present": {"matching_metric": "binary_polarity",
                               "na_values": ["not_applicable"]}},
        gold_rows=[{"panel_label": "A", "present": "not needed"}])
    found = [f for f in audit_check("toy", check_dir, gold) if f.rule == "legacy-token"]
    assert found and "in gold" in found[0].detail


def test_not_reported_and_unclear_are_real_answers(tmp_path):
    """C2: never normalised away with the not-applicable spellings."""
    check_dir, gold = _contract(
        tmp_path,
        {"reported": {"type": "string", "enum": ["yes", "no", "not_reported", "unclear"]}},
        {"outputs[].reported": {"matching_metric": "multiclass"}})
    assert not {"legacy-token", "enum-na"} & _rules(audit_check("toy", check_dir, gold))


def test_orphan_manifest_token(tmp_path):
    """The stat-significance-level case: a token nothing produces."""
    check_dir, gold = _contract(
        tmp_path, {"present": {"type": "string", "enum": ["yes", "no", "not_applicable"]}},
        {"outputs[].present": {"matching_metric": "binary_polarity",
                               "na_values": ["not_applicable", "nothing_uses_this"]}},
        gold_rows=[{"panel_label": "A", "present": "yes"}])
    found = [f for f in audit_check("toy", check_dir, gold) if f.rule == "orphan-token"]
    assert [f.tokens for f in found] == [("nothing_uses_this",)]


def test_free_text_scored_exactly(tmp_path):
    check_dir, gold = _contract(tmp_path, {"url": {"type": "string"}},
                                {"outputs[].url": {"matching_metric": "graded_string",
                                                   "string_compare": "exact"}})
    assert "text-metric" in _rules(audit_check("toy", check_dir, gold))


def test_a_declared_identifier_may_be_scored_exactly(tmp_path):
    check_dir, gold = _contract(tmp_path, {"url": {"type": "string"}},
                                {"outputs[].url": {"matching_metric": "graded_string",
                                                   "string_compare": "exact"}})
    findings = audit_check("toy", check_dir, gold,
                           identifiers={("toy-check", "outputs[].url"): "a URL"})
    assert "text-metric" not in _rules(findings)


def test_gold_outside_the_schema_enum(tmp_path):
    """The individual-data-points case: blank gold under a PASS/FAIL enum."""
    check_dir, gold = _contract(
        tmp_path, {"decision": {"type": "string", "enum": ["PASS", "FAIL"]}},
        {"outputs[].decision": {"matching_metric": "multiclass"}},
        gold_rows=[{"panel_label": "A", "decision": ""},
                   {"panel_label": "B", "decision": "PASS"}])
    found = [f for f in audit_check("toy", check_dir, gold) if f.rule == "gold-off-enum"]
    assert found and "''" in found[0].detail


def test_a_field_declared_unscored_is_outside_the_metric_rules(tmp_path):
    check_dir, gold = _contract(tmp_path, {"explanation": {"type": "string"}},
                                {"outputs[].explanation": {"scored": False}})
    assert audit_check("toy", check_dir, gold) == []
