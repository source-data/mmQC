"""Build `do-fig-checklist`'s contract from the three checks' exp-02 contracts.

`do-fig-checklist` is the only leaf of `fig-checklist-exp03`: one session runs
all three checks and answers once, so it needs one output contract. That
contract is **derived, never authored**, so that a check scored inside it can
differ from the same check scored on its own by nothing but a key prefix:

    schema.json          {<check>: <that check's `outputs` array schema, verbatim>, ...}
    eval-manifest.json   defaults shared; `outputs` -> `<check>`;
                         `outputs[].x` -> `<check>[].x`
    benchmark.json       the 38 examples, identical in all three checks
    gold                 examples/<ex>/checks/do-fig-checklist/expected_output.json,
                         each check's gold rows under that check's key

**Each check's rows sit directly under its name**, not under
`<check>.outputs`. The scorer reads a list only at the document root or inside
a list row: a list nested in a plain object is found by schema discovery but
read as empty. Three root-level lists need no change to the scorer, and lose
nothing -- every source schema's only top-level property is `outputs`.

The sources are the per-check contracts in `fig-checklist-exp03-per-check`,
which are byte copies of exp-02's. Controls and fan-out are therefore scored
from one set of files.

**Verification is the point of this script, not a courtesy.** Before writing
anything it scores exp-02's committed predictions twice -- once per check under
that check's own contract, once wrapped into the combined shape under the
combined contract -- and refuses unless every instance and every layer-S row
set agree. A combined contract that scored differently would make every
fan-out comparison a comparison of contracts.

    python experiments/exp-03-checklist-entry/build_contract.py           # contracts
    python experiments/exp-03-checklist-entry/build_contract.py --gold    # and gold
    python experiments/exp-03-checklist-entry/build_contract.py --check   # drift only

Gold is behind a flag because it writes 38 files into the shared examples tree,
which is reviewed separately from the contract.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Mapping

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

import jsonschema                                                  # noqa: E402

from soda_mmqc.core.eval_manifest import parse_eval_manifest       # noqa: E402
from soda_mmqc.core.evaluation import FlatEvaluator                # noqa: E402

CHECKLISTS = REPO / "soda_mmqc" / "data" / "checklist"
SOURCE = CHECKLISTS / "fig-checklist-exp03-per-check"
TARGET = CHECKLISTS / "fig-checklist-exp03" / "do-fig-checklist"
from soda_mmqc.gold import snapshot                            # noqa: E402

#: exp-03 is frozen: its gold is the gold at the tag `gold-v1`, read from a
#: gold-only snapshot (soda_mmqc/gold.py), not the live tree, which the
#: contract cleanup has since migrated to a new vocabulary.
GOLD_TAG = "gold-v1"
EXAMPLES = snapshot(GOLD_TAG)
EXP02_RUNS = REPO / "experiments" / "runs" / "exp-02-delegation-depth"

ENTRY = "do-fig-checklist"

#: In the order D's prose names them. The order of keys in the combined schema
#: follows it, and nothing else depends on it.
CHECKS = ("micrograph-scale-bar", "individual-data-points", "error-bars-defined")

#: The per-check list every source contract aligns, and the prefix every field
#: pattern carries. Asserted, not assumed: a source that differed would need a
#: different merge.
LIST = "outputs"


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def sources() -> Dict[str, Dict[str, Any]]:
    """Each check's schema envelope, manifest and benchmark."""
    return {
        check: {
            "schema": read_json(SOURCE / check / "schema.json"),
            "manifest": read_json(SOURCE / check / "eval-manifest.json"),
            "benchmark": read_json(SOURCE / check / "benchmark.json"),
        }
        for check in CHECKS
    }


