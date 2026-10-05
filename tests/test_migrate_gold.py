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


# --- curation files ------------------------------------------------------------

def _curation(tmp_path: Path, lines: list) -> Path:
    path = tmp_path / "curation.csv"
    fields = ["example", "panel", "plot", "individual_values", "decision", "note", "curator", "date"]
    import csv
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for line in lines:
            w.writerow({k: line.get(k, "") for k in fields})
    return path


ODD = {**ROW, "plot": "yes", "individual_values": "no", "decision": "PASS"}


def test_a_curated_judgement_becomes_writable(tmp_path):
    examples = _gold(tmp_path, [ODD])
    overrides = m.read_curation("individual-data-points", [_curation(tmp_path, [
        {"example": "doc/content/1", "panel": "A", "individual_values": "not_required"}])])
    (result,) = [r for _, _, r in m.plan("individual-data-points", examples, overrides)]
    assert result.kind == "mechanical"
    assert (result.new["individual_values"], result.new["decision"]) == ("not_required", "PASS")


def test_a_curated_value_that_breaks_the_rule_is_still_a_judgement(tmp_path):
    examples = _gold(tmp_path, [ODD])
    overrides = m.read_curation("individual-data-points", [_curation(tmp_path, [
        {"example": "doc/content/1", "panel": "A", "individual_values": "not_required",
         "decision": "not_applicable"}])])
    (result,) = [r for _, _, r in m.plan("individual-data-points", examples, overrides)]
    assert result.kind == "judgement"


def test_a_curation_line_matching_no_gold_row_is_an_error(tmp_path):
    examples = _gold(tmp_path, [ODD])
    overrides = m.read_curation("individual-data-points", [_curation(tmp_path, [
        {"example": "doc/content/1", "panel": "Z", "individual_values": "yes"}])])
    with pytest.raises(ValueError, match="match no gold row"):
        m.plan("individual-data-points", examples, overrides)


def test_curating_the_same_row_twice_is_an_error(tmp_path):
    line = {"example": "doc/content/1", "panel": "A", "individual_values": "yes"}
    with pytest.raises(ValueError, match="curated twice"):
        m.read_curation("individual-data-points", [_curation(tmp_path, [line, line])])


def test_write_applies_curation_and_the_rule_together(tmp_path):
    examples = _gold(tmp_path, [ROW, {**ODD, "panel_label": "B"}])
    overrides = m.read_curation("individual-data-points", [_curation(tmp_path, [
        {"example": "doc/content/1", "panel": "B", "individual_values": "not_required"}])])
    m.write("individual-data-points", m.plan("individual-data-points", examples, overrides),
            fill_blank=False, examples=examples)
    rows = json.loads(next(examples.glob("**/expected_output.json")).read_text())["outputs"]
    assert [(r["individual_values"], r["decision"]) for r in rows] == [
        ("not_applicable", "not_applicable"), ("not_required", "PASS")]


# --- error-bars-defined ----------------------------------------------------------

EBD_NA = {"panel_label": "A", "is_a_plot": "no", "error_bar_on_figure": "no",
          "error_bar_defined_in_caption": "not needed", "from_the_caption": "not needed",
          "Decision_and_explanation": "not needed"}


def test_ebd_a_non_plot_becomes_not_applicable_and_splits_in_place():
    result = m.ebd_rule(EBD_NA)
    assert result.kind == "mechanical"
    assert list(result.new) == ["panel_label", "is_a_plot", "error_bar_on_figure",
                                "error_bar_defined_in_caption", "from_the_caption",
                                "decision", "explanation"]
    assert (result.new["error_bar_on_figure"], result.new["error_bar_defined_in_caption"],
            result.new["decision"]) == ("not_applicable", "not_applicable", "not_applicable")
    assert result.new["from_the_caption"] == "" and result.new["explanation"] == ""


