"""Build exp-04's two contracts from the three checks' cleaned contracts.

`fig-checklist-exp04` has two entry points, one per contract shape, with
identical prose but for their name. Each is a leaf and owns one contract, which
is **derived, never authored**, so that a check scored inside it differs from
the same check scored on its own by nothing but where its fields sit:

    do-fig-checklist-cm   check-major, as exp-03's:
                          {<check>: <that check's `outputs` array schema, verbatim>, ...}
                          manifest: `outputs[].x` -> `<check>[].x`
    do-fig-checklist-pm   panel-major, one row per panel:
                          {"outputs": [{"panel_label": ..., "panel_classes": [...],
                                        <check>: {<its row fields but panel_label>},
                                        ...}]}
                          manifest: `outputs[].x` -> `outputs[].<check>.x`;
                          `panel_label` once; `panel_classes` unscored (no gold)

    benchmark.json        the 38 examples, identical in all three checks
    gold                  examples/<ex>/checks/<leaf>/expected_output.json, each
                          check's rows from `gold-v3`, merged per check (cm) or
                          per panel (pm)

The sources are the per-check contracts of the production `fig-checklist`,
cleaned by the contract cleanup, and the gold at `gold-v3`. The PM gold carries
`panel_classes: []`: the strict schema requires the field, nothing scores it.

**Verification is the point of this script.** No predictions exist yet in the
cleaned vocabulary, so it scores answers made from the gold -- rows dropped,
added, reordered, values flipped, text altered -- under each check's own
contract and under both combined ones, and refuses unless every instance and
every layer-S row set agree. A combined contract that scored differently would
make the CM/PM comparison a comparison of scorers.

    python experiments/exp-04-panel-major/build_contract.py           # contracts
    python experiments/exp-04-panel-major/build_contract.py --gold    # and gold
    python experiments/exp-04-panel-major/build_contract.py --check   # drift only

Gold is behind a flag because it writes into the shared examples tree, which is
reviewed separately from the contract.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Mapping, Tuple

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import jsonschema                                                  # noqa: E402

from soda_mmqc.core.eval_manifest import parse_eval_manifest       # noqa: E402
from soda_mmqc.core.evaluation import FlatEvaluator                # noqa: E402
from soda_mmqc.gold import snapshot                                # noqa: E402

CHECKLISTS = REPO / "soda_mmqc" / "data" / "checklist"
SOURCE = CHECKLISTS / "fig-checklist"
TARGET = CHECKLISTS / "fig-checklist-exp04"
LIVE_EXAMPLES = REPO / "soda_mmqc" / "data" / "examples"

#: The gold exp-04 is scored against. Read from its snapshot, and the live
#: tree is checked to agree with it, so the merged gold written there is
#: exactly gold-v3's.
GOLD_TAG = "gold-v3"

CM, PM = "do-fig-checklist-cm", "do-fig-checklist-pm"

#: In the order D's prose names them. The order of keys follows it.
CHECKS = ("micrograph-scale-bar", "individual-data-points", "error-bars-defined")

#: The per-check list every source contract aligns, and the field it aligns on.
LIST, LABEL = "outputs", "panel_label"

#: The classification vocabulary of classify-panels and the v1 checks' inline
#: classification step.
PANEL_CLASSES = ("micrograph", "plot", "blot", "molecular_or_protein_structure",
                 "sequence", "schematic", "photograph", "table", "other")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------

def sources() -> Dict[str, Dict[str, Any]]:
    return {
        check: {name: read_json(SOURCE / check / f"{name}.json")
                for name in ("schema", "eval-manifest", "benchmark")}
        for check in CHECKS
    }


def row_schema(src: Mapping[str, Any]) -> Dict[str, Any]:
    return src["schema"]["format"]["schema"]["properties"][LIST]["items"]


def check_sources(src: Mapping[str, Mapping[str, Any]]) -> None:
    """Refuse a source this merge would change rather than carry."""
    for check, s in src.items():
        root = s["schema"]["format"]["schema"]
        if set(root["properties"]) != {LIST} or root.get("required") != [LIST]:
            raise ValueError(f"{check}'s schema has more at its root than {LIST!r}")
        row = row_schema(s)
        closed = row.get("additionalProperties") is False
        if not closed or set(row["required"]) != set(row["properties"]):
            raise ValueError(f"{check}'s rows are not closed and fully required")
        manifest = s["eval-manifest"]
        if set(manifest) - {"checklist", "defaults", "list_alignment", "fields"}:
            raise ValueError(f"{check}'s manifest carries keys this merge ignores")
        if manifest["list_alignment"] != {LIST: [LABEL]}:
            raise ValueError(f"{check} aligns {manifest['list_alignment']}, not {LIST}: [{LABEL}]")
        if any(not p.startswith(f"{LIST}[].") for p in manifest["fields"]):
            raise ValueError(f"{check} has a field outside {LIST}[]")
    for what, get in (("envelope type", lambda s: s["schema"]["format"]["type"]),
                      ("strict", lambda s: s["schema"]["format"].get("strict")),
                      ("manifest defaults", lambda s: s["eval-manifest"]["defaults"]),
                      ("panel_label schema", lambda s: row_schema(s)["properties"][LABEL]),
                      ("panel_label profile",
                       lambda s: s["eval-manifest"]["fields"][f"{LIST}[].{LABEL}"]),
                      ("examples", lambda s: s["benchmark"]["examples"]),
                      ("example class", lambda s: s["benchmark"]["example_class"])):
        values = [get(s) for s in src.values()]
        if any(v != values[0] for v in values):
            raise ValueError(f"the three checks differ in {what}; merging would change "
                             f"how one is scored")


def check_entry_prose() -> None:
    """The two entry points differ in their name and nothing else."""
    texts = {leaf: (TARGET / leaf / "v1" / "SKILL.md").read_text(encoding="utf-8")
             for leaf in (CM, PM)}
    if texts[CM].replace(CM, "<leaf>") != texts[PM].replace(PM, "<leaf>"):
        raise ValueError(f"{CM} and {PM} differ in more than their name")


# --------------------------------------------------------------------------
# The two contracts
# --------------------------------------------------------------------------

def envelope(name: str, schema: Mapping[str, Any], src) -> Dict[str, Any]:
    first = next(iter(src.values()))["schema"]["format"]
    return {"format": {"type": first["type"], "name": name, "schema": schema, "strict": True}}


def build_cm_schema(src) -> Dict[str, Any]:
    return envelope(CM, {
        "type": "object",
        "properties": {c: src[c]["schema"]["format"]["schema"]["properties"][LIST]
                       for c in CHECKS},
        "required": list(CHECKS),
        "additionalProperties": False,
    }, src)


def build_cm_manifest(src) -> Dict[str, Any]:
    fields: Dict[str, Any] = {}
    for check in CHECKS:
        for pattern, profile in src[check]["eval-manifest"]["fields"].items():
            fields[check + pattern[len(LIST):]] = profile
    return {"checklist": CM, "defaults": src[CHECKS[0]]["eval-manifest"]["defaults"],
            "list_alignment": {c: [LABEL] for c in CHECKS}, "fields": fields}


def build_pm_schema(src) -> Dict[str, Any]:
    properties: Dict[str, Any] = {
        LABEL: row_schema(src[CHECKS[0]])["properties"][LABEL],
        "panel_classes": {
            "type": "array",
            "items": {"type": "string", "enum": list(PANEL_CLASSES)},
            "description": "Every content type the panel shows, from the panel classification",
        },
    }
    for check in CHECKS:
        row = row_schema(src[check])
        properties[check] = {
            "type": "object",
            "properties": {k: v for k, v in row["properties"].items() if k != LABEL},
            "required": [k for k in row["required"] if k != LABEL],
            "additionalProperties": False,
        }
    return envelope(PM, {
        "type": "object",
        "properties": {LIST: {"type": "array", "items": {
            "type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}}},
        "required": [LIST],
        "additionalProperties": False,
    }, src)


def build_pm_manifest(src) -> Dict[str, Any]:
    label = f"{LIST}[].{LABEL}"
    fields: Dict[str, Any] = {label: src[CHECKS[0]]["eval-manifest"]["fields"][label],
                              f"{LIST}[].panel_classes": {"scored": False}}
    for check in CHECKS:
        for pattern, profile in src[check]["eval-manifest"]["fields"].items():
            if pattern != label:
                fields[f"{LIST}[].{check}." + pattern[len(f'{LIST}[].'):]] = profile
    return {"checklist": PM, "defaults": src[CHECKS[0]]["eval-manifest"]["defaults"],
            "list_alignment": {LIST: [LABEL]}, "fields": fields}


def build_benchmark(leaf: str, shape: str, src) -> Dict[str, Any]:
    first = src[CHECKS[0]]["benchmark"]
    return {
        "name": leaf,
        "description": (f"Runs micrograph-scale-bar, individual-data-points and "
                        f"error-bars-defined on one figure, in one session; {shape} answer."),
        "example_class": first["example_class"],
        "examples": first["examples"],
    }


# --------------------------------------------------------------------------
# Gold
# --------------------------------------------------------------------------

def contracted(record: Mapping[str, Any], schema: Mapping[str, Any]) -> Dict[str, Any]:
    allowed = set(schema["format"]["schema"]["properties"])
    return {k: v for k, v in record.items() if k in allowed}


def per_check_gold(example: str, src, gold_root: Path) -> Dict[str, Dict[str, Any]]:
    """Each check's gold rows for one example, validated against its schema."""
    out: Dict[str, Dict[str, Any]] = {}
    for check in CHECKS:
        path = gold_root / example / "checks" / check / "expected_output.json"
        if not path.is_file():
            raise FileNotFoundError(f"no gold for {check} on {example}: {path}")
        record = contracted(read_json(path), src[check]["schema"])
        jsonschema.Draft7Validator(src[check]["schema"]["format"]["schema"]).validate(record)
        out[check] = record
    return out


