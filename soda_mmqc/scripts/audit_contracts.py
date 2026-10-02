"""Audit every check's output schema against its eval manifest and its gold.

    python -m soda_mmqc.scripts.audit_contracts                       # every checklist
    python -m soda_mmqc.scripts.audit_contracts --checklist fig-checklist
    python -m soda_mmqc.scripts.audit_contracts --runs                # and what runs wrote

A contract has halves that must agree: the schema says what a session may
write, the manifest says how each field is scored, and the gold is what it is
scored against. Where they disagree, a correct judgement can be scored as a
wrong one. The case that prompted this: `error-bars-defined ·
Decision_and_explanation` is free text, the manifest treats only the exact
token "not needed" as not applicable, and a session writing "not needed -
micrograph panel with no error bars." is scored as an applicable answer
(exp-03, addendum of 2026-09-30). The conventions the rules enforce are in
thinking/plans/2026-09-30-contract-cleanup.md (C1-C5).

Rules:

``no-manifest``   a check with a schema and no manifest
``untyped``       a field the scorer cannot type, and so cannot score (C5)
``default``       a field with no manifest entry inherits a default polarity
                  that does not fit the schema's values -- scored by a rule
                  nobody chose for it
``na-text``       a not-applicable token in a free-text field (C3)
``polar-text``    a field scored as a yes/no polarity whose schema is free text
``enum-na``       an enum value meaning "not applicable" that the manifest
                  scores as an ordinary class, at layer 2 (C1)
``enum-gap``      an enum missing a token the manifest scores against
``legacy-token``  a not-applicable spelling other than ``not_applicable``, in
                  the schema, the manifest or the gold (C1)
``orphan-token``  a manifest token that neither the schema nor the gold uses
``text-metric``   free text not scored semantically, unless declared an
                  identifier in IDENTIFIERS (C4)
``gold-off-enum`` gold holding a value its own schema's enum does not allow --
                  an answer no strict session can give, so a forced mismatch
``gold-control``  gold text holding control characters (NUL, \\x04, \\r ...):
                  damaged text, usually where a character was lost

The experiment checklists are frozen copies of the contracts their runs were
scored against, so they keep their legacy findings by design; scope the audit
with ``--checklist`` to the contracts that are meant to be clean.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Set, Tuple

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from soda_mmqc.core.schema_discovery import (  # noqa: E402
    SchemaTypingError,
    discover_schema,
)

CHECKLISTS = REPO / "soda_mmqc" / "data" / "checklist"
EXAMPLES = REPO / "soda_mmqc" / "data" / "examples"
RUNS = REPO / "experiments" / "runs"

#: Control characters that do not belong in gold text: everything below 0x20
#: except tab and newline, and DEL.
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

#: The one not-applicable token (C1).
CANONICAL_NA = "not_applicable"

#: Spellings that mean "not applicable". `not_reported` and `unclear` are real
#: answers (C2) and deliberately absent.
NA_LIKE = re.compile(
    r"^(not[ _-]?(needed|applicable)|n/?a|not[ _-]?a[ _-]?plot)$", re.IGNORECASE
)

#: Free-text fields scored exactly on purpose, because they are identifiers --
#: a symbol, URL, accession or section name -- not prose (C4). Keyed by
#: (check, field pattern), each with its reason. Filled at gate G2.
IDENTIFIERS: Dict[Tuple[str, str], str] = {
    ("stat-significance-level", "outputs[].significance_level_symbols_on_image"):
        "significance symbols: *, ** and ns are different answers",
}


@dataclass(frozen=True)
class Finding:
    checklist: str
    check: str
    field: str
    rule: str
    detail: str
    tokens: Tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

def leaves(node: Mapping[str, Any], prefix: str = "") -> Iterator[Tuple[str, Mapping]]:
    """(manifest pattern, schema node) for every leaf, typed or not."""
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


def enum_of(node: Mapping[str, Any]) -> Optional[List[Any]]:
    """The fixed values a node allows, including through ``anyOf``/``oneOf``."""
    if "enum" in node:
        return list(node["enum"])
    alternatives = node.get("anyOf") or node.get("oneOf") or []
    found = [v for alt in alternatives for v in alt.get("enum", [])]
    return found or None


def is_free_text(node: Mapping[str, Any]) -> bool:
    if enum_of(node):
        return False
    alternatives = node.get("anyOf") or node.get("oneOf") or []
    return "string" in [node.get("type")] + [a.get("type") for a in alternatives]


def gold_values(gold_root: Path, check: str) -> Dict[str, Counter]:
    """Every string the gold holds, per row field, across all of a check's gold."""
    values: Dict[str, Counter] = defaultdict(Counter)
    for path in gold_root.glob(f"**/checks/{check}/expected_output.json"):
        try:
            gold = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for row in gold.get("outputs", []) if isinstance(gold, dict) else []:
            _collect(row, "outputs[]", values)
    return values


