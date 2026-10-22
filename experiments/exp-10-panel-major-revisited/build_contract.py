"""Build exp-10's two contracts: the eleven checks check-major and panel-major.

`fig-checklist-exp10` has two entry points, one per contract shape, with
identical prose but for their name. Each owns one contract, **derived, never
authored**, so that a check scored inside it differs from the same check scored
on its own by nothing but where its fields sit:

    do-fig-checklist-cm   check-major, exp-06's derivation, unchanged:
                          {<check>: <that check's `outputs` array schema>, ...}
    do-fig-checklist-pm   panel-major, exp-04's shape for eleven checks:
                          {"outputs": [{"panel_label": ..., "panel_classes": [...],
                                        <check>: {<its row fields but panel_label>},
                                        ...}]}
                          manifest: `outputs[].x` -> `outputs[].<check>.x`;
                          `panel_label` once; `panel_classes` unscored (no gold);
                          nested lists (plot-axis-units' per-axis lists) keep
                          their alignment
    gold                  examples/<ex>/checks/<entry>/expected_output.json:
                          each check's rows merged per check (cm) or per panel
                          (pm, `panel_classes: []`), from the live gold

The check-major half is exp-06's builder (experiments/exp-06-full-checklist/
build_contract.py), imported, not copied; this script adds the panel-major half
and verifies both.

**Verification is the point of this script.** It scores answers made from the
gold -- rows dropped, added and reordered, every field perturbed by type --
under each check's own contract and under both combined ones, and refuses
unless every instance and every layer-S row set agree. Answers whose row sets
differ between checks cannot be written panel-major and are verified
check-major only. A combined contract that scored differently would make the
comparison one of scorers.

    python experiments/exp-10-panel-major-revisited/build_contract.py           # contracts
    python experiments/exp-10-panel-major-revisited/build_contract.py --gold    # and gold
    python experiments/exp-10-panel-major-revisited/build_contract.py --check   # drift only
    python experiments/exp-10-panel-major-revisited/build_contract.py --target fig-checklist   # production
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Tuple

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location(
    "exp06_build_contract", HERE.parent / "exp-06-full-checklist" / "build_contract.py")
cm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cm)

import jsonschema                                                  # noqa: E402

from soda_mmqc.core.eval_manifest import parse_eval_manifest       # noqa: E402
from soda_mmqc.core.evaluation import FlatEvaluator                # noqa: E402

REPO, EXAMPLES, CHECKS, LIST, LABEL = cm.REPO, cm.EXAMPLES, cm.CHECKS, cm.LIST, cm.LABEL
TARGET = cm.CHECKLISTS / "fig-checklist-exp10"
cm.TARGET = TARGET
CM, PM = "do-fig-checklist-cm", "do-fig-checklist-pm"

#: classify-panels v1's vocabulary.
PANEL_CLASSES = ("micrograph", "plot", "blot", "molecular_or_protein_structure",
                 "sequence", "schematic", "photograph", "table", "other")


def check_entry_prose() -> None:
    """The two entry points differ in their name and nothing else."""
    manifest = (TARGET / "version-manifest.yaml").read_text(encoding="utf-8")
    version = {leaf: re.search(rf"^  {leaf}: (v\d+)$", manifest, re.M).group(1) for leaf in (CM, PM)}
    texts = {leaf: (TARGET / leaf / version[leaf] / "SKILL.md").read_text(encoding="utf-8")
             for leaf in (CM, PM)}
    if texts[CM].replace(CM, "<leaf>") != texts[PM].replace(PM, "<leaf>"):
        raise ValueError(f"{CM} and {PM} differ in more than their name")


# --------------------------------------------------------------------------
# The panel-major contract
# --------------------------------------------------------------------------

def build_pm_schema(src) -> Dict[str, Any]:
    first = src[CHECKS[0]]["schema"]["format"]
    properties: Dict[str, Any] = {
        LABEL: cm.row_schema(src[CHECKS[0]])["properties"][LABEL],
        "panel_classes": {
            "type": "array",
            "items": {"type": "string", "enum": list(PANEL_CLASSES)},
            "description": "Every content type the panel shows, from the panel classification",
        },
    }
    for check in CHECKS:
        row = cm.row_schema(src[check])
        properties[check] = {
            "type": "object",
            "properties": {k: v for k, v in row["properties"].items() if k != LABEL},
            "required": [k for k in row["required"] if k != LABEL],
            "additionalProperties": False,
        }
    return {"format": {
        "type": first["type"], "name": PM,
        "schema": {
            "type": "object",
            "properties": {LIST: {"type": "array", "items": {
                "type": "object", "properties": properties,
                "required": list(properties), "additionalProperties": False}}},
            "required": [LIST],
            "additionalProperties": False,
        },
        "strict": True,
    }}


def build_pm_manifest(src) -> Dict[str, Any]:
    label = f"{LIST}[].{LABEL}"
    fields: Dict[str, Any] = {label: src[CHECKS[0]]["eval-manifest"]["fields"][label],
                              f"{LIST}[].panel_classes": {"scored": False}}
    list_alignment: Dict[str, Any] = {LIST: [LABEL]}
    for check in CHECKS:
        manifest = src[check]["eval-manifest"]
        for key, by in manifest["list_alignment"].items():
            if key != LIST:
                # A list nested in a check's row is named by its path in the panel row.
                list_alignment[f"{check}.{key}"] = by
        for pattern, profile in manifest["fields"].items():
            if pattern != label:
                fields[f"{LIST}[].{check}." + pattern[len(f"{LIST}[]."):]] = profile
    return {"checklist": PM, "defaults": src[CHECKS[0]]["eval-manifest"]["defaults"],
            "list_alignment": list_alignment, "fields": fields}


def build_benchmark(leaf: str, shape: str, examples: List[str], src) -> Dict[str, Any]:
    return {"name": leaf,
            "description": f"Runs the eleven checks of the figure checklist on one figure, in one "
                           f"session; {shape} answer.",
            "example_class": src[CHECKS[0]]["benchmark"]["example_class"],
            "examples": examples}


def to_pm(parts: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """Per-check records -> one row per panel. Labels must agree, in order."""
    labels = {c: [row[LABEL] for row in parts[c][LIST]] for c in CHECKS}
    first = labels[CHECKS[0]]
    if any(labels[c] != first for c in CHECKS) or len(set(first)) != len(first):
        raise ValueError(f"panel labels disagree across checks, or repeat: {labels}")
    rows = []
    for i, label in enumerate(first):
        row: Dict[str, Any] = {LABEL: label, "panel_classes": []}
        for check in CHECKS:
            row[check] = {k: v for k, v in parts[check][LIST][i].items() if k != LABEL}
        rows.append(row)
    return {LIST: rows}


def from_pm(record: Mapping[str, Any]) -> Dict[str, Dict[str, Any]]:
    """One row per panel -> per-check records: how a PM answer is read per check."""
    return {c: {LIST: [{LABEL: row[LABEL], **row[c]} for row in record[LIST]]} for c in CHECKS}


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------

_PM_LABEL = re.compile(rf"^{LIST}\[\d*\]\.{LABEL}$")


def _pm_part(result: Mapping[str, Any], check: str, nested: List[str]) -> Dict[str, Any]:
    """One check's share of a PM result -- its fields, the shared panel label,
    and its own nested lists -- in that check's own terms."""
    def own(path: str) -> str:
        return path.replace(f"].{check}.", "].")

    def own_context(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # A nested row reports its parent row's scalar fields as context. The
        # panel row holds every check's object; the check's own context is the
        # label and its own scalars -- what its own row holds. Reporting only.
        out = []
        for row in rows:
            row = dict(row)
            for side in ("ancestor_gold", "ancestor_pred"):
                row[side] = [{**a, "fields": {
                    **({LABEL: a["fields"][LABEL]} if LABEL in a["fields"] else {}),
                    **{k: v for k, v in (a["fields"].get(check) or {}).items()
                       if not isinstance(v, (dict, list))}}} for a in row.get(side) or []]
            out.append(row)
        return out

    by_list = {LIST: result["by_list"][LIST]} if LIST in result["by_list"] else {}
    for key in nested:
        if f"{check}.{key}" in result["by_list"]:
            nested_list = dict(result["by_list"][f"{check}.{key}"])
            nested_list["rows"] = own_context(nested_list.get("rows") or [])
            by_list[key] = nested_list
    return cm._rewrite({
        "instances": [i for i in result["instances"]
                      if f"].{check}." in i["leaf_property"] or _PM_LABEL.match(i["leaf_property"])],
        "by_list": by_list,
    }, own)


def _panel_level(answers: Iterator[Tuple[str, Dict[str, Dict[str, Any]]]]):
    """The answers whose row sets agree across checks: expressible panel-major."""
    for name, parts in answers:
        labels = [[r[LABEL] for r in parts[c][LIST]] for c in CHECKS]
        if all(l == labels[0] for l in labels):
            yield name, parts


def verify_pm(schema, manifest, src, examples: List[str]) -> int:
    combined = FlatEvaluator(schema["format"]["schema"], parse_eval_manifest(manifest))
    validator = jsonschema.Draft7Validator(schema["format"]["schema"])
    alone = {c: FlatEvaluator(src[c]["schema"]["format"]["schema"],
                              parse_eval_manifest(src[c]["eval-manifest"])) for c in CHECKS}
    nested = {c: [k for k in src[c]["eval-manifest"]["list_alignment"] if k != LIST] for c in CHECKS}
    compared = 0
    for example in examples:
        gold = cm.per_check_gold(example, src)
        pm_gold = to_pm(gold)
        validator.validate(pm_gold)
        for name, parts in _panel_level(cm.answers(gold, src)):
            pred = to_pm(parts)
            if from_pm(pred) != {c: parts[c] for c in CHECKS}:
                raise AssertionError(f"{example} [{name}]: the PM answer does not read back per check")
            validator.validate(pred)
            together = cm._canonical(combined.evaluate(pm_gold, pred))
            claimed = set()
            for c in CHECKS:
                single = cm._canonical(alone[c].evaluate(gold[c], parts[c]))
                part = _pm_part(together, c, nested[c])
                if part != single:
                    raise AssertionError(f"{c} on {example} [{name}]: {PM} scores this check "
                                         f"differently from its own contract")
                claimed |= {i["leaf_property"] for i in together["instances"]
                            if f"].{c}." in i["leaf_property"] or _PM_LABEL.match(i["leaf_property"])}
                compared += 1
            left = {i["leaf_property"] for i in together["instances"]} - claimed
            if left:
                raise AssertionError(f"{example} [{name}]: {PM} scores {sorted(left)[:5]}, which "
                                     f"belong to no check")
    return compared


# --------------------------------------------------------------------------

def main(argv: List[str] | None = None) -> int:
    global TARGET
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gold", action="store_true",
                        help="Also write the merged gold into the examples tree")
    parser.add_argument("--check", action="store_true",
                        help="Write nothing; fail if a committed file differs from what would be built")
    parser.add_argument("--target", default=TARGET.name,
                        help="Checklist to write the contracts into (default: %(default)s); "
                             "production fig-checklist since 2026-10-22")
    args = parser.parse_args(argv)
    TARGET = cm.CHECKLISTS / args.target
    cm.TARGET = TARGET

    src = cm.sources()
    cm.check_sources(src)
    check_entry_prose()
    examples = cm.shared_examples(src)
    cm_schema, cm_manifest = cm.build_schema(src), cm.build_manifest(src)
    pm_schema, pm_manifest = build_pm_schema(src), build_pm_manifest(src)

    n_cm = cm.verify(cm_schema, cm_manifest, src, examples)
    n_pm = verify_pm(pm_schema, pm_manifest, src, examples)
    print(f"verified on {len(examples)} figures: {n_cm} (check, figure, answer) scorings identical "
          f"under {CM}, {n_pm} under {PM}, and each check's own contract")

    outputs: Dict[Path, str] = {}
    for leaf, schema, manifest, shape in ((CM, cm_schema, cm_manifest, "check-major"),
                                          (PM, pm_schema, pm_manifest, "panel-major")):
        outputs[TARGET / leaf / "schema.json"] = cm.dump(schema)
        outputs[TARGET / leaf / "eval-manifest.json"] = cm.dump(manifest)
        outputs[TARGET / leaf / "benchmark.json"] = cm.dump(build_benchmark(leaf, shape, examples, src))
    if args.gold:
        for example in examples:
            gold = cm.per_check_gold(example, src)
            outputs[EXAMPLES / example / "checks" / CM / "expected_output.json"] = cm.dump(cm.combine(gold))
            outputs[EXAMPLES / example / "checks" / PM / "expected_output.json"] = cm.dump(to_pm(gold))

    stale = [p for p, text in outputs.items() if not p.is_file() or p.read_text(encoding="utf-8") != text]
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
