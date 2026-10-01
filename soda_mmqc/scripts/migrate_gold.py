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

A run is idempotent: rows already in the new vocabulary are left alone, so it
can be re-run after any amount of curation. ``--write`` rewrites only files
whose content changes, in the curation app's own format (4-space JSON, no
trailing newline, and its ``expected_output.html`` where one exists), and
verifies every rewritten row against the check's schema and rule.
"""

from __future__ import annotations

import argparse
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


RULES: Dict[str, Tuple[Callable, Callable]] = {
    "individual-data-points": (idp_rule, idp_verify),
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


def plan(check: str, examples: Optional[Path] = None) -> List[Tuple[Path, int, RowResult]]:
    rule, _ = RULES[check]
    results = []
    for path in gold_files(check, examples):
        gold = json.loads(path.read_text(encoding="utf-8"))
        for index, row in enumerate(gold.get("outputs", [])):
            if isinstance(row, dict):
                results.append((path, index, rule(row)))
    return results


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
        gold = json.loads(path.read_text(encoding="utf-8"))
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
        path.write_text(json.dumps(gold, indent=4, ensure_ascii=False), encoding="utf-8")
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
    args = parser.parse_args(argv)

    results = plan(args.check)
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