@pytest.mark.parametrize("legacy", [True, False])
def test_ebd_a_plot_without_error_bars_is_a_pass(legacy):
    """Whether the gold is still lumped or already split, the decision becomes PASS."""
    row = {**EBD_NA, "is_a_plot": "yes"}
    if not legacy:
        row = {k: v for k, v in row.items() if k != "Decision_and_explanation"}
        row.update(error_bar_defined_in_caption="not_applicable", from_the_caption="",
                   decision="not_applicable", explanation="")
    result = m.ebd_rule(row)
    assert (result.new["error_bar_defined_in_caption"], result.new["decision"]) == ("not_required", "PASS")
    assert m.ebd_verify(result.new) is None


@pytest.mark.parametrize("defined, verdict, decision", [
    ("yes", "PASS: defined as mean +/- SEM", "PASS"),
    ("no", "FAIL - the caption does not define them", "FAIL"),
])
def test_ebd_verdict_and_reason_split(defined, verdict, decision):
    row = {"panel_label": "B", "is_a_plot": "yes", "error_bar_on_figure": "yes",
           "error_bar_defined_in_caption": defined, "from_the_caption": "mean +/- SEM",
           "Decision_and_explanation": verdict}
    result = m.ebd_rule(row)
    assert result.kind == "mechanical" and result.new["decision"] == decision
    assert result.new["explanation"] == verdict.split(" ", 1)[1].lstrip(":- ").strip()
    assert "Decision_and_explanation" not in result.new


@pytest.mark.parametrize("row, why", [
    ({"is_a_plot": "yes", "error_bar_on_figure": "yes", "error_bar_defined_in_caption": "yes",
      "from_the_caption": "SD", "Decision_and_explanation": "FAIL: no"}, "the rule gives PASS"),
    ({"is_a_plot": "no", "error_bar_on_figure": "yes", "error_bar_defined_in_caption": "yes",
      "from_the_caption": "SD", "Decision_and_explanation": "PASS"}, "not a plot"),
    ({"is_a_plot": "yes", "error_bar_on_figure": "no", "error_bar_defined_in_caption": "not needed",
      "from_the_caption": "mean +/- SD", "Decision_and_explanation": "not needed"}, "from_the_caption"),
    ({"is_a_plot": "yes", "error_bar_on_figure": "yes", "error_bar_defined_in_caption": "yes",
      "from_the_caption": "SD", "Decision_and_explanation": "looks fine"}, "no verdict token"),
    ({"error_bar_on_figure": "no", "error_bar_defined_in_caption": "not needed",
      "from_the_caption": "", "Decision_and_explanation": "not needed"}, "is_a_plot"),
])
def test_ebd_rows_that_need_a_judgement(row, why):
    result = m.ebd_rule({"panel_label": "C", **row})
    assert result.kind == "judgement" and why in result.reason


def test_ebd_a_blank_verdict_is_derived_but_only_offered():
    row = {"panel_label": "D", "is_a_plot": "yes", "error_bar_on_figure": "yes",
           "error_bar_defined_in_caption": "yes", "from_the_caption": "SD", "Decision_and_explanation": ""}
    result = m.ebd_rule(row)
    assert result.kind == "blank" and result.new["decision"] == "PASS"


def test_ebd_is_idempotent_on_migrated_rows():
    migrated = m.ebd_rule(EBD_NA).new
    assert m.ebd_rule(migrated).kind == "unchanged"
    assert m.ebd_verify(migrated) is None


def test_ebd_is_a_plot_comes_from_individual_data_points(tmp_path):
    base = tmp_path / "examples" / "doc" / "content" / "1" / "checks"
    (base / "individual-data-points").mkdir(parents=True)
    (base / "individual-data-points" / "expected_output.json").write_text(
        json.dumps({"outputs": [{"panel_label": "A", "plot": "yes"}]}))
    row = {k: v for k, v in EBD_NA.items() if k != "is_a_plot"}
    enriched = m._enrich_is_a_plot(row, "doc/content/1", tmp_path / "examples")
    assert list(enriched)[:2] == ["panel_label", "is_a_plot"] and enriched["is_a_plot"] == "yes"