def _collect(row: Any, prefix: str, values: Dict[str, Counter]) -> None:
    """Strings of a row, by manifest pattern -- into lists of objects too."""
    if not isinstance(row, dict):
        return
    for key, value in row.items():
        pattern = f"{prefix}.{key}"
        for item in value if isinstance(value, list) else [value]:
            if isinstance(item, str):
                values[pattern][item] += 1
            elif isinstance(item, dict):
                _collect(item, f"{pattern}[]", values)


# ---------------------------------------------------------------------------
# The audit
# ---------------------------------------------------------------------------

def audit_check(
    checklist: str,
    check_dir: Path,
    gold_root: Path = EXAMPLES,
    identifiers: Mapping[Tuple[str, str], str] = IDENTIFIERS,
) -> List[Finding]:
    """Every finding for one check's contract."""
    check = check_dir.name
    out: List[Finding] = []

    def add(pattern: str, rule: str, detail: str, tokens: Iterable[str] = ()) -> None:
        out.append(Finding(checklist, check, pattern, rule, detail, tuple(sorted(tokens))))

    manifest_path = check_dir / "eval-manifest.json"
    if not manifest_path.is_file():
        add("", "no-manifest", "schema.json without eval-manifest.json")
        return out
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    envelope = json.loads((check_dir / "schema.json").read_text(encoding="utf-8"))
    schema = envelope.get("format", {}).get("schema", envelope)
    defaults = manifest.get("defaults", {})
    gold = gold_values(gold_root, check)

    try:
        visible = {spec.pattern for spec in discover_schema(schema)}
    except SchemaTypingError as exc:
        add("", "untyped", str(exc))
        visible = None

    for pattern, node in leaves(schema):
        if pattern.endswith("panel_label"):
            continue
        if visible is not None and pattern not in visible:
            add(pattern, "untyped", f"not discovered by the scorer (keys {sorted(node)})")
            continue
        own = manifest.get("fields", {}).get(pattern)
        if own == {"scored": False}:
            # Declared unscored (C3, C5): outside every metric rule by design.
            continue
        profile = {**defaults, **(own or {})}
        metric = profile.get("matching_metric")
        na = [v for v in profile.get("na_values", []) if v != ""]
        polar = [v for v in (profile.get("positive_value"), profile.get("negative_value")) if v]
        scored_tokens = set(na) | (set(polar) if metric == "binary_polarity" else set())
        values = enum_of(node)
        free = is_free_text(node)
        seen_gold = gold.get(pattern, Counter())

        if own is None and metric == "binary_polarity" and (
            values is None or not set(values) <= set(polar) | set(na) | {""}
        ):
            add(pattern, "default",
                f"inherits binary_polarity {polar}; schema allows {values or node.get('type') or 'a union'}",
                polar)
        if na and free:
            add(pattern, "na-text", f"not-applicable token(s) {na} in a free-text field", na)
        if metric == "binary_polarity" and own is not None and free:
            add(pattern, "polar-text", f"scored as {polar} but free text", polar)
        if values:
            unscored_na = [v for v in values if NA_LIKE.match(str(v)) and v not in na]
            if unscored_na:
                add(pattern, "enum-na", f"{unscored_na} scored as a class, not as NA", unscored_na)
            if metric == "binary_polarity":
                missing = [t for t in polar + na if t not in values]
                if missing:
                    add(pattern, "enum-gap", f"enum lacks {missing}", missing)

        damaged = {v: n for v, n in seen_gold.items() if _CONTROL.search(v)}
        if damaged:
            sample = next(iter(damaged))
            add(pattern, "gold-control",
                f"{sum(damaged.values())} gold value(s) hold control characters, e.g. {sample[:50]!r}")

        if values:
            off = {v: n for v, n in seen_gold.items() if v not in values}
            if off:
                add(pattern, "gold-off-enum",
                    f"gold holds {dict(sorted(off.items()))} outside the enum {values}",
                    off)

        legacy: Set[str] = set()
        for source, tokens in (("schema enum", values or []), ("manifest", na),
                               ("gold", seen_gold)):
            for token in tokens:
                if isinstance(token, str) and NA_LIKE.match(token) and token != CANONICAL_NA:
                    legacy.add(f"{token!r} in {source}")
        if legacy:
            add(pattern, "legacy-token",
                f"retire legacy spelling(s) -- {CANONICAL_NA!r} where the check does not "
                f"apply, a real-answer token such as 'not_required' where it does: "
                + ", ".join(sorted(legacy)))

        for token in sorted(scored_tokens):
            in_schema = token in (values or []) or token in node.get("description", "")
            if not in_schema and token not in seen_gold:
                add(pattern, "orphan-token",
                    f"manifest scores {token!r}, which neither the schema nor the gold uses",
                    [token])

        if free and not (metric == "graded_string" and profile.get("string_compare") == "semantic"):
            reason = identifiers.get((check, pattern))
            if reason is None:
                add(pattern, "text-metric",
                    f"free text scored {metric}/{profile.get('string_compare')}: "
                    f"make it semantic, an enum, or declare it an identifier")
    return out


