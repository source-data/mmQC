"""Run the replicate-variability probe: one check, one arm, seven replicates.

How much does a check's score move between identical runs? exp-01 was
sketched at five replicates and could be three; nothing but this decides
which.

    python experiments/exploration-replicate-variability/run.py

266 sessions -- 38 examples x 7 replicates -- at roughly $0.035 each, so about
$9. Re-running is safe: the harness skips an example that already has a
prediction, so an interruption costs what it interrupted.

Nothing is unpinned. Every skill stays at its manifest pin, which for
`fig-checklist-exp01` is the detailed `v1`, so all seven replicates are the
same configuration and differ only because the model is non-deterministic.

The note is `thinking/experiments/exploration-replicate-variability.md`; the
analysis is `notebooks/experiments/exploration-replicate-variability.ipynb`
and reads what this writes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from soda_mmqc import logger                                  # noqa: E402
from soda_mmqc.agentic.runner import run_check_live           # noqa: E402
from soda_mmqc.agentic.skills import resolve_check_dir        # noqa: E402

CHECKLIST = "fig-checklist-exp01"
CHECK = "micrograph-scale-bar"

#: Pinned by exact name: a number used to size exp-01 has to stay meaningful
#: after the `sonnet` alias moves.
MODEL = "claude-sonnet-5"
PROVIDER = "claude-sdk"

#: Odd, and more than the five under question, so the estimate of the spread
#: is not made from the number it is meant to decide.
REPLICATES = 7

RUNS = REPO / "experiments" / "runs" / "exploration-replicate-variability"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replicates", type=int, default=REPLICATES,
        help="Samples of the one configuration (default: %(default)s)",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Run at most this many examples, for a smoke test",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-run examples that already have a prediction",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print the size of the job without running it",
    )
    args = parser.parse_args(argv)

    benchmark = json.loads(
        (resolve_check_dir(CHECKLIST, CHECK) / "benchmark.json").read_text(
            encoding="utf-8"
        )
    )
    examples = len(benchmark["examples"]) if args.limit is None else min(
        args.limit, len(benchmark["examples"])
    )
    sessions = examples * args.replicates
    logger.info(
        "%s: %d example(s) x %d replicate(s) = %d session(s), one arm",
        CHECK, examples, args.replicates, sessions,
    )
    if args.dry_run:
        print(f"  would write under {RUNS}")
        return 0

    _, report = run_check_live(
        CHECKLIST,
        CHECK,
        output=RUNS,
        model=MODEL,
        provider=PROVIDER,
        limit=args.limit,
        replicates=args.replicates,
        force=args.force,
    )

    ran = sum(1 for e in report if e["status"] == "ok")
    skipped = sum(1 for e in report if e["status"] == "skipped")
    failed = [e for e in report if e["status"] == "failed"]
    spent = sum(
        (e.get("usage") or {}).get("total_cost_usd") or 0.0 for e in report
    )
    logger.info(
        "%d ran, %d skipped, %d failed; $%.2f this invocation",
        ran, skipped, len(failed), spent,
    )
    for entry in failed:
        # Reported, never swallowed: a replicate that failed is not a
        # replicate that agreed, and averaging the survivors would say it was.
        logger.error(
            "  rep-%02d %s: %s",
            entry["replicate"], entry["example"], entry.get("error", ""),
        )

    if failed:
        return 1
    logger.info("runs under %s", RUNS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