# --- plot-axis-units, plot-gap-labeling, stat-significance-level --------------------

AX = lambda *answers: [{"axis": a, "answer": v} for a, v in zip("xyz", answers)]


@pytest.mark.parametrize("row, decision, answers", [
    ({"is_a_plot": "no", "units_provided": [], "decision": "N/A"}, "not_applicable", []),
    ({"is_a_plot": "yes", "units_provided": [], "decision": "N/A"}, "PASS", []),   # pie chart: a plot, so checked
    ({"is_a_plot": "yes", "units_provided": AX("yes", "not needed"), "decision": "PASS"},
     "PASS", ["yes", "not_required"]),
    ({"is_a_plot": "yes", "units_provided": AX("no", "yes"), "decision": "FAIL"}, "FAIL", ["no", "yes"]),
])
def test_plot_axis_units_rule(row, decision, answers):
    result = m.pau_rule({"panel_label": "A", "unit_definition_as_provided": [], "explanation": [], **row})
    assert result.kind in ("mechanical", "unchanged")
    assert result.new["decision"] == decision
    assert [u["answer"] for u in result.new["units_provided"]] == answers
    assert m.pau_verify(result.new) is None


def test_plot_axis_units_a_verdict_against_the_rule_is_a_judgement():
    row = {"panel_label": "A", "is_a_plot": "yes", "units_provided": AX("no"), "decision": "PASS",
           "unit_definition_as_provided": [], "explanation": []}
    assert m.pau_rule(row).kind == "judgement"


@pytest.mark.parametrize("plot, anomaly, marked, decision", [
    ("no", "not_applicable", "not_applicable", "not_applicable"),
    ("yes", "no", "not_applicable", "PASS"),
    ("yes", "yes", "yes", "PASS"),
    ("yes", "yes", "no", "FAIL"),
])
def test_plot_gap_labeling_rule(plot, anomaly, marked, decision):
    row = {"panel_label": "A", "is_a_plot": plot, "tick_sequence_anomaly": anomaly,
           "gap_visually_marked": marked, "decision": "N/A" if decision == "not_applicable" else decision}
    result = m.pgl_rule(row)
    assert result.new["decision"] == decision and m.pgl_verify(result.new) is None


@pytest.mark.parametrize("plot, symbols, defined, decision", [
    ("no", [], [], "not_applicable"),
    ("yes", [], [], "PASS"),                    # a plot with no symbols: nothing to fail
    ("yes", ["*"], ["yes"], "PASS"),
    ("yes", ["*", "**"], ["yes", "no"], "FAIL"),
])
def test_stat_significance_level_rule(plot, symbols, defined, decision):
    row = {"panel_label": "A", "is_a_plot": plot, "significance_level_symbols_on_image": symbols,
           "symbols_defined": defined, "decision": "N/A" if (decision == "not_applicable" or not symbols) else decision}
    result = m.ssl_rule(row)
    assert result.new["decision"] == decision and m.ssl_verify(result.new) is None


def test_stat_significance_level_blank_is_a_plot_is_a_judgement():
    row = {"panel_label": "", "is_a_plot": "", "significance_level_symbols_on_image": [],
           "symbols_defined": [], "decision": "N/A"}
    assert m.ssl_rule(row).kind == "judgement"


def test_na_on_a_plot_with_nothing_to_check_becomes_pass_but_other_na_does_not():
    """N/A was the gold's word for a plot with nothing to check; that class
    became PASS. N/A on a plot that does have something to check stays a
    judgement."""
    empty = {"panel_label": "A", "is_a_plot": "yes", "significance_level_symbols_on_image": [],
             "symbols_defined": [], "decision": "N/A"}
    assert m.ssl_rule(empty).new["decision"] == "PASS"
    shown = {**empty, "significance_level_symbols_on_image": ["*"], "symbols_defined": ["yes"]}
    assert m.ssl_rule(shown).kind == "judgement"


