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
        if key == "Decision_and_explanation":
            out["decision"], out["explanation"] = decision, explanation
        elif key not in ("decision", "explanation"):
            out[key] = fields.get(key, value)
        else:
            out[key] = value
    out.update({k: v for k, v in fields.items() if k in out})
    if "decision" not in out:
        out["decision"], out["explanation"] = decision, explanation
    return out


def ebd_rule(row: Mapping[str, Any]) -> RowResult:
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

    if on_figure == "no":
        if defined not in ("not needed", "not_applicable"):
            return RowResult("judgement", dict(row),
                             f"no error bars, but defined_in_caption is {defined!r}")
        if caption not in ("", "not needed", None):
            return RowResult("judgement", dict(row),
                             f"no error bars, but from_the_caption holds text")
        if verdict not in ("", "not_applicable"):
            return RowResult("judgement", dict(row), f"no error bars, but the verdict is {verdict!r}")
        new = _ebd_row(row, "not_applicable", explanation,
                       error_bar_defined_in_caption="not_applicable", from_the_caption="")
        kind = "blank" if verdict == "" else None
    elif on_figure == "yes":
        if defined not in ("yes", "no"):
            return RowResult("judgement", dict(row),
                             f"error bars present, but defined_in_caption is {defined!r}")
        derived = "PASS" if defined == "yes" else "FAIL"
        if verdict not in ("", derived):
            return RowResult("judgement", dict(row),
                             f"verdict {verdict!r}, but defined_in_caption {defined!r} gives {derived}")
        new = _ebd_row(row, derived, explanation)
        kind = "blank" if verdict == "" else None
    else:
        return RowResult("judgement", dict(row), f"error_bar_on_figure is {on_figure!r}")

    if kind == "blank":
        return RowResult("blank", new, f"blank verdict; the rule gives {new['decision']}")
    return RowResult("unchanged" if new == dict(row) else "mechanical", new)


def ebd_verify(row: Mapping[str, Any]) -> Optional[str]:
    if "Decision_and_explanation" in row:
        return "Decision_and_explanation is still present"
    on_figure, defined, decision = (row.get("error_bar_on_figure"),
                                    row.get("error_bar_defined_in_caption"), row.get("decision"))
    ok = ((on_figure == "no" and defined == "not_applicable" and decision == "not_applicable"
           and row.get("from_the_caption") == "")
          or (on_figure == "yes" and defined == "yes" and decision == "PASS")
          or (on_figure == "yes" and defined == "no" and decision == "FAIL"))
    return None if ok else f"on_figure {on_figure!r}, defined {defined!r}, decision {decision!r}"


# ---------------------------------------------------------------------------
# plot-axis-units, plot-gap-labeling, stat-significance-level
# ---------------------------------------------------------------------------
#
# Their decision held N/A, scored as a class; it becomes not_applicable (C1).
# The prose (v1/SKILL.md, 2026-10-02) gives each rule below.

_NA = ("N/A", "not_applicable")


def _verdict(row, derived: str, reason: str) -> Optional[RowResult]:
    """A judgement if the gold's decision is neither blank nor the derived one."""
    current = row.get("decision")
    current = "not_applicable" if current in _NA else current
    if current not in (None, "", derived):
        return RowResult("judgement", dict(row), f"decision {row.get('decision')!r}, but {reason} gives {derived}")
    return None


def _settle(row, new) -> RowResult:
    if row.get("decision") in (None, ""):
        return RowResult("blank", new, f"blank decision; the rule gives {new['decision']}")
    return RowResult("unchanged" if new == dict(row) else "mechanical", new)


