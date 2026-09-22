"""Run the replicate-variability probe: one check, one arm, ten replicates.

How much does a check's score move between identical runs? exp-01 was
sketched at five replicates and could be three; nothing but this decides
which.

    python experiments/exploration-replicate-variability/run.py

100 sessions -- 10 examples x 10 replicates -- at roughly $0.035 each, so about
$3.50. Re-running is safe: the harness skips an example that already has a
prediction, so an interruption costs what it interrupted.

Nothing is unpinned. Every skill stays at its manifest pin, which for
`fig-checklist-exp01` is the detailed `v1`, so all ten replicates are the
same configuration and differ only because the model is non-deterministic.

Ten examples rather than all thirty-eight because the example count can be
taken out of the answer: ten examples x ten replicates gives ten independent
estimates of the *per-example* between-replicate variance, and the spread of
a check mean over any number of examples follows from that. Reporting the
ten-example spread directly would overstate exp-01's noise by about
sqrt(38/10).

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

#: The check with the most semantically-scored fields -- `replicate_statements`,
#: `replicate_type`, `explanation` -- which is where run-to-run variation should
#: concentrate, because a rephrasing moves a similarity score and cannot move a
#: yes/no. The probe is deliberately aimed at the noisy end.
CHECK = "replication-reporting"

#: Pinned by exact name: a number used to size exp-01 has to stay meaningful
#: after the `sonnet` alias moves.
MODEL = "claude-sonnet-5"
PROVIDER = "claude-sdk"

#: More than the five under question, so the estimate of the spread is not
#: made from the number it is meant to decide. Ten also estimates a
#: per-example variance more precisely than seven.
REPLICATES = 10

RUNS = REPO / "experiments" / "runs" / "exploration-replicate-variability"

#: One figure per document, from ten distinct documents: the first figure in
#: benchmark order, per document, where the check actually applies.
#:
#: Listed rather than computed so the probe is exactly reproducible even if
#: the benchmark or the gold changes. Taking the first ten examples in
#: benchmark order would have been simpler and worse -- seven come from one
#: paper, and figures from one paper share conventions, so their scores are
#: not independent draws.
EXAMPLES = (
    "10.1038_s44318-026-00715-1/content/1",
    "10.1038_s44319-025-00631-1/content/1",
    "10.1038_emboj.2009.312/content/1",
    "10.1038_emboj.2009.340/content/3",
    "10.1038_s44319-025-00438-0/content/1",
    "10.1038_embor.2009.217/content/4",
    "10.1038_s44320-025-00092-7/content/2",
    "10.1038_embor.2009.233/content/2",
    "10.1038_s44320-025-00094-5/content/2",
    "10.1038_s44318-025-00409-0/content/1",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replicates", type=int, default=REPLICATES,
        help="Samples of the one configuration (default: %(default)s)",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Use only the first N of the ten examples, for a smoke test",
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
    missing = sorted(set(EXAMPLES) - set(benchmark["examples"]))
    if missing:
        parser.error(
            f"no longer in the benchmark of {CHECK}: {', '.join(missing)}"
        )
    wanted = list(EXAMPLES[: args.limit] if args.limit else EXAMPLES)
    sessions = len(wanted) * args.replicates
    logger.info(
        "%s: %d example(s) x %d replicate(s) = %d session(s), one arm",
        CHECK, len(wanted), args.replicates, sessions,
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
        examples=wanted,
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