def build_schema(src: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    for check, s in src.items():
        root = s["schema"]["format"]["schema"]
        if set(root["properties"]) != {LIST} or root.get("required") != [LIST]:
            raise ValueError(
                f"{check}'s schema has more at its root than {LIST!r}; lifting "
                f"{LIST!r} to the check's key would drop it"
            )
    kinds = {s["schema"]["format"]["type"] for s in src.values()}
    strict = {s["schema"]["format"].get("strict") for s in src.values()}
    if len(kinds) != 1 or strict != {True}:
        raise ValueError(f"source envelopes differ: type {kinds}, strict {strict}")
    return {
        "format": {
            "type": kinds.pop(),
            "name": ENTRY,
            "schema": {
                "type": "object",
                "properties": {
                    check: src[check]["schema"]["format"]["schema"]["properties"][LIST]
                    for check in CHECKS
                },
                "required": list(CHECKS),
                "additionalProperties": False,
            },
            "strict": True,
        }
    }


def build_manifest(src: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    defaults = [s["manifest"]["defaults"] for s in src.values()]
    if any(d != defaults[0] for d in defaults):
        raise ValueError(
            "source manifests have different defaults; merging them would "
            "change how some check is scored"
        )
    unexpected = {
        key for s in src.values() for key in s["manifest"]
    } - {"checklist", "defaults", "list_alignment", "fields"}
    if unexpected:
        raise ValueError(f"source manifests carry keys this merge ignores: {unexpected}")

    list_alignment: Dict[str, Any] = {}
    fields: Dict[str, Any] = {}
    for check in CHECKS:
        manifest = src[check]["manifest"]
        if set(manifest["list_alignment"]) != {LIST}:
            raise ValueError(f"{check} aligns {set(manifest['list_alignment'])}, not {LIST!r}")
        list_alignment[check] = manifest["list_alignment"][LIST]
        for pattern, profile in manifest["fields"].items():
            if not pattern.startswith(f"{LIST}[]."):
                raise ValueError(f"{check} field {pattern!r} is outside {LIST}[]")
            fields[check + pattern[len(LIST):]] = profile
    return {
        "checklist": ENTRY,
        "defaults": defaults[0],
        "list_alignment": list_alignment,
        "fields": fields,
    }


def build_benchmark(src: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    examples = [s["benchmark"]["examples"] for s in src.values()]
    if any(e != examples[0] for e in examples):
        raise ValueError("the three checks do not share one example list, in one order")
    classes = {s["benchmark"]["example_class"] for s in src.values()}
    if len(classes) != 1:
        raise ValueError(f"example classes differ: {classes}")
    return {
        "name": ENTRY,
        "description": (
            "Runs micrograph-scale-bar, individual-data-points and "
            "error-bars-defined on one figure, in one session."
        ),
        "example_class": classes.pop(),
        "examples": examples[0],
    }


def gold_for(example: str, src: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """Each check's gold for one example, validated against its source schema.

    Returned in the check's own shape; `combine` lifts it into D's.
    """
    merged: Dict[str, Any] = {}
    for check in CHECKS:
        path = EXAMPLES / example / "checks" / check / "expected_output.json"
        if not path.is_file():
            # The loader warns and scores against `{}` when gold is missing,
            # which would pass silently as a check with no rows.
            raise FileNotFoundError(f"no gold for {check} on {example}: {path}")
        part = read_json(path)
        # Gold carries curation metadata (`updated_at`) that the strict schema
        # forbids and the scorer never reads. It is projected away for
        # validation, as `runner._as_prediction` does, and does not survive
        # `combine`, which keeps the rows only.
        jsonschema.Draft7Validator(src[check]["schema"]["format"]["schema"]).validate(
            contracted(part, src[check]["schema"])
        )
        merged[check] = part
    return merged


def combine(parts: Mapping[str, Mapping[str, Any]]) -> Dict[str, Any]:
    """Three per-check records -> one record in D's shape."""
    return {check: parts[check][LIST] for check in CHECKS}


def contracted(record: Mapping[str, Any], envelope: Mapping[str, Any]) -> Dict[str, Any]:
    """The part of a gold record its schema describes."""
    allowed = set(envelope["format"]["schema"]["properties"])
    return {key: value for key, value in record.items() if key in allowed}


# --------------------------------------------------------------------------
# Verification: the combined contract scores exactly as the three it replaces.
# --------------------------------------------------------------------------

#: The fields of a scoring result that carry a list or leaf path.
PATH_FIELDS = ("path", "leaf_property", "context_path")


def _as_own(value: Any, check: str) -> Any:
    """Rewrite a path in D's terms (`<check>[0].x`) into the check's (`outputs[0].x`)."""
    if isinstance(value, str) and (value == check or value.startswith((f"{check}[", f"{check}."))):
        return LIST + value[len(check):]
    return value


def _rename_paths(node: Any, check: str) -> Any:
    if isinstance(node, Mapping):
        return {
            key: _as_own(value, check) if key in PATH_FIELDS else _rename_paths(value, check)
            for key, value in node.items()
        }
    if isinstance(node, list):
        return [_rename_paths(v, check) for v in node]
    return node


def _canonical(result: Any) -> Dict[str, Any]:
    data = asdict(result)
    return json.loads(json.dumps(data, sort_keys=True, default=str))


def _part(combined: Mapping[str, Any], check: str) -> Dict[str, Any]:
    """One check's share of a combined result, in that check's own terms."""
    return _rename_paths({
        "instances": [
            i for i in combined["instances"]
            if _as_own(i["leaf_property"], check) != i["leaf_property"]
        ],
        "by_list": {
            LIST: value for key, value in combined["by_list"].items() if key == check
        },
    }, check)


def verify(schema: Mapping[str, Any], manifest: Mapping[str, Any],
           src: Mapping[str, Mapping[str, Any]], benchmark: Mapping[str, Any]) -> int:
    """Score exp-02 predictions both ways; return how many scorings were compared.

    Uses replicate 0 of exp-02's `pinned` and `<check>@v3` arms -- the two
    arrangements exp-03 runs -- so the predictions cover both what a monolith
    and what a delegating check actually answer.
    """
    combined = FlatEvaluator(schema["format"]["schema"], parse_eval_manifest(manifest))
    alone = {
        check: FlatEvaluator(
            src[check]["schema"]["format"]["schema"],
            parse_eval_manifest(src[check]["manifest"]),
        )
        for check in CHECKS
    }
    combined_schema = jsonschema.Draft7Validator(schema["format"]["schema"])
    compared = 0
    for arm in ("pinned", "{check}@v3"):
        for example in benchmark["examples"]:
            paths = {
                check: EXP02_RUNS / check / arm.format(check=check) / "rep-00"
                / example / "prediction.json"
                for check in CHECKS
            }
            if not all(p.is_file() for p in paths.values()):
                continue
            preds = {check: read_json(p) for check, p in paths.items()}
            gold = gold_for(example, src)
            combined_gold, combined_pred = combine(gold), combine(preds)
            combined_schema.validate(combined_gold)
            combined_schema.validate(combined_pred)

            together = _canonical(combined.evaluate(combined_gold, combined_pred))
            claimed = 0
            for check in CHECKS:
                single = _canonical(alone[check].evaluate(gold[check], preds[check]))
                part = _part(together, check)
                if part != single:
                    raise AssertionError(
                        f"{check} on {example} [{arm}]: the combined contract "
                        f"scores this check differently from its own contract"
                    )
                claimed += len(part["instances"])
                compared += 1
            if claimed != len(together["instances"]) or (
                len(together["by_list"]) != len(CHECKS)
            ):
                raise AssertionError(
                    f"{example} [{arm}]: the combined result holds instances or "
                    f"lists that belong to no check"
                )
    if not compared:
        raise AssertionError("no exp-02 predictions found to verify against")
    return compared


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", action="store_true",
                        help="Also write the merged gold into the examples tree")
    parser.add_argument("--check", action="store_true",
                        help="Write nothing; fail if a committed file differs from what would be built")
    args = parser.parse_args(argv)

    src = sources()
    schema = build_schema(src)
    manifest = build_manifest(src)
    benchmark = build_benchmark(src)

    compared = verify(schema, manifest, src, benchmark)
    print(f"verified: {compared} (check, example, arm) scorings identical "
          f"under the combined contract and each check's own")

    outputs = {
        TARGET / "schema.json": dump(schema),
        TARGET / "eval-manifest.json": dump(manifest),
        TARGET / "benchmark.json": dump(benchmark),
    }
    if args.gold:
        for example in benchmark["examples"]:
            outputs[EXAMPLES / example / "checks" / ENTRY / "expected_output.json"] = (
                dump(combine(gold_for(example, src)))
            )

    if args.gold and not args.check:
        # The merged gold is part of exp-03's frozen gold, at GOLD_TAG. Writing
        # it again would write into the snapshot, which git rebuilds from the tag.
        parser.error(f"exp-03's gold is frozen at {GOLD_TAG}; use --gold --check to verify it")

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
