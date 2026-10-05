"""Run exp-04: panel-major or check-major, on exp-03's DAG with the cleaned wording.

One checklist, `fig-checklist-exp04`, with two entry points whose prose is
identical but for the name; each owns one contract shape:

    do-fig-checklist-cm   check-major: one list per check, as exp-03's
    do-fig-checklist-pm   panel-major: one row per panel, each check's fields
                          in an object inside it

and three arrangements, reached by moving pins:

    A|B|C_i <- D          pinned           checks at v1, A and B inline
    A|B <- C_i <- D       checks @v3       checks call classify-panels v1
    A <- B <- C_i <- D    checks @v3,      classify-panels v2 calls
                          classify @v2     identify-panels

where A is panel identification, B classification, C_i a check and D the entry
point. Six conditions: each arrangement under each shape.

Every session is assembled as the **closure** of its entry point, so a session
started from one entry point never sees the other, and `identify-panels` is
offered only in the third arrangement, the one whose prose reaches it.

Output:

    experiments/runs/exp-04-panel-major/<cm|pm>/<arm>/rep-NN/<example>/

**Smoke test first.** `--smoke` runs all six conditions on a few examples, one
replicate, and reports from the traces whether D dispatched to all three
checks, how often `classify-panels` and `identify-panels` were invoked, in
which order the checks ran, and what a figure cost.

    python experiments/exp-04-panel-major/run.py --smoke
    python experiments/exp-04-panel-major/run.py --dry-run
    python experiments/exp-04-panel-major/run.py

The full run is 1,140 sessions: 38 figures x 5 replicates x 6 conditions.
Re-running is safe: the harness skips an example that already has a
prediction. Use `--force` only to deliberately redo work.

Scoring is the notebook's, against the gold at `gold-v4`; this script runs
sessions and reads traces, nothing else.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from soda_mmqc import logger                                  # noqa: E402
from soda_mmqc.agentic.runner import run_check_live           # noqa: E402
from soda_mmqc.agentic.runtime import ASSEMBLY_CLOSURE        # noqa: E402
from soda_mmqc.agentic.skills import resolve_check_dir        # noqa: E402

CHECKLIST = "fig-checklist-exp04"
ENTRIES = {"cm": "do-fig-checklist-cm", "pm": "do-fig-checklist-pm"}
CHECKS = ("micrograph-scale-bar", "individual-data-points", "error-bars-defined")
CLASSIFY, IDENTIFY = "classify-panels", "identify-panels"

#: As exp-03, pinned by exact name: the series compares models later, not here.
MODEL = "claude-sonnet-5"
PROVIDER = "claude-sdk"

#: The gold the analysis scores against: gold-v3 with the merged gold of the
#: two entry points added. Named here so the notebook and this script agree.
GOLD_TAG = "gold-v4"

RUNS = REPO / "experiments" / "runs" / "exp-04-panel-major"

#: Named rather than left to the default, so a later change of default cannot
#: change what this run assembles.
ASSEMBLY = ASSEMBLY_CLOSURE

#: The three arrangements, each one unpin map, so `unpin` -- which expands to
#: the product of what it is given -- yields exactly one arm per map.
ARRANGEMENTS: Dict[str, Optional[Mapping[str, Sequence[str]]]] = {
    "A|B|C_i <- D": None,
    "A|B <- C_i <- D": {check: ("v3",) for check in CHECKS},
    "A <- B <- C_i <- D": {**{check: ("v3",) for check in CHECKS}, CLASSIFY: ("v2",)},
}


def arm_label(unpin: Optional[Mapping[str, Sequence[str]]]) -> str:
    """The directory the harness writes an arrangement to."""
    if not unpin:
        return "pinned"
    return "-".join(f"{skill}@{versions[0]}" for skill, versions in sorted(unpin.items()))


def arrangement_of(label: str) -> str:
    return next(name for name, unpin in ARRANGEMENTS.items() if arm_label(unpin) == label)


def example_count(entry: str) -> int:
    benchmark = json.loads((resolve_check_dir(CHECKLIST, entry) / "benchmark.json")
                           .read_text(encoding="utf-8"))
    return len(benchmark["examples"])


def planned_sessions(shapes: Sequence[str], replicates: int,
                     limit: Optional[int] = None) -> Dict[str, int]:
    planned = {}
    for shape in shapes:
        n = example_count(ENTRIES[shape])
        planned[shape] = (min(n, limit) if limit else n) * len(ARRANGEMENTS) * replicates
    return planned


def run_shape(shape: str, root: Path, *, replicates: int, limit: Optional[int],
              force: bool) -> List[str]:
    """Run one entry point under every arrangement; return the failures."""
    entry = ENTRIES[shape]
    failures: List[str] = []
    for name, unpin in ARRANGEMENTS.items():
        _, report = run_check_live(
            CHECKLIST,
            entry,
            output=root / shape,
            model=MODEL,
            provider=PROVIDER,
            limit=limit,
            replicates=replicates,
            unpin=unpin,
            force=force,
            assembly=ASSEMBLY,
        )
        for e in report:
            if e["status"] == "failed":
                # A failed session loses all three checks at once, so it is
                # one failure of the condition, never three.
                failures.append(f"{shape} {name} rep-{e['replicate']:02d} "
                                f"{e['example']}: {e.get('error', '')}")
        logger.info("  %s %-20s %d ran, %d skipped, %d failed", shape, name,
                    sum(e["status"] == "ok" for e in report),
                    sum(e["status"] == "skipped" for e in report),
                    sum(e["status"] == "failed" for e in report))
    return failures


# --------------------------------------------------------------------------
# Smoke report: read the traces and the audits, nothing else.
# --------------------------------------------------------------------------

def _session(example_dir: Path) -> Dict[str, Any]:
    """What one session invoked, in order, and what it spent."""
    intermediates = example_dir / "intermediates"
    trace = json.loads((intermediates / "skill_trace.json").read_text(encoding="utf-8"))
    audit = json.loads((intermediates / "tool_audit.json").read_text(encoding="utf-8"))
    usage = audit.get("usage") or {}
    return {
        "skills": [e.get("skill") for e in trace if isinstance(e, dict)],
        "cost": usage.get("total_cost_usd") or 0.0,
        "turns": usage.get("num_turns") or 0,
        "ms": usage.get("duration_ms") or 0,
    }


def _sessions(root: Path) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Every session under one shape's root, keyed by (arrangement, example)."""
    found: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for prediction in root.glob("*/rep-00/**/prediction.json"):
        label = prediction.relative_to(root).parts[0]
        example = str(prediction.parent.relative_to(root / label / "rep-00"))
        found[(arrangement_of(label), example)] = _session(prediction.parent)
    return found


