"""Run exp-08: the deeper arrangement, A <- B <- C_i <- D, with Sonnet 5.5.

exp-04 and exp-06 compared check-major `A|B <- C_i <- D` with
`A <- B <- C_i <- D` on earlier skills, gold and model. exp-08 repeats the
comparison on exp-07's configuration (thinking/experiments/exp-08-arrangements-sonnet.md):
`fig-checklist-exp07`, Sonnet 5.5, `gold-v6`. Its `A|B <- C_i <- D` arm is
exp-07's Sonnet 5.5 run, reused as it stands; this script runs only the other:

    A <- B <- C_i <- D    classify-panels @v3, which invokes identify-panels
                          with the `Skill` tool

Output:

    experiments/runs/exp-08-arrangements-sonnet/classify-panels@v3/rep-NN/<example>/

    python experiments/exp-08-arrangements-sonnet/run.py --smoke
    python experiments/exp-08-arrangements-sonnet/run.py --dry-run
    python experiments/exp-08-arrangements-sonnet/run.py

185 sessions: 37 figures x 5 replicates, at concurrency 50. Re-running skips
what already has a prediction and leaves a kept failure alone; an account or
connection error stops the run. Scoring is the notebook's, against `gold-v6`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from soda_mmqc import logger                                      # noqa: E402
from soda_mmqc.agentic.runner import RunAborted, run_check_live   # noqa: E402
from soda_mmqc.agentic.runtime import ASSEMBLY_CLOSURE            # noqa: E402
from soda_mmqc.config import resolve_check_dir                    # noqa: E402

CHECKLIST = "fig-checklist-exp07"
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
REPLICATES = 5
CONCURRENCY = 50

RUNS = REPO / "experiments" / "runs" / "exp-08-arrangements-sonnet"
#: The A|B <- C_i <- D arm: exp-07's Sonnet 5.5 run.
BASELINE = REPO / "experiments" / "runs" / "exp-07-models" / MODEL
UNPIN = {CLASSIFY: ("v3",)}
ARM = "classify-panels@v3"


def example_count() -> int:
    return len(json.loads((resolve_check_dir(CHECKLIST, ENTRY) / "benchmark.json")
                          .read_text(encoding="utf-8"))["examples"])


def run(root: Path, *, replicates: int, limit: Optional[int], force: bool) -> List[str]:
    _, report = run_check_live(
        CHECKLIST, ENTRY, output=root, model=MODEL, provider=PROVIDER, limit=limit,
        replicates=replicates, unpin=UNPIN, force=force, assembly=ASSEMBLY,
        concurrency=CONCURRENCY, retry_failed=False,
    )
    logger.info("  %d ran, %d skipped, %d failed",
                sum(e["status"] == "ok" for e in report),
                sum(e["status"] == "skipped" for e in report),
                sum(e["status"] == "failed" for e in report))
    return [f"rep-{e['replicate']:02d} {e['example']}: {e.get('error', '')}"
            for e in report if e["status"] == "failed"]


def report_smoke(root: Path) -> int:
    worst = 0
    found = sorted((root / ARM).glob("rep-00/**/prediction.json"))
    if not found:
        logger.error("  no sessions")
        return 1
    for prediction in found:
        intermediates = prediction.parent / "intermediates"
        skills = [e.get("skill") for e in json.loads((intermediates / "skill_trace.json").read_text())]
        audit = json.loads((intermediates / "tool_audit.json").read_text())
        usage = audit.get("usage") or {}
        called = list(dict.fromkeys(k for k in skills if k in CHECKS))
        logger.info("  %-38s %2d/11 checks  classify x%d  identify x%d  $%.3f  %d turns  models %s",
                    prediction.parent.relative_to(root / ARM / "rep-00"), len(called),
                    skills.count(CLASSIFY), skills.count(IDENTIFY), usage.get("total_cost_usd") or 0,
                    usage.get("num_turns") or 0, sorted(usage.get("model_usage") or {}))
        if not skills.count(IDENTIFY):
            logger.warning("    identify-panels was not invoked")
            worst = 1
        unexpected = set(skills) - {ENTRY, CLASSIFY, IDENTIFY, *CHECKS}
        if unexpected:
            logger.warning("    outside the closure: %s", sorted(unexpected))
            worst = 1
    return worst


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="A few figures, one replicate")
    args = parser.parse_args(argv)

    if args.smoke:
        root = RUNS / "smoke"
        limit = args.limit or 3
        logger.info("exp-08 smoke test: %d figure(s), 1 replicate", limit)
        try:
            failures = run(root, replicates=1, limit=limit, force=True)
        except RunAborted as stopped:
            logger.error("smoke test stopped on an account or connection error: %s", stopped)
            return 2
        for line in failures:
            logger.error("  %s", line)
        return report_smoke(root) or (1 if failures else 0)

    n = example_count()
    n = min(n, args.limit) if args.limit else n
    logger.info("exp-08: up to %d session(s), concurrency %d; baseline arm %s",
                n * REPLICATES, CONCURRENCY, BASELINE)
    if args.dry_run:
        print(f"  A <- B <- C_i <- D  unpin {UNPIN} -> {RUNS / ARM}")
        print(f"  A|B <- C_i <- D     reused: {BASELINE / 'pinned'}")
        return 0
    try:
        failures = run(RUNS, replicates=REPLICATES, limit=args.limit, force=args.force)
    except RunAborted as stopped:
        logger.error("exp-08 stopped on an account or connection error: %s", stopped)
        logger.error("Fix the API key, the account or the network, then rerun the same command: "
                     "predictions already written are skipped.")
        return 2
    if failures:
        logger.error("%d session(s) failed:", len(failures))
        for line in failures:
            logger.error("  %s", line)
        return 1
    logger.info("exp-08 complete; runs under %s", RUNS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
