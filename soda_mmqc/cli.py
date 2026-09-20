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
from soda_mmqc.agentic.pinning import (  # noqa: F401  (compatibility surface)
    DAG_FILENAME,
    GENERATED_README_FILENAME,
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
    "validate_intermediates",
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


def _read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


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




# ---------------------------------------------------------------------------
# Generated graph views
# ---------------------------------------------------------------------------
#
# `dag.yaml` and `README.md` are generated and drift-checked rather than
# hand-written, for one reason: a hand-written picture of a graph is correct
# on the day it is written and silently wrong afterwards, and a silently wrong
# picture is what people reason from. The generator is deliberately a pure
# function of the skills plus the manifest -- no timestamps, no absolute
# paths, no filesystem ordering -- because a drift check that reports noise
# teaches people to ignore it, which is the only way it can fail completely.

_GENERATED_BANNER = (
    "This file is generated. Never hand-edit it: run "
    "`python -m soda_mmqc.cli graph {checklist} --write` instead. "
    "`graph {checklist}` fails when it and the skills disagree."
)


def _graph_view_context(
    checklist: str, checklist_dir: Path
) -> Tuple[Dict[str, Dict[str, Skill]], Dict[str, str], SkillSet]:
    skills = validate_skills(checklist_dir)
    pins = load_version_manifest(checklist_dir)
    validate_version_manifest(skills, pins, checklist_dir)
    return skills, pins, resolve_skill_set(skills, pins)


def render_dag(checklist: str, checklist_dir: Path) -> str:
    """Render ``dag.yaml`` for a checklist.

    Edges come from the **prose**, via :func:`invoked_skills`, not from
    ``requires``. Validation has already asserted the two agree, so the two
    sources give the same answer -- but the prose is what actually runs, and a
    generated picture should be drawn from the thing that runs.
    """
    checklist_dir = Path(checklist_dir)
    skills, pins, skill_set = _graph_view_context(checklist, checklist_dir)
    known = sorted(skills)

    entries = []
    for name in known:
        skill = skills[name][pins[name]]
        entries.append(
            {
                "name": name,
                "version": pins[name],
                "content_hash": skill_content_hash(skill),
                "kind": (
                    "check"
                    if owns_evaluation_contracts(skill.skill_dir)
                    else "shared"
                ),
                "description": skill.description,
                "calls": sorted(invoked_skills(skill, known)),
                "produces": sorted(skill.produces),
            }
        )

    document = {
        "checklist": checklist,
        "skill_set": skill_set.digest,
        "skills": entries,
    }
    banner = _GENERATED_BANNER.format(checklist=checklist)
    body = yaml.safe_dump(
        document, sort_keys=False, default_flow_style=False, allow_unicode=True
    )
    return f"# {banner}\n" + body


def _call_tree(
    name: str,
    skills: Mapping[str, Mapping[str, Skill]],
    pins: Mapping[str, str],
    known: Sequence[str],
    depth: int = 0,
    seen: Optional[Tuple[str, ...]] = None,
) -> List[str]:
    seen = seen or ()
    indent = "  " * depth
    if name in seen:
        return [f"{indent}- `{name}` (already shown above)"]
    lines = [f"{indent}- `{name}`"]
    for callee in sorted(invoked_skills(skills[name][pins[name]], known)):
        lines += _call_tree(
            callee, skills, pins, known, depth + 1, seen + (name,)
        )
    return lines


def render_readme(checklist: str, checklist_dir: Path) -> str:
    """Render the human-readable ``README.md`` for a checklist."""
    checklist_dir = Path(checklist_dir)
    skills, pins, skill_set = _graph_view_context(checklist, checklist_dir)
    known = sorted(skills)
    checks = [
        name for name in known
        if owns_evaluation_contracts(skills[name][pins[name]].skill_dir)
    ]
    shared = [name for name in known if name not in checks]

    lines = [
        f"<!-- {_GENERATED_BANNER.format(checklist=checklist)} -->",
        "",
        f"# `{checklist}`",
        "",
        f"{len(checks)} check(s) and {len(shared)} shared skill(s), pinned by "
        f"[`{VERSION_MANIFEST_FILENAME}`]({VERSION_MANIFEST_FILENAME}).",
        "",
        f"- **SkillSet digest:** `{skill_set.digest}`",
        "",
        "A check is a skill that owns the evaluation contracts "
        f"({', '.join(EVALUATION_CONTRACT_FILES)}). Nothing else "
        "distinguishes a check from a shared skill: the hierarchy below is "
        "carried entirely by what each skill's own prose asks for, never by "
        "where its directory sits.",
        "",
        "## Skills",
        "",
        "| skill | version | kind | description |",
        "| --- | --- | --- | --- |",
    ]
    for name in known:
        skill = skills[name][pins[name]]
        kind = "check" if name in checks else "shared"
        description = skill.description.replace("|", "\\|")
        lines.append(
            f"| `{name}` | {pins[name]} | {kind} | {description} |"
        )

    lines += ["", "## Call graph", ""]
    if shared:
        lines += [
            "Each entry is one check and the skills its prose asks for, "
            "transitively.",
            "",
        ]
    for name in checks:
        lines += _call_tree(name, skills, pins, known)
    unreached = [
        name for name in shared
        if not any(
            name in _joined_tree(check, skills, pins, known) for check in checks
        )
    ]
    if unreached:
        lines += [
            "",
            "### Called by no check",
            "",
            "These are pinned and assembled -- every skill's description "
            "competes in every session -- but no check's prose asks for them "
            "today.",
            "",
        ]
        lines += [f"- `{name}`" for name in unreached]
    return "\n".join(lines) + "\n"


def _joined_tree(
    name: str,
    skills: Mapping[str, Mapping[str, Skill]],
    pins: Mapping[str, str],
    known: Sequence[str],
) -> Set[str]:
    reached: Set[str] = set()
    stack = [name]
    while stack:
        current = stack.pop()
        for callee in invoked_skills(skills[current][pins[current]], known):
            if callee not in reached:
                reached.add(callee)
                stack.append(callee)
    return reached


def graph_checklist(checklist: str, *, write: bool = False) -> int:
    """Drift-check or regenerate a checklist's graph views.

    Metadata only: no example is read and no session is opened, so this is
    cheap enough to run in CI on every checklist on every commit -- which is
    the only way the views stay true.

    Returns:
        ``0`` when the committed views match the skills (or were just
        written), ``1`` when they drift.
    """
    checklist_dir = config.CHECKLIST_DIR / checklist
    if not checklist_dir.is_dir():
        raise FileNotFoundError(f"Checklist not found: {checklist_dir}")

    views = {
        DAG_FILENAME: render_dag(checklist, checklist_dir),
        GENERATED_README_FILENAME: render_readme(checklist, checklist_dir),
    }

    if write:
        for filename, text in views.items():
            (checklist_dir / filename).write_text(text, encoding="utf-8")
        print(
            f"wrote {', '.join(sorted(views))} in {checklist_dir}"
        )
        return 0

    drifted = []
    for filename, expected in sorted(views.items()):
        path = checklist_dir / filename
        actual = path.read_text(encoding="utf-8") if path.is_file() else ""
        if actual != expected:
            drifted.append(filename)
            print(f"--- drift in {path} ---")
            print(
                "".join(
                    difflib.unified_diff(
                        actual.splitlines(keepends=True),
                        expected.splitlines(keepends=True),
                        fromfile=f"{filename} (committed)",
                        tofile=f"{filename} (from the skills)",
                    )
                )
            )

    if drifted:
        print(
            f"{len(drifted)} generated view(s) disagree with the skills. "
            f"Run `python -m soda_mmqc.cli graph {checklist} --write` and "
            "commit the result."
        )
        return 1
    print(f"{checklist}: generated views are in sync with the skills")
    return 0


#: Files that must never reach the runtime. The evaluation contracts are the
#: answer key and the list of other examples; `prompts/` is the legacy asset
#: the skills replace. None of them is an input to a session.
WITHHELD_FROM_RUNTIME = ("benchmark.json", "eval-manifest.json")

#: Subdirectory of an example holding its gold. Never copied.
EXAMPLE_GOLD_SUBDIR = "checks"

#: Subdirectory of an example holding its inputs. The only thing copied.
EXAMPLE_INPUT_SUBDIR = "content"


@dataclass(frozen=True)
class RuntimeLayout:
    """The assembled, sealed runtime directory for one example.

    Every path is inside :attr:`root`, which sits outside the repository.
    Nothing here refers back to the skill store, the benchmark, or any other
    example -- that is the point of the type.
    """

    root: Path
    skills_root: Path
    input_root: Path
    artifacts_root: Path
    orientation_path: Path
    entry_point: str
    schema_path: Path
    agent_home: Path
    example: str

    #: The example's content, as provider-neutral parts, with `path`
    #: values rebased onto this runtime. Resolved at assembly because the
    #: layout deliberately keeps no link back to the benchmark that names
    #: the example class.
    input_parts: Tuple[Mapping[str, Any], ...] = ()



def _resolve_example_input_dir(example: str) -> Path:
    """Return the directory holding one example's inputs.

    Raises:
        FileNotFoundError: If the example or its input directory is absent.
    """
    example_dir = EXAMPLES_DIR / example
    if not example_dir.is_dir():
        raise FileNotFoundError(f"Example not found: {example_dir}")
    input_dir = example_dir / EXAMPLE_INPUT_SUBDIR
    if not input_dir.is_dir():
        raise FileNotFoundError(
            f"Example {example} has no {EXAMPLE_INPUT_SUBDIR}/ directory: "
            f"{input_dir}"
        )
    return input_dir


def _copy_skill(skill: Skill, destination: Path) -> None:
    """Copy one skill version into the runtime, flattened and stripped.

    The version directory disappears -- the SDK looks for
    ``<name>/SKILL.md`` -- and only the instruction file plus the runtime
    schema travel. The evaluation contracts and the legacy prompts stay in
    the store.
    """
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(skill.path, destination / SKILL_FILENAME)

    schema = skill.skill_dir / "schema.json"
    if schema.is_file():
        shutil.copy2(schema, destination / "schema.json")


def _resolve_example(checklist: str, check: str, example: str) -> Example:
    """Build the `Example` for one benchmark entry.

    Raises:
        ValueError: If the check's benchmark declares no ``example_class``.
    """
    benchmark = _read_json(
        resolve_check_dir(checklist, check) / "benchmark.json"
    )
    example_class = benchmark.get("example_class")
    if not example_class:
        raise ValueError(
            f"No example_class in {checklist}/{check}/benchmark.json. The "
            "harness cannot state this example's input without knowing what "
            "kind of example it is, and it must not guess from extensions."
        )
    return EXAMPLE_FACTORY.create(example, example_class)


def _rebase_into_input(value: Any) -> Any:
    """Move one content-relative path onto the runtime's `input/`."""
    if value is None:
        return None
    if isinstance(value, str):
        return f"{AGENTIC_INPUT_SUBDIR}/{value}"
    if isinstance(value, list):
        return [_rebase_into_input(item) for item in value]
    raise TypeError(
        f"paths must be str, None or list of str; got {type(value).__name__}"
    )


def _rebase_parts(
    parts: Sequence[Mapping[str, Any]]
) -> Tuple[Mapping[str, Any], ...]:
    """Rebase image parts onto the runtime; text parts pass through."""
    rebased: List[Mapping[str, Any]] = []
    for part in parts:
        if part["kind"] == "image":
            rebased.append({**part, "path": _rebase_into_input(part["path"])})
        else:
            rebased.append(dict(part))
    return tuple(rebased)


def _write_input_manifest(source_root: Path, staged: Example) -> None:
    """Write `input/inputs.json`, naming the files the session may open.

    The example's *content* is not here -- it is in the opening message, so
    it cannot be missed. What remains are files the session may want and
    usually does not: a figure example may carry several spreadsheets, and
    most checks open none of them. That is the whole argument for leaving
    them as files. It is not an argument about *when* something enters
    context -- a file that is read stays in the history exactly as a pushed
    part does -- but about the ones that are never read at all, which cost
    nothing.

    The session has no shell, no glob and no directory listing, so a file
    this does not name is one it can only guess at.
    """
    manifest = {
        role: _rebase_into_input(value)
        for role, value in staged.supporting_files().items()
    }
    path = source_root / AGENTIC_INPUT_SUBDIR / AGENTIC_INPUT_MANIFEST_FILENAME
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def assemble_runtime(
    checklist: str,
    check: str,
    example: str,
    *,
    root: Optional[Path] = None,
    pins: Optional[Mapping[str, str]] = None,
) -> RuntimeLayout:
    """Assemble a sealed runtime directory for one example.

    The result contains **every** skill of the checklist -- so that all of
    their descriptions compete for the agent's attention, which is the thing
    Milestone 4 measures -- exactly one version of each, the named check as
    the entry point, and the one example's inputs. It contains no evaluation
    contract, no gold, no other example, no sibling version, and no link of
    any kind back to the repository.

    Assembly is atomic: the runtime is built in a staging directory and moved
    into place only once complete, so a failure leaves nothing half-built.

    Args:
        checklist: Checklist name, e.g. ``fig-checklist``.
        check: The entry-point leaf.
        example: Example relative source path.
        root: Where to put the runtime. Defaults to a fresh directory under
            the configured runtime root, which is outside the repository.
        pins: Optional ``{skill: version}``. Defaults to the checklist's
            ``version-manifest.yaml``, and -- only when there is none -- to
            the highest version of each skill.

    Raises:
        FileNotFoundError: If the checklist, check or example is absent.
        ValueError: If the check is not a check, or the skills are invalid.
    """
    check_dir = resolve_check_dir(checklist, check)
    checklist_dir = check_dir.parent

    # Validate the graph before building anything from it: a runtime
    # assembled from an inconsistent checklist would fail confusingly, at
    # session time, per example.
    skills = validate_skills(checklist_dir)
    if check not in skills:
        raise ValueError(
            f"{check!r} owns the evaluation contracts but has no "
            f"{SKILL_FILENAME}; it cannot be an agentic entry point"
        )
    if pins is None:
        pins = checklist_pins(checklist_dir)
        if pins is not None:
            validate_version_manifest(skills, pins, checklist_dir)
    selected = select_versions(skills, pins)
    input_dir = _resolve_example_input_dir(example)
    staged_example = _resolve_example(checklist, check, example)

    if root is None:
        root = Path(
            tempfile.mkdtemp(
                prefix=AGENTIC_RUNTIME_PREFIX,
                dir=resolve_agentic_runtime_root(),
            )
        )
        root.rmdir()  # mkdtemp reserved the name; staging is renamed onto it
    root = Path(root)
    root.parent.mkdir(parents=True, exist_ok=True)

    staging = Path(
        tempfile.mkdtemp(prefix=f".{root.name}.partial-", dir=root.parent)
    )
    try:
        skills_root = staging / AGENTIC_SKILLS_SUBDIR
        skills_root.mkdir(parents=True)
        for name, skill in selected.items():
            _copy_skill(skill, skills_root / name)

        # `content/` is copied whole, minus any nested answer key. The
        # example layout is recursive -- a document-level example's
        # `content/` holds its figure sub-examples, each with its own
        # `checks/` -- so a plain copy would stage the gold for every figure
        # in the manuscript. `_assert_sealed` catches that afterwards; this
        # is the copier honouring the rule rather than relying on the alarm.
        shutil.copytree(
            input_dir,
            staging / AGENTIC_INPUT_SUBDIR,
            symlinks=False,
            ignore=shutil.ignore_patterns(EXAMPLE_GOLD_SUBDIR),
        )
        (staging / AGENTIC_ARTIFACTS_SUBDIR).mkdir()
        (staging / AGENTIC_AGENT_HOME_SUBDIR).mkdir()

        layout = RuntimeLayout(
            root=root,
            skills_root=root / AGENTIC_SKILLS_SUBDIR,
            input_root=root / AGENTIC_INPUT_SUBDIR,
            agent_home=root / AGENTIC_AGENT_HOME_SUBDIR,
            artifacts_root=root / AGENTIC_ARTIFACTS_SUBDIR,
            orientation_path=root / AGENTIC_ORIENTATION_FILENAME,
            entry_point=check,
            schema_path=root / AGENTIC_SKILLS_SUBDIR / check / "schema.json",
            example=example,
            input_parts=_rebase_parts(staged_example.input_parts()),
        )
        _write_input_manifest(staging, staged_example)
        shutil.copy2(
            AGENTIC_CLAUDE_TEMPLATE, staging / AGENTIC_ORIENTATION_FILENAME
        )

        _assert_sealed(staging)
        os.replace(staging, root)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    logger.info(
        "Assembled runtime for %s/%s at %s (%d skills)",
        checklist, check, root, len(selected),
    )
    return layout


def _assert_sealed(staging: Path) -> None:
    """Refuse to hand over a runtime that leaks.

    This is a belt-and-braces check on the assembler's own output rather than
    a substitute for the tests. It runs on every assembly, including in
    production, because the cost of a leak is a scored run that quietly saw
    the answer key.
    """
    leaked = sorted(
        str(p.relative_to(staging))
        for p in staging.rglob("*")
        if p.name in WITHHELD_FROM_RUNTIME
        or p.is_symlink()
        or p.name == EXAMPLE_GOLD_SUBDIR
    )
    if leaked:
        raise ValueError(
            f"Refusing to assemble a runtime that exposes: {', '.join(leaked)}"
        )


def _abs_rule_path(path: Path) -> str:
    """Render a path for an SDK permission rule, portably.

    The SDK's ``//path`` form means "absolute filesystem path"; a single
    leading slash anchors at the session's working directory instead, which
    would scope the rule to the wrong place. ``as_posix()`` keeps the rule
    readable on Windows, where a native path would carry backslashes that the
    glob syntax does not expect.
    """
    return f"//{path.resolve().as_posix().lstrip('/')}/**"


def session_options(layout: RuntimeLayout) -> Dict[str, Any]:
    """Return the literal session options for one assembled runtime.

    This is the artifact human gate 3B reviews, and the thing Milestone 4
    hands to the Agent SDK. It is built from the layout so that the permission
    boundary is decided by the runtime's own shape rather than by whatever
    directory a caller happens to be in.

    Containment rests on four properties, and three of them are easy to get
    subtly wrong:

    * ``cwd`` is the runtime root, so project-scope skill discovery finds the
      assembled tree.
    * ``setting_sources`` omits ``user``, so the operator's own settings are
      not read. On its own this does **not** keep foreign skills out of the
      session's ``init`` report -- the installation's bundled ones are listed
      either way. What keeps them out of a scored run is the named ``skills``
      pool below, which is what makes them non-invocable.
    * ``permission_mode`` is ``dontAsk``. Without it ``allowed_tools`` is only
      a list of auto-approvals and every *unlisted* tool remains reachable.
    * The file rules are **scoped to paths**, not bare tool names: reads are
      confined to the runtime, writes to its artifacts directory. A bare
      ``Read`` would auto-approve reading anything on disk, including the
      repository and the gold.

    ``skills="all"`` is deliberate: every assembled skill must be invocable,
    because delegating discovery to the agent is the premise under test. It is
    not a widening -- the set is bounded by what was assembled.
    """
    return {
        "cwd": str(layout.root),
        "setting_sources": list(AGENTIC_SETTING_SOURCES),
        # The assembled skills by name, never "all". Naming the pool does not
        # empty the session's `init` report: measured 2026-09-18 against
        # claude-sonnet-5 and claude_agent_sdk 0.2.152, `init` still listed 29
        # skills -- ours plus 16 bundled with the CLI installation
        # (deep-research, code-review, debug, ...). That array is an
        # installation inventory, not this session's pool, and it is the same
        # with and without this list. Do not assert on its length.
        #
        # What the list does bound is everything downstream of it, which is
        # what the measurement needs. In the same probe the Skill tool offered
        # the model exactly our 13 names -- the foreign descriptions never
        # reached its context, so they cannot compete for its attention -- and
        # a forced call came back:
        #
        #     <tool_use_error>Skill code-review is not in this session's
        #     skills allowlist</tool_use_error>
        #
        # So the bundled skills are present in the report, invisible to the
        # model, and not invocable. Assert on invocability, never on `init`.
        #
        # This is not preselection: every skill of the checklist is listed, so
        # they all still compete with each other, which is what the plan
        # requires. It removes contamination, not choice.
        "skills": sorted(
            p.parent.name
            for p in layout.skills_root.glob(f"*/{SKILL_FILENAME}")
        ),
        # What the session *has*. Everything else is absent from its context
        # rather than merely denied, so it cannot be reached by a tool name
        # this profile failed to anticipate.
        "tools": list(AGENTIC_BASE_TOOLS),
        # What it may use without prompting, scoped to paths. There is no
        # write rule because there is no write tool: the runner serialises
        # the structured result, so nothing the session does needs to touch
        # the filesystem.
        "allowed_tools": [
            f"Read({_abs_rule_path(layout.root)})",
            "Skill",
        ],
        "disallowed_tools": sorted(AGENTIC_FORBIDDEN_TOOLS),
        "permission_mode": AGENTIC_PERMISSION_MODE,
        # Without this the session dies the moment it opens the figure: the
        # image arrives base64-encoded in one JSON message and overflows the
        # SDK's 1 MB default reader buffer.
        "max_buffer_size": AGENTIC_MAX_BUFFER_BYTES,
        # Keeps the transcript and the auto-memory directory inside the
        # runtime instead of ~/.claude/projects/, where they outlive teardown
        # and carry gold-derived reasoning out of the sealed tree.
        "env": {"CLAUDE_CONFIG_DIR": str(layout.agent_home)},
        # The schema is enforced, not described. Prose asking the model to
        # "conform exactly" is a request; this is a constraint, and the M2
        # spike measured it reaching enum level -- the model could not write
        # "MAYBE" into a yes/no field even when told to.
        "output_format": {
            "type": "json_schema",
            "schema": _leaf_schema(layout),
        },
    }


def describe_permission_profile(layout: RuntimeLayout) -> str:
    """Render the permission profile for a human to read.

    Printed by the runner so that gate 3C can compare what actually ran
    against what was approved at gate 3B.
    """
    options = session_options(layout)
    skill_count = len(list(layout.skills_root.glob(f"*/{SKILL_FILENAME}")))
    lines = [
        "Agentic session permission profile",
        "=" * 34,
        f"  runtime root     : {options['cwd']}",
        f"  setting sources  : {', '.join(options['setting_sources'])}"
        "   (no 'user': the operator's settings are not read)",
        f"  skills           : {options['skills']}"
        f"   ({skill_count} assembled)",
        f"  permission mode  : {options['permission_mode']}"
        "   (anything that would prompt is denied)",
        "  allowed (scoped) :",
    ]
    for rule in options["allowed_tools"]:
        lines.append(f"      {rule}")
    lines.append("  forbidden tools  :")
    for tool in options["disallowed_tools"]:
        lines.append(f"      {tool:<14} {AGENTIC_FORBIDDEN_TOOLS[tool]}")
    return "\n".join(lines)


@contextlib.contextmanager
def runtime_session(
    checklist: str,
    check: str,
    example: str,
    *,
    root: Optional[Path] = None,
    keep: bool = False,
    pins: Optional[Mapping[str, str]] = None,
) -> Iterator[RuntimeLayout]:
    """Assemble a runtime, yield it, and remove it afterwards.

    The runtime is removed even when the body raises, because the common
    reason for raising is a failed session and leaving gold-derived
    intermediates behind is exactly what the sealed runtime exists to avoid.
    ``keep=True`` preserves it for debugging, including after a failure --
    which is when it is most wanted.
    """
    layout = assemble_runtime(
        checklist, check, example, root=root, pins=pins
    )
    try:
        yield layout
    finally:
        if keep:
            logger.info("Keeping runtime at %s", layout.root)
        else:
            shutil.rmtree(layout.root, ignore_errors=True)


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


def default_predictions_dir(checklist: str, check: str, model: str) -> Path:
    """Where a run writes its predictions, mirroring the analysis layout."""
    return EVALUATION_DIR / checklist / check / model / "predictions"


def _write_prediction(
    predictions_dir: Path,
    example: str,
    prediction: Dict[str, Any],
    trace: List[Dict[str, Any]],
    skill_set: Optional[SkillSet] = None,
) -> Path:
    """Write one example's leaf JSON plus its trace sidecar."""
    example_dir = predictions_dir / example
    example_dir.mkdir(parents=True, exist_ok=True)

    prediction_path = example_dir / PREDICTION_FILENAME
    prediction_path.write_text(
        json.dumps(prediction, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    intermediates = example_dir / INTERMEDIATES_DIRNAME
    intermediates.mkdir(exist_ok=True)
    if skill_set is not None:
        (intermediates / SKILL_SET_FILENAME).write_text(
            json.dumps(
                {
                    "digest": skill_set.digest,
                    "skills": [
                        dataclasses.asdict(e)
                        for e in sorted(
                            skill_set.entries, key=lambda e: e.name
                        )
                    ],
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
    (intermediates / SKILL_TRACE_FILENAME).write_text(
        json.dumps(trace, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return prediction_path


def _mock_trace(checklist_dir: Path, check: str) -> List[Dict[str, Any]]:
    """A deterministic stand-in for the trace a real session would leave.

    It reports the hops the entry point *declares*, which is what a correctly
    behaving session would produce. That makes `--mock` exercise the whole
    path -- including the declared-versus-observed comparison -- without
    credentials.

    It is explicitly **not** evidence that discovery works. Mock traces are
    generated from the frontmatter, so comparing them against the frontmatter
    is circular; only a live run answers that question, which is what gate 4D
    is for. `source: "mock"` marks every entry so the two can never be
    confused in a report.
    """
    skills = load_skills(checklist_dir)
    selected = select_versions(skills, checklist_pins(checklist_dir))
    entry = selected[check]
    return [
        {
            "skill": name,
            "version": selected[name].version,
            "tool_input": {"name": name},
            "tool_use_id": f"mock-{index:04d}",
            "timestamp": None,
            "source": "mock",
        }
        for index, name in enumerate(entry.requires)
    ]


def _as_prediction(gold: Mapping[str, Any], schema: Mapping[str, Any]) -> Dict[str, Any]:
    """Project a gold record onto the fields the output schema declares.

    Gold files carry curation metadata -- ``updated_at`` and friends -- that
    the leaf schema does not allow, because the schema describes what a
    *session* must produce, not what the curation UI stores. Writing gold
    verbatim as a mock prediction therefore produces output that a real
    session would be rejected for, which would make ``--mock`` exercise a
    path the live runner cannot take.

    So the mock writes the contracted fields only. The stripped keys are
    metadata by construction; nothing scored is lost, because the evaluator
    reads the same gold through its own path.
    """
    allowed = set(schema.get("properties") or {})
    if not allowed:
        return dict(gold)
    return {key: value for key, value in gold.items() if key in allowed}


def run_check_mock(
    checklist: str,
    check: str,
    *,
    output: Optional[Path] = None,
    model: str = DEFAULT_MODEL,
    examples: Optional[Sequence[str]] = None,
) -> Path:
    """Write each benchmark example's gold as its prediction, offline.

    This is the credential-free path: it opens no session, contacts no
    provider, and validates nothing it has not been given. Its purpose is to
    let CI exercise prediction layout, trace layout and scoring end to end.

    **It is genuinely offline**, which the legacy ``evaluate --mock`` is not:
    that path validates the model against the provider first and so aborts
    without an API key. Milestone 1's gate 1B recorded that as debt precisely
    because it makes a credential-free gate impossible; this implementation
    does not repeat it.

    Returns:
        The predictions directory.
    """
    check_dir = resolve_check_dir(checklist, check)
    checklist_dir = check_dir.parent
    benchmark = _read_json(check_dir / "benchmark.json")
    schema = _read_json(check_dir / "schema.json")["format"]["schema"]

    check_name = benchmark.get("name", check)
    example_class = benchmark["example_class"]
    wanted = list(examples) if examples else list(benchmark.get("examples") or [])
    if not wanted:
        raise ValueError(f"No examples to run for {check_name}")

    predictions_dir = Path(
        output or default_predictions_dir(checklist, check, model)
    )
    trace = _mock_trace(checklist_dir, check)

    written = 0
    for relative_source_path in wanted:
        example = EXAMPLE_FACTORY.create(relative_source_path, example_class)
        expected = example.get_expected_output(check_name)
        if not expected:
            logger.warning(
                "No expected output for %s; skipping", relative_source_path
            )
            continue
        _write_prediction(
            predictions_dir,
            relative_source_path,
            _as_prediction(expected, schema),
            trace,
        )
        written += 1

    if not written:
        raise ValueError(
            f"No gold found for any example of {check_name}; nothing written"
        )
    logger.info(
        "Wrote %d mock prediction(s) to %s", written, predictions_dir
    )
    return predictions_dir


def _leaf_schema(layout: RuntimeLayout) -> Dict[str, Any]:
    """The JSON Schema the final prediction must satisfy."""
    envelope = _read_json(layout.schema_path)
    return envelope["format"]["schema"]


def validate_against_schema(payload: Any, schema: Mapping[str, Any]) -> None:
    """Raise if ``payload`` does not satisfy ``schema``.

    Raises:
        ValueError: With every validation error, not just the first, so a
            malformed prediction can be fixed in one pass.
    """
    import jsonschema

    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(
            f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
            for e in errors
        )
        raise ValueError(f"Output does not match the schema: {detail}")


class SkillTraceRecorder:
    """Records ``Skill`` invocations as they happen.

    This is the milestone's primary instrument -- the only evidence that the
    prose actually reached the intended skill -- so it is deliberately dumb:
    it records what the SDK reports about a tool call and nothing else. It
    never parses transcript JSONL and never infers a call from agent prose,
    because an inferred trace would be indistinguishable from a wish.

    Entries are appended to disk as calls occur, so a session that fails
    halfway still leaves the record of how far it got. That is usually the
    session whose trace matters most.
    """

    def __init__(self, path: Path, versions: Mapping[str, str]):
        self.path = Path(path)
        self._versions = dict(versions)
        self.entries: List[Dict[str, Any]] = []
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._flush()

    def record(self, tool_name: str, tool_input: Any, tool_use_id: Any) -> None:
        """Record one tool call if it is a ``Skill`` invocation."""
        if tool_name != SKILL_TOOL:
            return
        name = None
        if isinstance(tool_input, Mapping):
            for key in ("name", "skill", "skill_name", "command"):
                value = tool_input.get(key)
                if isinstance(value, str) and value:
                    name = value.lstrip("/")
                    break
        self.entries.append(
            {
                "skill": name,
                "version": self._versions.get(name),
                "tool_input": tool_input,
                "tool_use_id": tool_use_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "hook",
            }
        )
        self._flush()

    def _flush(self) -> None:
        self.path.write_text(
            json.dumps(self.entries, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    @property
    def invoked(self) -> List[str]:
        return [e["skill"] for e in self.entries if e["skill"]]


def compare_declared_and_observed(
    checklist_dir: Path,
    check: str,
    observed: Sequence[str],
    *,
    pins: Optional[Mapping[str, str]] = None,
) -> Dict[str, List[str]]:
    """Report declared hops against the ones that actually fired.

    Diagnostic only, never enforcement. A declared hop that never fired is a
    prompt-authoring problem to fix in the skill text; it is emphatically not
    something the runner should paper over by calling the skill itself, which
    would make the trace a record of our control flow instead of the agent's.

    ``pins`` must name the version that actually ran. Without it this falls
    back to the checklist manifest, and only then to the highest version --
    comparing a ``v1`` session against ``v2``'s declared hops would invent
    both missing and extra hops out of nothing, in exactly the unpinned
    comparison this diagnostic exists to inform.
    """
    skills = load_skills(checklist_dir)
    if pins is None:
        pins = checklist_pins(checklist_dir)
    declared = set(select_versions(skills, pins)[check].requires)
    seen = set(observed)
    return {
        "declared": sorted(declared),
        "observed": sorted(seen),
        "declared_not_observed": sorted(declared - seen),
        "observed_not_declared": sorted(seen - declared),
    }


async def _default_client(
    parts: Sequence[Mapping[str, Any]], options: Mapping[str, Any]
):
    """Adapter over the Agent SDK's ``query()``.

    Isolated behind one function so every test can substitute a fake and the
    SDK import stays lazy -- importing it costs a ~200 MB bundled binary's
    worth of path resolution, and a credential-free ``--mock`` run must not
    need it at all.

    ``query`` accepts ``str | AsyncIterable[dict]``. Streaming mode is used
    because the example's content travels with the request, and content
    blocks are how an image gets into an opening message.
    """
    from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, query

    from soda_mmqc.agentic_render import render_anthropic

    payload = dict(options)
    # `hooks` travels through session_options() as plain callables so the
    # profile stays reviewable and testable without importing the SDK. Only
    # here, at the boundary, does it become SDK types.
    raw_hooks = payload.pop("hooks", None)
    if raw_hooks:
        payload["hooks"] = {
            event: [HookMatcher(hooks=list(callbacks))]
            for event, callbacks in raw_hooks.items()
        }

    root = Path(payload["cwd"])

    async def message_stream():
        yield {
            "type": "user",
            "message": {
                "role": "user",
                "content": render_anthropic(parts, root),
            },
        }

    async for message in query(
        prompt=message_stream(), options=ClaudeAgentOptions(**payload)
    ):
        yield message


def _session_message(layout: RuntimeLayout) -> List[Dict[str, Any]]:
    """The request handed to the session: an instruction, then the content.

    It names the entry point and does **not** name the entry point's
    dependencies or order them: reaching them is the agent's job, and
    supplying a closure here would make the trace a measurement of this
    string rather than of the skills' prose.

    The example's content follows the instruction rather than waiting in a
    file. A session cannot fail to fetch what it was already given, which is
    why this commit deletes the gate that used to check.
    """
    instruction = {
        "kind": "text",
        "text": (
            f"Apply the `{layout.entry_point}` check to the example below, "
            f"and answer with the structured output you were given a schema "
            f"for. Supporting files, if any, are named in "
            f"{AGENTIC_INPUT_SUBDIR}/{AGENTIC_INPUT_MANIFEST_FILENAME}."
        ),
    }
    return [instruction, *(dict(part) for part in layout.input_parts)]


def _extract_result_text(message: Any) -> Optional[str]:
    """The session's final structured answer, if this message carries one.

    Tolerant of object and mapping shapes so a fake client can be a plain
    dict, like the other extractors here.
    """
    if isinstance(message, Mapping):
        value = message.get("result")
    else:
        value = getattr(message, "result", None)
    return value if isinstance(value, str) else None


def _extract_session_info(message: Any) -> Optional[Dict[str, Any]]:
    """Pull the SDK's startup report out of the `init` system message.

    That message carries the tool set and skills the session actually got,
    which is the evidence human gate 3B asks for and the only place it
    exists. Tolerant of object and mapping shapes so a fake client can supply
    a plain dict.
    """
    def get(obj, key):
        if isinstance(obj, Mapping):
            return obj.get(key)
        return getattr(obj, key, None)

    if get(message, "subtype") != "init":
        return None
    data = get(message, "data")
    source = data if isinstance(data, Mapping) else message
    return {
        key: get(source, key)
        for key in ("tools", "skills", "model", "permissionMode", "cwd")
        if get(source, key) is not None
    }


def _extract_tool_calls(message: Any) -> Iterator[Tuple[str, Any, Any]]:
    """Yield ``(tool_name, tool_input, tool_use_id)`` from an SDK message.

    Tolerant of both object and mapping shapes so a fake client can be a
    plain dict and the real SDK's dataclasses work unchanged.
    """
    content = None
    if isinstance(message, Mapping):
        content = message.get("content")
    else:
        content = getattr(message, "content", None)
    if not isinstance(content, (list, tuple)):
        return
    for block in content:
        if isinstance(block, Mapping):
            name = block.get("name")
            payload = block.get("input")
            use_id = block.get("id")
        else:
            name = getattr(block, "name", None)
            payload = getattr(block, "input", None)
            use_id = getattr(block, "id", None)
        if isinstance(name, str):
            yield name, payload, use_id


async def _run_agent_session(
    layout: RuntimeLayout,
    *,
    client=None,
    trace_path: Optional[Path] = None,
    versions: Optional[Mapping[str, str]] = None,
    audit_log: Optional[ToolAuditLog] = None,
    approver: Optional[Any] = None,
    denied_shared_skills: Optional[Set[str]] = None,
    options: Optional[Mapping[str, Any]] = None,
) -> Tuple[Dict[str, Any], SkillTraceRecorder, ToolAuditLog]:
    """Run one session against an assembled runtime and return its output.

    The session is given the runtime, the entry point and the example, and
    nothing else. Every assembled skill's description is loaded -- the runner
    preselects nothing -- so the hops have to be found by the agent.

    The prediction is read from the artifacts directory and **validated
    before it is returned**, so an invalid output fails before any caller can
    write it as a prediction.

    Raises:
        ValueError: If the session wrote no prediction, or wrote one that
            does not satisfy the leaf schema.
    """
    intermediates = layout.artifacts_root / INTERMEDIATES_DIRNAME
    recorder = SkillTraceRecorder(
        trace_path or intermediates / SKILL_TRACE_FILENAME, versions or {}
    )
    audit = audit_log or ToolAuditLog(intermediates / TOOL_AUDIT_FILENAME)
    run = client or _default_client
    options = dict(options if options is not None else session_options(layout))
    options["hooks"] = {
        "PreToolUse": [
            make_pretooluse_hook(audit, approver, denied_shared_skills)
        ]
    }

    read_paths: Set[str] = set()
    result_text: Optional[str] = None
    async for message in run(_session_message(layout), options):
        info = _extract_session_info(message)
        if info:
            audit.note_session(info)
        result_text = _extract_result_text(message) or result_text
        for tool_name, tool_input, tool_use_id in _extract_tool_calls(message):
            recorder.record(tool_name, tool_input, tool_use_id)
            if tool_name == "Read" and isinstance(tool_input, Mapping):
                read_paths.add(str(tool_input.get("file_path") or ""))

    # The structured result is the answer; the runner serialises it. Asking
    # the session to write the file made "forgot to write it" and "wrote
    # something that is not JSON" into failure modes of the measurement
    # rather than of the model's judgement.
    if result_text is None:
        raise ValueError(
            "The session returned no structured result. `output_format` "
            "constrains the answer to the leaf schema, so its absence means "
            "the session ended without answering."
        )
    try:
        prediction = json.loads(result_text)
    except json.JSONDecodeError as exc:
        # Documented behaviour: asked for something the schema cannot express,
        # the model explains itself in prose instead. That is a real outcome,
        # and the decode failure is how it is detected.
        raise ValueError(
            f"The session's result is not JSON, which means it declined to "
            f"answer within the schema: {exc}. First 200 characters: "
            f"{result_text[:200]!r}"
        ) from exc
    output_path = layout.artifacts_root / PREDICTION_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(prediction, indent=2) + "\n", encoding="utf-8")
    validate_against_schema(prediction, _leaf_schema(layout))
    return prediction, recorder, audit


def validate_intermediates(
    layout: RuntimeLayout,
    skills: Mapping[str, Mapping[str, Skill]],
    *,
    pins: Optional[Mapping[str, str]] = None,
    strict: bool = True,
) -> Tuple[Dict[str, Path], List[str]]:
    """Validate the intermediate artifacts a session produced.

    A skill that declares ``produces: [panels]`` and ships a ``schema.json``
    has a runtime contract, and an intermediate that violates it is worth
    recording.

    Absence is not an error. Whether a shared skill ran at all is the
    question gate 4D exists to answer, and failing the run because an
    intermediate is missing would convert that observation into a crash and
    destroy the evidence.

    ``strict=False`` extends that same reasoning to an *invalid*
    intermediate, and the runner uses it. This function only ever runs after
    the session has closed, so the "catch it before a downstream skill
    consumes it" it was written for is not available to it: by the time it
    looks, every downstream skill has already consumed the artifact and the
    leaf has already produced its answer. Raising at that point cannot
    protect anything -- its only effect is to throw away a completed,
    schema-valid prediction because a *debug sidecar* was malformed. The plan
    is explicit that only leaf JSON is scored and intermediates are sidecars,
    so the violation is reported and kept, not fatal.

    Returns:
        ``({artifact name: path}, [problem, ...])`` -- the intermediates that
        were found and valid, and one message per invalid one.
    """
    selected = select_versions(skills, pins)
    found: Dict[str, Path] = {}
    problems: List[str] = []
    for name, skill in selected.items():
        schema_path = skill.skill_dir / "schema.json"
        for produced in skill.produces:
            artifact = layout.artifacts_root / f"{produced}.json"
            if not artifact.is_file() or not schema_path.is_file():
                continue
            if produced == layout.entry_point:
                continue  # the leaf's own output, validated separately
            envelope = _read_json(schema_path)
            try:
                validate_against_schema(
                    _read_json(artifact), envelope["format"]["schema"]
                )
            except ValueError as exc:
                problem = (
                    f"Intermediate {artifact.name} produced by {name!r} does "
                    f"not match its schema: {exc}"
                )
                if strict:
                    raise ValueError(problem) from None
                logger.warning("%s", problem)
                problems.append(problem)
                continue
            found[produced] = artifact
    return found, problems


def effective_session_options(
    layout: RuntimeLayout,
    skills: Mapping[str, Mapping[str, Skill]],
    *,
    defaults: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Session options after checklist defaults and declared ``needs``.

    The union of the assembled skills' ``needs`` may **narrow** the Milestone
    3 permission profile but never widen it past its allowlist. That
    direction is deliberate: a skill asking for a capability is a request,
    and honouring it silently would let any future skill author widen the
    containment boundary by editing frontmatter. Anything requested that the
    profile does not already grant is dropped and logged, and granting it is
    a new human gate.
    """
    options = session_options(layout)
    for key, value in (defaults or {}).items():
        if key in ("allowed_tools", "disallowed_tools", "permission_mode",
                   "setting_sources", "cwd"):
            logger.warning(
                "Ignoring checklist default %r: the permission profile is "
                "not configurable per checklist", key
            )
            continue
        options[key] = value

    requested: Set[str] = set()
    for versions in skills.values():
        for skill in versions.values():
            requested.update(skill.needs)
    granted = {
        rule.split("(")[0] for rule in options["allowed_tools"]
    }
    refused = sorted(requested - granted)
    if refused:
        logger.warning(
            "Skill `needs` requested capabilities the permission profile "
            "does not grant; refusing to widen it: %s", ", ".join(refused)
        )
    return options


def session_cache_key(
    layout: RuntimeLayout,
    *,
    model: str,
    options: Mapping[str, Any],
    skill_set: Optional[SkillSet] = None,
) -> str:
    """Key a cached session by everything that could change its output.

    Deliberately **not** keyed on the observed trace. The trace is an
    observation of the run, so keying on it would mean a session that took a
    different path could never reuse a cached result -- and, worse, that the
    cache would encode our expectation of how discovery should go. The inputs
    are what determine the output: the example, the SkillSet, the model, the
    effective configuration, and the schema the answer must satisfy.

    The skills term is the **SkillSet digest** rather than a raw hash of the
    assembled files, so that a cache entry is attributable to the same
    identity the manifest and `dag.yaml` name. When no SkillSet is supplied
    one is derived from the assembled runtime, which keeps the key honest
    about what the session actually saw even if the caller did not say which
    versions produced it.
    """
    def digest(paths: Iterable[Path]) -> str:
        h = hashlib.sha256()
        for path in sorted(paths):
            h.update(path.name.encode())
            h.update(path.read_bytes())
        return h.hexdigest()

    if skill_set is None:
        skill_set = runtime_skill_set(layout)

    # The permission rules embed the runtime's absolute path, which is a
    # fresh temp directory every run. Hashing it verbatim would give every
    # assembly a unique key and the cache would never hit once -- so the
    # runtime root is replaced by a placeholder, leaving the part that
    # actually constrains behaviour: which tools, scoped to which position
    # inside the runtime.
    root = str(layout.root)
    canonical = json.dumps(
        {k: v for k, v in options.items() if k != "cwd"}, sort_keys=True
    ).replace(root, "<runtime>").replace(
        layout.root.resolve().as_posix(), "<runtime>"
    )

    parts = {
        "example": digest(
            p for p in layout.input_root.rglob("*") if p.is_file()
        ),
        "skill_set": skill_set.digest,
        "model": model,
        "config": hashlib.sha256(canonical.encode()).hexdigest(),
        "leaf_schema": hashlib.sha256(
            layout.schema_path.read_bytes()
        ).hexdigest(),
    }
    return hashlib.sha256(
        json.dumps(parts, sort_keys=True).encode()
    ).hexdigest()


def runtime_skill_set(
    layout: RuntimeLayout, versions: Optional[Mapping[str, str]] = None
) -> SkillSet:
    """Build a SkillSet from what was actually assembled.

    Assembly flattens the version directory away -- the SDK looks for
    ``<name>/SKILL.md`` -- so the version labels have to be supplied by the
    caller that chose them. Content is read from the runtime regardless, so
    a runtime whose files were altered after assembly hashes differently
    than the store it came from, which is the honest answer.
    """
    versions = versions or {}
    entries = []
    for path in sorted(layout.skills_root.glob(f"*/{SKILL_FILENAME}")):
        name = path.parent.name
        entries.append(
            SkillSetEntry(
                name=name,
                version=versions.get(name, "unpinned"),
                content_hash=hashlib.sha256(path.read_bytes()).hexdigest(),
            )
        )
    return SkillSet(entries=tuple(entries))


class ToolAuditLog:
    """Every tool call the session attempted, and what happened to it.

    The permission profile decides what is *allowed*; this records what was
    *attempted*. The two differ in the case that matters — a session trying to
    read outside the runtime is invisible in the profile and obvious here.

    Written to disk on every call, so a session that is interrupted or dies
    still leaves the record of what it tried.
    """

    def __init__(self, path: Path):
        self.path = Path(path)
        self.entries: List[Dict[str, Any]] = []
        #: What the SDK reported about the session at startup, notably the
        #: tool set it actually granted. Human gate 3B asks for exactly this,
        #: diffed against our allowlist, and it is only available from a live
        #: session -- so it is captured here rather than inferred.
        self.session_info: Dict[str, Any] = {}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._flush()

    def record(
        self,
        tool_name: str,
        tool_input: Any,
        tool_use_id: Any,
        decision: str,
        reason: str = "",
    ) -> None:
        self.entries.append(
            {
                "tool": tool_name,
                "input": tool_input,
                "tool_use_id": tool_use_id,
                "decision": decision,
                "reason": reason,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        self._flush()

    def _flush(self) -> None:
        self.path.write_text(
            json.dumps(
                {"session": self.session_info, "calls": self.entries},
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    def note_session(self, info: Mapping[str, Any]) -> None:
        self.session_info = dict(info)
        self._flush()

    @property
    def denied(self) -> List[Dict[str, Any]]:
        return [e for e in self.entries if e["decision"] == "deny"]

    def summary(self) -> str:
        counts: Dict[str, int] = {}
        for entry in self.entries:
            key = f"{entry['tool']} ({entry['decision']})"
            counts[key] = counts.get(key, 0) + 1
        if not counts:
            return "no tool calls"
        return ", ".join(f"{k} x{v}" for k, v in sorted(counts.items()))


def make_pretooluse_hook(
    audit: ToolAuditLog,
    approver: Optional[Any] = None,
    denied_shared_skills: Optional[Set[str]] = None,
):
    """Build the ``PreToolUse`` hook: audit always, approval optionally.

    This is the answer to "how do we get more human input?" recorded at gate
    3B. It has to be a hook rather than a ``canUseTool`` callback, because the
    SDK never calls ``canUseTool`` under ``dontAsk`` and skips it for
    auto-approved tools in every mode -- so the calls most worth reviewing are
    exactly the ones it would never receive. A ``PreToolUse`` hook runs before
    every other step in every mode.

    ``approver`` is a callable ``(tool_name, tool_input) -> (bool, reason)``.
    Omit it for an unattended run: the audit still records everything, which
    is what makes a completed run reviewable after the fact.

    The hook only ever *narrows*: it can deny a call the profile allowed, and
    never allows one the profile denied -- a hook ``allow`` does not override
    a deny rule in the SDK's evaluation order, and relying on it to do so
    would put the containment boundary in two places.
    """

    async def hook(input_data, tool_use_id, context):  # noqa: ANN001
        payload = input_data if isinstance(input_data, Mapping) else {}
        tool_name = payload.get("tool_name") or ""
        tool_input = payload.get("tool_input") or {}
        use_id = payload.get("tool_use_id", tool_use_id)
        denied_names = denied_shared_skills or set()

        decision, reason = "allow", ""
        if (
            tool_name == SKILL_TOOL
            and isinstance(tool_input, Mapping)
            and isinstance(tool_input.get("name"), str)
            and tool_input["name"] in denied_names
        ):
            decision = "deny"
            reason = (
                f"shared skill {tool_input['name']!r} is denied in this run; "
                "reuse the seeded intermediate artifacts"
            )
        elif approver is not None:
            approved, why = approver(tool_name, tool_input)
            if not approved:
                decision = "deny"
                reason = why or "denied by operator"

        audit.record(tool_name, tool_input, use_id, decision, reason)
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": decision,
                "permissionDecisionReason": reason,
            }
        }

    return hook


def interactive_approver(
    prompt_fn: Optional[Any] = None, out: Optional[Any] = None
):
    """An approver that asks a person before each tool call.

    Intended for the handful of supervised examples gate 4C authorises, not
    for a full benchmark: a run of 38 examples would ask hundreds of times.
    Answering ``a`` stops asking for that tool for the rest of the session,
    which keeps a supervised run finishable while still requiring a decision
    the first time each capability is used.
    """
    ask = prompt_fn or input
    stream = out or sys.stdout
    always: Set[str] = set()

    def approve(tool_name: str, tool_input: Any) -> Tuple[bool, str]:
        if tool_name in always:
            return True, ""
        detail = json.dumps(tool_input, ensure_ascii=False)
        if len(detail) > 300:
            detail = detail[:300] + "…"
        print(f"\n  tool: {tool_name}\n  input: {detail}", file=stream)
        answer = (ask("  allow? [y]es / [n]o / [a]lways: ") or "").strip().lower()
        if answer.startswith("a"):
            always.add(tool_name)
            return True, ""
        if answer.startswith("y"):
            return True, ""
        return False, "denied by operator"

    return approve


def _openai_session_client(layout: RuntimeLayout, model: str):
    """Build the OpenAI-backed client for one assembled runtime.

    Every assembled skill's description goes in; its *body* is handed over
    only when the model invokes it, mirroring how the Agent SDK's `Skill`
    tool behaves. Nothing tells the model which skill the entry point needs.
    """
    from soda_mmqc.agentic_openai import RuntimeTools, make_openai_client

    bodies, descriptions = {}, {}
    for path in sorted(layout.skills_root.glob(f"*/{SKILL_FILENAME}")):
        skill = load_skill_file(path)
        bodies[path.parent.name] = skill["body"]
        descriptions[path.parent.name] = skill["description"]

    return make_openai_client(
        bodies,
        descriptions,
        RuntimeTools(layout.root, layout.artifacts_root),
        layout.orientation_path.read_text(encoding="utf-8"),
        model=model,
    )


def load_skill_file(path: Path) -> Dict[str, str]:
    """Read an assembled SKILL.md, which has no version directory above it."""
    text = Path(path).read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if match is None:
        raise ValueError(f"{path}: no YAML frontmatter")
    front = yaml.safe_load(match.group("yaml")) or {}
    return {
        "name": front.get("name", Path(path).parent.name),
        "description": " ".join(str(front.get("description", "")).split()),
        "body": match.group("body").strip(),
    }


def resolve_model(
    checklist_dir: Path, provider: str, model: Optional[str] = None
) -> str:
    """Pick the model: the caller's choice, the checklist default, then ours.

    The checklist default sits in the middle deliberately. A checklist knows
    which model its skills were written and scored against; the runner's
    constant knows nothing except which provider it is talking to.
    """
    if model:
        return model
    return (
        load_model_defaults(checklist_dir).model_for(provider)
        or AGENTIC_DEFAULT_MODEL
    )


def run_check_live(
    checklist: str,
    check: str,
    *,
    output: Optional[Path] = None,
    model: Optional[str] = None,
    examples: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
    keep_runtime: bool = False,
    approve_tools: bool = False,
    provider: str = "openai",
    unpin: Optional[Mapping[str, Optional[Sequence[str]]]] = None,
    seed_intermediates: Optional[Mapping[str, Mapping[str, Any]]] = None,
    shared_skill_denials: Optional[Mapping[str, Sequence[str]]] = None,
) -> Tuple[Path, List[Dict[str, Any]]]:
    """Run one real session per example, for each selected SkillSet.

    One sealed runtime and one session per example, assembled fresh and
    removed afterwards unless ``keep_runtime``. A failure on one example is
    recorded and the run continues: a single malformed output should not cost
    the whole batch, and the failures are as interesting as the successes.

    Versions come from the checklist's ``version-manifest.yaml``. ``unpin``
    varies one or more of those pins, producing one SkillSet per combination;
    each gets its own predictions subdirectory named after what it changed, so
    two versions of one skill can be scored against the same gold with the
    same shared ``eval-manifest.json``. With no ``unpin`` there is exactly one
    SkillSet and the output layout is unchanged.

    Returns:
        ``(predictions directory, per-example report)``. With more than one
        SkillSet the directory is the parent holding one subdirectory per set.
    """
    check_dir = resolve_check_dir(checklist, check)
    checklist_dir = check_dir.parent
    benchmark = _read_json(check_dir / "benchmark.json")
    check_name = benchmark.get("name", check)

    wanted = list(examples) if examples else list(benchmark.get("examples") or [])
    if limit is not None:
        wanted = wanted[:limit]
    if not wanted:
        raise ValueError(f"No examples to run for {check_name}")

    skills = validate_skills(checklist_dir)
    pins = checklist_pins(checklist_dir)
    if pins is None:
        pins = {name: s.version for name, s in select_versions(skills).items()}
    else:
        validate_version_manifest(skills, pins, checklist_dir)

    skill_sets = expand_skill_sets(skills, pins, dict(unpin or {}))
    model = resolve_model(checklist_dir, provider, model)
    defaults = load_model_defaults(checklist_dir).session
    root_dir = Path(output or default_predictions_dir(checklist, check, model))
    approver = interactive_approver() if approve_tools else None

    report: List[Dict[str, Any]] = []
    for skill_set in skill_sets:
        label = skill_set.label(pins)
        # Keyed on the label, never on how many sets there happen to be.
        # `--unpin X --versions v2` expands to exactly one set, and writing
        # that variant into the baseline directory would silently overwrite
        # the pinned run's predictions with a different SkillSet's answers --
        # the one outcome a version comparison must never produce.
        predictions_dir = (
            root_dir if label == "pinned" else root_dir / label
        )
        versions = skill_set.pins
        for relative_source_path in wanted:
            logger.info(
                "Running %s on %s [%s]", check_name, relative_source_path, label
            )
            entry: Dict[str, Any] = {
                "example": relative_source_path,
                "skill_set": skill_set.digest,
                "label": label,
            }
            try:
                with runtime_session(
                    checklist, check, relative_source_path,
                    keep=keep_runtime, pins=versions,
                ) as layout:
                    seeded = dict((seed_intermediates or {}).get(relative_source_path, {}))
                    for name, payload in seeded.items():
                        path = layout.artifacts_root / f"{name}.json"
                        path.write_text(
                            json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8",
                        )
                    options = effective_session_options(
                        layout, skills, defaults=defaults
                    )
                    options["model"] = model
                    denied_shared = set(
                        (shared_skill_denials or {}).get(relative_source_path, ())
                    )
                    client = (
                        _openai_session_client(layout, model)
                        if provider == "openai"
                        else None
                    )
                    session_kwargs: Dict[str, Any] = {
                        "versions": versions,
                        "approver": approver,
                        "options": options,
                        "client": client,
                    }
                    if denied_shared:
                        session_kwargs["denied_shared_skills"] = denied_shared
                    prediction, recorder, audit = asyncio.run(
                        _run_agent_session(
                            layout,
                            **session_kwargs,
                        )
                    )
                    # The file-production contract is gone with the write
                    # tool: nothing the session does touches the filesystem.
                    # What that check protected -- a shared skill that was
                    # declared but never fired -- is answered by the hop
                    # trace below, which reads the session's own tool calls
                    # and needs no artifact to exist.
                    found_intermediates, invalid = validate_intermediates(
                        layout, skills, pins=versions, strict=False
                    )
                    entry["intermediates"] = sorted(found_intermediates)
                    if invalid:
                        raise ValueError(
                            "Session produced invalid intermediate artifact(s): "
                            + "; ".join(invalid)
                        )
                    entry["hops"] = compare_declared_and_observed(
                        checklist_dir, check, recorder.invoked, pins=versions
                    )
                    entry["tools"] = audit.summary()
                    entry["reported_tools"] = audit.session_info.get("tools")
                    _write_prediction(
                        predictions_dir,
                        relative_source_path,
                        prediction,
                        recorder.entries,
                        skill_set,
                    )
                    for name, artifact_path in found_intermediates.items():
                        _copy_sidecar(
                            artifact_path,
                            predictions_dir
                            / relative_source_path
                            / INTERMEDIATES_DIRNAME
                            / f"{name}.json",
                        )
                    _copy_sidecar(
                        audit.path,
                        predictions_dir / relative_source_path
                        / INTERMEDIATES_DIRNAME / TOOL_AUDIT_FILENAME,
                    )
                    entry["status"] = "ok"
            except Exception as exc:  # noqa: BLE001 - one example must not end the run
                logger.error("%s failed: %s", relative_source_path, exc)
                entry["status"] = "failed"
                entry["error"] = str(exc)
            report.append(entry)

    ok = sum(1 for e in report if e["status"] == "ok")
    logger.info(
        "Completed %d/%d session(s) over %d SkillSet(s); predictions in %s",
        ok, len(report), len(skill_sets), root_dir,
    )
    return root_dir, report


def _required_shared_skills(
    check_name: str, selected: Mapping[str, Skill]
) -> Set[str]:
    """Shared skills reachable from `check_name` via declared requirements."""
    entry = selected.get(check_name)
    if entry is None:
        return set()
    pending = list(entry.requires)
    seen: Set[str] = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        skill = selected.get(name)
        if skill is None:
            continue
        seen.add(name)
        pending.extend(skill.requires)
    return seen


def _expand_example_selectors(
    benchmark_examples: Sequence[str], selectors: Optional[Sequence[str]]
) -> Optional[List[str]]:
    """Expand doc-level selectors to concrete benchmark example paths."""
    if not selectors:
        return None
    expanded: List[str] = []
    seen: Set[str] = set()
    for selector in selectors:
        selector = selector.strip()
        if not selector:
            continue
        matched = [
            example
            for example in benchmark_examples
            if example == selector or example.startswith(f"{selector}/")
        ]
        for example in matched:
            if example not in seen:
                seen.add(example)
                expanded.append(example)
    return expanded


def run_checklist_live(
    checklist: str,
    *,
    output: Optional[Path] = None,
    model: Optional[str] = None,
    examples: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
    keep_runtime: bool = False,
    approve_tools: bool = False,
    provider: str = "openai",
    unpin: Optional[Mapping[str, Optional[Sequence[str]]]] = None,
) -> Tuple[Path, List[Dict[str, Any]]]:
    """Run all checks in a checklist, reusing shared intermediates per example."""
    if unpin:
        raise ValueError("--all-checks does not support --unpin")

    checklist_dir = config.CHECKLIST_DIR / checklist
    if not checklist_dir.is_dir():
        raise FileNotFoundError(f"Checklist not found: {checklist_dir}")

    checks = sorted(list_checks(checklist_dir))
    if not checks:
        raise ValueError(f"No checks found in checklist: {checklist}")

    selected = select_versions(validate_skills(checklist_dir), checklist_pins(checklist_dir))
    run_model = resolve_model(checklist_dir, provider, model)
    root_dir = Path(
        output
        or EVALUATION_DIR / checklist / "__all-checks__" / run_model / "predictions"
    )

    cache: Dict[str, Dict[str, Any]] = {}
    denied: Dict[str, Set[str]] = {}
    combined: List[Dict[str, Any]] = []
    shared_by_check = {name: _required_shared_skills(name, selected) for name in checks}
    producers: Dict[str, Set[str]] = {
        name: set(selected[name].produces)
        for name in selected
        if selected[name].produces
    }

    for check in checks:
        benchmark = _read_json(checklist_dir / check / "benchmark.json")
        check_examples = _expand_example_selectors(
            benchmark.get("examples") or [],
            examples,
        )
        check_output = root_dir / check
        _, report = run_check_live(
            checklist,
            check,
            output=check_output,
            model=model,
            examples=check_examples,
            limit=limit,
            keep_runtime=keep_runtime,
            approve_tools=approve_tools,
            provider=provider,
            unpin=unpin,
            seed_intermediates=cache,
            shared_skill_denials={k: sorted(v) for k, v in denied.items()},
        )
        for entry in report:
            item = dict(entry)
            item["check"] = check
            combined.append(item)
            if item.get("status") != "ok":
                continue
            example = item["example"]
            produced = set(item.get("intermediates") or ())
            for skill_name in shared_by_check.get(check, set()):
                artifacts = producers.get(skill_name, set())
                available = sorted(artifacts & produced)
                if not available:
                    continue
                denied.setdefault(example, set()).add(skill_name)
                for artifact_name in available:
                    artifact_path = (
                        check_output
                        / example
                        / INTERMEDIATES_DIRNAME
                        / f"{artifact_name}.json"
                    )
                    if artifact_path.is_file():
                        cache.setdefault(example, {})[artifact_name] = _read_json(
                            artifact_path
                        )
    return root_dir, combined


def _copy_sidecar(source: Path, destination: Path) -> None:
    if source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


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
    run_target = run.add_mutually_exclusive_group(required=True)
    run_target.add_argument("--check", type=str, help="Check to run")
    run_target.add_argument(
        "--all-checks",
        action="store_true",
        help="Run all checks in the checklist (agentic mode)",
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
                if args.all_checks:
                    logger.error("--all-checks is not supported with --mock")
                    return 2
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
                if args.all_checks:
                    if args.unpin:
                        logger.error(
                            "--all-checks does not support --unpin yet"
                        )
                        return 2
                    path, report = run_checklist_live(
                        args.checklist,
                        output=args.output,
                        model=args.model,
                        examples=args.examples,
                        limit=args.limit,
                        keep_runtime=args.keep_runtime,
                        approve_tools=args.approve_tools,
                        provider=args.provider,
                        unpin={name: versions for name in (args.unpin or [])},
                    )
                else:
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