def pau_rule(row: Mapping[str, Any]) -> RowResult:
    """plot-axis-units: not a plot, or a plot with no axes, is not_applicable;
    a plot fails if any axis lacks its unit.

    units_provided[].answer "not needed" -- an axis that needs no unit -- is
    not_required, a real answer; a plot with no axes, such as a pie chart, has
    nothing to check (both decided 2026-10-02).
    """
    plot, units = row.get("is_a_plot"), row.get("units_provided") or []
    if plot == "yes" and not units and not row.get("unit_definition_as_provided"):
        derived = "not_applicable"
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
    stop = _verdict(row, derived, f"is_a_plot {plot!r} and the axis answers")
    if stop:
        return stop
    new["decision"] = derived
    return _settle(row, new)


def pau_verify(row: Mapping[str, Any]) -> Optional[str]:
    plot, units = row.get("is_a_plot"), row.get("units_provided") or []
    answers = [u.get("answer") for u in units]
    if plot == "no" or (plot == "yes" and not units):
        ok = row.get("decision") == "not_applicable" and not units
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
    elif plot == "yes" and anomaly == "no" and marked == "not_applicable":
        derived = "PASS"
    elif plot == "yes" and anomaly == "yes" and marked in ("yes", "no"):
        derived = "PASS" if marked == "yes" else "FAIL"
    else:
        return RowResult("judgement", dict(row), f"is_a_plot {plot!r}, anomaly {anomaly!r}, marked {marked!r}")
    stop = _verdict(row, derived, f"anomaly {anomaly!r}, marked {marked!r}")
    return stop or _settle(row, {**row, "decision": derived})


def pgl_verify(row: Mapping[str, Any]) -> Optional[str]:
    return None if pgl_rule(row).kind == "unchanged" else f"decision {row.get('decision')!r} breaks the rule"


def ssl_rule(row: Mapping[str, Any]) -> RowResult:
    """stat-significance-level: not a plot, or no symbols, is not_applicable (decided 2026-10-02)."""
    plot = row.get("is_a_plot")
    symbols, defined = row.get("significance_level_symbols_on_image") or [], row.get("symbols_defined") or []
    if plot == "no":
        if symbols or defined:
            return RowResult("judgement", dict(row), "not a plot, but it lists symbols")
        derived = "not_applicable"
    elif plot == "yes" and not symbols:
        derived = "not_applicable"
    elif plot == "yes":
        if len(defined) != len(symbols) or any(d not in ("yes", "no") for d in defined):
            return RowResult("judgement", dict(row), f"{len(symbols)} symbols but symbols_defined {defined}")
        derived = "FAIL" if "no" in defined else "PASS"
    else:
        return RowResult("judgement", dict(row), f"is_a_plot is {plot!r}")
    stop = _verdict(row, derived, f"is_a_plot {plot!r} and {len(symbols)} symbol(s)")
    return stop or _settle(row, {**row, "decision": derived})


def ssl_verify(row: Mapping[str, Any]) -> Optional[str]:
    return None if ssl_rule(row).kind == "unchanged" else f"decision {row.get('decision')!r} breaks the rule"


RULES: Dict[str, Tuple[Callable, Callable]] = {
    "individual-data-points": (idp_rule, idp_verify),
    "error-bars-defined": (ebd_rule, ebd_verify),
    "plot-axis-units": (pau_rule, pau_verify),
    "plot-gap-labeling": (pgl_rule, pgl_verify),
    "stat-significance-level": (ssl_rule, ssl_verify),
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
    "error-bars-defined": ("error_bar_on_figure", "error_bar_defined_in_caption",
                           "from_the_caption", "decision", "explanation"),
    "plot-axis-units": ("is_a_plot", "decision"),
    "plot-gap-labeling": ("is_a_plot", "tick_sequence_anomaly", "gap_visually_marked", "decision"),
    "stat-significance-level": ("is_a_plot", "decision"),
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
            curated = {**row, **overrides[key]} if key in overrides else row
            if key in overrides:
                if key in used:
                    raise ValueError(f"{key} matches more than one gold row")
                used.add(key)
            result = rule(curated)
            if curated is not row and result.kind in ("unchanged", "mechanical"):
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
