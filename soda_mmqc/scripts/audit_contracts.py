"""Audit every check's output schema against its eval manifest.

    python -m soda_mmqc.scripts.audit_contracts            # contracts only
    python -m soda_mmqc.scripts.audit_contracts --runs     # and what the runs wrote

A contract has two halves that must agree: the schema says what a session may
write, the manifest says how each field is scored. Where they disagree, a
correct judgement can be scored as a wrong one. The case that prompted this:
`error-bars-defined · Decision_and_explanation` is free text, the manifest
treats only the exact token "not needed" as not applicable, and a session that
writes "not needed - micrograph panel with no error bars." is scored as an
applicable answer (exp-03, addendum of 2026-09-30).

Rules, one per way the halves can disagree:

``invisible`` a schema field the scorer's own discovery does not see -- it is
              never scored, and nothing says so. A field typed only through
              ``anyOf`` is the known case (`replication-reporting ·
              n_value_min`)
``default``   a field with no manifest entry inherits a default metric whose
              tokens do not fit the schema's values -- it is scored by a rule
              nobody chose for it
``na-text``   a field whose not-applicable tokens are free text: nothing stops
              the model writing the token with an annotation
``polar-text`` a field scored as a yes/no polarity whose schema is free text
``enum-na``   an enum offering a not-applicable-looking value the manifest
              scores as an ordinary class -- applicability then moves from
              layer 1 to layer 2, unlike checks that treat it as NA
``enum-gap``  an enum missing a token the manifest scores against

``--runs`` counts, for every flagged field, how often committed predictions
wrote a token exactly, wrote it with an annotation, or wrote something else.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from soda_mmqc.core.schema_discovery import discover_schema  # noqa: E402
CHECKLISTS = REPO / "soda_mmqc" / "data" / "checklist"
RUNS = REPO / "experiments" / "runs"

#: Values that read as "not applicable" in a schema enum or description.
NA_LIKE = re.compile(
    r"^(not[ _]?(needed|applicable)|n/?a|none)$", re.IGNORECASE
)


def leaves(node: Mapping[str, Any], prefix: str = "") -> Iterator[Tuple[str, Mapping]]:
    """(manifest pattern, schema node) for every scored leaf."""
    kind = node.get("type")
    kind = kind[0] if isinstance(kind, list) else kind
    if kind == "object":
        for name, child in node.get("properties", {}).items():
            yield from leaves(child, f"{prefix}.{name}" if prefix else name)
    elif kind == "array":
        items = node.get("items", {})
        if items.get("type") == "object":
            for name, child in items.get("properties", {}).items():
                yield from leaves(child, f"{prefix}[].{name}")
        else:
            yield prefix, items
    else:
        yield prefix, node


def enum_of(node: Mapping[str, Any]) -> Optional[List[str]]:
    """The fixed values a node allows, including through ``anyOf``."""
    if "enum" in node:
        return list(node["enum"])
    found = [v for alt in node.get("anyOf", []) for v in alt.get("enum", [])]
    return found or None


def is_free_text(node: Mapping[str, Any]) -> bool:
    if enum_of(node):
        return False
    kinds = [node.get("type")] + [a.get("type") for a in node.get("anyOf", [])]
    return "string" in kinds


def audit_check(checklist: str, check_dir: Path) -> List[Dict[str, Any]]:
    manifest = json.loads((check_dir / "eval-manifest.json").read_text())
    schema = json.loads((check_dir / "schema.json").read_text())["format"]["schema"]
    defaults = manifest.get("defaults", {})
    visible = {spec.pattern for spec in discover_schema(schema)}
    findings = []
    for pattern, node in leaves(schema):
        if pattern.endswith("panel_label"):
            continue
        if pattern not in visible:
            findings.append({
                "checklist": checklist, "check": check_dir.name, "field": pattern,
                "rule": "invisible",
                "detail": "not discovered by the scorer, so never scored "
                          f"(schema node has no 'type': {sorted(node)})",
                "tokens": [],
            })
            continue
        own = manifest.get("fields", {}).get(pattern)
        profile = {**defaults, **(own or {})}
        metric = profile.get("matching_metric")
        na = [v for v in profile.get("na_values", []) if v != ""]
        polar = [profile.get("positive_value"), profile.get("negative_value")]
        values = enum_of(node)
        rules = []
        if own is None and metric == "binary_polarity" and (
            values is None or not set(values) <= set(polar) | set(na) | {""}
        ):
            rules.append(("default", f"inherits binary_polarity {polar}; schema allows "
                                     f"{values or node.get('type') or 'anyOf'}"))
        if na and is_free_text(node):
            rules.append(("na-text", f"not-applicable token(s) {na} in a free-text field"))
        if metric == "binary_polarity" and own is not None and is_free_text(node):
            rules.append(("polar-text", f"scored as {polar} but free text"))
        if values:
            na_like = [v for v in values if NA_LIKE.match(str(v)) and v not in na]
            if na_like:
                rules.append(("enum-na", f"enum value(s) {na_like} scored as a class, not as NA"))
            if metric == "binary_polarity":
                missing = [t for t in polar + na if t and t not in values]
                if missing:
                    rules.append(("enum-gap", f"enum lacks {missing}"))
        for rule, detail in rules:
            findings.append({
                "checklist": checklist, "check": check_dir.name, "field": pattern,
                "rule": rule, "detail": detail,
                "tokens": sorted(set(na) | ({t for t in polar if t} if metric == "binary_polarity" else set())),
            })
    return findings


def run_values(checks: Sequence[str]) -> Dict[Tuple[str, str], Counter]:
    """Every string a committed prediction wrote, per (check, row field)."""
    seen: Dict[Tuple[str, str], Counter] = defaultdict(Counter)
    known = set(checks)
    for pred in RUNS.rglob("prediction.json"):
        parts = pred.relative_to(RUNS).parts
        if any(p == "smoke" or p.endswith("superseded") for p in parts):
            continue
        try:
            data = json.loads(pred.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        check = next((p for p in parts if p in known), None)
        lists = ({check: data["outputs"]} if check and "outputs" in data
                 else {k: v for k, v in data.items() if k in known and isinstance(v, list)})
        for name, rows in lists.items():
            for row in rows:
                if isinstance(row, dict):
                    for key, value in row.items():
                        if isinstance(value, str):
                            seen[(name, f"outputs[].{key}")][value] += 1
    return seen


def annotated(value: str, token: str) -> bool:
    """``token`` followed by a separator and more text: "not needed - …"."""
    v, t = value.strip().lower(), token.lower()
    return v != t and v.startswith(t) and bool(re.match(r"[\s\-–:;,.(]", v[len(t):]))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--runs", action="store_true",
                        help="Also count what committed predictions wrote in each flagged field")
    args = parser.parse_args(argv)

    findings: List[Dict[str, Any]] = []
    for checklist in sorted(c for c in CHECKLISTS.iterdir() if c.is_dir()):
        for check_dir in sorted(checklist.iterdir()):
            if (check_dir / "schema.json").is_file() and (check_dir / "eval-manifest.json").is_file():
                findings += audit_check(checklist.name, check_dir)

    seen = run_values(sorted({f["check"] for f in findings})) if args.runs else {}
    for f in findings:
        line = f"{f['rule']:<10} {f['checklist']}/{f['check']} · {f['field']}: {f['detail']}"
        values = seen.get((f["check"], f["field"].replace(f"{f['check']}[]", "outputs[]")))
        if args.runs and values and f["tokens"]:
            total = sum(values.values())
            exact = sum(n for v, n in values.items() if v in f["tokens"])
            ann = sum(n for v, n in values.items() if any(annotated(v, t) for t in f["tokens"]))
            line += f"  [runs: {total} values, {exact} exact token, {ann} annotated token]"
        print(line)
    print(f"\n{len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
