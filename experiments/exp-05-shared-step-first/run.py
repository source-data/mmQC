"""Run exp-05: the shared step first, by design.

One arrangement, `[A|B, {C_i}] <- D`: the entry point (v2) invokes
`classify-panels` (A|B) once, then each check (v4), which classifies nothing
itself. Both contract shapes, from `fig-checklist-exp05`'s pins:

    do-fig-checklist-cm   check-major
    do-fig-checklist-pm   panel-major

Their references are exp-04's `A|B <- C_i <- D` of the same shape, **reused**
from `experiments/runs/exp-04-panel-major/`. As a sanity check, not a gate,
exp-04's PM `A|B <- C_i <- D` is rerun once on every figure from the frozen
`fig-checklist-exp04`.

Output:

    experiments/runs/exp-05-shared-step-first/<cm|pm>/pinned/rep-NN/<example>/
    experiments/runs/exp-05-shared-step-first/sanity/pm/<exp-04 arm>/rep-00/<example>/

    python experiments/exp-05-shared-step-first/run.py --smoke
    python experiments/exp-05-shared-step-first/run.py --dry-run
    python experiments/exp-05-shared-step-first/run.py

The full run is 418 sessions: 2 x 38 figures x 5 replicates, and 38 for the
sanity rerun. Re-running skips what already has a prediction; an account error
stops the run at once.

Scoring is the notebook's, against `gold-v4`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from soda_mmqc import logger                                      # noqa: E402
from soda_mmqc.agentic.runner import RunAborted, run_check_live   # noqa: E402
from soda_mmqc.agentic.runtime import ASSEMBLY_CLOSURE            # noqa: E402
from soda_mmqc.agentic.skills import resolve_check_dir            # noqa: E402

CHECKLIST = "fig-checklist-exp05"
ENTRIES = {"cm": "do-fig-checklist-cm", "pm": "do-fig-checklist-pm"}
CHECKS = ("micrograph-scale-bar", "individual-data-points", "error-bars-defined")
CLASSIFY, IDENTIFY = "classify-panels", "identify-panels"

#: exp-04's model, so its runs can serve as references.
MODEL = "claude-sonnet-5"
PROVIDER = "claude-sdk"
GOLD_TAG = "gold-v4"
ASSEMBLY = ASSEMBLY_CLOSURE

RUNS = REPO / "experiments" / "runs" / "exp-05-shared-step-first"
EXP04_RUNS = REPO / "experiments" / "runs" / "exp-04-panel-major"

#: The sanity rerun: exp-04's PM under A|B <- C_i <- D, from exp-04's frozen
#: checklist, the same unpin exp-04's runner used.
SANITY_CHECKLIST = "fig-checklist-exp04"
SANITY_ENTRY = "do-fig-checklist-pm"
SANITY_UNPIN = {check: ("v3",) for check in CHECKS}
SANITY_ARM = "-".join(f"{c}@v3" for c in sorted(CHECKS))


def example_count(checklist: str, entry: str) -> int:
    return len(json.loads((resolve_check_dir(checklist, entry) / "benchmark.json")
                          .read_text(encoding="utf-8"))["examples"])


def jobs(root: Path, replicates: int, *, sanity: bool):
    """(label, checklist, entry, output, unpin, replicates) for every condition."""
    for shape, entry in ENTRIES.items():
        yield shape, CHECKLIST, entry, root / shape, None, replicates
    if sanity:
        yield "sanity", SANITY_CHECKLIST, SANITY_ENTRY, root / "sanity" / "pm", SANITY_UNPIN, 1


def run(root: Path, *, replicates: int, limit: Optional[int], force: bool,
        sanity: bool) -> List[str]:
    failures: List[str] = []
    for label, checklist, entry, output, unpin, reps in jobs(root, replicates, sanity=sanity):
        _, report = run_check_live(
            checklist, entry, output=output, model=MODEL, provider=PROVIDER,
            limit=limit, replicates=reps, unpin=unpin, force=force, assembly=ASSEMBLY,
        )
        for e in report:
            if e["status"] == "failed":
                failures.append(f"{label} rep-{e['replicate']:02d} {e['example']}: "
                                f"{e.get('error', '')}")
        logger.info("  %-6s %d ran, %d skipped, %d failed", label,
                    sum(e["status"] == "ok" for e in report),
                    sum(e["status"] == "skipped" for e in report),
                    sum(e["status"] == "failed" for e in report))
    return failures


# --------------------------------------------------------------------------
# Smoke report: read the traces and the audits, nothing else.
# --------------------------------------------------------------------------

def _session(example_dir: Path) -> Dict[str, Any]:
    intermediates = example_dir / "intermediates"
    trace = json.loads((intermediates / "skill_trace.json").read_text(encoding="utf-8"))
    usage = json.loads((intermediates / "tool_audit.json").read_text(encoding="utf-8")
                       ).get("usage") or {}
    return {
        "skills": [e.get("skill") for e in trace if isinstance(e, dict)],
        "cost": usage.get("total_cost_usd") or 0.0,
        "output_tokens": (usage.get("usage") or {}).get("output_tokens") or 0,
        "turns": usage.get("num_turns") or 0,
        "ms": usage.get("duration_ms") or 0,
    }


def report_smoke(root: Path) -> int:
    worst = 0
    logger.info("--- smoke test: shared step first? all checks dispatched? cost? ---")
    for shape, entry in ENTRIES.items():
        found = sorted((root / shape).glob("pinned/rep-00/**/prediction.json"))
        if not found:
            logger.error("  %s: no sessions", shape)
            worst = 1
            continue
        dispatched = first = 0
        for prediction in found:
            s = _session(prediction.parent)
            skills = s["skills"]
            called = [k for k in skills if k in CHECKS]
            full = set(called) == set(CHECKS)
            dispatched += full
            classify_first = (CLASSIFY in skills and
                              (not called or skills.index(CLASSIFY) < skills.index(called[0])))
            first += classify_first
            example = str(prediction.parent.relative_to(root / shape / "pinned" / "rep-00"))
            logger.info("  %s %-42s %s  classify x%d %s  order %s  $%.3f  %d out  %d turns  %.0fs",
                        shape, example,
                        "all 3 checks" if full else f"ONLY {sorted(set(called))}",
                        skills.count(CLASSIFY), "first" if classify_first else "NOT FIRST",
                        " > ".join(dict.fromkeys(called)) or "-",
                        s["cost"], s["output_tokens"], s["turns"], s["ms"] / 1000)
            unexpected = set(skills) - {entry, CLASSIFY, *CHECKS}
            if unexpected:
                logger.warning("    outside the closure: %s", sorted(unexpected))
                worst = 1
        logger.info("  %s: all three checks in %d/%d; classify-panels before any check in %d/%d",
                    shape, dispatched, len(found), first, len(found))
        if dispatched == 0:
            logger.error("  %s: D never dispatched to all three checks", shape)
            worst = 1
    return worst


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--replicates", type=int, default=5)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--smoke", action="store_true",
                        help="Both new conditions on a few figures, one replicate; no sanity rerun")
    args = parser.parse_args(argv)

    if args.smoke:
        root = RUNS / "smoke"
        limit = args.limit or 3
        logger.info("exp-05 smoke test: %d figure(s), 1 replicate, 2 conditions", limit)
        try:
            failures = run(root, replicates=1, limit=limit, force=True, sanity=False)
        except RunAborted as stopped:
            logger.error("smoke test stopped on an account error: %s", stopped)
            return 2
        for line in failures:
            logger.error("  %s", line)
        return report_smoke(root) or (1 if failures else 0)

    n = example_count(CHECKLIST, ENTRIES["cm"])
    n = min(n, args.limit) if args.limit else n
    logger.info("exp-05: up to %d session(s): cm %d, pm %d, sanity %d",
                2 * n * args.replicates + n, n * args.replicates, n * args.replicates, n)
    if args.dry_run:
        for label, checklist, entry, output, unpin, reps in jobs(RUNS, args.replicates, sanity=True):
            print(f"  {label:<6} {checklist}/{entry}  unpin {dict(unpin or {}) or 'none'}  "
                  f"x{reps} -> {output}")
        return 0
    try:
        failures = run(RUNS, replicates=args.replicates, limit=args.limit, force=args.force,
                       sanity=True)
    except RunAborted as stopped:
        logger.error("exp-05 stopped on an account error: %s", stopped)
        logger.error("Fix the API key or the account, then rerun the same command: "
                     "predictions already written are skipped.")
        return 2
    if failures:
        logger.error("%d session(s) failed:", len(failures))
        for line in failures:
            logger.error("  %s", line)
        return 1
    logger.info("exp-05 complete; runs under %s", RUNS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
