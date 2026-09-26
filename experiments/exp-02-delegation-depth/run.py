"""Run exp-02: does splitting a check skill into a DAG degrade it?

Every check of `fig-checklist-exp02` is built from three blocks -- **A** panel
identification, **B** panel classification, **C** the check itself -- and
carries three versions that spread those blocks over a different number of
skills. `classify-panels` carries two. Together they give four arrangements:

    A|B|C        check v1                          the monolith, and baseline
    A <- B|C     check v2                          identification split off
    A|B <- C     check v3 + classify-panels v1     the check split off
    A <- B <- C  check v3 + classify-panels v2     both split, as a chain

The prose is the same in all four; what differs is how many skills it is
spread across. The evaluation contracts sit above the version directories, so
every arrangement of one check is scored by the same schema and the same gold.

**Two invocations per check, not one.** `unpin` expands to the *product* of the
versions given, so unpinning the check to three versions and `classify-panels`
to two would run six arms -- and two of them would be duplicates, because
nothing calls `classify-panels` when the check is at v1 or v2. Splitting it in
two asks for exactly the four arrangements that differ:

    {check: (v1, v2)}                          -> pinned, <check>@v2
    {check: (v3,), classify-panels: (v1, v2)}  -> <check>@v3,
                                                  classify-panels@v2-<check>@v3

Output lands under `experiments/runs/exp-02-delegation-depth/<check>/`, and the
harness adds `<arm>/rep-NN/<example>/` beneath that.

**Smoke test first.** `--smoke` runs the deepest arrangement only, on a few
examples of each check, one replicate, and then reads `skill_trace.json` to
report what fraction of sessions actually ran the chain. Nothing else here is worth running
until it does: the whole experiment rests on a leaf that names another skill
causing that skill to be invoked, and no checklist has ever exercised that --
exp-01 was leaf-only by construction. A few dollars answers it.

    python experiments/exp-02-delegation-depth/run.py --smoke
    python experiments/exp-02-delegation-depth/run.py --dry-run
    python experiments/exp-02-delegation-depth/run.py

**The full run is long and expensive.** Three checks over 38 examples, four
arrangements, five replicates: 2,280 sessions, roughly $135-180 and a day of
model time. Re-running is safe: the harness skips an example that already has a
prediction, so an interruption costs what it interrupted. Use `--force` only to
deliberately redo work.

The analysis lives in `notebooks/experiments/exp-02-delegation-depth.ipynb` and
reads what this writes. It does not run anything.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from soda_mmqc import logger                                  # noqa: E402
from soda_mmqc.agentic.runner import run_check_live           # noqa: E402
from soda_mmqc.agentic.skills import resolve_check_dir        # noqa: E402

CHECKLIST = "fig-checklist-exp02"

#: Pinned by exact name rather than the bare `sonnet` alias: exp-02 is
#: preregistered, and a result attributed to an alias stops being reproducible
#: the moment the alias moves.
MODEL = "claude-sonnet-5"
PROVIDER = "claude-sdk"

RUNS = REPO / "experiments" / "runs" / "exp-02-delegation-depth"

CLASSIFY = "classify-panels"
IDENTIFY = "identify-panels"

#: How many arrangements a full run produces per check. Used only to size a
#: dry run; the arms themselves come from the unpin maps below.
ARRANGEMENTS = 4


def unpin_maps(check: str) -> List[Mapping[str, Sequence[str]]]:
    """The two unpin maps whose arms are the four arrangements.

    Kept as data rather than a loop over versions, because the fourth
    arrangement is not "a version of the check" -- it is a version of the check
    *and* a version of `classify-panels`, moved together.
    """
    return [
        {check: ("v1", "v2")},
        {check: ("v3",), CLASSIFY: ("v1", "v2")},
    ]


def smoke_unpin(check: str) -> Mapping[str, Sequence[str]]:
    """Just `A <- B <- C`: the arrangement with the most to go wrong."""
    return {check: ("v3",), CLASSIFY: ("v2",)}


def checks() -> List[str]:
    """Every check of the experiment's checklist, in a stable order."""
    root = REPO / "soda_mmqc" / "data" / "checklist" / CHECKLIST
    return sorted(
        p.name for p in root.iterdir()
        if p.is_dir() and (p / "benchmark.json").is_file()
    )


def example_count(check: str) -> int:
    benchmark = json.loads(
        (resolve_check_dir(CHECKLIST, check) / "benchmark.json").read_text(
            encoding="utf-8"
        )
    )
    return len(benchmark["examples"])


def planned_sessions(wanted: Sequence[str], replicates: int) -> int:
    """How many sessions this invocation would run if nothing were skipped."""
    return sum(example_count(c) for c in wanted) * ARRANGEMENTS * replicates


