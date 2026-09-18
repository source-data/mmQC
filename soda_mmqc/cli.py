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

from soda_mmqc import logger
from soda_mmqc.config import (
    AGENTIC_ALLOWED_TOOL_NAMES,
    AGENTIC_ARTIFACTS_SUBDIR,
    AGENTIC_DEFAULT_MODEL,
    AGENTIC_FORBIDDEN_TOOLS,
    AGENTIC_INPUT_SUBDIR,
    AGENTIC_ORIENTATION_FILENAME,
    AGENTIC_PERMISSION_MODE,
    AGENTIC_RUNTIME_PREFIX,
    AGENTIC_SETTING_SOURCES,
    AGENTIC_SKILLSET_WARN_THRESHOLD,
    AGENTIC_SKILLS_SUBDIR,
    CHECKLIST_DIR,
    DEFAULT_MODEL,
    DEFAULT_SENTENCE_TRANSFORMER_MODEL,
    EVALUATION_DIR,
    EXAMPLES_DIR,
    resolve_agentic_runtime_root,
)
from soda_mmqc.core.examples import EXAMPLE_FACTORY
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

#: Name of a skill's instruction file. One per version directory.
SKILL_FILENAME = "SKILL.md"

#: The tool a skill's prose tells the agent to use when calling a sub-skill.
SKILL_TOOL = "Skill"

#: A version directory is named ``v`` followed by digits. Only ``SKILL.md`` is
#: versioned; the evaluation contracts stay at the skill level so that two
#: versions of one skill remain comparable.
_VERSION_DIR = re.compile(r"^v\d+$")

#: Frontmatter is a YAML block delimited by ``---`` lines at the top of the
#: file, in the convention the Agent SDK uses for skills.
_FRONTMATTER = re.compile(r"\A---\r?\n(?P<yaml>.*?)\r?\n---[ \t]*\r?\n?(?P<body>.*)\Z", re.DOTALL)

#: Frontmatter keys that hold a list of names.
_LIST_KEYS = ("requires", "produces", "needs")


def resolve_check_dir(checklist: str, check: str) -> Path:
    """Return the directory of ``check`` within ``checklist``.

    Raises:
        FileNotFoundError: If the checklist or the check directory is absent.
        ValueError: If the directory exists but is not a check, i.e. it does
            not own the evaluation contracts (a shared skill, for instance).
    """
    checklist_dir = CHECKLIST_DIR / checklist
    if not checklist_dir.is_dir():
        raise FileNotFoundError(f"Checklist not found: {checklist_dir}")

    check_dir = checklist_dir / check
    if not check_dir.is_dir():
        known = ", ".join(sorted(list_checks(checklist_dir))) or "none"
        raise FileNotFoundError(
            f"Check not found: {check_dir}. Known checks: {known}"
        )
    if not owns_evaluation_contracts(check_dir):
        raise ValueError(
            f"{check_dir} is not a check: it does not own "
            f"{' and '.join(EVALUATION_CONTRACT_FILES)}. Shared skills sit "
            "beside the checks but cannot be scored."
        )
    return check_dir


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


@dataclass(frozen=True)
class Skill:
    """One version of one skill, as read from a ``SKILL.md`` file.

    ``name`` comes from the frontmatter, never from the directory the file
    sits in. That is deliberate: the hierarchy is carried by skill-to-skill
    calls, not by the filesystem, so moving or renaming a skill directory must
    leave the resolved graph untouched.
    """

    name: str
    version: str
    path: Path
    description: str
    body: str
    requires: Tuple[str, ...] = ()
    produces: Tuple[str, ...] = ()
    needs: Tuple[str, ...] = ()

    @property
    def directory(self) -> Path:
        """Directory holding this version's ``SKILL.md``."""
        return self.path.parent

    @property
    def skill_dir(self) -> Path:
        """Directory holding every version of this skill.

        This is also where the shared, unversioned assets live -- the runtime
        ``schema.json`` and, for a leaf, the evaluation contracts.
        """
        return self.path.parent.parent


