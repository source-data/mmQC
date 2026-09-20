"""CLI for agentic checklists.

This module owns the agentic side of the checklist workflow: *running* a check
(assembling a sealed runtime directory and driving one agent session per
example) and *scoring* the predictions that come out of it.

Milestone 1 delivered the scoring half. ``score`` is the seam that separates
running from scoring: it takes predictions that were produced somewhere else,
pairs them with the gold expected outputs of the same examples, and hands them
to the unchanged ``FlatEvaluator`` wiring in :mod:`soda_mmqc.scripts.run`.
Nothing about evaluator semantics, thresholds, or the shape of ``analysis.json``
changes here -- ``analyze_results`` and ``save_analysis`` are reused verbatim.

Milestone 2 adds *skill loading*: reading the ``SKILL.md`` files of a checklist,
resolving the graph they describe, and validating that the graph is consistent.
The graph is carried by the skills' **prose** -- a sentence telling the agent to
call another skill with the ``Skill`` tool -- while the ``requires``/``produces``
frontmatter is runner-owned documentation of the same edges. Nothing here turns
frontmatter into a call sequence; :func:`validate_skills` only checks that the
two descriptions of the graph agree.

Usage::

    python -m soda_mmqc.cli score fig-checklist \\
        --check micrograph-scale-bar \\
        --predictions path/to/predictions
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import dataclasses
import difflib
import hashlib
import itertools
import json
import os
import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Set,
    Tuple,
)

import yaml

from soda_mmqc import config, logger
from soda_mmqc.config import (
    AGENTIC_AGENT_HOME_SUBDIR,
    AGENTIC_BASE_TOOLS,
    AGENTIC_ALLOWED_TOOL_NAMES,
    AGENTIC_ARTIFACTS_SUBDIR,
    AGENTIC_DEFAULT_MODEL,
    AGENTIC_FORBIDDEN_TOOLS,
    AGENTIC_MAX_BUFFER_BYTES,
    AGENTIC_CLAUDE_TEMPLATE,
    AGENTIC_INPUT_MANIFEST_FILENAME,
    AGENTIC_INPUT_SUBDIR,
    AGENTIC_ORIENTATION_FILENAME,
    AGENTIC_PERMISSION_MODE,
    AGENTIC_RUNTIME_PREFIX,
    AGENTIC_SETTING_SOURCES,
    AGENTIC_SKILLSET_WARN_THRESHOLD,
    AGENTIC_SKILLS_SUBDIR,
    DEFAULT_MODEL,
    DEFAULT_SENTENCE_TRANSFORMER_MODEL,
    EVALUATION_DIR,
    EXAMPLES_DIR,
    resolve_agentic_runtime_root,
)
from soda_mmqc.core.examples import EXAMPLE_FACTORY, Example
from soda_mmqc.agentic.session import (  # noqa: F401  (compatibility surface)
    _default_client,
    _extract_tool_calls,
    _openai_session_client,
    _run_agent_session,
    _session_message,
    SKILL_SET_FILENAME,
    SKILL_TRACE_FILENAME,
    TOOL_AUDIT_FILENAME,
    SkillTraceRecorder,
    ToolAuditLog,
    compare_declared_and_observed,
    interactive_approver,
    load_skill_file,
    make_pretooluse_hook,
    runtime_session,
    validate_against_schema,
)
from soda_mmqc.agentic.runner import (  # noqa: F401  (compatibility surface)
    _as_prediction,
    _mock_trace,
    _write_prediction,
    DEFAULT_RUN_LABEL,
    INTERMEDIATES_DIRNAME,
    PREDICTION_FILENAME,
    default_predictions_dir,
    resolve_model,
    run_check_live,
    run_check_mock,
)
from soda_mmqc.agentic.runtime import (  # noqa: F401  (compatibility surface)
    EXAMPLE_GOLD_SUBDIR,
    EXAMPLE_INPUT_SUBDIR,
    WITHHELD_FROM_RUNTIME,
    _leaf_schema,
    _resolve_example_input_dir,
    RuntimeLayout,
    assemble_runtime,
    describe_permission_profile,
    effective_session_options,
    runtime_skill_set,
    session_cache_key,
    session_options,
)
from soda_mmqc.agentic.views import (  # noqa: F401  (compatibility surface)
    DAG_FILENAME,
    GENERATED_README_FILENAME,
    graph_checklist,
    render_dag,
    render_readme,
)
from soda_mmqc.agentic.pinning import (  # noqa: F401  (compatibility surface)
    MODEL_DEFAULTS_FILENAME,
    ModelDefaults,
    SkillSet,
    SkillSetEntry,
    VERSION_MANIFEST_FILENAME,
    checklist_pins,
    expand_skill_sets,
    load_model_defaults,
    load_version_manifest,
    resolve_skill_set,
    skill_content_hash,
    validate_version_manifest,
)
from soda_mmqc.agentic.skills import (  # noqa: F401  (compatibility surface)
    _read_json,
    SKILL_FILENAME,
    SKILL_TOOL,
    Skill,
    build_graph,
    find_cycle,
    invoked_skills,
    load_skill,
    load_skills,
    resolve_check_dir,
    select_versions,
    validate_skills,
    _prose_blocks,
)
from soda_mmqc.scripts.run import (
    EVALUATION_CONTRACT_FILES,
    ModelResult,
    analyze_results,
    list_checks,
    owns_evaluation_contracts,
    save_analysis,
)

__all__ = [
    "PREDICTION_FILENAME",
    "DEFAULT_RUN_LABEL",
    "SKILL_FILENAME",
    "SKILL_TOOL",
    "Skill",
    "RuntimeLayout",
    "resolve_check_dir",
    "load_predictions",
    "score_check",
    "load_skill",
    "load_skills",
    "build_graph",
    "find_cycle",
    "invoked_skills",
    "validate_skills",
    "select_versions",
    "VERSION_MANIFEST_FILENAME",
    "MODEL_DEFAULTS_FILENAME",
    "DAG_FILENAME",
    "GENERATED_README_FILENAME",
    "SkillSet",
    "SkillSetEntry",
    "ModelDefaults",
    "skill_content_hash",
    "resolve_skill_set",
    "load_version_manifest",
    "validate_version_manifest",
    "checklist_pins",
    "load_model_defaults",
    "expand_skill_sets",
    "render_dag",
    "render_readme",
    "graph_checklist",
    "assemble_runtime",
    "runtime_session",
    "session_options",
    "describe_permission_profile",
    "run_check_mock",
    "run_check_live",
    "run_checklist_live",
    "SkillTraceRecorder",
    "validate_against_schema",
    "compare_declared_and_observed",
    "effective_session_options",
    "session_cache_key",
    "runtime_skill_set",
    "ToolAuditLog",
    "make_pretooluse_hook",
    "interactive_approver",
    "TOOL_AUDIT_FILENAME",
    "SKILL_SET_FILENAME",
    "default_predictions_dir",
    "INTERMEDIATES_DIRNAME",
    "SKILL_TRACE_FILENAME",
    "main",
]

#: Name of the file holding one example's final leaf JSON inside a
#: predictions directory. The runner (Milestone 4) writes one per example.
PREDICTION_FILENAME = "prediction.json"

#: Top-level key under which scored records are stored in ``analysis.json``.
#: The legacy path keys this by prompt name; the agentic path has no prompt.
DEFAULT_RUN_LABEL = "agentic"



def load_predictions(predictions_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load stored predictions, keyed by example relative source path.

    Two layouts are accepted:

    * **A directory** -- the layout the runner writes: one subdirectory per
      example, mirroring the example's relative source path, each holding a
      ``prediction.json`` with that example's final leaf JSON. Debug sidecars
      (intermediate artifacts, skill traces) may sit alongside and are
      ignored here; only leaf JSON is scored.
    * **A JSON file** -- an object mapping example relative source path to
      that example's leaf JSON. Convenient for hand-assembled runs.

    Raises:
        FileNotFoundError: If ``predictions_path`` does not exist.
        ValueError: If the file layout is malformed or a directory holds no
            predictions at all.
    """
    predictions_path = Path(predictions_path)
    if not predictions_path.exists():
        raise FileNotFoundError(f"Predictions not found: {predictions_path}")

    if predictions_path.is_dir():
        return _load_predictions_from_dir(predictions_path)
    return _load_predictions_from_file(predictions_path)


