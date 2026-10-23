"""Run exp-06: the full figure checklist, fanned in from one entry point.

`fig-checklist-exp06`'s entry point, `do-fig-checklist-cm`, dispatches the
eleven checks in one session per figure, under two arrangements:

    A|B <- C_i <- D       the pins: each check invokes classify-panels v1
    A <- B <- C_i <- D    classify-panels @v2, which invokes identify-panels

Output:

    experiments/runs/exp-06-full-checklist/<arm>/rep-NN/<example>/

    python experiments/exp-06-full-checklist/run.py --smoke
    python experiments/exp-06-full-checklist/run.py --dry-run
    python experiments/exp-06-full-checklist/run.py

The full run is 370 sessions: 2 arrangements x 37 figures x 5 replicates, at
concurrency 50. Re-running skips what already has a prediction; an account
error stops the run at once. Scoring is the notebook's, against `gold-v5`.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from soda_mmqc import logger                                      # noqa: E402
from soda_mmqc.agentic.runner import RunAborted, run_check_live   # noqa: E402
from mmqc_utils.agentic.runtime import ASSEMBLY_CLOSURE            # noqa: E402
from soda_mmqc.config import resolve_check_dir                    # noqa: E402

CHECKLIST = "fig-checklist-exp06"
ENTRY = "do-fig-checklist-cm"
#: In D's order.
CHECKS = (
    "micrograph-scale-bar", "image-annotation-defined", "single-channel-for-overlay",
    "individual-data-points", "error-bars-defined", "plot-axis-units", "plot-gap-labeling",
    "stat-significance-level", "stat-test", "replication-reporting",
    "panel-image-matches-caption",
)
CLASSIFY, IDENTIFY = "classify-panels", "identify-panels"

MODEL = "claude-sonnet-5"
PROVIDER = "claude-sdk"
GOLD_TAG = "gold-v5"
ASSEMBLY = ASSEMBLY_CLOSURE

#: Above the recommended 38 (soda_mmqc.agentic.runner.RECOMMENDED_CONCURRENCY):
#: decided for exp-06, ~13 GB of session processes and about a sixth of the
#: output-token rate limit.
CONCURRENCY = 50

RUNS = REPO / "experiments" / "runs" / "exp-06-full-checklist"

ARRANGEMENTS: Dict[str, Optional[Mapping[str, Sequence[str]]]] = {
    "A|B <- C_i <- D": None,
    "A <- B <- C_i <- D": {CLASSIFY: ("v2",)},
}
EXPECTED_SHARED = {"A|B <- C_i <- D": {CLASSIFY}, "A <- B <- C_i <- D": {CLASSIFY, IDENTIFY}}


def arm_label(unpin: Optional[Mapping[str, Sequence[str]]]) -> str:
    if not unpin:
        return "pinned"
    return "-".join(f"{skill}@{versions[0]}" for skill, versions in sorted(unpin.items()))


def arrangement_of(label: str) -> str:
    return next(name for name, unpin in ARRANGEMENTS.items() if arm_label(unpin) == label)


def example_count() -> int:
    return len(json.loads((resolve_check_dir(CHECKLIST, ENTRY) / "benchmark.json")
                          .read_text(encoding="utf-8"))["examples"])


def run(root: Path, *, replicates: int, limit: Optional[int], force: bool) -> List[str]:
    failures: List[str] = []
    for name, unpin in ARRANGEMENTS.items():
        _, report = run_check_live(
            CHECKLIST, ENTRY, output=root, model=MODEL, provider=PROVIDER, limit=limit,
            replicates=replicates, unpin=unpin, force=force, assembly=ASSEMBLY,
            concurrency=CONCURRENCY,
        )
        for e in report:
            if e["status"] == "failed":
                failures.append(f"{name} rep-{e['replicate']:02d} {e['example']}: "
                                f"{e.get('error', '')}")
        logger.info("  %-20s %d ran, %d skipped, %d failed", name,
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
    skipped: Counter = Counter()
    logger.info("--- smoke test: how many of the eleven checks, the shared step, cost ---")
    for name, unpin in ARRANGEMENTS.items():
        found = sorted((root / arm_label(unpin)).glob("rep-00/**/prediction.json"))
        if not found:
            logger.error("  %s: no sessions", name)
            worst = 1
            continue
        full = 0
        for prediction in found:
            s = _session(prediction.parent)
            called = list(dict.fromkeys(k for k in s["skills"] if k in CHECKS))
            missing = [c for c in CHECKS if c not in called]
            skipped.update(missing)
            full += not missing
            in_order = called == [c for c in CHECKS if c in called]
            example = str(prediction.parent.relative_to(root / arm_label(unpin) / "rep-00"))
            logger.info("  %-20s %-42s %2d/11 checks%s  classify x%d  identify x%d  %s  "
                        "$%.3f  %d out  %d turns  %.0fs",
                        name, example, len(called),
                        f" (missing {missing})" if missing else "",
                        s["skills"].count(CLASSIFY), s["skills"].count(IDENTIFY),
                        "in order" if in_order else "OUT OF ORDER",
                        s["cost"], s["output_tokens"], s["turns"], s["ms"] / 1000)
            unexpected = set(s["skills"]) - {ENTRY, *CHECKS, *EXPECTED_SHARED[name]}
            if unexpected:
                logger.warning("    outside the closure: %s", sorted(unexpected))
                worst = 1
        logger.info("  %-20s all eleven checks in %d/%d", name, full, len(found))
        if full == 0:
            logger.error("  %s: D never dispatched all eleven checks", name)
            worst = 1
    if skipped:
        logger.info("  skipped, across sessions: %s", dict(skipped.most_common()))
    return worst


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--replicates", type=int, default=5)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--smoke", action="store_true",
                        help="Both arrangements on a few figures, one replicate")
    args = parser.parse_args(argv)

    if args.smoke:
        root = RUNS / "smoke"
        limit = args.limit or 3
        logger.info("exp-06 smoke test: %d figure(s), 1 replicate, 2 arrangements", limit)
        try:
            failures = run(root, replicates=1, limit=limit, force=True)
        except RunAborted as stopped:
            logger.error("smoke test stopped on an account error: %s", stopped)
            return 2
        for line in failures:
            logger.error("  %s", line)
        return report_smoke(root) or (1 if failures else 0)

    n = example_count()
    n = min(n, args.limit) if args.limit else n
    logger.info("exp-06: up to %d session(s), concurrency %d",
                len(ARRANGEMENTS) * n * args.replicates, CONCURRENCY)
    if args.dry_run:
        for name, unpin in ARRANGEMENTS.items():
            print(f"  {name:<20} unpin {dict(unpin or {}) or 'none'} -> {RUNS / arm_label(unpin)}")
        return 0
    try:
        failures = run(RUNS, replicates=args.replicates, limit=args.limit, force=args.force)
    except RunAborted as stopped:
        logger.error("exp-06 stopped on an account error: %s", stopped)
        logger.error("Fix the API key or the account, then rerun the same command: "
                     "predictions already written are skipped.")
        return 2
    if failures:
        logger.error("%d session(s) failed:", len(failures))
        for line in failures:
            logger.error("  %s", line)
        return 1
    logger.info("exp-06 complete; runs under %s", RUNS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