def load_skill(path: Path) -> Skill:
    """Read one ``SKILL.md`` file into a :class:`Skill`.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the frontmatter is missing, unparseable, or does not
            carry a usable ``name`` and ``description``; if the body is empty;
            or if the version directory is not named ``vN``. Every message
            names the offending file.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Skill file not found: {path}")

    version = path.parent.name
    if not _VERSION_DIR.match(version):
        raise ValueError(
            f"{path}: a skill version directory must be named 'v' followed by "
            f"digits (v1, v2, ...), got {version!r}"
        )

    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER.match(text)
    if match is None:
        raise ValueError(
            f"{path}: no YAML frontmatter. A SKILL.md must open with a '---' "
            "line, the frontmatter, and a closing '---' line"
        )

    try:
        front = yaml.safe_load(match.group("yaml"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: frontmatter is not valid YAML: {exc}") from exc

    if front is None:
        front = {}
    if not isinstance(front, dict):
        raise ValueError(
            f"{path}: frontmatter must be a mapping, got "
            f"{type(front).__name__}"
        )

    name = _required_string(front, "name", path)
    description = _required_string(front, "description", path)
    body = match.group("body").strip()
    if not body:
        raise ValueError(f"{path}: the skill body is empty")

    lists = {key: _name_list(front, key, path) for key in _LIST_KEYS}
    return Skill(
        name=name,
        version=version,
        path=path,
        description=description,
        body=body,
        **lists,
    )


def _required_string(front: Mapping[str, Any], key: str, path: Path) -> str:
    value = front.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"{path}: frontmatter key {key!r} must be a non-empty string"
        )
    return " ".join(value.split())


def _name_list(front: Mapping[str, Any], key: str, path: Path) -> Tuple[str, ...]:
    value = front.get(key)
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item.strip() for item in value
    ):
        raise ValueError(
            f"{path}: frontmatter key {key!r} must be a list of non-empty "
            "names"
        )
    names = tuple(item.strip() for item in value)
    duplicates = sorted({n for n in names if names.count(n) > 1})
    if duplicates:
        raise ValueError(
            f"{path}: frontmatter key {key!r} lists {', '.join(duplicates)} "
            "more than once"
        )
    return names


def load_skills(checklist_dir: Path) -> Dict[str, Dict[str, Skill]]:
    """Load every skill of a checklist, keyed by skill name and version.

    Discovery walks the checklist directory for ``SKILL.md`` files and takes
    each skill's identity from its frontmatter, so the returned mapping is
    independent of where the directories sit.

    Raises:
        FileNotFoundError: If ``checklist_dir`` is not a directory.
        ValueError: If a skill file is malformed, or if two files declare the
            same name and version.
    """
    checklist_dir = Path(checklist_dir)
    if not checklist_dir.is_dir():
        raise FileNotFoundError(f"Checklist not found: {checklist_dir}")

    skills: Dict[str, Dict[str, Skill]] = {}
    for skill_file in sorted(checklist_dir.rglob(SKILL_FILENAME)):
        skill = load_skill(skill_file)
        versions = skills.setdefault(skill.name, {})
        if skill.version in versions:
            first, second = sorted(
                [versions[skill.version].path, skill_file]
            )
            raise ValueError(
                f"Two files declare skill {skill.name!r} version "
                f"{skill.version!r}: {first} and {second}. A skill's identity "
                "comes from its frontmatter, not its directory, so renaming "
                "one of the directories does not resolve this -- change one "
                "file's `name`, or delete it"
            )
        versions[skill.version] = skill
    return skills


def build_graph(
    skills: Mapping[str, Mapping[str, Skill]]
) -> Dict[str, Set[str]]:
    """Resolve the skill graph, as declared by ``requires``.

    Edges are keyed by skill *name*, unioned over that skill's versions --
    version pinning is Milestone 6's job, and a cycle that exists in any
    version is a cycle worth refusing.
    """
    graph: Dict[str, Set[str]] = {}
    for name, versions in skills.items():
        edges = graph.setdefault(name, set())
        for skill in versions.values():
            edges.update(skill.requires)
    return graph


def find_cycle(graph: Mapping[str, Set[str]]) -> Optional[List[str]]:
    """Return one cycle in ``graph`` as a list of names, or None if acyclic.

    The returned path starts and ends with the same name, so it reads as the
    loop it is.
    """
    visiting: Set[str] = set()
    done: Set[str] = set()
    stack: List[str] = []

    def walk(node: str) -> Optional[List[str]]:
        if node in done:
            return None
        if node in visiting:
            start = stack.index(node)
            return stack[start:] + [node]
        visiting.add(node)
        stack.append(node)
        for neighbour in sorted(graph.get(node, ())):
            cycle = walk(neighbour)
            if cycle is not None:
                return cycle
        stack.pop()
        visiting.discard(node)
        done.add(node)
        return None

    for node in sorted(graph):
        cycle = walk(node)
        if cycle is not None:
            return cycle
    return None


def invoked_skills(skill: Skill, known_names: Sequence[str]) -> Set[str]:
    """Return the known skill names that ``skill``'s prose mentions.

    Prose is what actually executes -- a sentence telling the agent to call
    another skill with the ``Skill`` tool -- so this is the observed half of
    the graph, against which the declared ``requires`` is checked. A skill
    mentioning its own name does not count as invoking itself.
    """
    return {
        name
        for name in known_names
        if name != skill.name and _mentions(skill.body, name)
    }


def _mentions(text: str, name: str) -> bool:
    # Hyphens are part of a skill name, so a plain word boundary would match
    # 'identify-panels' inside 'identify-panels-v2'.
    pattern = re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")
    return pattern.search(text) is not None


#: A markdown list item starts a new prose block even without a blank line
#: before it, so a leaf that lists its hops as bullets is checked per hop.
_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _prose_blocks(body: str) -> List[str]:
    """Split a skill body into the units a sub-skill call has to fit inside.

    A block is a paragraph, except that each markdown list item is its own
    block. Line wrapping inside a block is ignored, so an instruction that
    wraps across two source lines is still one block.

    The unit matters because "does the prose actually ask the agent to call
    this skill?" is a question about one requirement, not about the file. A
    leaf with two requirements must instruct the agent twice; a single
    ``Skill`` mention somewhere else in the file does not vouch for both.
    """
    blocks: List[str] = []
    for paragraph in re.split(r"\n\s*\n", body):
        current: List[str] = []
        for line in paragraph.splitlines():
            if _LIST_ITEM.match(line) and current:
                blocks.append(" ".join(current))
                current = [line]
            else:
                current.append(line)
        if current:
            blocks.append(" ".join(current))
    return [block for block in blocks if block.strip()]


def _without_self_edges(graph: Mapping[str, Set[str]]) -> Dict[str, Set[str]]:
    # A skill that requires itself is a cycle, but it already gets its own,
    # clearer message. Reporting it twice makes the shorter message harder to
    # find, so cycle detection ignores self-edges.
    return {node: edges - {node} for node, edges in graph.items()}


def validate_skills(checklist_dir: Path) -> Dict[str, Dict[str, Skill]]:
    """Load a checklist's skills and check that its graph is consistent.

    Four things are asserted, and every failure names the offending file:

    * every name in ``requires`` is a skill of this checklist, and is not the
      skill itself;
    * the graph is acyclic;
    * every name in ``requires`` also appears in the prose body, in a block
      that also tells the agent to use the ``Skill`` tool -- a declared edge
      that no sentence asks for would never fire at runtime, and a bare mention
      is not a call. The check is per requirement, so a leaf with two
      requirements has to instruct the agent twice;
    * no skill mentioned in the prose is missing from ``requires`` -- an
      undeclared edge is invisible to the DAG documentation.

    Returns:
        The loaded skills, so a caller can validate and use in one step.

    Raises:
        ValueError: If any check fails. All problems are reported at once.
    """
    skills = load_skills(checklist_dir)
    known = sorted(skills)
    problems: List[str] = []

    for name in known:
        for version in sorted(skills[name]):
            skill = skills[name][version]
            declared = set(skill.requires)
            blocks = _prose_blocks(skill.body)

            for requirement in skill.requires:
                if requirement == name:
                    problems.append(
                        f"{skill.path}: {name!r} requires itself"
                    )
                    continue
                if requirement not in skills:
                    problems.append(
                        f"{skill.path}: requires unknown skill "
                        f"{requirement!r}; known skills are "
                        f"{', '.join(known)}"
                    )
                    continue

                asking = [
                    block for block in blocks if _mentions(block, requirement)
                ]
                if not asking:
                    problems.append(
                        f"{skill.path}: declares requires: {requirement!r} but "
                        "never asks for it in the prose; frontmatter documents "
                        "the graph, prose runs it"
                    )
                elif not any(
                    _mentions(block, SKILL_TOOL) for block in asking
                ):
                    problems.append(
                        f"{skill.path}: mentions {requirement!r} but never "
                        f"tells the agent to use the {SKILL_TOOL!r} tool on "
                        "it; a bare mention is not a call"
                    )

            for invoked in sorted(invoked_skills(skill, known) - declared):
                problems.append(
                    f"{skill.path}: prose invokes {invoked!r} but it is "
                    "missing from requires"
                )

    cycle = find_cycle(_without_self_edges(build_graph(skills)))
    if cycle is not None:
        problems.append(
            f"{checklist_dir}: the skill graph has a cycle: "
            f"{' -> '.join(cycle)}"
        )

    if problems:
        raise ValueError(
            f"{len(problems)} problem(s) in the skills of {checklist_dir}:\n"
            + "\n".join(f"  - {problem}" for problem in problems)
        )
    return skills


# ---------------------------------------------------------------------------
# Version pinning: the manifest, the SkillSet, and expansion
# ---------------------------------------------------------------------------
#
# Up to here a version is chosen by convention -- the highest ``vN``. That is
# fine for a pilot and wrong for anything whose results get attributed to a
# name. `version-manifest.yaml` replaces the convention with a file someone
# signed off on, and the SkillSet is what that file resolves to: the exact
# set of skill versions a run saw, hashed, so two runs can be compared or
# told apart without trusting a directory listing.

#: Hand-maintained. Pins exactly one version of every skill in the checklist.
VERSION_MANIFEST_FILENAME = "version-manifest.yaml"

#: Hand-maintained. Provider-neutral model and session defaults.
MODEL_DEFAULTS_FILENAME = "model-defaults.yaml"

#: Generated. The machine-readable picture of the graph.
DAG_FILENAME = "dag.yaml"

#: Generated. The same picture, for a person.
GENERATED_README_FILENAME = "README.md"

#: Session option keys `model-defaults.yaml` may not set. These are the
#: containment boundary, which is a property of the runtime rather than of a
#: checklist; letting a checklist file move it would make the Milestone 3
#: profile advisory.
_PROFILE_OWNED_OPTIONS = (
    "allowed_tools",
    "cwd",
    "disallowed_tools",
    "permission_mode",
    "setting_sources",
    "skills",
)


@dataclass(frozen=True)
class SkillSetEntry:
    """One skill as it participates in a SkillSet."""

    name: str
    version: str
    content_hash: str


@dataclass(frozen=True)
class SkillSet:
    """The exact set of skill versions one run is built from.

    Identity is the digest, which covers *content*, not just version labels.
    A version number is a claim about content; the hash is the content. Both
    are carried so that a digest mismatch can be explained ("``shared`` moved
    from v1 to v2") rather than merely reported.
    """

    entries: Tuple[SkillSetEntry, ...]

    @property
    def pins(self) -> Dict[str, str]:
        return {entry.name: entry.version for entry in self.entries}

    @property
    def digest(self) -> str:
        """SHA-256 over the canonical JSON of the sorted entries."""
        canonical = json.dumps(
            [
                {
                    "name": e.name,
                    "version": e.version,
                    "content_hash": e.content_hash,
                }
                for e in sorted(self.entries, key=lambda e: e.name)
            ],
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode()).hexdigest()

    def label(self, baseline: Mapping[str, str]) -> str:
        """Name this set by what it changes relative to ``baseline``.

        Used for the per-set output directory of an unpinned comparison: the
        interesting thing about a set is never all fifteen pins, it is the
        one that moved.
        """
        differing = sorted(
            f"{e.name}@{e.version}"
            for e in self.entries
            if baseline.get(e.name) != e.version
        )
        return "-".join(differing) if differing else "pinned"


def skill_content_hash(skill: Skill) -> str:
    """SHA-256 of a skill version's ``SKILL.md`` bytes."""
    return hashlib.sha256(skill.path.read_bytes()).hexdigest()


def resolve_skill_set(
    skills: Mapping[str, Mapping[str, Skill]],
    pins: Mapping[str, str],
) -> SkillSet:
    """Resolve pins to the SkillSet they name.

    Raises:
        KeyError: If a pin names a skill or version that is not present.
            Callers that want a readable message validate first.
    """
    return SkillSet(
        entries=tuple(
            SkillSetEntry(
                name=name,
                version=pins[name],
                content_hash=skill_content_hash(skills[name][pins[name]]),
            )
            for name in sorted(pins)
        )
    )


def load_version_manifest(checklist_dir: Path) -> Dict[str, str]:
    """Read ``version-manifest.yaml`` into ``{skill: version}``.

    Completeness is checked separately, by
    :func:`validate_version_manifest`, because that needs the inventory and
    this only needs the file.

    Raises:
        FileNotFoundError: If the manifest is absent.
        ValueError: If it is unparseable, misshapen, or declares a different
            checklist than the directory it sits in.
    """
    checklist_dir = Path(checklist_dir)
    path = checklist_dir / VERSION_MANIFEST_FILENAME
    if not path.is_file():
        try:
            inventory = ", ".join(sorted(load_skills(checklist_dir)))
        except (FileNotFoundError, ValueError):
            inventory = ""
        raise FileNotFoundError(
            f"{checklist_dir}: no {VERSION_MANIFEST_FILENAME}. Every checklist "
            "run agentically needs one, pinning exactly one version of every "
            "skill, because it is the identity results are attributed to. "
            f"Create {path} with a 'skills:' mapping of 'skill-name: vN'"
            + (f" covering: {inventory}" if inventory else "")
        )

    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: not valid YAML: {exc}") from exc

    if not isinstance(document, dict):
        raise ValueError(
            f"{path}: must be a mapping with a 'skills' key, got "
            f"{type(document).__name__}"
        )

    declared = document.get("checklist")
    if declared is not None and declared != checklist_dir.name:
        raise ValueError(
            f"{path}: declares checklist {declared!r} but sits in "
            f"{checklist_dir.name!r}; this manifest belongs somewhere else"
        )

    pins = document.get("skills")
    if not isinstance(pins, dict) or not pins:
        raise ValueError(
            f"{path}: key 'skills' must be a non-empty mapping of skill name "
            "to version"
        )
    bad = sorted(
        str(name) for name, version in pins.items()
        if not isinstance(name, str) or not isinstance(version, str)
    )
    if bad:
        raise ValueError(
            f"{path}: every pin must be 'skill-name: vN'; offending: "
            f"{', '.join(bad)}"
        )
    return {str(name): str(version) for name, version in pins.items()}


def validate_version_manifest(
    skills: Mapping[str, Mapping[str, Skill]],
    pins: Mapping[str, str],
    checklist_dir: Path,
) -> None:
    """Check a manifest against the checklist's inventory.

    Three failures, reported together:

    * a skill with no pin -- a partial manifest is worse than none, because
      it looks authoritative while the unpinned half still drifts;
    * a pin naming a skill that is not there -- usually a rename or a
      deletion the manifest did not follow;
    * a pin naming a version that does not exist.

    Validation is against the **inventory**, not against a reachable closure.
    A skill nothing calls today still has to be pinned: discovery is the
    agent's job and today's graph is not a promise about tomorrow's session.

    Raises:
        ValueError: If any of the three fails.
    """
    path = Path(checklist_dir) / VERSION_MANIFEST_FILENAME
    problems: List[str] = []

    for name in sorted(set(skills) - set(pins)):
        problems.append(
            f"{name!r} has no pin; every skill of the checklist must be "
            f"pinned (available: {', '.join(sorted(skills[name]))})"
        )
    for name in sorted(set(pins) - set(skills)):
        problems.append(
            f"{name!r} is pinned but is not a skill of this checklist; it was "
            "renamed, moved or removed and the manifest did not follow"
        )
    for name in sorted(set(pins) & set(skills)):
        if pins[name] not in skills[name]:
            problems.append(
                f"{name!r} is pinned to {pins[name]!r}, which does not exist; "
                f"available: {', '.join(sorted(skills[name]))}"
            )

    if problems:
        raise ValueError(
            f"{path}: {len(problems)} problem(s):\n"
            + "\n".join(f"  - {problem}" for problem in problems)
        )


def checklist_pins(checklist_dir: Path) -> Optional[Dict[str, str]]:
    """Return the manifest pins, or ``None`` when there is no manifest.

    Falling back is deliberate but never silent: the synthetic checklists the
    tests build have no manifest and should not need one, while a production
    checklist losing its manifest must be visible in the log of the run that
    used the fallback -- not only in a `graph` invocation nobody ran.
    """
    try:
        return load_version_manifest(checklist_dir)
    except FileNotFoundError:
        logger.warning(
            "%s has no %s; falling back to the highest version of each skill. "
            "That is a convention, not a pin: results from this run are not "
            "attributable to a reviewed SkillSet.",
            Path(checklist_dir).name, VERSION_MANIFEST_FILENAME,
        )
        return None


@dataclass(frozen=True)
class ModelDefaults:
    """Provider-neutral defaults for a checklist.

    ``models`` is keyed by provider so that the file names *which* model each
    runtime should use without the file itself taking a side; ``session``
    holds the provider-neutral knobs (turn ceilings and the like) that
    :func:`effective_session_options` folds in.
    """

    models: Mapping[str, str] = dataclasses.field(default_factory=dict)
    session: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def model_for(self, provider: str) -> Optional[str]:
        return self.models.get(provider)


def load_model_defaults(checklist_dir: Path) -> ModelDefaults:
    """Read ``model-defaults.yaml``; an absent file means no defaults.

    Unlike the version manifest, absence is legitimate: a checklist that is
    happy with the runner's defaults has nothing to say here.

    Raises:
        ValueError: If the file is unparseable, misshapen, or tries to set a
            session option the permission profile owns.
    """
    path = Path(checklist_dir) / MODEL_DEFAULTS_FILENAME
    if not path.is_file():
        return ModelDefaults()

    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"{path}: not valid YAML: {exc}") from exc
    if document is None:
        return ModelDefaults()
    if not isinstance(document, dict):
        raise ValueError(
            f"{path}: must be a mapping, got {type(document).__name__}"
        )

    models = document.get("models") or {}
    if not isinstance(models, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in models.items()
    ):
        raise ValueError(
            f"{path}: key 'models' must map a provider name to a model name, "
            "e.g. `openai: gpt-5-mini`"
        )

    session = document.get("session") or {}
    if not isinstance(session, dict):
        raise ValueError(
            f"{path}: key 'session' must be a mapping of option name to value"
        )
    owned = sorted(set(session) & set(_PROFILE_OWNED_OPTIONS))
    if owned:
        raise ValueError(
            f"{path}: may not set {', '.join(owned)}. The permission profile "
            "is a property of the sealed runtime, not of a checklist; "
            "widening it is a human gate, not a config edit"
        )
    return ModelDefaults(models=dict(models), session=dict(session))


