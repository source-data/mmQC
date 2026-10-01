"""Tests for the gold migration: the individual-data-points rule sorts rows as
the prose says, and writing touches only what it should."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from soda_mmqc.scripts import migrate_gold as m


@pytest.mark.parametrize("row, kind, values, decision", [
    ({"plot": "no", "individual_values": "not needed", "decision": "PASS"},
     "mechanical", "not_applicable", "not_applicable"),
    ({"plot": "no", "individual_values": "not needed", "decision": ""},
     "mechanical", "not_applicable", "not_applicable"),
    ({"plot": "yes", "individual_values": "not needed", "decision": "PASS"},
     "mechanical", "not_required", "PASS"),
    ({"plot": "yes", "individual_values": "yes", "decision": "PASS"},
     "unchanged", "yes", "PASS"),
    ({"plot": "yes", "individual_values": "no", "decision": "FAIL"},
     "unchanged", "no", "FAIL"),
    ({"plot": "yes", "individual_values": "not_required", "decision": "PASS"},
     "unchanged", "not_required", "PASS"),
    ({"plot": "no", "individual_values": "not_applicable", "decision": "not_applicable"},
     "unchanged", "not_applicable", "not_applicable"),
])
def test_rows_the_rule_settles(row, kind, values, decision):
    result = m.idp_rule({"panel_label": "A", **row})
    assert result.kind == kind
    assert (result.new["individual_values"], result.new["decision"]) == (values, decision)


@pytest.mark.parametrize("row", [
    {"plot": "yes", "individual_values": "no", "decision": "PASS"},   # the 30
    {"plot": "no", "individual_values": "no", "decision": "PASS"},    # the 1
    {"plot": "yes", "individual_values": "not_applicable", "decision": "PASS"},
    {"plot": "", "individual_values": "yes", "decision": "PASS"},
])
def test_rows_that_need_a_judgement_are_left_alone(row):
    result = m.idp_rule({"panel_label": "A", **row})
    assert result.kind == "judgement"
    assert result.new == {"panel_label": "A", **row}


def test_a_blank_decision_on_a_plot_is_derived_but_only_offered():
    result = m.idp_rule({"panel_label": "A", "plot": "yes",
                         "individual_values": "no", "decision": ""})
    assert result.kind == "blank" and result.new["decision"] == "FAIL"


def _gold(tmp_path: Path, rows: list, *, html: bool = True) -> Path:
    d = tmp_path / "examples" / "doc" / "content" / "1" / "checks" / "individual-data-points"
    d.mkdir(parents=True)
    (d / "expected_output.json").write_text(
        json.dumps({"outputs": rows, "updated_at": "2026-01-01"}, indent=4, ensure_ascii=False))
    if html:
        (d / "expected_output.html").write_text("<old/>")
    return tmp_path / "examples"


ROW = {"panel_label": "A", "plot": "no", "individual_values": "not needed",
       "decision": "PASS", "explanation": "Micrograph — check does not apply."}


def test_write_rewrites_in_the_curation_format_and_keeps_the_rest(tmp_path):
    examples = _gold(tmp_path, [ROW])
    written = m.write("individual-data-points", m.plan("individual-data-points", examples),
                      fill_blank=False, examples=examples)
    assert len(written) == 1
    text = written[0].read_text()
    assert not text.endswith("\n") and '    "outputs"' in text and "—" in text
    gold = json.loads(text)
    assert gold["updated_at"] == "2026-01-01"
    assert gold["outputs"][0] == {**ROW, "individual_values": "not_applicable",
                                  "decision": "not_applicable"}
    assert written[0].with_name("expected_output.html").read_text() != "<old/>"


def test_write_is_idempotent(tmp_path):
    examples = _gold(tmp_path, [ROW])
    for _ in range(2):
        written = m.write("individual-data-points", m.plan("individual-data-points", examples),
                          fill_blank=False, examples=examples)
    assert written == []


def test_write_leaves_judgement_rows_untouched(tmp_path):
    odd = {**ROW, "panel_label": "B", "plot": "yes", "individual_values": "no", "decision": "PASS"}
    examples = _gold(tmp_path, [ROW, odd])
    m.write("individual-data-points", m.plan("individual-data-points", examples),
            fill_blank=False, examples=examples)
    gold = json.loads(next(examples.glob("**/expected_output.json")).read_text())
    assert gold["outputs"][1] == odd


def test_main_refuses_to_write_while_judgements_remain(tmp_path, monkeypatch, capsys):
    odd = {**ROW, "plot": "yes", "individual_values": "no", "decision": "PASS"}
    examples = _gold(tmp_path, [odd])
    before = next(examples.glob("**/expected_output.json")).read_text()
    monkeypatch.setattr(m, "EXAMPLES", examples)
    assert m.main(["individual-data-points", "--write"]) == 1
    assert "Refusing to write" in capsys.readouterr().out
    assert next(examples.glob("**/expected_output.json")).read_text() == before


def test_main_writes_once_nothing_needs_a_judgement(tmp_path, monkeypatch):
    examples = _gold(tmp_path, [ROW])
    monkeypatch.setattr(m, "EXAMPLES", examples)
    assert m.main(["individual-data-points", "--write"]) == 0
    gold = json.loads(next(examples.glob("**/expected_output.json")).read_text())
    assert gold["outputs"][0]["decision"] == "not_applicable"