def _load_predictions_from_dir(root: Path) -> Dict[str, Dict[str, Any]]:
    predictions: Dict[str, Dict[str, Any]] = {}
    for prediction_file in sorted(root.rglob(PREDICTION_FILENAME)):
        example = prediction_file.parent.relative_to(root).as_posix()
        if example == ".":
            raise ValueError(
                f"{prediction_file} sits at the root of the predictions "
                "directory; predictions must live under a subdirectory "
                "named after the example's relative source path"
            )
        predictions[example] = _read_prediction(prediction_file)

    if not predictions:
        raise ValueError(
            f"No {PREDICTION_FILENAME} files found under {root}"
        )
    return predictions


def _load_predictions_from_file(path: Path) -> Dict[str, Dict[str, Any]]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(
            f"Expected an object mapping example path to leaf JSON in "
            f"{path}, got {type(payload).__name__}"
        )
    for example, output in payload.items():
        if not isinstance(output, dict):
            raise ValueError(
                f"Prediction for {example!r} in {path} is not an object"
            )
    return dict(payload)


def _read_prediction(path: Path) -> Dict[str, Any]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(
            f"Expected a JSON object (the check's leaf output) in {path}, "
            f"got {type(payload).__name__}"
        )
    return payload


def score_check(
    checklist: str,
    check: str,
    predictions_path: Path,
    *,
    model: str = DEFAULT_MODEL,
    run_label: str = DEFAULT_RUN_LABEL,
    sentence_transformer_model: str = DEFAULT_SENTENCE_TRANSFORMER_MODEL,
    embedder: Optional[Any] = None,
    save: bool = True,
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Score stored predictions for one check against its gold outputs.

    Only the examples that have a prediction are scored; examples listed in
    ``benchmark.json`` without one are reported and skipped, so a partial run
    over a handful of examples can still be scored.

    Args:
        checklist: Checklist name, e.g. ``fig-checklist``.
        check: Check name, e.g. ``micrograph-scale-bar``.
        predictions_path: Directory or JSON file of stored predictions.
        model: Model label the predictions came from. Only used to place the
            output under ``EVALUATION_DIR/<checklist>/<check>/<model>``.
        run_label: Top-level key for the scored records in ``analysis.json``.
        sentence_transformer_model: Embedding model for semantic comparisons.
        embedder: Optional embedder override, mainly for tests.
        save: If True, write ``analysis.json`` via ``save_analysis``.

    Returns:
        ``{run_label: {"flat": [...]}}`` -- the same shape the legacy
        ``evaluate`` path produces, keyed by ``run_label`` instead of by
        prompt name.
    """
    check_dir = resolve_check_dir(checklist, check)
    schema = _read_json(check_dir / "schema.json")
    benchmark = _read_json(check_dir / "benchmark.json")

    check_name = benchmark.get("name", check_dir.name)
    try:
        example_class = benchmark["example_class"]
    except KeyError:
        raise ValueError(
            f"No example_class in {check_dir / 'benchmark.json'}"
        ) from None
    benchmark_examples = benchmark.get("examples") or []
    if not benchmark_examples:
        raise ValueError(
            f"No examples listed in {check_dir / 'benchmark.json'}"
        )

    predictions = load_predictions(Path(predictions_path))

    unknown = [ex for ex in predictions if ex not in set(benchmark_examples)]
    if unknown:
        logger.warning(
            "Ignoring %d prediction(s) for examples not in the benchmark of "
            "%s: %s",
            len(unknown),
            check_name,
            ", ".join(sorted(unknown)),
        )
    scored_examples = [ex for ex in benchmark_examples if ex in predictions]
    missing = [ex for ex in benchmark_examples if ex not in predictions]
    if missing:
        logger.warning(
            "No prediction for %d of %d benchmark example(s) of %s; "
            "scoring the remaining %d",
            len(missing),
            len(benchmark_examples),
            check_name,
            len(scored_examples),
        )
    if not scored_examples:
        known = set(benchmark_examples)
        # Every key having the form `<something>/<known example>` means this
        # is a run root, not a predictions directory: a run writes one leaf
        # per arm per replicate, and each is scored on its own. Saying so
        # beats reporting that nothing matched.
        leaves = set()
        for key in predictions:
            for example in known:
                if key.endswith("/" + example):
                    leaves.add(key[: -len(example) - 1])
                    break
        if leaves:
            raise ValueError(
                f"{predictions_path} looks like a run root, not a predictions "
                f"directory: it holds {len(leaves)} of them "
                f"({', '.join(sorted(leaves))}). A run writes one per arm per "
                f"replicate, and each is scored on its own -- point "
                f"--predictions at one of them."
            )
        raise ValueError(
            f"None of the predictions in {predictions_path} match an example "
            f"in the benchmark of {check_name}"
        )

    results: List[ModelResult] = []
    expected_outputs: List[Dict[str, Any]] = []
    for relative_source_path in scored_examples:
        example = EXAMPLE_FACTORY.create(relative_source_path, example_class)
        expected_output = example.get_expected_output(check_name)
        if not expected_output:
            logger.warning(
                "No expected output for %s; skipping", relative_source_path
            )
            continue
        expected_outputs.append(expected_output)
        results.append(
            ModelResult(
                doc_id=example.doc_id,
                model_output=predictions[relative_source_path],
                metadata={
                    "doc_id": example.doc_id,
                    "source": example.relative_source_path,
                    "example_type": example.example_class_name,
                },
            )
        )

    if not results:
        raise ValueError(
            f"No expected outputs found for the predicted examples of "
            f"{check_name}"
        )

    analyzed_results = analyze_results(
        results,
        schema,
        expected_outputs,
        check_dir=check_dir,
        sentence_transformer_model=sentence_transformer_model,
        embedder=embedder,
    )

    all_results = {run_label: analyzed_results}
    if save:
        save_analysis(all_results, checklist, check_name, model)
    return all_results






#: Sidecar directory for debug artifacts beside a prediction. Scored output is
#: `prediction.json` only; everything here is diagnostic.
INTERMEDIATES_DIRNAME = "intermediates"

#: Every tool call the session attempted, with the decision taken on it.
TOOL_AUDIT_FILENAME = "tool_audit.json"

#: The per-example record of which skills the session actually invoked. This
#: is the instrument for whether delegated discovery worked, so it is written
#: from a hook as calls occur -- never reconstructed from agent prose.
SKILL_TRACE_FILENAME = "skill_trace.json"

#: The SkillSet a prediction came from, written beside it. Without this the
#: identity of a stored prediction lives only in the runner's in-memory
#: report, which is printed once and discarded -- and a directory name is not
#: evidence.
SKILL_SET_FILENAME = "skill_set.json"























































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
            "Directory of per-example prediction.json files, or a JSON file "
            "mapping example path to leaf output"
        ),
    )
    score.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help="Model label the predictions came from (used in the output path)",
    )
    score.add_argument(
        "--run-label",
        type=str,
        default=DEFAULT_RUN_LABEL,
        help="Top-level key for the scored records in analysis.json",
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
                model=args.model,
                run_label=args.run_label,
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
