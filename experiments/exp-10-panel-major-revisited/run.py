"""Run exp-10: check-major against panel-major, on exp-07's configuration.

`fig-checklist-exp10`'s two entry points -- identical prose, two answer shapes
(thinking/experiments/exp-10-panel-major-revisited.md) -- each run on every
figure, the same day, with Sonnet 5.5 and the arrangement A|B <- C_i <- D:

    cm   do-fig-checklist-cm   {<check>: [rows], ...}
    pm   do-fig-checklist-pm   {"outputs": [{panel_label, panel_classes, <check>: {...}}, ...]}

Output:

    experiments/runs/exp-10-panel-major-revisited/{cm,pm}/pinned/rep-NN/<example>/

    python experiments/exp-10-panel-major-revisited/run.py --smoke
    python experiments/exp-10-panel-major-revisited/run.py --dry-run
    python experiments/exp-10-panel-major-revisited/run.py

370 sessions: 2 shapes x 37 figures x 5 replicates, at concurrency 50.
Re-running skips what already has a prediction and leaves a kept failure
alone; an account or connection error stops the run. Scoring is the
notebook's, against `gold-v7`.
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
from mmqc_harness.runtime import ASSEMBLY_CLOSURE            # noqa: E402
from soda_mmqc.config import resolve_check_dir                    # noqa: E402

CHECKLIST = "fig-checklist-exp10"
CM, PM = "do-fig-checklist-cm", "do-fig-checklist-pm"
#: arm -> entry point
ARMS: Dict[str, str] = {"cm": CM, "pm": PM}
#: In D's order.
CHECKS = (
    "micrograph-scale-bar", "image-annotation-defined", "single-channel-for-overlay",
    "individual-data-points", "error-bars-defined", "plot-axis-units", "plot-gap-labeling",
    "stat-significance-level", "stat-test", "replication-reporting",
    "panel-image-matches-caption",
)
CLASSIFY = "classify-panels"

MODEL = "claude-sonnet-5-5"
PROVIDER = "claude-sdk"
GOLD_TAG = "gold-v7"
ASSEMBLY = ASSEMBLY_CLOSURE
REPLICATES = 5
CONCURRENCY = 50
ARM_DIR = "pinned"

RUNS = REPO / "experiments" / "runs" / "exp-10-panel-major-revisited"


def example_count() -> int:
    return len(json.loads((resolve_check_dir(CHECKLIST, CM) / "benchmark.json")
                          .read_text(encoding="utf-8"))["examples"])


def run(root: Path, arms: Dict[str, str], *, replicates: int, limit: Optional[int],
        force: bool) -> List[str]:
    failures: List[str] = []
    for arm, entry in arms.items():
        logger.info("--- %s: %s, %d replicate(s) ---", arm, entry, replicates)
        _, report = run_check_live(
            CHECKLIST, entry, output=root / arm, model=MODEL, provider=PROVIDER, limit=limit,
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
    for arm, entry in ARMS.items():
        found = sorted((root / arm / ARM_DIR).glob("rep-00/**/prediction.json"))
        if not found:
            logger.error("  %s: no sessions", arm)
            worst = 1
            continue
        for prediction in found:
            intermediates = prediction.parent / "intermediates"
            skills = [e.get("skill") for e in json.loads((intermediates / "skill_trace.json").read_text())]
            usage = json.loads((intermediates / "tool_audit.json").read_text()).get("usage") or {}
            called = list(dict.fromkeys(k for k in skills if k in CHECKS))
            answer = json.loads(prediction.read_text())
            shape_ok = (set(answer) == {"outputs"}) if arm == "pm" else (set(answer) == set(CHECKS))
            logger.info("  %-3s %-38s %2d/11 checks  classify x%d  $%.3f  %d turns  %d out  shape %s",
                        arm, prediction.parent.relative_to(root / arm / ARM_DIR / "rep-00"),
                        len(called), skills.count(CLASSIFY), usage.get("total_cost_usd") or 0,
                        usage.get("num_turns") or 0, (usage.get("usage") or {}).get("output_tokens") or 0,
                        "ok" if shape_ok else "WRONG")
            unexpected = set(skills) - {entry, CLASSIFY, *CHECKS}
            if unexpected:
                logger.warning("    outside the closure: %s", sorted(unexpected))
            if unexpected or not shape_ok:
                worst = 1
    return worst


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--smoke", action="store_true", help="Both shapes on a few figures, one replicate")
    args = parser.parse_args(argv)

    if args.smoke:
        root = RUNS / "smoke"
        limit = args.limit or 3
        logger.info("exp-10 smoke test: both shapes, %d figure(s), 1 replicate", limit)
        try:
            failures = run(root, ARMS, replicates=1, limit=limit, force=True)
        except RunAborted as stopped:
            logger.error("smoke test stopped on an account or connection error: %s", stopped)
            return 2
        for line in failures:
            logger.error("  %s", line)
        return report_smoke(root) or (1 if failures else 0)

    n = example_count()
    n = min(n, args.limit) if args.limit else n
    logger.info("exp-10: up to %d session(s), concurrency %d", len(ARMS) * n * REPLICATES, CONCURRENCY)
    if args.dry_run:
        for arm, entry in ARMS.items():
            print(f"  {arm}  {CHECKLIST} {entry}, {REPLICATES} replicates -> {RUNS / arm / ARM_DIR}")
        return 0
    try:
        failures = run(RUNS, ARMS, replicates=REPLICATES, limit=args.limit, force=args.force)
    except RunAborted as stopped:
        logger.error("exp-10 stopped on an account or connection error: %s", stopped)
        logger.error("Fix the API key, the account or the network, then rerun the same command: "
                     "predictions already written are skipped.")
        return 2
    if failures:
        logger.error("%d session(s) failed:", len(failures))
        for line in failures:
            logger.error("  %s", line)
        return 1
    logger.info("exp-10 complete; runs under %s", RUNS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