# --- stat-test, replication-reporting ------------------------------------------------

@pytest.mark.parametrize("plot, needed, mentioned, decision, out", [
    ("no", "no", "not needed", "PASS", ("not_applicable", "not_applicable", "not_applicable")),
    ("yes", "no", "not needed", "PASS", ("no", "not_required", "PASS")),
    ("yes", "yes", "yes", "PASS", ("yes", "yes", "PASS")),
    ("yes", "yes", "no", "FAIL", ("yes", "no", "FAIL")),
])
def test_stat_test_rule(plot, needed, mentioned, decision, out):
    row = {"panel_label": "A", "is_a_plot": plot, "statistical_test_needed": needed,
           "statistical_test_mentioned": mentioned, "from_the_caption": "t-test" if mentioned == "yes" else "",
           "decision": decision, "explanation": ""}
    new = m.st_rule(row).new
    assert (new["statistical_test_needed"], new["statistical_test_mentioned"], new["decision"]) == out
    assert m.st_rule(new).kind == "unchanged"


@pytest.mark.parametrize("involves, n, t, n_min, rtype, decision, out", [
    ("no", "not_applicable", "not_applicable", "not_applicable", "not_applicable", "PASS",
     ("not_applicable", "not_applicable", "")),
    ("yes", "yes", "yes", 2, "technical duplicates", "FAIL", ("PASS", 2, "technical duplicates")),  # n<3 is not this check's
    ("yes", "no", "yes", "not_reported", "cells", "FAIL", ("FAIL", "not_reported", "cells")),
    ("yes", "yes", "no", 3, "not_reported", "FAIL", ("FAIL", 3, "")),
])
def test_replication_reporting_rule(involves, n, t, n_min, rtype, decision, out):
    row = {"panel_label": "A", "involves_replicates": involves, "replicate_statements": [],
           "n_reported": n, "n_value_min": n_min, "replicate_type_reported": t,
           "replicate_type": rtype, "decision": decision, "explanation": ""}
    new = m.rr_rule(row).new
    assert (new["decision"], new["n_value_min"], new["replicate_type"]) == out
    assert m.rr_rule(new).kind == "unchanged"


def test_replication_reporting_contradictions_need_a_judgement():
    row = {"panel_label": "B", "involves_replicates": "no", "n_reported": "yes",
           "replicate_type_reported": "yes", "decision": "PASS"}
    assert m.rr_rule(row).kind == "judgement"


def _msb(micrograph, on, caption, image, from_caption="", from_image=""):
    return {"panel_label": "A", "micrograph": micrograph, "scale_bar_on_image": on,
            "scale_bar_defined_in_caption": caption, "from_the_caption": from_caption,
            "scale_bar_defined_in_image": image, "from_the_image": from_image}


def test_micrograph_scale_bar_non_micrograph_becomes_not_applicable():
    result = m.msb_rule(_msb("no", "", "", ""))
    assert result.kind == "mechanical"
    assert [result.new[f] for f in m.MSB_ENUMS] == ["not_applicable"] * 3
    assert (result.new["from_the_caption"], result.new["from_the_image"]) == ("", "")
    assert m.msb_rule(result.new).kind == "unchanged"


def test_micrograph_without_a_scale_bar_keeps_no():
    """A missing scale bar fails the check: nothing is 'not required'."""
    assert m.msb_rule(_msb("yes", "no", "no", "no")).kind == "unchanged"
    assert m.msb_rule(_msb("yes", "yes", "yes", "no", "Scale bar, 10 µm.")).kind == "unchanged"


@pytest.mark.parametrize("row", [
    _msb("no", "yes", "", ""),
    _msb("no", "", "", "", from_caption="Scale bar, 10 µm."),
    _msb("yes", "", "no", "no"),
    _msb("", "", "", ""),
])
def test_micrograph_scale_bar_contradictions_need_a_judgement(row):
    assert m.msb_rule(row).kind == "judgement"