def expand_skill_sets(
    skills: Mapping[str, Mapping[str, Skill]],
    pins: Mapping[str, str],
    unpin: Mapping[str, Optional[Sequence[str]]],
    *,
    warn_above: int = AGENTIC_SKILLSET_WARN_THRESHOLD,
) -> List[SkillSet]:
    """Expand the manifest into one SkillSet per version combination.

    Every skill not named in ``unpin`` keeps its manifest pin, so a
    comparison varies only what it says it varies. ``unpin`` maps a skill
    name to the versions to try, or ``None`` for all of them.

    Multiple unpinned skills are permitted -- the product of two skills'
    versions is a legitimate thing to want -- but the result is a session
    count multiplied by the number of examples, so crossing ``warn_above``
    says so rather than refusing. Refusing would be the runner making a
    spending decision that is the operator's.

    Raises:
        ValueError: If ``unpin`` names an unknown skill or version.
    """
    unknown = sorted(set(unpin) - set(skills))
    if unknown:
        raise ValueError(
            f"Cannot unpin {', '.join(unknown)}: not a skill of this "
            f"checklist. Known skills: {', '.join(sorted(skills))}"
        )

    choices: List[List[Tuple[str, str]]] = []
    for name in sorted(skills):
        if name in unpin:
            wanted = unpin[name]
            available = sorted(skills[name], key=lambda v: int(v[1:]))
            if wanted is None:
                versions = available
            else:
                missing = sorted(set(wanted) - set(available))
                if missing:
                    raise ValueError(
                        f"Cannot unpin {name!r} to {', '.join(missing)}: no "
                        f"such version. Available: {', '.join(available)}"
                    )
                versions = [v for v in available if v in set(wanted)]
        else:
            versions = [pins[name]]
        choices.append([(name, version) for version in versions])

    sets: List[SkillSet] = []
    for combination in itertools.product(*choices):
        sets.append(resolve_skill_set(skills, dict(combination)))

    if warn_above is not None and len(sets) > warn_above:
        logger.warning(
            "This expansion is %d SkillSets (threshold %d); every example "
            "will be run %d times. Narrow it with --versions if that is not "
            "what you meant.",
            len(sets), warn_above, len(sets),
        )
    return sets


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
    checklist_dir = CHECKLIST_DIR / checklist
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
    example: str


