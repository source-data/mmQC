"""Run exp-07: three models on the full checklist.

exp-06's baseline configuration -- `fig-checklist-exp06`, check-major
`A|B <- C_i <- D`, its pins with `individual-data-points` v4 -- run by each
model in turn (thinking/experiments/exp-07-models.md):

    claude-opus-5-5, claude-sonnet-5-5, claude-haiku-5-5

Output:

    experiments/runs/exp-07-models/<model>/pinned/rep-NN/<example>/

    python experiments/exp-07-models/run.py --smoke
    python experiments/exp-07-models/run.py --dry-run
    python experiments/exp-07-models/run.py
    python experiments/exp-07-models/run.py --extend    # only on the author's go-ahead

The run is 333 sessions: 3 models x 37 figures x 3 replicates, at concurrency
50, one model after another. `--extend` takes every model to five replicates
(555 sessions); the plan's rule says when, and the author decides whether.
Re-running skips what already has a prediction; an account error stops the
run at once. Scoring is the notebook's, against `gold-v6`.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from soda_mmqc import logger                                      # noqa: E402
from soda_mmqc.agentic.runner import RunAborted, run_check_live   # noqa: E402
from soda_mmqc.agentic.runtime import ASSEMBLY_CLOSURE            # noqa: E402
from soda_mmqc.agentic.skills import resolve_check_dir            # noqa: E402

CHECKLIST = "fig-checklist-exp06"
ENTRY = "do-fig-checklist-cm"
#: In D's order.
CHECKS = (
    "micrograph-scale-bar", "image-annotation-defined", "single-channel-for-overlay",
    "individual-data-points", "error-bars-defined", "plot-axis-units", "plot-gap-labeling",
    "stat-significance-level", "stat-test", "replication-reporting",
    "panel-image-matches-caption",
)
CLASSIFY = "classify-panels"

#: Run in this order, one after another.
MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5")
PROVIDER = "claude-sdk"
GOLD_TAG = "gold-v6"
ASSEMBLY = ASSEMBLY_CLOSURE
ARM = "pinned"

REPLICATES, EXTENDED = 3, 5
#: As exp-06.
CONCURRENCY = 50

RUNS = REPO / "experiments" / "runs" / "exp-07-models"


def example_count() -> int:
    return len(json.loads((resolve_check_dir(CHECKLIST, ENTRY) / "benchmark.json")
                          .read_text(encoding="utf-8"))["examples"])


def run(root: Path, *, replicates: int, limit: Optional[int], force: bool) -> List[str]:
    failures: List[str] = []
    for model in MODELS:
        logger.info("--- %s ---", model)
        _, report = run_check_live(
            CHECKLIST, ENTRY, output=root / model, model=model, provider=PROVIDER,
            limit=limit, replicates=replicates, force=force, assembly=ASSEMBLY,
            concurrency=CONCURRENCY,
        )
        for e in report:
            if e["status"] == "failed":
                failures.append(f"{model} rep-{e['replicate']:02d} {e['example']}: "
                                f"{e.get('error', '')}")
        logger.info("  %-20s %d ran, %d skipped, %d failed", model,
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
        "answered_by": sorted(usage.get("model_usage") or {}),
        "cost": usage.get("total_cost_usd") or 0.0,
        "output_tokens": (usage.get("usage") or {}).get("output_tokens") or 0,
        "turns": usage.get("num_turns") or 0,
        "ms": usage.get("duration_ms") or 0,
    }


def report_smoke(root: Path) -> int:
    worst = 0
    skipped: Counter = Counter()
    logger.info("--- smoke test: the model that answered, the eleven checks, cost ---")
    for model in MODELS:
        found = sorted((root / model / ARM).glob("rep-00/**/prediction.json"))
        if not found:
            logger.error("  %s: no sessions", model)
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
            example = str(prediction.parent.relative_to(root / model / ARM / "rep-00"))
            logger.info("  %-18s %-38s %2d/11 checks%s  classify x%d  %s  $%.3f  %d out  "
                        "%d turns  %.0fs  answered by %s",
                        model, example, len(called),
                        f" (missing {missing})" if missing else "",
                        s["skills"].count(CLASSIFY),
                        "in order" if in_order else "OUT OF ORDER",
                        s["cost"], s["output_tokens"], s["turns"], s["ms"] / 1000,
                        s["answered_by"])
            if model not in s["answered_by"]:
                logger.error("    %s is not among the models that answered", model)
                worst = 1
            unexpected = set(s["skills"]) - {ENTRY, *CHECKS, CLASSIFY}
            if unexpected:
                logger.warning("    outside the closure: %s", sorted(unexpected))
                worst = 1
        logger.info("  %-18s all eleven checks in %d/%d", model, full, len(found))
        if full == 0:
            logger.error("  %s: D never dispatched all eleven checks", model)
            worst = 1
    if skipped:
        logger.info("  skipped, across sessions: %s", dict(skipped.most_common()))
    return worst


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--extend", action="store_true",
                        help=f"Take every model to {EXTENDED} replicates (the author's decision)")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--smoke", action="store_true",
                        help="Each model on a few figures, one replicate")
    args = parser.parse_args(argv)

    if args.smoke:
        root = RUNS / "smoke"
        limit = args.limit or 3
        logger.info("exp-07 smoke test: %d figure(s), 1 replicate, %d models", limit, len(MODELS))
        try:
            failures = run(root, replicates=1, limit=limit, force=True)
        except RunAborted as stopped:
            logger.error("smoke test stopped on an account error: %s", stopped)
            return 2
        for line in failures:
            logger.error("  %s", line)
        return report_smoke(root) or (1 if failures else 0)

    replicates = EXTENDED if args.extend else REPLICATES
    n = example_count()
    n = min(n, args.limit) if args.limit else n
    logger.info("exp-07: up to %d session(s), %d replicates, concurrency %d",
                len(MODELS) * n * replicates, replicates, CONCURRENCY)
    if args.dry_run:
        for model in MODELS:
            print(f"  {model:<20} -> {RUNS / model / ARM}")
        return 0
    try:
        failures = run(RUNS, replicates=replicates, limit=args.limit, force=args.force)
    except RunAborted as stopped:
        logger.error("exp-07 stopped on an account error: %s", stopped)
        logger.error("Fix the API key or the account, then rerun the same command: "
                     "predictions already written are skipped.")
        return 2
    if failures:
        logger.error("%d session(s) failed:", len(failures))
        for line in failures:
            logger.error("  %s", line)
        return 1
    logger.info("exp-07 complete; runs under %s", RUNS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