def audit(checklists: Optional[Sequence[str]] = None,
          checklist_root: Path = CHECKLISTS,
          gold_root: Path = EXAMPLES) -> List[Finding]:
    findings: List[Finding] = []
    for checklist in sorted(c for c in checklist_root.iterdir() if c.is_dir()):
        if checklists and checklist.name not in checklists:
            continue
        for check_dir in sorted(p for p in checklist.iterdir() if p.is_dir()):
            if (check_dir / "schema.json").is_file():
                findings += audit_check(checklist.name, check_dir, gold_root)
    return findings


# ---------------------------------------------------------------------------
# What committed runs wrote
# ---------------------------------------------------------------------------

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
    parser.add_argument("--checklist", action="append", default=None,
                        help="Audit only this checklist; repeatable. Default: all")
    parser.add_argument("--runs", action="store_true",
                        help="Also count what committed predictions wrote in each flagged field")
    args = parser.parse_args(argv)

    findings = audit(args.checklist)
    seen = run_values(sorted({f.check for f in findings})) if args.runs else {}
    for f in findings:
        where = f"{f.checklist}/{f.check}" + (f" · {f.field}" if f.field else "")
        line = f"{f.rule:<13} {where}: {f.detail}"
        values = seen.get((f.check, f.field))
        if values and f.tokens:
            total = sum(values.values())
            exact = sum(n for v, n in values.items() if v in f.tokens)
            ann = sum(n for v, n in values.items() if any(annotated(v, t) for t in f.tokens))
            line += f"  [runs: {total} values, {exact} exact, {ann} annotated]"
        print(line)
    by_rule = Counter(f.rule for f in findings)
    print(f"\n{len(findings)} finding(s)" + (": " + ", ".join(f"{r} {n}" for r, n in sorted(by_rule.items())) if findings else ""))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
