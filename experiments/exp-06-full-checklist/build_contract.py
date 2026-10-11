"""Build exp-06's contract: the eleven checks' cleaned contracts, check-major.

`fig-checklist-exp06` has one entry point, `do-fig-checklist-cm`, and it owns
one contract, **derived, never authored**, so that a check scored inside it
differs from the same check scored on its own by nothing but its key:

    schema.json          {<check>: <that check's `outputs` array schema, verbatim>, ...}
    eval-manifest.json   defaults shared; `outputs` -> `<check>`;
                         `outputs[].x` -> `<check>[].x`; lists nested in a row
                         (plot-axis-units' per-axis lists) keep their alignment
    benchmark.json       the 38 figures every check's benchmark holds
    gold                 examples/<ex>/checks/do-fig-checklist-cm/expected_output.json,
                         each check's gold rows under that check's key

The sources are the production `fig-checklist` contracts and the live gold,
after the contract cleanup and the renames and changes of 2026-10-08 to
2026-10-11 (`plot-axis-units` and `plot-gap-labeling`'s `is_a_plot_with_axes`,
`stat-test`'s `statistical_significance_claim`, `single-channel-for-overlay`'s
counts and `overlay_channels`). The merged gold is tagged with them as
`gold-v5`.

**Verification is the point of this script.** It scores answers made from the
gold -- rows dropped, added and reordered, every field perturbed by type
(enums cycled, text altered, integers moved, lists of strings and of objects
changed), and one check at a time on its own -- under each check's own
contract and under the combined one, and refuses unless every instance and
every layer-S row set agree.

    python experiments/exp-06-full-checklist/build_contract.py           # contract
    python experiments/exp-06-full-checklist/build_contract.py --gold    # and gold
    python experiments/exp-06-full-checklist/build_contract.py --check   # drift only

Gold is behind a flag because it writes into the shared examples tree, which is
reviewed separately from the contract.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Mapping, Tuple

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import jsonschema                                                  # noqa: E402

from soda_mmqc.core.eval_manifest import parse_eval_manifest       # noqa: E402
from soda_mmqc.core.evaluation import FlatEvaluator                # noqa: E402

CHECKLISTS = REPO / "soda_mmqc" / "data" / "checklist"
SOURCE = CHECKLISTS / "fig-checklist"
TARGET = CHECKLISTS / "fig-checklist-exp06"
EXAMPLES = REPO / "soda_mmqc" / "data" / "examples"

ENTRY = "do-fig-checklist-cm"

#: In the order D's prose names them; the schema's keys follow it.
CHECKS = (
    "micrograph-scale-bar", "image-annotation-defined", "single-channel-for-overlay",
    "individual-data-points", "error-bars-defined", "plot-axis-units", "plot-gap-labeling",
    "stat-significance-level", "stat-test", "replication-reporting",
    "panel-image-matches-caption",
)

LIST, LABEL = "outputs", "panel_label"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------

def sources() -> Dict[str, Dict[str, Any]]:
    return {c: {n: read_json(SOURCE / c / f"{n}.json") for n in ("schema", "eval-manifest", "benchmark")}
            for c in CHECKS}


def row_schema(src: Mapping[str, Any]) -> Dict[str, Any]:
    return src["schema"]["format"]["schema"]["properties"][LIST]["items"]


def check_sources(src) -> None:
    """Refuse a source this merge would change rather than carry."""
    for check, s in src.items():
        root = s["schema"]["format"]["schema"]
        if set(root["properties"]) != {LIST} or root.get("required") != [LIST]:
            raise ValueError(f"{check}'s schema has more at its root than {LIST!r}")
        manifest = s["eval-manifest"]
        if set(manifest) - {"checklist", "defaults", "list_alignment", "fields"}:
            raise ValueError(f"{check}'s manifest carries keys this merge ignores")
        if manifest["list_alignment"].get(LIST) != [LABEL]:
            raise ValueError(f"{check} does not align {LIST} on {LABEL}")
        if any(not p.startswith(f"{LIST}[].") for p in manifest["fields"]):
            raise ValueError(f"{check} has a field outside {LIST}[]")
    for what, get in (("envelope type", lambda s: s["schema"]["format"]["type"]),
                      ("strict", lambda s: s["schema"]["format"].get("strict")),
                      ("manifest defaults", lambda s: s["eval-manifest"]["defaults"]),
                      ("example class", lambda s: s["benchmark"]["example_class"])):
        values = [get(s) for s in src.values()]
        if any(v != values[0] for v in values):
            raise ValueError(f"the checks differ in {what}; merging would change how one is scored")
    nested = [k for s in src.values() for k in s["eval-manifest"]["list_alignment"] if k != LIST]
    if len(nested) != len(set(nested)):
        raise ValueError(f"two checks align a nested list of the same name: {nested}")


#: Left out of exp-06, decided by the author 2026-10-11. A Nature Methods guide
#: on preparing figures, made of example images: not a research figure, and not
#: what the checklist meets in production, which is what exp-06 sets the
#: baseline for. In every other check's benchmark, and in exp-01 to exp-05; only
#: image-annotation-defined's benchmark already lacked it.
EXCLUDED = {"10.1038_s41592-023-01987/content/4"}

#: exp-04's 38 figures, less EXCLUDED.
N_EXAMPLES = 37


def shared_examples(src) -> List[str]:
    """The figures every check's benchmark holds, in the first check's order, less EXCLUDED."""
    first = src[CHECKS[0]]["benchmark"]["examples"]
    every = set.intersection(*(set(s["benchmark"]["examples"]) for s in src.values()))
    examples = [e for e in first if e in every and e not in EXCLUDED]
    if len(examples) != N_EXAMPLES:
        raise ValueError(f"{len(examples)} figures, not {N_EXAMPLES}: a benchmark has changed")
    return examples


# --------------------------------------------------------------------------
# The contract
# --------------------------------------------------------------------------

def build_schema(src) -> Dict[str, Any]:
    first = src[CHECKS[0]]["schema"]["format"]
    return {"format": {
        "type": first["type"], "name": ENTRY,
        "schema": {
            "type": "object",
            "properties": {c: src[c]["schema"]["format"]["schema"]["properties"][LIST] for c in CHECKS},
            "required": list(CHECKS),
            "additionalProperties": False,
        },
        "strict": True,
    }}


def build_manifest(src) -> Dict[str, Any]:
    list_alignment: Dict[str, Any] = {}
    fields: Dict[str, Any] = {}
    for check in CHECKS:
        manifest = src[check]["eval-manifest"]
        for key, by in manifest["list_alignment"].items():
            list_alignment[check if key == LIST else key] = by
        for pattern, profile in manifest["fields"].items():
            fields[check + pattern[len(LIST):]] = profile
    return {"checklist": ENTRY, "defaults": src[CHECKS[0]]["eval-manifest"]["defaults"],
            "list_alignment": list_alignment, "fields": fields}


def build_benchmark(src, examples: List[str]) -> Dict[str, Any]:
    return {"name": ENTRY,
            "description": "Runs the eleven checks of the figure checklist on one figure, in one "
                           "session; check-major answer.",
            "example_class": src[CHECKS[0]]["benchmark"]["example_class"],
            "examples": examples}


# --------------------------------------------------------------------------
# Gold
# --------------------------------------------------------------------------

def per_check_gold(example: str, src) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for check in CHECKS:
        path = EXAMPLES / example / "checks" / check / "expected_output.json"
        if not path.is_file():
            raise FileNotFoundError(f"no gold for {check} on {example}: {path}")
        record = {LIST: read_json(path)[LIST]}
        jsonschema.Draft7Validator(src[check]["schema"]["format"]["schema"]).validate(record)
        out[check] = record
    return out


def combine(parts: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    return {check: parts[check][LIST] for check in CHECKS}


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------

def perturb(value: Any, node: Mapping[str, Any]) -> Any:
    """A different value of the same type, valid against ``node``."""
    if "enum" in node:
        enum = node["enum"]
        return enum[(enum.index(value) + 1) % len(enum)] if value in enum else value
    if "anyOf" in node:
        if isinstance(value, int) and not isinstance(value, bool):
            return value + 1
        integer = next((o for o in node["anyOf"] if o.get("type") == "integer"), None)
        return max(integer.get("minimum", 0), 1) + 1 if integer else value
    kind = node.get("type")
    if kind == "string":
        return value + " altered" if value else "spurious text"
    if kind == "integer":
        return value + 1
    if kind == "array":
        items = node.get("items") or {}
        if items.get("type") == "object":
            if not value:
                return value
            return [perturb_row(r, items) for r in value[:-1]] + [value[-1]] if len(value) > 1 \
                else [perturb_row(value[0], items)]
        if "enum" in items:
            return [perturb(v, items) for v in value]
        return list(value) + ["spurious"]
    return value


def perturb_row(row: Mapping[str, Any], schema_row: Mapping[str, Any], every: int = 1) -> Dict[str, Any]:
    out = dict(row)
    for i, (key, node) in enumerate(schema_row["properties"].items()):
        if key in (LABEL, "axis") or i % every:
            continue
        out[key] = perturb(out[key], node)
    return out


def answers(gold, src) -> Iterator[Tuple[str, Dict[str, Dict[str, Any]]]]:
    rows = {c: gold[c][LIST] for c in CHECKS}
    schema_rows = {c: row_schema(src[c]) for c in CHECKS}

    def each(fn: Callable[[str, List[Dict[str, Any]]], List[Dict[str, Any]]]):
        return {c: {LIST: fn(c, copy.deepcopy(rows[c]))} for c in CHECKS}

    yield "identity", each(lambda c, r: r)
    yield "drop-first", each(lambda c, r: r[1:])
    yield "spurious", each(lambda c, r: r + [{**r[-1], LABEL: "ZZ"}] if r else r)
    yield "reversed", each(lambda c, r: r[::-1])
    yield "perturb-all", each(lambda c, r: [perturb_row(x, schema_rows[c]) for x in r])
    yield "perturb-some", each(lambda c, r: [perturb_row(x, schema_rows[c], every=2) if i % 2 else x
                                             for i, x in enumerate(r)])
    for k, check in enumerate(CHECKS):
        if len(rows[check]) > 1:
            parts = copy.deepcopy(dict(gold))
            parts[check] = {LIST: rows[check][:k % len(rows[check])] + rows[check][k % len(rows[check]) + 1:]}
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


def _part(result: Mapping[str, Any], check: str, nested: List[str]) -> Dict[str, Any]:
    """One check's share of the combined result, in that check's own terms."""
    def own(path: str) -> str:
        if path == check or path.startswith((f"{check}[", f"{check}.")):
            return LIST + path[len(check):]
        return path

    return _rewrite({
        "instances": [i for i in result["instances"] if own(i["leaf_property"]) != i["leaf_property"]],
        "by_list": {(LIST if k == check else k): v for k, v in result["by_list"].items()
                    if k == check or k in nested},
    }, own)


def verify(schema, manifest, src, examples: List[str]) -> int:
    combined = FlatEvaluator(schema["format"]["schema"], parse_eval_manifest(manifest))
    validator = jsonschema.Draft7Validator(schema["format"]["schema"])
    alone = {c: FlatEvaluator(src[c]["schema"]["format"]["schema"],
                              parse_eval_manifest(src[c]["eval-manifest"])) for c in CHECKS}
    alone_validator = {c: jsonschema.Draft7Validator(src[c]["schema"]["format"]["schema"])
                       for c in CHECKS}
    nested = {c: [k for k in src[c]["eval-manifest"]["list_alignment"] if k != LIST] for c in CHECKS}
    compared = 0
    for example in examples:
        gold = per_check_gold(example, src)
        combined_gold = combine(gold)
        validator.validate(combined_gold)
        for name, parts in answers(gold, src):
            for c in CHECKS:
                alone_validator[c].validate(parts[c])
            pred = combine(parts)
            validator.validate(pred)
            together = _canonical(combined.evaluate(combined_gold, pred))
            claimed = 0
            for c in CHECKS:
                single = _canonical(alone[c].evaluate(gold[c], parts[c]))
                part = _part(together, c, nested[c])
                if part != single:
                    raise AssertionError(f"{c} on {example} [{name}]: the combined contract scores "
                                         f"this check differently from its own contract")
                claimed += len(part["instances"])
                compared += 1
            if claimed != len(together["instances"]):
                raise AssertionError(f"{example} [{name}]: instances that belong to no check")
    return compared


# --------------------------------------------------------------------------

def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--gold", action="store_true",
                        help="Also write the merged gold into the examples tree")
    parser.add_argument("--check", action="store_true",
                        help="Write nothing; fail if a committed file differs from what would be "
                             "built")
    args = parser.parse_args(argv)

    src = sources()
    check_sources(src)
    examples = shared_examples(src)
    schema, manifest = build_schema(src), build_manifest(src)
    benchmark = build_benchmark(src, examples)

    compared = verify(schema, manifest, src, examples)
    print(f"verified: {compared} (check, figure, answer) scorings identical under {ENTRY} and "
          f"each check's own contract, on {len(examples)} figures")

    outputs: Dict[Path, str] = {
        TARGET / ENTRY / "schema.json": dump(schema),
        TARGET / ENTRY / "eval-manifest.json": dump(manifest),
        TARGET / ENTRY / "benchmark.json": dump(benchmark),
    }
    if args.gold:
        for example in examples:
            outputs[EXAMPLES / example / "checks" / ENTRY / "expected_output.json"] = \
                dump(combine(per_check_gold(example, src)))

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
