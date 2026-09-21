"""Command line interface for agentic checklists.

Every command this project offers is declared here and dispatched from
:func:`main`. The implementations live elsewhere -- the harness in
:mod:`soda_mmqc.agentic`, scoring in :mod:`soda_mmqc.core.scoring`, the two
Streamlit apps behind the launchers in :mod:`soda_mmqc.scripts` -- and this
module holds no domain logic of its own.

It also re-exports nothing. It used to carry about forty names from
``agentic/`` under a "compatibility surface" comment so that tests could
reach them as ``cli.X``, and it redefined five constants it had already
imported, leaving two definitions of each with nothing keeping them equal.
Import a name from the module that defines it.

Usage::

    python -m soda_mmqc.cli score fig-checklist \\
        --check micrograph-scale-bar \\
        --predictions path/to/predictions
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

from soda_mmqc import logger
from soda_mmqc.config import (
    AGENTIC_DEFAULT_MODEL,
    DEFAULT_SENTENCE_TRANSFORMER_MODEL,
)
from soda_mmqc.agentic.pinning import MODEL_DEFAULTS_FILENAME
from soda_mmqc.agentic.runner import run_check_live, run_check_mock
from soda_mmqc.agentic.runtime import describe_permission_profile
from soda_mmqc.agentic.session import runtime_session
from soda_mmqc.agentic.views import graph_checklist
from soda_mmqc.core.gold_drafts import init_expected_outputs
from soda_mmqc.core.scoring import score_check


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="soda_mmqc.cli",
        description="Run and score agentic checklists",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    score = subparsers.add_parser(
        "score",
        help="Score stored predictions against gold expected outputs",
    )
    score.add_argument("checklist", type=str, help="Name of the checklist")
    score.add_argument(
        "--check", type=str, required=True, help="Name of the check to score"
    )
    score.add_argument(
        "--predictions",
        type=Path,
        required=True,
        help=(
            "One run leaf -- <root>/<arm>/rep-NN/ -- or a JSON file "
            "mapping example path to leaf output. The analysis is written "
            "beside it."
        ),
    )
    score.add_argument(
        "--sentence-transformer-model",
        type=str,
        default=DEFAULT_SENTENCE_TRANSFORMER_MODEL,
        help="SentenceTransformer model for semantic similarity",
    )
    score.add_argument(
        "--no-save",
        action="store_true",
        help="Score without writing analysis.json",
    )

    assemble = subparsers.add_parser(
        "assemble",
        help=(
            "Assemble a sealed runtime directory for one example and print "
            "the permission profile, without running a session"
        ),
    )
    assemble.add_argument("checklist", type=str, help="Name of the checklist")
    assemble.add_argument(
        "--check", type=str, required=True, help="Entry-point check"
    )
    assemble.add_argument(
        "--example",
        type=str,
        required=True,
        help="Example relative source path",
    )
    assemble.add_argument(
        "--keep-runtime",
        action="store_true",
        help="Keep the assembled directory instead of removing it",
    )

    run = subparsers.add_parser(
        "run", help="Run a check over its benchmark examples"
    )
    run.add_argument("checklist", type=str, help="Name of the checklist")
    run.add_argument(
        "--check", type=str, required=True, help="Check to run"
    )
    run.add_argument(
        "--mock",
        action="store_true",
        help=(
            "Write each example's gold as its prediction. Fully offline: no "
            "session is opened and no provider is contacted"
        ),
    )
    run.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Predictions directory (default: under EVALUATION_DIR)",
    )
    run.add_argument(
        "--model",
        type=str,
        default=None,
        help=(
            "Model for the session. Defaults to the checklist's "
            f"{MODEL_DEFAULTS_FILENAME}, then to {AGENTIC_DEFAULT_MODEL}"
        ),
    )
    run.add_argument(
        "--provider",
        choices=("openai", "claude-sdk"),
        default="openai",
        help=(
            "Which agent runtime to drive (default: %(default)s). "
            "claude-sdk needs ANTHROPIC_API_KEY"
        ),
    )
    run.add_argument(
        "--force",
        action="store_true",
        help=(
            "Re-run examples that already have a prediction. Without it a run "
            "skips them, so an interrupted run resumes where it stopped"
        ),
    )
    run.add_argument(
        "--replicates",
        type=int,
        default=1,
        metavar="N",
        help=(
            "Run each configuration N times (default: %(default)s). There is "
            "no seed to fix, so replicates are resamples of a "
            "non-deterministic system rather than reproductions: they are how "
            "its variance is measured, and they are not expected to agree"
        ),
    )
    run.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run at most this many examples",
    )
    run.add_argument(
        "--example",
        action="append",
        dest="examples",
        default=None,
        help="Limit to this example; repeatable",
    )
    run.add_argument(
        "--approve-tools",
        action="store_true",
        help=(
            "Ask before every tool call. For the supervised first run only; "
            "a full benchmark would ask hundreds of times"
        ),
    )
    run.add_argument(
        "--keep-runtime",
        action="store_true",
        help="Keep each assembled runtime for inspection",
    )
    run.add_argument(
        "--unpin",
        action="append",
        dest="unpin",
        default=None,
        metavar="SKILL",
        help=(
            "Compare versions of SKILL instead of using its manifest pin. "
            "Every other skill stays pinned. Repeatable; repeating it "
            "multiplies the number of runs"
        ),
    )
    run.add_argument(
        "--versions",
        type=str,
        default=None,
        help=(
            "Comma-separated versions for --unpin, e.g. v1,v2. Applies to "
            "every unpinned skill; omit it to take all versions"
        ),
    )

    init = subparsers.add_parser(
        "init",
        help=(
            "Draft expected_output.json for a check's benchmark examples, "
            "so curation is correction rather than typing"
        ),
    )
    init.add_argument("checklist", type=str, help="Name of the checklist")
    init.add_argument(
        "--check",
        type=str,
        action="append",
        dest="checks",
        default=None,
        help="Check to initialize; repeatable. Default: every check.",
    )
    init.add_argument(
        "--from-run",
        type=Path,
        default=None,
        help=(
            "Take drafts from an existing run root instead of running the "
            "check. Uses rep-00 of the pinned arm -- a curator corrects one "
            "answer, not an average. Costs nothing."
        ),
    )
    init.add_argument(
        "--model",
        type=str,
        default=None,
        help="Model for a live run (ignored with --from-run)",
    )
    init.add_argument(
        "--provider",
        choices=("openai", "claude-sdk"),
        default="openai",
        help="Agent runtime for a live run (default: %(default)s)",
    )
    init.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run at most this many examples (ignored with --from-run)",
    )
    init.add_argument(
        "--example",
        action="append",
        dest="examples",
        default=None,
        help="Limit a live run to this example; repeatable",
    )
    init.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Keep any expected_output.json that already exists",
    )

    graph = subparsers.add_parser(
        "graph",
        help=(
            "Check the generated dag.yaml/README.md against the skills, or "
            "regenerate them with --write"
        ),
    )
    graph.add_argument("checklist", type=str, help="Name of the checklist")
    graph.add_argument(
        "--write",
        action="store_true",
        help="Regenerate the views instead of checking them",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Entry point for ``python -m soda_mmqc.cli``."""
    args = _build_parser().parse_args(argv)

    if args.command == "score":
        try:
            score_check(
                args.checklist,
                args.check,
                args.predictions,
                sentence_transformer_model=args.sentence_transformer_model,
                save=not args.no_save,
            )
        except (FileNotFoundError, ValueError) as exc:
            logger.error("%s", exc)
            return 1
        return 0

    if args.command == "run":
        try:
            if args.mock:
                path = run_check_mock(
                    args.checklist,
                    args.check,
                    output=args.output,
                    model=args.model or AGENTIC_DEFAULT_MODEL,
                    examples=args.examples,
                )
                report = None
            else:
                if args.limit is None and not args.examples:
                    logger.error(
                        "A live run costs money. Scope it with --limit or "
                        "--example; running a whole benchmark unscoped is "
                        "never what you want for a first run."
                    )
                    return 2
                versions = (
                    tuple(v.strip() for v in args.versions.split(",") if v.strip())
                    if args.versions else None
                )
                if versions and not args.unpin:
                    logger.error(
                        "--versions has no effect without --unpin: it says "
                        "which versions to try, --unpin says of what."
                    )
                    return 2
                if args.replicates < 1:
                    logger.error("--replicates must be at least one")
                    return 2
                logger.info(
                    "Live run: %d replicate(s) of %s/%s, one session per "
                    "example per replicate per skill set",
                    args.replicates, args.checklist, args.check,
                )
                path, report = run_check_live(
                    args.checklist,
                    args.check,
                    output=args.output,
                    model=args.model,
                    examples=args.examples,
                    limit=args.limit,
                    keep_runtime=args.keep_runtime,
                    approve_tools=args.approve_tools,
                    provider=args.provider,
                    unpin={name: versions for name in (args.unpin or [])},
                    replicates=args.replicates,
                    force=args.force,
                )
        except (FileNotFoundError, ValueError, KeyError) as exc:
            logger.error("%s", exc)
            return 1
        print(f"predictions: {path}")
        if report:
            print()
            labels = {entry.get("label") for entry in report}
            for entry in report:
                hops = entry.get("hops") or {}
                print(
                    f"  {entry['status']:7s} {entry['example']}"
                    + (
                        f"  [{entry['label']}]"
                        if len(labels) > 1 else ""
                    )
                    + (
                        f"  hops observed={hops.get('observed')} "
                        f"missing={hops.get('declared_not_observed')}"
                        if hops else ""
                    )
                    + (f"  [{entry['error']}]" if entry.get("error") else "")
                )
        return 0

    if args.command == "init":
        if args.from_run is None and args.limit is None and not args.examples:
            logger.error(
                "A live init costs money: it runs the check once per "
                "example. Scope it with --limit or --example, or take the "
                "drafts from a run you already have with --from-run."
            )
            return 2
        try:
            written = init_expected_outputs(
                args.checklist,
                args.checks,
                from_run=args.from_run,
                model=args.model,
                provider=args.provider,
                overwrite=not args.no_overwrite,
                examples=args.examples,
                limit=args.limit,
            )
        except (FileNotFoundError, ValueError) as exc:
            logger.error("%s", exc)
            return 1
        for check, examples in sorted(written.items()):
            print(f"{check}: {len(examples)} draft(s)")
        return 0

    if args.command == "graph":
        try:
            return graph_checklist(args.checklist, write=args.write)
        except (FileNotFoundError, ValueError) as exc:
            logger.error("%s", exc)
            return 1

    if args.command == "assemble":
        try:
            with runtime_session(
                args.checklist,
                args.check,
                args.example,
                keep=args.keep_runtime,
            ) as layout:
                print(describe_permission_profile(layout))
                print()
                print(f"runtime: {layout.root}")
                if not args.keep_runtime:
                    print(
                        "(removing it now; pass --keep-runtime to inspect it)"
                    )
        except (FileNotFoundError, ValueError) as exc:
            logger.error("%s", exc)
            return 1
        return 0

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