def read_traces(root: Path) -> Tuple[int, Counter]:
    """Count sessions under ``root`` and which skills each one invoked.

    The trace is the only record of whether delegation actually happened: a
    prediction that looks right tells you nothing about how it was reached, and
    an arm whose shared skill never fired is not the arm it claims to be.
    """
    sessions = 0
    invoked: Counter = Counter()
    for trace_path in root.rglob("intermediates/skill_trace.json"):
        sessions += 1
        try:
            entries = json.loads(trace_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        names = {
            entry.get("skill")
            for entry in entries
            if isinstance(entry, dict)
        }
        for name in names:
            if name:
                invoked[name] += 1
    return sessions, invoked


def report_smoke_all(roots: Sequence[Tuple[str, Path]]) -> int:
    """Report the invocation rate per check and overall.

    The rate is the point. One session that delegates says the mechanism
    works; what gate 0 preregisters is a 95% floor, and only a rate over
    several sessions and several checks says anything about that.
    """
    logger.info("--- smoke test: did the chain fire? ---")
    total = chained = 0
    for check, root in roots:
        sessions, invoked = read_traces(root)
        if not sessions:
            logger.error("  %-24s no traces found under %s", check, root)
            continue
        both = min(invoked.get(CLASSIFY, 0), invoked.get(IDENTIFY, 0))
        total += sessions
        chained += both
        logger.info(
            "  %-24s %d/%d full chain   (%s %d, %s %d)",
            check, both, sessions,
            CLASSIFY, invoked.get(CLASSIFY, 0),
            IDENTIFY, invoked.get(IDENTIFY, 0),
        )
        for name, n in sorted(invoked.items()):
            if name not in (check, CLASSIFY, IDENTIFY):
                logger.warning("    unexpected skill invoked: %s (%d)", name, n)

    if not total:
        logger.error("no skill traces found at all")
        return 1

    rate = chained / total
    logger.info("  %s", "-" * 60)
    logger.info("  overall: %d/%d sessions ran the full chain (%.0f%%)",
                chained, total, 100 * rate)
    if chained == 0:
        logger.error(
            "The chain never fired. `A <- B <- C` is not what ran, and there "
            "is no point running exp-02 until this works."
        )
        return 1
    if rate < 0.95:
        logger.warning(
            "Below the 95%% floor gate 0 preregisters. Delegation works but "
            "is not reliable; that is a finding about how skills compose, and "
            "it belongs in the note rather than being tuned away quietly."
        )
    else:
        logger.info("At or above the 95%% floor gate 0 preregisters.")
    return 0


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--replicates", type=int, default=5,
        help=(
            "Samples per arm (default: %(default)s). Five rather than exp-01's "
            "three because exp-02's endpoints are planned under a null, where "
            "the variance is measurement noise and falls as 1/n; it is what "
            "makes the layer-S margin provable and leaves no layer-2 property "
            "below the gate-3 floor"
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
    parser.add_argument(
        "--smoke", action="store_true",
        help=(
            "Run only `A <- B <- C`, on a few examples of each check, one "
            "replicate, then report what fraction of sessions ran the chain"
        ),
    )
    args = parser.parse_args(argv)

    known = checks()
    wanted = args.checks or known
    unknown = sorted(set(wanted) - set(known))
    if unknown:
        parser.error(f"not checks of {CHECKLIST}: {', '.join(unknown)}")

    if args.smoke:
        limit = args.limit or 2
        logger.info(
            "exp-02 smoke test: %d check(s), arrangement A <- B <- C, %d "
            "example(s) each, 1 replicate -- up to %d session(s)",
            len(wanted), limit, len(wanted) * limit,
        )
        roots: List[Tuple[str, Path]] = []
        for check in wanted:
            root, report = run_check_live(
                CHECKLIST,
                check,
                output=RUNS / "smoke" / check,
                model=MODEL,
                provider=PROVIDER,
                limit=limit,
                replicates=1,
                unpin=smoke_unpin(check),
                force=True,
            )
            roots.append((check, root))
            for entry in report:
                if entry["status"] == "failed":
                    logger.error(
                        "  %s %s rep-%02d %s: %s",
                        check, entry["label"], entry["replicate"],
                        entry["example"], entry.get("error", ""),
                    )
        return report_smoke_all(roots)

    ceiling = planned_sessions(wanted, args.replicates)
    logger.info(
        "exp-02: %d check(s), %d arrangement(s), %d replicate(s) -- up to %d "
        "session(s)",
        len(wanted), ARRANGEMENTS, args.replicates, ceiling,
    )
    if args.dry_run:
        for check in wanted:
            print(f"  {check:<30} -> {RUNS / check}")
            for unpin in unpin_maps(check):
                print(f"      unpin {dict(unpin)}")
        return 0

    failures: List[str] = []
    for index, check in enumerate(wanted, start=1):
        logger.info("[%d/%d] %s", index, len(wanted), check)
        for unpin in unpin_maps(check):
            _, report = run_check_live(
                CHECKLIST,
                check,
                output=RUNS / check,
                model=MODEL,
                provider=PROVIDER,
                limit=args.limit,
                replicates=args.replicates,
                unpin=unpin,
                force=args.force,
            )
            for entry in report:
                if entry["status"] == "failed":
                    failures.append(
                        f"{check} {entry['label']} "
                        f"rep-{entry['replicate']:02d} {entry['example']}: "
                        f"{entry.get('error', '')}"
                    )
            done = sum(1 for e in report if e["status"] == "ok")
            skipped = sum(1 for e in report if e["status"] == "skipped")
            logger.info(
                "  %s %s: %d ran, %d skipped, %d failed",
                check, dict(unpin), done, skipped,
                sum(1 for e in report if e["status"] == "failed"),
            )

    if failures:
        # Failures are reported, never swallowed: an arm that fails more often
        # than another is a result about that arm, and a run that hides it
        # would report the survivors as though they were the whole sample.
        logger.error("%d example(s) failed:", len(failures))
        for line in failures:
            logger.error("  %s", line)
        return 1

    logger.info("exp-02 complete; runs under %s", RUNS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
