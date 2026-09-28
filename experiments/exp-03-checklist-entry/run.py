"""Run exp-03: does running the checks through one entry skill degrade them?

Two checklists, built from byte-identical skills:

    fig-checklist-exp03             the fan-out: `do-fig-checklist` (D) is the
                                    one leaf, and one session per figure runs
                                    all three checks through it
    fig-checklist-exp03-per-check   the controls: each check dispatched on its
                                    own, one session per figure per check

and, in each, the two arrangements exp-02 found worth carrying forward:

    fan-out                       control
    A|B|C_i <- D      pinned      A|B|C_i      pinned
    A|B <- C_i <- D   all @v3     A|B <- C_i   <check>@v3

where A is panel identification, B classification, C_i a check. Neither
checklist carries `identify-panels`: nothing here calls A on its own.

**The controls are run here, not borrowed from exp-02.** exp-02's controls had
`identify-panels` in their skill pool, and its description alone drew calls in
5-12% of `A|B <- C` sessions. Re-running them without it keeps the fan-out and
its controls identical in everything but the entry point.

Output:

    experiments/runs/exp-03-checklist-entry/fan-out/<arm>/rep-NN/<example>/
    experiments/runs/exp-03-checklist-entry/per-check/<check>/<arm>/rep-NN/<example>/

**Smoke test first.** `--smoke` runs every arm of both checklists on a few
examples, one replicate, and reports from the traces whether D dispatched to all
three checks, how often `classify-panels` was invoked per session, in which
order the checks ran, and what a figure cost each way.

    python experiments/exp-03-checklist-entry/run.py --smoke
    python experiments/exp-03-checklist-entry/run.py --dry-run
    python experiments/exp-03-checklist-entry/run.py

The full run is 1,520 sessions: 380 fan-out, 1,140 per-check. Re-running is
safe: the harness skips an example that already has a prediction. Use
`--force` only to deliberately redo work.

The analysis lives in `notebooks/experiments/exp-03-checklist-entry.ipynb` and
reads what this writes. It does not run anything.
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
from soda_mmqc.agentic.skills import resolve_check_dir        # noqa: E402

FAN_OUT = "fig-checklist-exp03"
PER_CHECK = "fig-checklist-exp03-per-check"
ENTRY = "do-fig-checklist"
CHECKS = ("micrograph-scale-bar", "individual-data-points", "error-bars-defined")
CLASSIFY = "classify-panels"

#: Pinned by exact name, as in exp-02 whose model this must match.
MODEL = "claude-sonnet-5"
PROVIDER = "claude-sdk"

RUNS = REPO / "experiments" / "runs" / "exp-03-checklist-entry"


def fan_out_unpins() -> List[Optional[Mapping[str, Sequence[str]]]]:
    """The two fan-out arms: the pins, and all three checks moved to v3 together.

    One unpin map per arm rather than one map with every version listed:
    `unpin` expands to the product of what it is given, and three checks at
    (v1, v3) would be eight arms, six of them mixtures nobody asked for.
    """
    return [None, {check: ("v3",) for check in CHECKS}]


def per_check_unpin(check: str) -> Mapping[str, Sequence[str]]:
    """Both control arms of one check: the pin (v1) and v3."""
    return {check: ("v1", "v3")}


def example_count(checklist: str, check: str) -> int:
    benchmark = json.loads(
        (resolve_check_dir(checklist, check) / "benchmark.json").read_text(
            encoding="utf-8"
        )
    )
    return len(benchmark["examples"])


def planned_sessions(parts: Sequence[str], replicates: int,
                     limit: Optional[int] = None) -> Dict[str, int]:
    def n(checklist: str, check: str) -> int:
        count = example_count(checklist, check)
        return min(count, limit) if limit else count

    planned: Dict[str, int] = {}
    if "fan-out" in parts:
        planned["fan-out"] = n(FAN_OUT, ENTRY) * len(fan_out_unpins()) * replicates
    if "per-check" in parts:
        planned["per-check"] = sum(n(PER_CHECK, c) * 2 for c in CHECKS) * replicates
    return planned


def run_part(part: str, root: Path, *, replicates: int, limit: Optional[int],
             force: bool) -> List[str]:
    """Run one checklist's arms under ``root``; return the failures."""
    jobs: List[Tuple[str, str, Path, Optional[Mapping[str, Sequence[str]]]]] = []
    if part == "fan-out":
        for unpin in fan_out_unpins():
            jobs.append((FAN_OUT, ENTRY, root / "fan-out", unpin))
    else:
        for check in CHECKS:
            jobs.append((PER_CHECK, check, root / "per-check" / check,
                         per_check_unpin(check)))

    failures: List[str] = []
    for checklist, check, output, unpin in jobs:
        _, report = run_check_live(
            checklist,
            check,
            output=output,
            model=MODEL,
            provider=PROVIDER,
            limit=limit,
            replicates=replicates,
            unpin=unpin,
            force=force,
        )
        for entry in report:
            if entry["status"] == "failed":
                # A failed fan-out session loses all three checks at once, so
                # it is reported as one failure of D, never as three.
                failures.append(
                    f"{part} {check} {entry['label']} "
                    f"rep-{entry['replicate']:02d} {entry['example']}: "
                    f"{entry.get('error', '')}"
                )
        logger.info(
            "  %s %s %s: %d ran, %d skipped, %d failed",
            part, check, dict(unpin or {}) or "pinned",
            sum(1 for e in report if e["status"] == "ok"),
            sum(1 for e in report if e["status"] == "skipped"),
            sum(1 for e in report if e["status"] == "failed"),
        )
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
    """Every session under a run root, keyed by (arm, example)."""
    found: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for prediction in root.glob("*/rep-00/**/prediction.json"):
        example_dir = prediction.parent
        arm = prediction.relative_to(root).parts[0]
        example = str(example_dir.relative_to(root / arm / "rep-00"))
        found[(arm, example)] = _session(example_dir)
    return found