def select_versions(
    skills: Mapping[str, Mapping[str, Skill]],
    pins: Optional[Mapping[str, str]] = None,
) -> Dict[str, Skill]:
    """Choose exactly one version of each skill.

    Version *pinning* by manifest is Milestone 6. Until then the default is
    the highest ``vN``, which keeps the runtime deterministic without
    pretending to be the manifest.

    Raises:
        ValueError: If a pin names a skill or a version that does not exist.
    """
    pins = dict(pins or {})
    unknown = sorted(set(pins) - set(skills))
    if unknown:
        raise ValueError(
            f"Pinned skill(s) not in the checklist: {', '.join(unknown)}"
        )

    selected: Dict[str, Skill] = {}
    for name, versions in skills.items():
        if name in pins:
            version = pins[name]
            if version not in versions:
                raise ValueError(
                    f"Pinned version {version!r} of {name!r} does not exist; "
                    f"available: {', '.join(sorted(versions))}"
                )
        else:
            version = max(versions, key=lambda v: int(v[1:]))
        selected[name] = versions[version]
    return selected


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


def _render_orientation(layout: RuntimeLayout) -> str:
    """Generate the per-run orientation file.

    It names the entry point and the roots, and **nothing else**. It does not
    name the entry point's dependencies, does not order them, and does not
    describe the graph: discovering that is the agent's job, and stating it
    here would make the Milestone 4 trace a measurement of our own control
    flow rather than of the prose.
    """
    return f"""# This run

You are checking one figure against one quality-control check.

- **Entry point:** the `{layout.entry_point}` skill. Start there.
- **Figure inputs:** `{AGENTIC_INPUT_SUBDIR}/` — the caption and image for
  this figure, and nothing else.
- **Write results to:** `{AGENTIC_ARTIFACTS_SUBDIR}/` — the only writable
  location. Put the final answer in
  `{AGENTIC_ARTIFACTS_SUBDIR}/{PREDICTION_FILENAME}`.
- **Final output schema:** `{layout.schema_path.relative_to(layout.root)}`.
  The answer must conform to it exactly.

Other skills are available to you. Read their descriptions and use the
`{SKILL_TOOL}` tool to call whichever the work needs.
"""


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

        shutil.copytree(input_dir, staging / AGENTIC_INPUT_SUBDIR, symlinks=False)
        (staging / AGENTIC_ARTIFACTS_SUBDIR).mkdir()

        layout = RuntimeLayout(
            root=root,
            skills_root=root / AGENTIC_SKILLS_SUBDIR,
            input_root=root / AGENTIC_INPUT_SUBDIR,
            artifacts_root=root / AGENTIC_ARTIFACTS_SUBDIR,
            orientation_path=root / AGENTIC_ORIENTATION_FILENAME,
            entry_point=check,
            schema_path=root / AGENTIC_SKILLS_SUBDIR / check / "schema.json",
            example=example,
        )
        (staging / AGENTIC_ORIENTATION_FILENAME).write_text(
            _render_orientation(layout), encoding="utf-8"
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
        "allowed_tools": [
            f"Read({_abs_rule_path(layout.root)})",
            f"Edit({_abs_rule_path(layout.artifacts_root)})",
            "Skill",
        ],
        "disallowed_tools": sorted(AGENTIC_FORBIDDEN_TOOLS),
        "permission_mode": AGENTIC_PERMISSION_MODE,
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


async def _default_client(prompt: str, options: Mapping[str, Any]):
    """Adapter over the Agent SDK's ``query()``.

    Isolated behind one function so every test can substitute a fake and the
    SDK import stays lazy -- importing it costs a ~200 MB bundled binary's
    worth of path resolution, and a credential-free ``--mock`` run must not
    need it at all.
    """
    from claude_agent_sdk import ClaudeAgentOptions, HookMatcher, query

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

    async for message in query(
        prompt=prompt, options=ClaudeAgentOptions(**payload)
    ):
        yield message


def _session_prompt(layout: RuntimeLayout) -> str:
    """The request handed to the session.

    It names the entry point and points at the orientation file. It does
    **not** name the entry point's dependencies or order them: reaching them
    is the agent's job, and supplying a closure here would make the trace a
    measurement of this string rather than of the skills' prose.
    """
    return (
        f"Read {AGENTIC_ORIENTATION_FILENAME} and follow it. Apply the "
        f"`{layout.entry_point}` check to the figure in "
        f"{AGENTIC_INPUT_SUBDIR}/, and write the result to "
        f"{AGENTIC_ARTIFACTS_SUBDIR}/{PREDICTION_FILENAME}."
    )


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
        "PreToolUse": [make_pretooluse_hook(audit, approver)]
    }

    async for message in run(_session_prompt(layout), options):
        info = _extract_session_info(message)
        if info:
            audit.note_session(info)
        for tool_name, tool_input, tool_use_id in _extract_tool_calls(message):
            recorder.record(tool_name, tool_input, tool_use_id)

    output_path = layout.artifacts_root / PREDICTION_FILENAME
    if not output_path.is_file():
        raise ValueError(
            f"The session wrote no {PREDICTION_FILENAME} to "
            f"{layout.artifacts_root}"
        )
    prediction = _read_json(output_path)
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

        decision, reason = "allow", ""
        if approver is not None:
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
                    options = effective_session_options(
                        layout, skills, defaults=defaults
                    )
                    options["model"] = model
                    client = (
                        _openai_session_client(layout, model)
                        if provider == "openai"
                        else None
                    )
                    prediction, recorder, audit = asyncio.run(
                        _run_agent_session(
                            layout,
                            versions=versions,
                            approver=approver,
                            options=options,
                            client=client,
                        )
                    )
                    entry["intermediates"], invalid = validate_intermediates(
                        layout, skills, pins=versions, strict=False
                    )
                    entry["intermediates"] = sorted(entry["intermediates"])
                    if invalid:
                        entry["invalid_intermediates"] = invalid
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
    run.add_argument("--check", type=str, required=True, help="Check to run")
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
