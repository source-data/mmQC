"""Assembling the sealed runtime for one example, and the session profile.

The runtime is a copy of one example's `content/` -- byte-identical, minus
any nested answer key -- plus exactly one version of every skill, and nothing
else: no evaluation contract, no gold, no sibling example, no link back to
the repository. `_assert_sealed` re-checks that on every assembly, in
production as well as in the tests, because the cost of a leak is a scored
run that quietly saw the answer.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from soda_mmqc import config, logger
from soda_mmqc.config import (
    AGENTIC_AGENT_HOME_SUBDIR,
    AGENTIC_ALLOWED_TOOL_NAMES,
    AGENTIC_ARTIFACTS_SUBDIR,
    AGENTIC_BASE_TOOLS,
    AGENTIC_CLAUDE_TEMPLATE,
    AGENTIC_FORBIDDEN_TOOLS,
    AGENTIC_INPUT_MANIFEST_FILENAME,
    AGENTIC_INPUT_SUBDIR,
    AGENTIC_MAX_BUFFER_BYTES,
    AGENTIC_ORIENTATION_FILENAME,
    AGENTIC_PERMISSION_MODE,
    AGENTIC_RUNTIME_PREFIX,
    AGENTIC_SETTING_SOURCES,
    AGENTIC_SKILLS_SUBDIR,
    EXAMPLES_DIR,
    resolve_agentic_runtime_root,
)
from soda_mmqc.core.examples import EXAMPLE_FACTORY, Example
from soda_mmqc.agentic.pinning import (
    SkillSet,
    SkillSetEntry,
    checklist_pins,
    load_model_defaults,
    validate_version_manifest,
)
from soda_mmqc.agentic.skills import (
    SKILL_FILENAME,
    _read_json,
    Skill,
    resolve_check_dir,
    select_versions,
    validate_skills,
)

__all__ = [
    "RuntimeLayout",
    "assemble_runtime",
    "session_options",
    "effective_session_options",
    "describe_permission_profile",
    "runtime_skill_set",
    "session_cache_key",
    "EXAMPLE_INPUT_SUBDIR",
    "_leaf_schema",
]



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


def _leaf_schema(layout: RuntimeLayout) -> Dict[str, Any]:
    """The JSON Schema the final prediction must satisfy."""
    envelope = _read_json(layout.schema_path)
    return envelope["format"]["schema"]


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