#: What each arrangement's prose should reach, beyond D and the checks.
EXPECTED_SHARED = {
    "A|B|C_i <- D": set(),
    "A|B <- C_i <- D": {CLASSIFY},
    "A <- B <- C_i <- D": {CLASSIFY, IDENTIFY},
}


def report_smoke(root: Path) -> int:
    sessions = {shape: _sessions(root / shape) for shape in ENTRIES}
    if not any(sessions.values()):
        logger.error("no sessions found under %s", root)
        return 1

    logger.info("--- smoke test: did D dispatch, what did it reach, what did it cost? ---")
    worst = 0
    for shape, found in sessions.items():
        entry = ENTRIES[shape]
        for name in ARRANGEMENTS:
            rows = {ex: s for (arr, ex), s in found.items() if arr == name}
            if not rows:
                logger.warning("  %s %-20s no sessions", shape, name)
                worst = 1
                continue
            dispatched = 0
            for example, s in sorted(rows.items()):
                called = [k for k in s["skills"] if k in CHECKS]
                full = set(called) == set(CHECKS)
                dispatched += full
                logger.info("  %s %-20s %-42s %s  classify x%d  identify x%d  order %s  "
                            "$%.3f  %d turns  %.0fs",
                            shape, name, example,
                            "all 3 checks" if full else f"ONLY {sorted(set(called))}",
                            s["skills"].count(CLASSIFY), s["skills"].count(IDENTIFY),
                            " > ".join(dict.fromkeys(called)) or "-",
                            s["cost"], s["turns"], s["ms"] / 1000)
                unexpected = set(s["skills"]) - {entry, *CHECKS, *EXPECTED_SHARED[name]}
                if unexpected:
                    logger.warning("    outside this arrangement's closure: %s", sorted(unexpected))
                    worst = 1
            logger.info("  %s %-20s dispatched to all three checks in %d/%d; $%.2f",
                        shape, name, dispatched, len(rows),
                        sum(s["cost"] for s in rows.values()))
            if dispatched == 0:
                logger.error("  %s %s: D never dispatched to all three checks; fix D's prose "
                             "before the full run", shape, name)
                worst = 1
    return worst


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--replicates", type=int, default=5,
                        help="Samples per condition (default: %(default)s)")
    parser.add_argument("--shape", choices=("all", "cm", "pm"), default="all",
                        help="Run only the check-major or only the panel-major entry point")
    parser.add_argument("--limit", type=int, default=None,
                        help="Run at most this many examples per condition")
    parser.add_argument("--force", action="store_true",
                        help="Re-run examples that already have a prediction")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would run, and its size, without running it")
    parser.add_argument("--smoke", action="store_true",
                        help="Run all six conditions on a few examples, one replicate, "
                             "then report dispatch, reach, order and cost")
    args = parser.parse_args(argv)
    shapes = tuple(ENTRIES) if args.shape == "all" else (args.shape,)

    if args.smoke:
        limit = args.limit or 3
        root = RUNS / "smoke"
        planned = planned_sessions(shapes, 1, limit)
        logger.info("exp-04 smoke test: %d example(s), 1 replicate -- %s", limit,
                    ", ".join(f"{k} {v}" for k, v in planned.items()))
        failures: List[str] = []
        for shape in shapes:
            failures += run_shape(shape, root, replicates=1, limit=limit, force=True)
        for line in failures:
            logger.error("  %s", line)
        return report_smoke(root) or (1 if failures else 0)

    planned = planned_sessions(shapes, args.replicates, args.limit)
    logger.info("exp-04: %d replicate(s) -- up to %d session(s) (%s)",
                args.replicates, sum(planned.values()),
                ", ".join(f"{k} {v}" for k, v in planned.items()))
    if args.dry_run:
        for shape in shapes:
            print(f"  {CHECKLIST}/{ENTRIES[shape]}")
            for name, unpin in ARRANGEMENTS.items():
                print(f"      {name:<20} -> {RUNS / shape / arm_label(unpin)}")
        return 0

    failures = []
    for shape in shapes:
        logger.info("[%s]", shape)
        failures += run_shape(shape, RUNS, replicates=args.replicates,
                              limit=args.limit, force=args.force)
    if failures:
        # Reported, never swallowed: a condition that fails more often than
        # another is a result about that condition.
        logger.error("%d session(s) failed:", len(failures))
        for line in failures:
            logger.error("  %s", line)
        return 1
    logger.info("exp-04 complete; runs under %s", RUNS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
