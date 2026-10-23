"""Run exp-09: A|B|C_i <- D, each check listing and classifying the panels itself.

On exp-07's configuration -- Sonnet 5.5, `gold-v6`, the entry point and its
contract -- with every check's `classify-panels` call replaced by
`classify-panels` v1's prose (thinking/experiments/exp-09-inline-panels.md).
Two arms, run the same day:

    inline   fig-checklist-exp09, its pins: the inline checks; 5 replicates
    drift    fig-checklist-exp07, its pins: A|B <- C_i <- D as exp-07 ran it;
             2 replicates, to show whether the model has moved since exp-07

Output:

    experiments/runs/exp-09-inline-panels/{inline,drift}/pinned/rep-NN/<example>/

    python experiments/exp-09-inline-panels/run.py --smoke
    python experiments/exp-09-inline-panels/run.py --dry-run
    python experiments/exp-09-inline-panels/run.py
    python experiments/exp-09-inline-panels/run.py --extend-drift   # only on the author's go-ahead

259 sessions: 37 figures x (5 + 2) replicates, at concurrency 50. If the drift
arm is not equivalent to exp-07's, `--extend-drift` takes it to 5 replicates.
Re-running skips what already has a prediction and leaves a kept failure
alone; an account or connection error stops the run.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from soda_mmqc import logger                                      # noqa: E402
from soda_mmqc.agentic.runner import RunAborted, run_check_live   # noqa: E402
from soda_mmqc.agentic.runtime import ASSEMBLY_CLOSURE            # noqa: E402
from soda_mmqc.config import resolve_check_dir                    # noqa: E402

ENTRY = "do-fig-checklist-cm"
#: In D's order.
CHECKS = (
    "micrograph-scale-bar", "image-annotation-defined", "single-channel-for-overlay",
    "individual-data-points", "error-bars-defined", "plot-axis-units", "plot-gap-labeling",
    "stat-significance-level", "stat-test", "replication-reporting",
    "panel-image-matches-caption",
)
CLASSIFY, IDENTIFY = "classify-panels", "identify-panels"

MODEL = "claude-sonnet-5-5"
PROVIDER = "claude-sdk"
GOLD_TAG = "gold-v6"
ASSEMBLY = ASSEMBLY_CLOSURE
CONCURRENCY = 50

#: arm -> (checklist, replicates)
ARMS: Dict[str, tuple] = {
    "inline": ("fig-checklist-exp09", 5),
    "drift": ("fig-checklist-exp07", 2),
}
DRIFT_EXTENDED = 5
ARM_DIR = "pinned"

RUNS = REPO / "experiments" / "runs" / "exp-09-inline-panels"
#: exp-07's Sonnet 5.5 run: A|B <- C_i <- D, 5 replicates, 2026-10-12.
BASELINE = REPO / "experiments" / "runs" / "exp-07-models" / MODEL
#: exp-08's run: A <- B <- C_i <- D, reported beside the others.
DEEP = REPO / "experiments" / "runs" / "exp-08-arrangements-sonnet"


def example_count(checklist: str) -> int:
    return len(json.loads((resolve_check_dir(checklist, ENTRY) / "benchmark.json")
                          .read_text(encoding="utf-8"))["examples"])


def run(root: Path, arms: Dict[str, tuple], *, limit: Optional[int], force: bool) -> List[str]:
    failures: List[str] = []
    for arm, (checklist, replicates) in arms.items():
        logger.info("--- %s: %s, %d replicate(s) ---", arm, checklist, replicates)
        _, report = run_check_live(
            checklist, ENTRY, output=root / arm, model=MODEL, provider=PROVIDER, limit=limit,
            replicates=replicates, force=force, assembly=ASSEMBLY,
            concurrency=CONCURRENCY, retry_failed=False,
        )
        logger.info("  %d ran, %d skipped, %d failed",
                    sum(e["status"] == "ok" for e in report),
                    sum(e["status"] == "skipped" for e in report),
                    sum(e["status"] == "failed" for e in report))
        failures += [f"{arm} rep-{e['replicate']:02d} {e['example']}: {e.get('error', '')}"
                     for e in report if e["status"] == "failed"]
    return failures


def report_smoke(root: Path) -> int:
    worst = 0
    found = sorted((root / "inline" / ARM_DIR).glob("rep-00/**/prediction.json"))
    if not found:
        logger.error("  no sessions")
        return 1
    for prediction in found:
        intermediates = prediction.parent / "intermediates"
        skills = [e.get("skill") for e in json.loads((intermediates / "skill_trace.json").read_text())]
        audit = json.loads((intermediates / "tool_audit.json").read_text())
        usage = audit.get("usage") or {}
        called = list(dict.fromkeys(k for k in skills if k in CHECKS))
        logger.info("  %-38s %2d/11 checks  classify x%d  $%.3f  %d turns  models %s",
                    prediction.parent.relative_to(root / "inline" / ARM_DIR / "rep-00"),
                    len(called), skills.count(CLASSIFY), usage.get("total_cost_usd") or 0,
                    usage.get("num_turns") or 0, sorted(usage.get("model_usage") or {}))
        unexpected = set(skills) - {ENTRY, *CHECKS}
        if unexpected:
            logger.warning("    outside the closure: %s", sorted(unexpected))
            worst = 1
    return worst


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--extend-drift", action="store_true",
                        help=f"Take the drift arm to {DRIFT_EXTENDED} replicates (the author's decision)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--smoke", action="store_true",
                        help="The inline arm on a few figures, one replicate")
    args = parser.parse_args(argv)

    if args.smoke:
        root = RUNS / "smoke"
        limit = args.limit or 3
        logger.info("exp-09 smoke test: inline arm, %d figure(s), 1 replicate", limit)
        try:
            failures = run(root, {"inline": (ARMS["inline"][0], 1)}, limit=limit, force=True)
        except RunAborted as stopped:
            logger.error("smoke test stopped on an account or connection error: %s", stopped)
            return 2
        for line in failures:
            logger.error("  %s", line)
        return report_smoke(root) or (1 if failures else 0)

    arms = dict(ARMS)
    if args.extend_drift:
        arms["drift"] = (ARMS["drift"][0], DRIFT_EXTENDED)
    n = example_count(ARMS["inline"][0])
    n = min(n, args.limit) if args.limit else n
    logger.info("exp-09: up to %d session(s), concurrency %d",
                n * sum(r for _, r in arms.values()), CONCURRENCY)
    if args.dry_run:
        for arm, (checklist, replicates) in arms.items():
            print(f"  {arm:<7} {checklist}, {replicates} replicate(s) -> {RUNS / arm / ARM_DIR}")
        print(f"  baseline (A|B <- C_i <- D, exp-07): {BASELINE / ARM_DIR}")
        print(f"  deep (A <- B <- C_i <- D, exp-08):  {DEEP / 'classify-panels@v3'}")
        return 0
    try:
        failures = run(RUNS, arms, limit=args.limit, force=args.force)
    except RunAborted as stopped:
        logger.error("exp-09 stopped on an account or connection error: %s", stopped)
        logger.error("Fix the API key, the account or the network, then rerun the same command: "
                     "predictions already written are skipped.")
        return 2
    if failures:
        logger.error("%d session(s) failed:", len(failures))
        for line in failures:
            logger.error("  %s", line)
        return 1
    logger.info("exp-09 complete; runs under %s", RUNS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