def to_cm(parts: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    return {check: parts[check][LIST] for check in CHECKS}


def to_pm(parts: Mapping[str, Mapping[str, Any]],
          classes: Mapping[str, List[str]] | None = None) -> Dict[str, Any]:
    """Three per-check records -> one row per panel. Labels must agree, in order."""
    labels = {check: [row[LABEL] for row in parts[check][LIST]] for check in CHECKS}
    first = labels[CHECKS[0]]
    if any(labels[c] != first for c in CHECKS) or len(set(first)) != len(first):
        raise ValueError(f"panel labels disagree across checks, or repeat: {labels}")
    rows = []
    for i, label in enumerate(first):
        row: Dict[str, Any] = {LABEL: label, "panel_classes": list((classes or {}).get(label, []))}
        for check in CHECKS:
            row[check] = {k: v for k, v in parts[check][LIST][i].items() if k != LABEL}
        rows.append(row)
    return {LIST: rows}


def from_pm(record: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """One row per panel -> three per-check records: how a PM answer is read per check."""
    return {check: {LIST: [{LABEL: row[LABEL], **row[check]} for row in record[LIST]]}
            for check in CHECKS}


# --------------------------------------------------------------------------
# Verification: each combined contract scores every check as its own contract does
# --------------------------------------------------------------------------

def _enum_cycle(value: Any, enum: List[Any]) -> Any:
    return enum[(enum.index(value) + 1) % len(enum)] if value in enum else value


def _flip(row: Dict[str, Any], schema_row: Mapping[str, Any], every: int = 1) -> Dict[str, Any]:
    out = dict(row)
    for i, (key, node) in enumerate(schema_row["properties"].items()):
        if key == LABEL or i % every:
            continue
        if "enum" in node:
            out[key] = _enum_cycle(out[key], node["enum"])
        elif node.get("type") == "string":
            out[key] = (out[key] + " altered") if out[key] else "spurious text"
    return out


def perturbations(gold: Mapping[str, Mapping[str, Any]],
                  src) -> Iterator[Tuple[str, Dict[str, Dict[str, Any]]]]:
    """Answers made from the gold, per check. Panel-level ones are expressible in both shapes."""
    rows = {c: gold[c][LIST] for c in CHECKS}
    n = len(rows[CHECKS[0]])
    schema_rows = {c: row_schema(src[c]) for c in CHECKS}

    def each(fn: Callable[[str, List[Dict[str, Any]]], List[Dict[str, Any]]]):
        return {c: {LIST: fn(c, copy.deepcopy(rows[c]))} for c in CHECKS}

    yield "identity", each(lambda c, r: r)
    if n > 1:
        yield "drop-first", each(lambda c, r: r[1:])
    yield "spurious", each(lambda c, r: r + [{**r[-1], LABEL: "ZZ"}] if r else r)
    yield "reversed", each(lambda c, r: r[::-1])
    yield "flip-all", each(lambda c, r: [_flip(x, schema_rows[c]) for x in r])
    yield "flip-some", each(lambda c, r: [_flip(x, schema_rows[c], every=2) if i % 2 else x
                                          for i, x in enumerate(r)])
    if n > 2:
        yield "drop-last-flip-first", each(lambda c, r: [_flip(r[0], schema_rows[c])] + r[1:-1])


def check_only_perturbations(gold, src):
    """Answers whose row sets differ between checks: expressible in CM only."""
    for k, check in enumerate(CHECKS):
        rows = gold[check][LIST]
        if len(rows) > 1:
            parts = copy.deepcopy(dict(gold))
            parts[check] = {LIST: rows[:k % len(rows)] + rows[k % len(rows) + 1:]}
            yield f"drop-one-in-{check}", parts


PATH_FIELDS = ("path", "leaf_property", "context_path")


def _canonical(result: Any) -> Dict[str, Any]:
    return json.loads(json.dumps(asdict(result), sort_keys=True, default=str))


def _rewrite(node: Any, fn: Callable[[str], str]) -> Any:
    if isinstance(node, Mapping):
        return {k: (fn(v) if k in PATH_FIELDS and isinstance(v, str) else _rewrite(v, fn))
                for k, v in node.items()}
    if isinstance(node, list):
        return [_rewrite(v, fn) for v in node]
    return node


def _cm_part(result: Mapping[str, Any], check: str) -> Dict[str, Any]:
    """One check's share of a CM result, in that check's own terms."""
    def own(path: str) -> str:
        if path == check or path.startswith((f"{check}[", f"{check}.")):
            return LIST + path[len(check):]
        return path

    return _rewrite({
        "instances": [i for i in result["instances"]
                      if own(i["leaf_property"]) != i["leaf_property"]],
        "by_list": {LIST: v for k, v in result["by_list"].items() if k == check},
    }, own)


_PM_LABEL = re.compile(rf"^{LIST}\[\d*\]\.{LABEL}$")


def _pm_part(result: Mapping[str, Any], check: str) -> Dict[str, Any]:
    """One check's share of a PM result -- its fields, and the shared panel
    label -- in that check's own terms."""
    def own(path: str) -> str:
        return path.replace(f"].{check}.", "].")

    return _rewrite({
        "instances": [i for i in result["instances"]
                      if f"].{check}." in i["leaf_property"]
                      or _PM_LABEL.match(i["leaf_property"])],
        "by_list": dict(result["by_list"]),
    }, own)


def _belongs(leaf: str, pattern: str) -> bool:
    """Whether a scored leaf is one some check owns -- `panel_classes` is not."""
    if leaf == CM:
        return any(pattern.startswith(f"{c}[") for c in CHECKS)
    return any(f"].{c}." in pattern for c in CHECKS) or bool(_PM_LABEL.match(pattern))


def verify(contracts: Mapping[str, Tuple[Mapping, Mapping]], src, gold_root: Path,
           examples: List[str]) -> Dict[str, int]:
    evaluator = {leaf: FlatEvaluator(s["format"]["schema"], parse_eval_manifest(m))
                 for leaf, (s, m) in contracts.items()}
    validator = {leaf: jsonschema.Draft7Validator(s["format"]["schema"])
                 for leaf, (s, _) in contracts.items()}
    alone = {c: FlatEvaluator(src[c]["schema"]["format"]["schema"],
                              parse_eval_manifest(src[c]["eval-manifest"]))
             for c in CHECKS}
    alone_validator = {c: jsonschema.Draft7Validator(src[c]["schema"]["format"]["schema"])
                       for c in CHECKS}
    compared = {CM: 0, PM: 0}

    for example in examples:
        gold = per_check_gold(example, src, gold_root)
        golds = {CM: to_cm(gold), PM: to_pm(gold)}
        for leaf in (CM, PM):
            validator[leaf].validate(golds[leaf])
        cases = [(name, parts, (CM, PM)) for name, parts in perturbations(gold, src)]
        cases += [(name, parts, (CM,)) for name, parts in check_only_perturbations(gold, src)]
        for name, parts, leaves in cases:
            for c in CHECKS:
                alone_validator[c].validate(parts[c])
            single = {c: _canonical(alone[c].evaluate(gold[c], parts[c])) for c in CHECKS}
            for leaf in leaves:
                pred = to_cm(parts) if leaf == CM else to_pm(parts)
                if leaf == PM and from_pm(pred) != {c: parts[c] for c in CHECKS}:
                    raise AssertionError(f"{example} [{name}]: the PM answer does not read "
                                         f"back per check")
                validator[leaf].validate(pred)
                together = _canonical(evaluator[leaf].evaluate(golds[leaf], pred))
                claimed = set()
                for c in CHECKS:
                    part = (_cm_part if leaf == CM else _pm_part)(together, c)
                    if part != single[c]:
                        raise AssertionError(f"{c} on {example} [{name}]: {leaf} scores this "
                                             f"check differently from its own contract")
                    claimed |= {i["leaf_property"] for i in part["instances"]}
                    compared[leaf] += 1
                left = {p for p in (i["leaf_property"] for i in together["instances"])
                        if not _belongs(leaf, p)}
                if left:
                    raise AssertionError(f"{example} [{name}]: {leaf} scores {left}, which "
                                         f"belong to no check")
    return compared


# --------------------------------------------------------------------------

def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gold", action="store_true",
                        help="Also write the merged gold into the examples tree")
    parser.add_argument("--check", action="store_true",
                        help="Write nothing; fail if a committed file differs from what "
                             "would be built")
    args = parser.parse_args(argv)

    src = sources()
    check_sources(src)
    check_entry_prose()
    contracts = {CM: (build_cm_schema(src), build_cm_manifest(src)),
                 PM: (build_pm_schema(src), build_pm_manifest(src))}
    benchmarks = {CM: build_benchmark(CM, "check-major", src),
                  PM: build_benchmark(PM, "panel-major", src)}
    examples = benchmarks[CM]["examples"]

    gold_root = snapshot(GOLD_TAG)
    for example in examples:
        if per_check_gold(example, src, gold_root) != per_check_gold(example, src, LIVE_EXAMPLES):
            raise ValueError(f"the live gold of {example} differs from {GOLD_TAG}; merge "
                             f"from one or the other")

    compared = verify(contracts, src, gold_root, examples)
    print(f"verified: {compared[CM]} (check, example, answer) scorings identical under {CM}, "
          f"{compared[PM]} under {PM}, and each check's own contract")

    outputs: Dict[Path, str] = {}
    for leaf, (schema, manifest) in contracts.items():
        outputs[TARGET / leaf / "schema.json"] = dump(schema)
        outputs[TARGET / leaf / "eval-manifest.json"] = dump(manifest)
        outputs[TARGET / leaf / "benchmark.json"] = dump(benchmarks[leaf])
    if args.gold:
        for example in examples:
            gold = per_check_gold(example, src, gold_root)
            checks = LIVE_EXAMPLES / example / "checks"
            outputs[checks / CM / "expected_output.json"] = dump(to_cm(gold))
            outputs[checks / PM / "expected_output.json"] = dump(to_pm(gold))

    stale = [p for p, text in outputs.items()
             if not p.is_file() or p.read_text(encoding="utf-8") != text]
    if args.check:
        for path in stale:
            print(f"out of date: {path.relative_to(REPO)}")
        return 1 if stale else 0
    for path in stale:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(outputs[path], encoding="utf-8")
        print(f"wrote {path.relative_to(REPO)}")
    print(f"{len(outputs) - len(stale)} file(s) already up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