def report_smoke(root: Path) -> int:
    fan_out = _sessions(root / "fan-out")
    per_check = {check: _sessions(root / "per-check" / check) for check in CHECKS}
    if not fan_out:
        logger.error("no fan-out sessions found under %s", root / "fan-out")
        return 1

    def control_arm(fan_out_arm: str, check: str) -> str:
        return "pinned" if fan_out_arm == "pinned" else f"{check}@v3"

    logger.info("--- smoke test: did D dispatch, and what did a figure cost? ---")
    dispatched = 0
    for (arm, example), s in sorted(fan_out.items()):
        called = [name for name in s["skills"] if name in CHECKS]
        full = set(called) == set(CHECKS)
        dispatched += full
        controls = [
            per_check[c].get((control_arm(arm, c), example)) for c in CHECKS
        ]
        have = [c for c in controls if c]
        logger.info(
            "  %-10s %-42s %s  classify x%d  order %s",
            "pinned" if arm == "pinned" else "all@v3",
            example,
            "all 3 checks" if full else f"ONLY {sorted(set(called))}",
            s["skills"].count(CLASSIFY),
            " > ".join(dict.fromkeys(called)) or "-",
        )
        if len(have) == len(CHECKS):
            logger.info(
                "  %-10s %-42s cost $%.3f vs $%.3f   turns %d vs %d   "
                "time %.0fs vs %.0fs sum, %.0fs max",
                "", "", s["cost"], sum(c["cost"] for c in have),
                s["turns"], sum(c["turns"] for c in have),
                s["ms"] / 1000, sum(c["ms"] for c in have) / 1000,
                max(c["ms"] for c in have) / 1000,
            )
        unexpected = set(s["skills"]) - {ENTRY, CLASSIFY, *CHECKS}
        if unexpected:
            logger.warning("    unexpected skill invoked: %s", sorted(unexpected))

    logger.info("  %s", "-" * 60)
    logger.info("  D dispatched to all three checks in %d/%d fan-out sessions",
                dispatched, len(fan_out))
    fan_cost = sum(s["cost"] for s in fan_out.values())
    ctl_cost = sum(s["cost"] for runs in per_check.values() for s in runs.values())
    logger.info("  spent: fan-out $%.2f over %d sessions, per-check $%.2f over %d",
                fan_cost, len(fan_out), ctl_cost,
                sum(len(r) for r in per_check.values()))
    if dispatched == 0:
        logger.error(
            "D never dispatched to all three checks. The fan-out arms are not "
            "what they are labelled as; fix D's prose before the full run."
        )
        return 1
    return 0


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replicates", type=int, default=5,
        help="Samples per arm (default: %(default)s), matching exp-02",
    )
    parser.add_argument(
        "--part", choices=("all", "fan-out", "per-check"), default="all",
        help="Run only the fan-out or only the per-check controls",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Run at most this many examples per check",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-run examples that already have a prediction",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would run, and its size, without running it",
    )
    parser.add_argument(
        "--smoke", action="store_true",
        help=(
            "Run every arm of both checklists on a few examples, one "
            "replicate, then report dispatch, reuse, order and cost"
        ),
    )
    args = parser.parse_args(argv)
    parts = ("fan-out", "per-check") if args.part == "all" else (args.part,)

    if args.smoke:
        limit = args.limit or 3
        root = RUNS / "smoke"
        planned = planned_sessions(parts, 1, limit)
        logger.info("exp-03 smoke test: %d example(s), 1 replicate -- %s",
                    limit, ", ".join(f"{k} {v}" for k, v in planned.items()))
        failures: List[str] = []
        for part in parts:
            failures += run_part(part, root, replicates=1, limit=limit, force=True)
        for line in failures:
            logger.error("  %s", line)
        return report_smoke(root) or (1 if failures else 0)

    planned = planned_sessions(parts, args.replicates, args.limit)
    logger.info(
        "exp-03: %d replicate(s) -- up to %d session(s) (%s)",
        args.replicates, sum(planned.values()),
        ", ".join(f"{k} {v}" for k, v in planned.items()),
    )
    if args.dry_run:
        if "fan-out" in parts:
            print(f"  {FAN_OUT}/{ENTRY:<24} -> {RUNS / 'fan-out'}")
            for unpin in fan_out_unpins():
                print(f"      unpin {dict(unpin or {}) or 'none (pinned)'}")
        if "per-check" in parts:
            for check in CHECKS:
                print(f"  {PER_CHECK}/{check:<24} -> {RUNS / 'per-check' / check}")
                print(f"      unpin {dict(per_check_unpin(check))}")
        return 0

    failures = []
    for part in parts:
        logger.info("[%s]", part)
        failures += run_part(part, RUNS, replicates=args.replicates,
                             limit=args.limit, force=args.force)
    if failures:
        # Reported, never swallowed: an arm that fails more often than its
        # control is a result about that arm.
        logger.error("%d session(s) failed:", len(failures))
        for line in failures:
            logger.error("  %s", line)
        return 1
    logger.info("exp-03 complete; runs under %s", RUNS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
