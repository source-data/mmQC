"""Run exp-01: detailed skill instructions against minimal ones.

Every check of `fig-checklist-exp01` carries two versions of its own skill --
`v1` with full stepwise instructions, `v2` with the same frontmatter and
opening paragraph and nothing else. Unpinning a check to both versions gives
two arms of one comparison:

    pinned        every skill at its manifest pin, i.e. the detailed v1
    <check>@v2    that one check at the minimal v2

Nothing else differs. The evaluation contracts sit above the version
directories, so both arms are scored by the same schema, the same
`eval-manifest.json` and the same gold -- the control is structural here, not
something this script has to assert.

Output lands under `experiments/runs/exp-01-skill-verbosity/<check>/`, and the
harness adds `<arm>/rep-NN/<example>/` beneath that.

**This is a long, expensive job.** Eleven checks over 436 example-checks, two
arms, N replicates: 872 sessions per replicate, 2,616 at the default three --
roughly $130 and 24 hours serial. Re-running is safe and cheap: the harness
skips an example that already has a prediction, so an interruption costs what
it interrupted. Use `--force` only to deliberately redo work.

    python experiments/exp-01-skill-verbosity/run.py
    python experiments/exp-01-skill-verbosity/run.py --check stat-test --replicates 1

The analysis lives in `notebooks/experiments/exp-01-skill-verbosity.ipynb` and
reads what this writes. It does not run anything: a notebook that triggers
2,616 sessions is a notebook nobody can re-execute.
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

#: Pinned by exact name rather than the bare `sonnet` alias: exp-01 is
#: preregistered, and a result attributed to an alias stops being reproducible
#: the moment the alias moves.
MODEL = "claude-sonnet-5"
PROVIDER = "claude-sdk"

RUNS = REPO / "experiments" / "runs" / "exp-01-skill-verbosity"

#: The two versions every check carries. `v1` is detailed, `v2` minimal;
#: unpinning to both is what produces the two arms.
ARMS = ("v1", "v2")


def checks() -> list[str]:
    """Every check of the experiment's checklist, in a stable order."""
    root = REPO / "soda_mmqc" / "data" / "checklist" / CHECKLIST
    return sorted(
        p.name for p in root.iterdir()
        if p.is_dir() and (p / "benchmark.json").is_file()
    )


def planned_sessions(wanted: list[str], replicates: int) -> int:
    """How many sessions this invocation would run if nothing were skipped."""
    total = 0
    for check in wanted:
        benchmark = json.loads(
            (resolve_check_dir(CHECKLIST, check) / "benchmark.json").read_text(
                encoding="utf-8"
            )
        )
        total += len(benchmark["examples"])
    return total * len(ARMS) * replicates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replicates", type=int, default=3,
        help=(
            "Samples per arm (default: %(default)s). Three rather than the "
            "five originally sketched, on the evidence of "
            "thinking/experiments/exploration-replicate-variability.md: the "
            "standard error of a paired difference is bounded at 0.0034 for "
            "n=3 against 0.0026 for n=5, which no plausible effect size would "
            "notice, for ~1,700 fewer sessions and 16 fewer hours"
        ),
    )
    parser.add_argument(
        "--check", action="append", dest="checks", default=None,
        help="Limit to this check; repeatable. Default: all of them",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Run at most this many examples per check, for a smoke test",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Re-run examples that already have a prediction",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would run, and its size, without running it",
    )
    args = parser.parse_args(argv)

    wanted = args.checks or checks()
    unknown = sorted(set(wanted) - set(checks()))
    if unknown:
        parser.error(f"not checks of {CHECKLIST}: {', '.join(unknown)}")

    ceiling = planned_sessions(wanted, args.replicates)
    logger.info(
        "exp-01: %d check(s), %d arm(s), %d replicate(s) -- up to %d session(s)",
        len(wanted), len(ARMS), args.replicates, ceiling,
    )
    if args.dry_run:
        for check in wanted:
            print(f"  {check:<30} -> {RUNS / check}")
        return 0

    failures: list[str] = []
    for index, check in enumerate(wanted, start=1):
        logger.info("[%d/%d] %s", index, len(wanted), check)
        # One call per check, both arms at once: `--unpin <check>` with both
        # versions is exactly the comparison, and running them together means
        # they share an invocation rather than drifting apart in time.
        _, report = run_check_live(
            CHECKLIST,
            check,
            output=RUNS / check,
            model=MODEL,
            provider=PROVIDER,
            limit=args.limit,
            replicates=args.replicates,
            unpin={check: ARMS},
            force=args.force,
        )
        for entry in report:
            if entry["status"] == "failed":
                failures.append(
                    f"{check} {entry['label']} rep-{entry['replicate']:02d} "
                    f"{entry['example']}: {entry.get('error', '')}"
                )
        done = sum(1 for e in report if e["status"] == "ok")
        skipped = sum(1 for e in report if e["status"] == "skipped")
        logger.info(
            "  %s: %d ran, %d skipped, %d failed",
            check, done, skipped,
            sum(1 for e in report if e["status"] == "failed"),
        )

    if failures:
        # Failures are reported, never swallowed: an arm that fails more often
        # than the other is a result about that arm, and a run that hides it
        # would report the survivors as though they were the whole sample.
        logger.error("%d example(s) failed:", len(failures))
        for line in failures:
            logger.error("  %s", line)
        return 1

    logger.info("exp-01 complete; runs under %s", RUNS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
