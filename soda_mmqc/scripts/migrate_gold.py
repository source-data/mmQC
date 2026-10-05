"""Migrate gold to the contract-cleanup vocabulary, one check at a time.

    python -m soda_mmqc.scripts.migrate_gold individual-data-points            # dry run
    python -m soda_mmqc.scripts.migrate_gold individual-data-points --write

The gold is rewritten in place, in ``soda_mmqc/data/examples/`` (decided at
G1, thinking/plans/2026-09-30-contract-cleanup.md). The frozen experiments
score against the tag ``gold-v1``, which this script never touches.

Each check has a migration rule that sorts every gold row into one of:

``mechanical``  the new values follow from the row itself and the check's
                prose -- a token rename, or a value derived by rule
``judgement``   the row contradicts the rule, so a person decides; the script
                changes nothing in such a row and ``--write`` refuses while
                any remain. Fix them in the curation app (``mmqc curate
                fig-checklist``), which writes the gold, then run again
``blank``       a value the rule could fill but the gold left empty; filled
                only with ``--fill-blank``, after someone has confirmed the
                example is real gold

A curator's judgements can be applied from a file instead of the curation app:
``--curation FILE`` names a CSV with ``example``, ``panel`` and the fields to
set (here ``plot``, ``individual_values``, ``decision``), plus ``note``,
``curator`` and ``date`` kept as the record. Each line must match exactly one
gold row; its values are applied before the rule runs, so a judgement that
contradicts the rule is still reported as one and still blocks ``--write``.
The file is committed beside the gold change it made.

A run is idempotent: rows already in the new vocabulary are left alone, so it
can be re-run after any amount of curation. ``--write`` rewrites only files
whose content changes, keeping each file's own layout -- indentation, final
newline, escaping -- so the diff shows only changed values (and refreshes its
``expected_output.html`` where one exists), and
verifies every rewritten row against the check's schema and rule.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

EXAMPLES = REPO / "soda_mmqc" / "data" / "examples"
CHECKLIST = REPO / "soda_mmqc" / "data" / "checklist" / "fig-checklist"


@dataclass
class RowResult:
    kind: str                      # unchanged | mechanical | judgement | blank
    new: Dict[str, Any]            # the row as it would be written
    reason: str = ""


# ---------------------------------------------------------------------------
# individual-data-points
# ---------------------------------------------------------------------------
#
# The prose (v1/SKILL.md, 2026-10-01):
#   plot no                          -> individual_values not_applicable, decision not_applicable
#   plot yes, individual_values yes or not_required -> PASS
#   plot yes, individual_values no   -> FAIL
# and "not needed" is retired: it meant not_applicable on a non-plot and
# not_required on an exempt plot type.

IDP_VALUES = {"yes": "yes", "no": "no", "not needed": "not_required",
              "not_required": "not_required", "not_applicable": "not_applicable"}


def idp_rule(row: Mapping[str, Any]) -> RowResult:
    new = dict(row)
    plot = row.get("plot")
    values = row.get("individual_values")
    decision = row.get("decision")

    if plot == "no":
        if values not in ("not needed", "not_applicable"):
            return RowResult("judgement", dict(row),
                             f"not a plot, but individual_values is {values!r}")
        new["individual_values"] = "not_applicable"
        new["decision"] = "not_applicable"
    elif plot == "yes":
        if values not in IDP_VALUES or IDP_VALUES[values] == "not_applicable":
            return RowResult("judgement", dict(row),
                             f"a plot, but individual_values is {values!r}")
        new["individual_values"] = IDP_VALUES[values]
        derived = "FAIL" if new["individual_values"] == "no" else "PASS"
        if decision in (None, ""):
            new["decision"] = derived
            return RowResult("blank", new,
                             f"blank decision; the rule gives {derived}")
        if decision != derived:
            return RowResult("judgement", dict(row),
                             f"decision {decision!r}, but individual_values "
                             f"{values!r} gives {derived}")
    else:
        return RowResult("judgement", dict(row), f"plot is {plot!r}")

    return RowResult("unchanged" if new == dict(row) else "mechanical", new)


def idp_verify(row: Mapping[str, Any]) -> Optional[str]:
    """None if a migrated row satisfies the rule, else what is wrong."""
    plot, values, decision = row.get("plot"), row.get("individual_values"), row.get("decision")
    if plot == "no":
        ok = values == "not_applicable" and decision == "not_applicable"
    elif plot == "yes":
        ok = (values in ("yes", "not_required") and decision == "PASS") or (
            values == "no" and decision == "FAIL")
    else:
        ok = False
    return None if ok else f"plot {plot!r}, individual_values {values!r}, decision {decision!r}"


# ---------------------------------------------------------------------------
# error-bars-defined
# ---------------------------------------------------------------------------
#
# The prose (v1/SKILL.md, 2026-10-02):
#   error_bar_on_figure no               -> error_bar_defined_in_caption not_applicable,
#                                           decision not_applicable, from_the_caption ""
#   error_bar_on_figure yes, defined yes -> PASS
#   error_bar_on_figure yes, defined no  -> FAIL
# and Decision_and_explanation -- a verdict token and its reason in one
# string -- splits into decision and explanation (C3).

import re as _re

_EBD_VERDICT = _re.compile(r"^\s*(PASS|FAIL|not needed|not_applicable)\b(.*)$", _re.S)
_SEPARATORS = " \t\n:-–—.,;"


def _split_verdict(text: str) -> Optional[Tuple[str, str]]:
    """'PASS: defined as SEM' -> ('PASS', 'defined as SEM'); None if no token."""
    match = _EBD_VERDICT.match(text or "")
    if not match:
        return None
    token = "not_applicable" if match.group(1) in ("not needed", "not_applicable") else match.group(1)
    return token, match.group(2).lstrip(_SEPARATORS).strip()


def _ebd_row(row: Mapping[str, Any], decision: str, explanation: str, **fields) -> Dict[str, Any]:
    """The row with Decision_and_explanation replaced, in place, by its two halves."""
    out: Dict[str, Any] = {}
    for key, value in row.items():
        if key in ("Decision_and_explanation", "decision"):
            # Either the lumped field or an already split decision: in both
            # cases the derived values go here, in this position.
            out["decision"], out["explanation"] = decision, explanation
        elif key != "explanation":
            out[key] = fields.get(key, value)
    if "decision" not in out:
        out["decision"], out["explanation"] = decision, explanation
    return out


def ebd_rule(row: Mapping[str, Any]) -> RowResult:
    """error-bars-defined, as of 2026-10-02: a plot is checked.

    Not a plot: not_applicable. A plot without error bars has nothing to
    define: error_bar_defined_in_caption not_required, decision PASS. A plot
    with error bars: PASS if the caption defines them, FAIL if not.
    is_a_plot is filled from individual-data-points' gold by ENRICH below.
    """
    plot = row.get("is_a_plot")
    on_figure = row.get("error_bar_on_figure")
    defined = row.get("error_bar_defined_in_caption")
    caption = row.get("from_the_caption")
    if "Decision_and_explanation" in row:
        combined = row.get("Decision_and_explanation") or ""
        split = _split_verdict(combined) if combined.strip() else ("", "")
        if split is None:
            return RowResult("judgement", dict(row), f"no verdict token in {combined[:40]!r}")
        verdict, explanation = split
    else:
        verdict, explanation = row.get("decision") or "", row.get("explanation") or ""
    verdict = "not_applicable" if verdict in ("N/A", "not needed") else verdict
    empty_caption = caption in ("", "not needed", None)

    if plot not in ("yes", "no"):
        return RowResult("judgement", dict(row), f"is_a_plot is {plot!r}")
    if plot == "no":
        if on_figure not in ("no", "not_applicable"):
            return RowResult("judgement", dict(row), "not a plot, but error bars are marked present")
        # A non-plot is not_applicable in every field the check asks about,
        # error_bar_on_figure included (wording by the curator, 2026-10-02).
        derived, fields = "not_applicable", {"error_bar_on_figure": "not_applicable",
                                             "error_bar_defined_in_caption": "not_applicable",
                                             "from_the_caption": ""}
        accepted = ("", "not_applicable")
    elif on_figure == "no":
        derived, fields = "PASS", {"error_bar_defined_in_caption": "not_required", "from_the_caption": ""}
        # Was not_applicable: a plot without error bars, now a PASS as a class.
        accepted = ("", "not_applicable", "PASS")
    elif on_figure == "yes":
        if defined not in ("yes", "no"):
            return RowResult("judgement", dict(row),
                             f"error bars present, but defined_in_caption is {defined!r}")
        derived, fields = ("PASS" if defined == "yes" else "FAIL"), {}
        accepted = ("", derived)
    else:
        return RowResult("judgement", dict(row), f"error_bar_on_figure is {on_figure!r}")

    if on_figure in ("no", "not_applicable"):
        if defined not in ("not needed", "not_applicable", "not_required"):
            return RowResult("judgement", dict(row),
                             f"no error bars, but defined_in_caption is {defined!r}")
        if not empty_caption:
            return RowResult("judgement", dict(row), "no error bars, but from_the_caption holds text")
    if verdict not in accepted:
        return RowResult("judgement", dict(row), f"the verdict is {verdict!r}, but the rule gives {derived}")

    new = _ebd_row(row, derived, explanation, **fields)
    if verdict == "":
        return RowResult("blank", new, f"blank verdict; the rule gives {derived}")
    return RowResult("unchanged" if new == dict(row) else "mechanical", new)


def ebd_verify(row: Mapping[str, Any]) -> Optional[str]:
    if "Decision_and_explanation" in row:
        return "Decision_and_explanation is still present"
    result = ebd_rule(row)
    return None if result.kind == "unchanged" else f"breaks the rule: {result.reason or result.kind}"


def _enrich_is_a_plot(row: Dict[str, Any], example: str, examples: Path) -> Dict[str, Any]:
    """error-bars-defined gains is_a_plot, from individual-data-points' gold.

    Decided 2026-10-02; the two checks' panel lists agree on every figure.
    Placed right after panel_label. Left absent when no such gold row exists,
    which makes the row a judgement.
    """
    if "is_a_plot" in row:
        return row
    path = examples / example / "checks" / "individual-data-points" / "expected_output.json"
    if not path.is_file():
        return row
    plots = {r.get("panel_label"): r.get("plot") for r in json.loads(path.read_text())["outputs"]}
    if row.get("panel_label") not in plots:
        return row
    out: Dict[str, Any] = {}
    for key, value in row.items():
        out[key] = value
        if key == "panel_label":
            out["is_a_plot"] = plots[row["panel_label"]]
    return out


# ---------------------------------------------------------------------------
# plot-axis-units, plot-gap-labeling, stat-significance-level
# ---------------------------------------------------------------------------
#
# Their decision held N/A, scored as a class; it becomes not_applicable (C1).
# The prose (v1/SKILL.md, 2026-10-02) gives each rule below.

_NA = ("N/A", "not_applicable")


def _verdict(row, derived: str, reason: str, *, na_means: Optional[str] = None) -> Optional[RowResult]:
    """A judgement if the gold's decision is neither blank nor the derived one.

    ``na_means`` names what the gold's N/A stands for in this case, when a
    decision of 2026-10-02 settled the whole class at once -- a plot with
    nothing to check was N/A and is now PASS -- so that it is a rename, not a
    contradiction.
    """
    current = row.get("decision")
    current = (na_means or "not_applicable") if current in _NA else current
    if current not in (None, "", derived):
        return RowResult("judgement", dict(row), f"decision {row.get('decision')!r}, but {reason} gives {derived}")
    return None


def _settle(row, new) -> RowResult:
    if row.get("decision") in (None, ""):
        return RowResult("blank", new, f"blank decision; the rule gives {new['decision']}")
    return RowResult("unchanged" if new == dict(row) else "mechanical", new)


def pau_rule(row: Mapping[str, Any]) -> RowResult:
    """plot-axis-units: not a plot is not_applicable; a plot is checked, and
    fails only if an axis lacks its unit.

    A plot means the check applies (decided 2026-10-02, the individual-data-
    points model): a plot with no axes, such as a pie chart, has nothing to
    fail and is a PASS; an axis that needs no unit answers not_required, a
    real answer, where the gold said "not needed".
    """
    plot, units = row.get("is_a_plot"), row.get("units_provided") or []
    if plot == "yes" and not units and not row.get("unit_definition_as_provided"):
        derived = "PASS"
        new = {**row}
    elif plot == "no":
        if units or row.get("unit_definition_as_provided") or row.get("explanation"):
            return RowResult("judgement", dict(row), "not a plot, but its axis lists are not empty")
        derived = "not_applicable"
        new = {**row}
    elif plot == "yes":
        answers = [u.get("answer") for u in units]
        if any(a not in ("yes", "no", "not needed", "not_required") for a in answers):
            return RowResult("judgement", dict(row), f"axis answers {answers}")
        derived = "FAIL" if "no" in answers else "PASS"
        new = {**row, "units_provided": [
            {**u, "answer": "not_required" if u.get("answer") == "not needed" else u.get("answer")}
            for u in units]}
    else:
        return RowResult("judgement", dict(row), f"is_a_plot is {plot!r}")
    nothing_to_check = plot == "yes" and not units
    stop = _verdict(row, derived, f"is_a_plot {plot!r} and the axis answers",
                    na_means="PASS" if nothing_to_check else None)
    if stop:
        return stop
    new["decision"] = derived
    return _settle(row, new)


def pau_verify(row: Mapping[str, Any]) -> Optional[str]:
    plot, units = row.get("is_a_plot"), row.get("units_provided") or []
    answers = [u.get("answer") for u in units]
    if plot == "no":
        ok = row.get("decision") == "not_applicable" and not units
    elif plot == "yes" and not units:
        ok = row.get("decision") == "PASS"
    else:
        ok = (plot == "yes" and units and all(a in ("yes", "no", "not_required") for a in answers)
              and row.get("decision") == ("FAIL" if "no" in answers else "PASS"))
    return None if ok else f"is_a_plot {plot!r}, answers {answers}, decision {row.get('decision')!r}"


def pgl_rule(row: Mapping[str, Any]) -> RowResult:
    """plot-gap-labeling: not a plot is not_applicable; FAIL only for an unmarked jump."""
    plot, anomaly, marked = row.get("is_a_plot"), row.get("tick_sequence_anomaly"), row.get("gap_visually_marked")
    if plot == "no":
        if anomaly != "not_applicable" or marked != "not_applicable":
            return RowResult("judgement", dict(row), f"not a plot, but anomaly {anomaly!r}, marked {marked!r}")
        derived = "not_applicable"
    elif plot == "yes" and anomaly == "no" and marked in ("not_applicable", "not_required"):
        # No anomaly: there is no gap to mark -- not_required, a real answer
        # (decided 2026-10-02), where the gold said not_applicable.
        derived = "PASS"
        row = {**row, "gap_visually_marked": "not_required"}
    elif plot == "yes" and anomaly == "yes" and marked in ("yes", "no"):
        derived = "PASS" if marked == "yes" else "FAIL"
    else:
        return RowResult("judgement", dict(row), f"is_a_plot {plot!r}, anomaly {anomaly!r}, marked {marked!r}")
    original = {k: (v if k != "gap_visually_marked" else marked) for k, v in row.items()}
    stop = _verdict(original, derived, f"anomaly {anomaly!r}, marked {marked!r}")
    if stop:
        return stop
    new = {**row, "decision": derived}
    if original.get("decision") in (None, ""):
        return RowResult("blank", new, f"blank decision; the rule gives {derived}")
    return RowResult("unchanged" if new == original else "mechanical", new)


def pgl_verify(row: Mapping[str, Any]) -> Optional[str]:
    return None if pgl_rule(row).kind == "unchanged" else f"decision {row.get('decision')!r} breaks the rule"


def ssl_rule(row: Mapping[str, Any]) -> RowResult:
    """stat-significance-level: not a plot is not_applicable; a plot with no
    symbols has nothing to fail and is a PASS (decided 2026-10-02, the
    individual-data-points model -- and what the skill always said)."""
    plot = row.get("is_a_plot")
    symbols, defined = row.get("significance_level_symbols_on_image") or [], row.get("symbols_defined") or []
    if plot == "no":
        if symbols or defined:
            return RowResult("judgement", dict(row), "not a plot, but it lists symbols")
        derived = "not_applicable"
    elif plot == "yes" and not symbols:
        derived = "PASS"
    elif plot == "yes":
        if len(defined) != len(symbols) or any(d not in ("yes", "no") for d in defined):
            return RowResult("judgement", dict(row), f"{len(symbols)} symbols but symbols_defined {defined}")
        derived = "FAIL" if "no" in defined else "PASS"
    else:
        return RowResult("judgement", dict(row), f"is_a_plot is {plot!r}")
    stop = _verdict(row, derived, f"is_a_plot {plot!r} and {len(symbols)} symbol(s)",
                    na_means="PASS" if plot == "yes" and not symbols else None)
    return stop or _settle(row, {**row, "decision": derived})


def ssl_verify(row: Mapping[str, Any]) -> Optional[str]:
    return None if ssl_rule(row).kind == "unchanged" else f"decision {row.get('decision')!r} breaks the rule"


# ---------------------------------------------------------------------------
# stat-test, replication-reporting  (decided 2026-10-03)
# ---------------------------------------------------------------------------

def st_rule(row: Mapping[str, Any]) -> RowResult:
    """stat-test: a non-plot is not_applicable throughout; a plot that makes no
    significance claim needs no test (statistical_test_mentioned not_required,
    PASS); a claim fails only if the test is not named.

    The gold's PASS on a non-plot is renamed to not_applicable as a class.
    """
    plot, needed = row.get("is_a_plot"), row.get("statistical_test_needed")
    mentioned, caption = row.get("statistical_test_mentioned"), row.get("from_the_caption") or ""
    decision = row.get("decision") or ""
    if plot == "no":
        if needed not in ("no", "not_applicable") or mentioned not in ("not needed", "not_applicable"):
            return RowResult("judgement", dict(row), f"not a plot, but needed {needed!r}, mentioned {mentioned!r}")
        if caption:
            return RowResult("judgement", dict(row), "not a plot, but from_the_caption holds text")
        derived, fields, accepted = "not_applicable", {
            "statistical_test_needed": "not_applicable", "statistical_test_mentioned": "not_applicable",
            "from_the_caption": ""}, ("", "PASS", "not_applicable")
    elif plot == "yes" and needed == "no":
        if mentioned not in ("not needed", "not_required"):
            return RowResult("judgement", dict(row), f"no test needed, but mentioned {mentioned!r}")
        derived, fields, accepted = "PASS", {"statistical_test_mentioned": "not_required"}, ("", "PASS")
    elif plot == "yes" and needed == "yes":
        if mentioned not in ("yes", "no"):
            return RowResult("judgement", dict(row), f"a test is needed, but mentioned {mentioned!r}")
        derived = "PASS" if mentioned == "yes" else "FAIL"
        fields, accepted = {}, ("", derived)
    else:
        return RowResult("judgement", dict(row), f"is_a_plot {plot!r}, needed {needed!r}")
    if decision not in accepted:
        return RowResult("judgement", dict(row), f"decision {decision!r}, but the rule gives {derived}")
    new = {**row, **fields, "decision": derived}
    if decision == "":
        return RowResult("blank", new, f"blank decision; the rule gives {derived}")
    return RowResult("unchanged" if new == dict(row) else "mechanical", new)


def rr_rule(row: Mapping[str, Any]) -> RowResult:
    """replication-reporting: applies to panels involving replicates. Not
    involving them (or unclear) is not_applicable; involving them, PASS when
    both n and replicate type are reported, else FAIL. Whether n is large
    enough is n-larger-two's question, not this one's.

    Renamed as classes: the gold's PASS on a panel without replicates becomes
    not_applicable, and its FAIL for n below 3 with both reported becomes PASS.
    """
    involves = row.get("involves_replicates")
    n_rep, t_rep = row.get("n_reported"), row.get("replicate_type_reported")
    decision = row.get("decision") or ""
    rtype = row.get("replicate_type") or ""
    rtype = "" if rtype in ("not_applicable", "not_reported") else rtype
    if involves in ("no", "unclear"):
        if n_rep != "not_applicable" or t_rep != "not_applicable":
            return RowResult("judgement", dict(row),
                             f"involves_replicates {involves!r}, but n_reported {n_rep!r}, type {t_rep!r}")
        derived, fields, accepted = "not_applicable", {
            "n_value_min": "not_applicable", "replicate_type": ""}, ("", "PASS", "not_applicable")
    elif involves == "yes":
        if n_rep not in ("yes", "no") or t_rep not in ("yes", "no"):
            return RowResult("judgement", dict(row), f"involves replicates, but n_reported {n_rep!r}, type {t_rep!r}")
        derived = "PASS" if (n_rep, t_rep) == ("yes", "yes") else "FAIL"
        accepted = ("", derived) + (("FAIL",) if derived == "PASS" else ())
        n_min = row.get("n_value_min")
        if n_rep == "no" and n_min not in ("not_reported", "not_applicable", None, ""):
            return RowResult("judgement", dict(row), f"n not reported, but n_value_min is {n_min!r}")
        fields = {"replicate_type": rtype if t_rep == "yes" else ""}
        if n_rep == "no":
            fields["n_value_min"] = "not_reported"
    else:
        return RowResult("judgement", dict(row), f"involves_replicates is {involves!r}")
    if decision not in accepted:
        return RowResult("judgement", dict(row), f"decision {decision!r}, but the rule gives {derived}")
    new = {**row, **fields, "decision": derived}
    if decision == "":
        return RowResult("blank", new, f"blank decision; the rule gives {derived}")
    return RowResult("unchanged" if new == dict(row) else "mechanical", new)


# ---------------------------------------------------------------------------
# micrograph-scale-bar  (decided 2026-10-05)
# ---------------------------------------------------------------------------

MSB_ENUMS = ("scale_bar_on_image", "scale_bar_defined_in_caption", "scale_bar_defined_in_image")


def msb_rule(row: Mapping[str, Any]) -> RowResult:
    """micrograph-scale-bar: a panel that is not a micrograph is not_applicable
    in the three yes/no fields, where the gold had an empty string; its two
    extracted texts stay empty. A micrograph keeps yes or no throughout: one
    without a scale bar fails the check, so its "defined" fields are "no",
    not not_required.
    """
    values = {f: row.get(f) for f in MSB_ENUMS}
    texts = [row.get("from_the_caption") or "", row.get("from_the_image") or ""]
    micrograph = row.get("micrograph")
    if micrograph == "no":
        if any(v not in ("", "not_applicable") for v in values.values()) or any(texts):
            return RowResult("judgement", dict(row), f"not a micrograph, but {values}, texts {texts}")
        new = {**row, **{f: "not_applicable" for f in MSB_ENUMS}}
    elif micrograph == "yes":
        if any(v not in ("yes", "no") for v in values.values()):
            return RowResult("judgement", dict(row), f"a micrograph, but {values}")
        new = dict(row)
    else:
        return RowResult("judgement", dict(row), f"micrograph is {micrograph!r}")
    return RowResult("unchanged" if new == dict(row) else "mechanical", new)


def _verify_by_rule(rule):
    return lambda row: None if rule(row).kind == "unchanged" else f"breaks the rule: {rule(row).reason}"


#: Per-check steps that add a field the rule needs before it runs.
ENRICH: Dict[str, Callable] = {"error-bars-defined": _enrich_is_a_plot}

RULES: Dict[str, Tuple[Callable, Callable]] = {
    "individual-data-points": (idp_rule, idp_verify),
    "error-bars-defined": (ebd_rule, ebd_verify),
    "plot-axis-units": (pau_rule, pau_verify),
    "plot-gap-labeling": (pgl_rule, pgl_verify),
    "stat-significance-level": (ssl_rule, ssl_verify),
    "stat-test": (st_rule, _verify_by_rule(st_rule)),
    "replication-reporting": (rr_rule, _verify_by_rule(rr_rule)),
    "micrograph-scale-bar": (msb_rule, _verify_by_rule(msb_rule)),
}


# ---------------------------------------------------------------------------
# Running a migration
# ---------------------------------------------------------------------------

def gold_files(check: str, examples: Optional[Path] = None) -> List[Path]:
    # Resolved at call time, not bound as a default, so the gold location can
    # be redirected -- by a test, or by a gold-location override.
    examples = examples or EXAMPLES
    return sorted(examples.glob(f"**/checks/{check}/expected_output.json"))


def example_of(path: Path, examples: Optional[Path] = None) -> str:
    return str(path.relative_to(examples or EXAMPLES).parent.parent.parent)


#: Fields a curation file may set, per check.
CURATED_FIELDS = {
    "individual-data-points": ("plot", "individual_values", "decision"),
    "error-bars-defined": ("is_a_plot", "error_bar_on_figure", "error_bar_defined_in_caption",
                           "from_the_caption", "decision", "explanation"),
    "plot-axis-units": ("is_a_plot", "decision"),
    "plot-gap-labeling": ("is_a_plot", "tick_sequence_anomaly", "gap_visually_marked", "decision"),
    "stat-significance-level": ("is_a_plot", "decision"),
    "stat-test": ("is_a_plot", "statistical_test_needed", "statistical_test_mentioned",
                  "from_the_caption", "decision"),
    "replication-reporting": ("involves_replicates", "n_reported", "n_value_min",
                              "replicate_type_reported", "replicate_type", "decision"),
}

Overrides = Dict[Tuple[str, str], Dict[str, str]]


def read_curation(check: str, paths: List[Path]) -> Overrides:
    """(example, panel) -> {field: value}, from one or more curation CSVs."""
    overrides: Overrides = {}
    for path in paths:
        with open(path, newline="", encoding="utf-8") as handle:
            for line in csv.DictReader(handle):
                key = (line["example"], line["panel"])
                if key in overrides:
                    raise ValueError(f"{path}: {key} is curated twice")
                overrides[key] = {f: line[f] for f in CURATED_FIELDS[check]
                                  if line.get(f) not in (None, "")}
    return overrides


def plan(check: str, examples: Optional[Path] = None,
         overrides: Optional[Overrides] = None) -> List[Tuple[Path, int, RowResult]]:
    """Every gold row of a check, sorted by the rule -- after any curation.

    A curated row's ``new`` holds the curator's values as well as the rule's;
    its ``kind`` is whatever the rule makes of them, so a judgement that
    contradicts the rule is reported as a judgement still.
    """
    rule, _ = RULES[check]
    overrides = dict(overrides or {})
    used = set()
    results = []
    for path in gold_files(check, examples):
        gold = json.loads(path.read_text(encoding="utf-8"))
        example = example_of(path, examples)
        for index, row in enumerate(gold.get("outputs", [])):
            if not isinstance(row, dict):
                continue
            key = (example, row.get("panel_label"))
            enrich = ENRICH.get(check)
            source = enrich(row, example, examples or EXAMPLES) if enrich else row
            curated = {**source, **overrides[key]} if key in overrides else source
            if key in overrides:
                if key in used:
                    raise ValueError(f"{key} matches more than one gold row")
                used.add(key)
            result = rule(curated)
            if (curated is not row) and result.kind in ("unchanged", "mechanical"):
                result = RowResult("unchanged" if result.new == row else "mechanical",
                                   result.new, "curated")
            results.append((path, index, result))
    unmatched = sorted(set(overrides) - used)
    if unmatched:
        raise ValueError(f"curation lines match no gold row: {unmatched}")
    return results


def _file_format(text: str) -> Dict[str, Any]:
    """How a gold file is laid out, so a rewrite changes only its values.

    Most gold is the curation app's format -- 4-space indent, non-ASCII kept,
    no trailing newline -- but some files were written by other tools, and a
    migration that normalised them would bury its real changes in the diff.
    """
    second = text.split("\n", 2)[1] if text.count("\n") >= 1 else ""
    indent = len(second) - len(second.lstrip(" ")) or 4
    escaped = "\\u" in text and not any(ord(ch) > 127 for ch in text)
    return {"indent": indent, "ensure_ascii": escaped, "newline": text.endswith("\n")}


def _dump_like(record: Any, fmt: Mapping[str, Any]) -> str:
    out = json.dumps(record, indent=fmt["indent"], ensure_ascii=fmt["ensure_ascii"])
    return out + ("\n" if fmt["newline"] else "")


def contracted(record: Mapping[str, Any], schema: Mapping[str, Any]) -> Dict[str, Any]:
    allowed = set(schema.get("properties") or {})
    return {k: v for k, v in record.items() if k in allowed}


def write(check: str, results, *, fill_blank: bool, examples: Optional[Path] = None,
          checklist: Optional[Path] = None) -> List[Path]:
    """Apply the plan; return the gold files rewritten."""
    import jsonschema

    _, verify = RULES[check]
    checklist = checklist or CHECKLIST
    schema = json.loads((checklist / check / "schema.json").read_text())["format"]["schema"]
    row_validator = jsonschema.Draft7Validator(schema["properties"]["outputs"]["items"])
    by_file: Dict[Path, Dict[int, RowResult]] = {}
    for path, index, result in results:
        by_file.setdefault(path, {})[index] = result

    written = []
    for path, rows in by_file.items():
        original = path.read_text(encoding="utf-8")
        fmt = _file_format(original)
        gold = json.loads(original)
        changed = False
        for index, result in rows.items():
            if result.kind == "mechanical" or (result.kind == "blank" and fill_blank):
                gold["outputs"][index] = result.new
                changed = True
        if not changed:
            continue
        for index, row in enumerate(gold["outputs"]):
            # Rows this run leaves alone are not checked against the rule:
            # a judgement row waits for a curator (and main() refuses to
            # write while any exist), a blank waits for --fill-blank.
            kind = rows[index].kind if index in rows else "unchanged"
            if kind == "judgement" or (kind == "blank" and not fill_blank):
                continue
            problem = verify(row)
            if problem:
                raise AssertionError(f"{path}: row {index} breaks the rule after migration: {problem}")
            row_validator.validate(row)
        path.write_text(_dump_like(gold, fmt), encoding="utf-8")
        html = path.with_name("expected_output.html")
        if html.is_file():
            from soda_mmqc.lib.expected_output_html import output_to_html
            html.write_text(output_to_html(gold, title=f"Expected output — {check}"),
                            encoding="utf-8")
        written.append(path)
    return written


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("check", choices=sorted(RULES))
    parser.add_argument("--write", action="store_true",
                        help="Apply the mechanical changes (refused while judgement rows remain)")
    parser.add_argument("--fill-blank", action="store_true",
                        help="Also fill blank values the rule can derive")
    parser.add_argument("--benchmark-only", action="store_true",
                        help="List only rows in the check's benchmark figures")
    parser.add_argument("--curation", action="append", type=Path, default=[],
                        help="A curator's decisions to apply first (CSV); repeatable")
    args = parser.parse_args(argv)

    results = plan(args.check, overrides=read_curation(args.check, args.curation))
    bench = set(json.loads((CHECKLIST / args.check / "benchmark.json").read_text())["examples"])
    from collections import Counter
    counts = Counter(r.kind for _, _, r in results)
    print(f"{args.check}: {len(results)} gold rows in {len({p for p, _, _ in results})} files — "
          + ", ".join(f"{k} {counts[k]}" for k in ("unchanged", "mechanical", "blank", "judgement")))

    for kind, title in (("judgement", "Rows needing a judgement (changed by no one but a curator)"),
                        ("blank", "Blank values the rule would fill (only with --fill-blank)")):
        rows = [(p, i, r) for p, i, r in results if r.kind == kind
                and (not args.benchmark_only or example_of(p) in bench)]
        if not rows:
            continue
        print(f"\n{title}: {len(rows)}")
        for path, index, result in rows:
            gold = json.loads(path.read_text(encoding="utf-8"))
            label = gold["outputs"][index].get("panel_label")
            mark = "benchmark" if example_of(path) in bench else "         "
            print(f"  {mark}  {example_of(path)} · panel {label}: {result.reason}")

    if not args.write:
        print("\nDry run: nothing written. --write applies the mechanical changes.")
        return 0
    if counts["judgement"]:
        print(f"\nRefusing to write: {counts['judgement']} row(s) need a judgement first.")
        return 1
    written = write(args.check, results, fill_blank=args.fill_blank)
    print(f"\nWrote {len(written)} gold file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
