"""Assembling the sealed runtime for one example, and the session profile.

The runtime is a copy of one example's content -- byte-identical, minus
whatever the caller excludes -- plus exactly one version of every skill, and
nothing else: no evaluation contract, no gold, no sibling example, no link
back to the repository. `_assert_sealed` re-checks that on every assembly, in
production as well as in the tests, because the cost of a leak is a scored
run that quietly saw the answer.

Assembly knows nothing about where examples are stored or what kind they
are. The caller states the content as an :class:`ExampleContent`: mmQC's
benchmark from its example store, an application from its own data.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import (
    Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple,
)

from mmqc_utils.agentic.pinning import (
    SkillSet,
    SkillSetEntry,
    checklist_pins,
    validate_version_manifest,
)
from mmqc_utils.agentic.skills import (
    SKILL_FILENAME,
    _read_json,
    Skill,
    call_closure,
    select_versions,
    validate_skills,
)

__all__ = [
    "ExampleContent",
    "RuntimeLayout",
    "assemble_runtime",
    "session_options",
    "effective_session_options",
    "describe_permission_profile",
    "runtime_skill_set",
    "session_cache_key",
    "ASSEMBLY_CLOSURE",
    "ASSEMBLY_ALL",
    "_leaf_schema",
]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# The runtime's layout and the session's permission profile
# ---------------------------------------------------------------------------
#
# Fixed by the harness, not configurable by a caller: the containment
# boundary is a property of the sealed runtime, as `model-defaults.yaml`'s
# loader already insists for checklists.

#: Directory name prefix of each runtime, under the runtime parent.
AGENTIC_RUNTIME_PREFIX = "soda-mmqc-agentic-"

#: Where the SDK expects to find skills, relative to the runtime root.
AGENTIC_SKILLS_SUBDIR = Path(".claude") / "skills"

#: Where the session writes intermediate artifacts and the final prediction,
#: relative to the runtime root. The only writable location in the profile.
AGENTIC_ARTIFACTS_SUBDIR = Path("artifacts")

#: Where the current example's inputs are copied, relative to the runtime root.
AGENTIC_INPUT_SUBDIR = Path("input")

#: `CLAUDE_CONFIG_DIR` for the session, inside the runtime.
#:
#: Without it the session writes its transcript to
#: `~/.claude/projects/<slugified-cwd>/` -- outside the runtime, surviving
#: teardown, and holding the gold-derived reasoning the containment exists to
#: keep in. Redirecting it also folds the transcript into the same artifact as
#: the skills and the staged example, so `--keep-runtime` preserves what the
#: session actually thought.
AGENTIC_AGENT_HOME_SUBDIR = Path("agent-home")

#: The base set of built-in tools the session *has*, as opposed to the ones it
#: may use without prompting.
#:
#: `tools` and `allowed_tools` are different mechanisms and the distinction
#: cost this project real containment. The SDK: `tools` is "the base set of
#: available built-in tools"; `allowed_tools` is "tool names that are
#: auto-allowed without prompting". Naming three tools in `allowed_tools`
#: left roughly twenty in the model's context, and the profile then had to
#: enumerate every dangerous one by name -- a list that grew on 2026-09-14
#: after a live session reported what it actually had, missed
#: `ShareOnboardingGuide` until 2026-09-19, and left `Write` reachable but
#: unscoped, so a skill told to write `artifacts/panels.json` could equally
#: have overwritten its own `SKILL.md`.
#:
#: Naming what the session may have turns "enumerate everything dangerous"
#: into "enumerate what is needed", which is a list the checks can justify:
#: Skill to reach the DAG. That is all.
#:
#: **The session writes nothing.** A check observes an example; it does not
#: change one. The final answer is a structured result the runner serialises,
#: so no file needs writing to deliver it, and the only remaining reason to
#: write was to hand an intermediate to a later check -- which is a channel
#: between runs that nothing bounds. "Only `panels.json`" is a convention,
#: not a constraint: a session with a write tool can put anything anywhere it
#: is allowed to write, and a later check picking that up would be an
#: interaction nobody declared.
#:
#: Not a permanent position. Whether skills should exchange artefacts on disk
#: is a real design question and deserves an experiment of its own, comparing
#: arms that do and do not. Starting without means the comparison has a
#: baseline; starting with means every arm already contains the thing under
#: test.
#:
#: No Glob either: the manifest names every staged file, and searching is not
#: the agent's job. The deny list below stays as defence in depth over a much
#: smaller surface.
AGENTIC_BASE_TOOLS = ("Skill",)

#: Ceiling for the SDK's newline-delimited JSON reader.
#:
#: The SDK reads the CLI's stream with a 1 MB default buffer, and a figure the
#: session opens arrives base64-encoded inside a single JSON message. Reading
#: one overflows that buffer and kills the session with a decode error rather
#: than anything that names an image. Nothing hit this until the harness began
#: naming the staged figure: before that the agent guessed filenames, never
#: opened one, and answered from the caption alone.
#:
#: A ceiling, not an allocation -- nothing is reserved.
AGENTIC_MAX_BUFFER_BYTES = 64 * 1024 * 1024

#: The generated per-run orientation file, relative to the runtime root.
#: The runtime's project instructions. `CLAUDE.md` rather than a bespoke
#: orientation file: the SDK loads it automatically when `setting_sources`
#: includes "project" (which it does), so the session starts with the layout
#: already in context instead of spending its first turn reading a file. It is
#: static -- identical for every run -- and everything per-run lives in the
#: manifest below.
AGENTIC_ORIENTATION_FILENAME = "CLAUDE.md"

#: Template copied verbatim into each runtime as `CLAUDE.md`. It lives
#: beside the harness rather than under `data/` because it is what dictates
#: the agent's general behaviour, not a data asset a checklist owns.
AGENTIC_CLAUDE_TEMPLATE = Path(__file__).resolve().parent / "CLAUDE.md"

#: Per-run manifest naming exactly what the harness staged. Machine-readable
#: on purpose: which files exist is data, not prose, and the agent has no way
#: to discover them otherwise.
AGENTIC_INPUT_MANIFEST_FILENAME = "inputs.json"

#: Setting sources passed to the SDK session.
#:
#: **"user" is deliberately absent.** It is what loads `~/.claude/skills/`,
#: which has nothing to do with this repository and would put whatever the
#: operator happens to have installed into a scored run -- silently, and
#: differently on every machine. Only "project" is used, and because the
#: runtime root is outside any repository, that resolves to exactly the
#: skills assembled under the runtime root.
#:
#: Widening this is a containment change and needs the same scrutiny as
#: widening the tool allowlist.
AGENTIC_SETTING_SOURCES = ("project",)

# ---------------------------------------------------------------------------
# Agentic permission profile
# ---------------------------------------------------------------------------
#
# Deny by default. The session may do exactly one thing: invoke a skill. It has
# no file tools -- the example's content travels with the request, and the
# runner serialises the structured result -- so nothing it does touches the
# filesystem.
#
# Three facts from the Agent SDK's permission documentation shape this, and
# each one invalidates an obvious-looking construction:
#
# 1. `allowed_tools` is NOT an allowlist. It is a list of *auto-approvals*.
#    "Any other tool not listed in allowed_tools is still available to Claude,
#    and a call to it that needs approval falls through to the permission mode
#    and canUseTool." So listing one tool does not remove the rest.
#
# 2. `permission_mode="dontAsk"` is what turns it into one: "Any call that
#    would otherwise prompt is denied [...] canUseTool is never called." The
#    documentation names `allowed_tools` + `dontAsk` as *the* locked-down
#    pairing. `default` -- what this profile used first -- leaves unlisted
#    tools falling through to a callback that does not exist.
#
# 3. Even under `dontAsk`, some calls "need no approval" and run regardless:
#    read-only shell commands, file reads inside the working directory, and
#    "tools like Agent that don't ask before running". The only way to put a
#    tool out of reach is a bare name in `disallowed_tools`, which removes it
#    from the model's context entirely. That is why the denials below are not
#    redundant with the allowlist -- for `Agent` in particular they are the
#    only thing that works.

#: Tool names the session may use. The options actually passed to the SDK are
#: built per-runtime by session_options().
#:
#: If a file tool ever comes back, scope writes with `Edit(...)`, never
#: `Write(...)`: "Edit(path) rules govern all built-in tools that write files,
#: including Write and NotebookEdit; a Write(path) rule is never matched by the
#: file permission checks." A scoped `Write(...)` rule would silently match
#: nothing.
AGENTIC_ALLOWED_TOOL_NAMES = ("Skill",)

#: Tools removed from the model's context entirely, each for a specific
#: reason. Bare names are required: a scoped rule leaves the tool available.
AGENTIC_FORBIDDEN_TOOLS = {
    # Shell and code execution: would let the session leave the runtime
    # directory entirely, making every other control cosmetic. Note that
    # read-only shell commands are auto-approved even under dontAsk, so the
    # bare-name denial is the only thing that actually removes Bash.
    "Bash": "shell access escapes the sealed runtime",
    "BashOutput": "shell access escapes the sealed runtime",
    "KillShell": "shell access escapes the sealed runtime",
    "NotebookEdit": "executes code",
    # Subagents: a spawned agent negotiates its own context and permissions,
    # which reopens containment from another direction, and its skill calls
    # do not appear in this session's trace -- so the per-example record of
    # which skills actually fired would be incomplete. The SDK documents
    # `Agent` as running without asking, so only a bare-name denial stops it.
    "Task": "subagents reopen containment and break the Skill trace",
    "Agent": "subagents reopen containment and break the Skill trace",
    # Network: nothing in a figure check needs the internet, and a fetch is
    # both an exfiltration path for gold-derived content and a source of
    # irreproducibility between runs.
    "WebFetch": "no network capability is justified by any skill's needs",
    "WebSearch": "no network capability is justified by any skill's needs",
    # --- Added 2026-09-14 after observing the SDK's *reported* tool set ---
    # The first live session reported 20 tools where this profile names 3.
    # `allowed_tools` auto-approves; it does not remove. Everything below was
    # present in the model's context and none of it was considered when the
    # profile was written -- which is precisely why gate 3B asks for the
    # reported set rather than trusting the allowlist.
    #
    # Egress and persistence. These are the serious ones: a session that can
    # message, notify or schedule can move gold-derived content out of the
    # runtime and can act after the run is over.
    "SendMessage": "egress path out of the sealed runtime",
    # Observed in the reported tool set on 2026-09-19 and missing from this
    # list: it uploads a local file and returns a shareable link, which is an
    # exfiltration path for gold-derived content exactly like the three below.
    "ShareOnboardingGuide": "egress path out of the sealed runtime",
    "PushNotification": "egress path out of the sealed runtime",
    "ScheduleWakeup": "would let the session act after the run ends",
    "CronCreate": "would let the session act after the run ends",
    "CronDelete": "scheduling surface, unused by any check",
    "CronList": "scheduling surface, unused by any check",
    "Monitor": "background observation, unused by any check",
    "Workflow": "orchestration surface, unused by any check",
    # Filesystem navigation beyond the runtime.
    "EnterWorktree": "moves the session out of the sealed runtime",
    "ExitWorktree": "moves the session out of the sealed runtime",
    # Discovery surfaces: the content arrives in the request, so there is
    # nothing to search for.
    "Glob": "no file tools: the content arrives in the request",
    "Grep": "no file tools: the content arrives in the request",
    "ToolSearch": "tool discovery, unused by any check",
    "ListAgents": "agent enumeration; subagents are already denied",
    "DesignSync": "unused by any check",
    "ReportFindings": "unused by any check",
}

#: Permission mode. `dontAsk` denies anything that would otherwise prompt,
#: which is what makes the scoped allowlist total. The runtime is unattended,
#: so there is no human to prompt anyway -- and `default` would leave unlisted
#: tools resolving through a `canUseTool` callback that is not supplied.
#:
#: Consequence worth knowing: under `dontAsk` the SDK never calls
#: `canUseTool`, so per-call human approval cannot be layered on top of this
#: mode. Interactive review has to come from a `PreToolUse` hook, which runs
#: before every other step in every mode. See the milestone 3 results doc.
AGENTIC_PERMISSION_MODE = "dontAsk"


#: Assemble the entry point and what its pinned prose reaches, transitively.
#: The default: a session holds one copy of each instruction it can use, and
#: no skill it has no route to.
ASSEMBLY_CLOSURE = "closure"
#: Assemble every skill of the checklist, reached or not. Kept for
#: reproducing runs made before closure became the default (exp-01, exp-02).
ASSEMBLY_ALL = "all"
ASSEMBLY_MODES = (ASSEMBLY_CLOSURE, ASSEMBLY_ALL)



WITHHELD_FROM_RUNTIME = ("benchmark.json", "eval-manifest.json")

#: A directory holding gold, wherever it sits. A runtime containing one is
#: refused, whatever the caller excluded.
EXAMPLE_GOLD_SUBDIR = "checks"


@dataclass(frozen=True)
class ExampleContent:
    """One example's content, as the caller states it.

    Nothing here says where the example is stored or what kind it is; that is
    the caller's knowledge, whether the caller is mmQC's benchmark or an
    application.
    """

    #: The directory staged as the runtime's ``input/``. Every path in
    #: :attr:`parts` and :attr:`files` is relative to it.
    source_root: Path
    #: What the example is, in order, as provider-neutral parts:
    #: ``{"kind": "text", "text": str}``, ``{"kind": "image", "path": str}``,
    #: or an image carrying its bytes,
    #: ``{"kind": "image", "media_type": str, "data": bytes}``.
    parts: Tuple[Mapping[str, Any], ...]
    #: Files that accompany the content without being sent: role to a path,
    #: ``None``, or a list of paths. Named in ``input/inputs.json``.
    files: Mapping[str, Any]
    #: How the example is named in the layout and in logs.
    label: str
    #: Names left out of the staged copy, wherever they occur under
    #: :attr:`source_root`.
    exclude: Tuple[str, ...] = ()


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
    #: values rebased onto this runtime.
    input_parts: Tuple[Mapping[str, Any], ...] = ()



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
    """Rebase image paths onto the runtime; everything else passes through.

    An image carrying its bytes has no path to rebase: it travels in the
    request and is never written into the runtime.
    """
    rebased: List[Mapping[str, Any]] = []
    for part in parts:
        if part["kind"] == "image" and "path" in part:
            rebased.append({**part, "path": _rebase_into_input(part["path"])})
        else:
            rebased.append(dict(part))
    return tuple(rebased)


def _write_input_manifest(
    source_root: Path, files: Mapping[str, Any]
) -> None:
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
        for role, value in files.items()
    }
    path = source_root / AGENTIC_INPUT_SUBDIR / AGENTIC_INPUT_MANIFEST_FILENAME
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def assemble_runtime(
    checklist_dir: Path,
    check: str,
    content: ExampleContent,
    *,
    root: Optional[Path] = None,
    parent: Optional[Path] = None,
    pins: Optional[Mapping[str, str]] = None,
    assembly: str = ASSEMBLY_CLOSURE,
) -> RuntimeLayout:
    """Assemble a sealed runtime directory for one example.

    The result contains the named check as the entry point and **every skill
    its pinned prose reaches, transitively** -- exactly one version of each --
    and the one example's inputs. It contains no evaluation contract, no gold,
    no other example, no sibling version, and no link of any kind back to the
    repository.

    **Closure, not the whole checklist, is the default.** Assembling every
    skill put redundant copies of instructions in front of the model: a
    monolith that carries classification inline was still offered
    `classify-panels`, and a check that calls one shared skill was offered
    another it had no use for. That tested nothing a modular checklist is
    meant to be -- one maintained copy of each instruction -- and the stray
    calls it drew (up to 7% of sessions in exp-02) blurred the arrangement a
    run was labelled with. ``assembly="all"`` restores the old behaviour, for
    reproducing runs made under it.

    Assembly is atomic: the runtime is built in a staging directory and moved
    into place only once complete, so a failure leaves nothing half-built.

    Args:
        checklist_dir: The checklist's directory.
        check: The entry-point leaf.
        content: The example's content, as the caller states it.
        root: Where to put the runtime. Defaults to a fresh directory under
            ``parent``.
        parent: Where fresh runtimes are created when ``root`` is not
            given. Defaults to the system's temporary directory. It must lie
            outside any repository whose skills the SDK could discover, and
            off any synced folder; checking that is the caller's job, since
            only the caller knows its repository.
        pins: Optional ``{skill: version}``. Defaults to the checklist's
            ``version-manifest.yaml``, and -- only when there is none -- to
            the highest version of each skill.
        assembly: ``"closure"`` (default) or ``"all"``.

    Raises:
        FileNotFoundError: If the checklist or the content's source
            directory is absent.
        ValueError: If the check is not a skill of the checklist, has no
            ``schema.json``, or the skills are invalid.
    """
    checklist_dir = Path(checklist_dir)
    if not checklist_dir.is_dir():
        raise FileNotFoundError(f"Checklist not found: {checklist_dir}")

    # Validate the graph before building anything from it: a runtime
    # assembled from an inconsistent checklist would fail confusingly, at
    # session time, per example.
    skills = validate_skills(checklist_dir)
    if check not in skills:
        raise ValueError(
            f"{check!r} has no {SKILL_FILENAME} in {checklist_dir}; it "
            "cannot be an agentic entry point"
        )
    # The entry point's schema is the answer's contract: the session is
    # constrained to it, and the prediction validated against it.
    if not (checklist_dir / check / "schema.json").is_file():
        raise ValueError(
            f"{check!r} has no schema.json in {checklist_dir}; an entry point "
            "answers with structured output, and its schema is the contract"
        )
    if pins is None:
        pins = checklist_pins(checklist_dir)
        if pins is not None:
            validate_version_manifest(skills, pins, checklist_dir)
    selected = select_versions(skills, pins)
    if assembly == ASSEMBLY_CLOSURE:
        reached = call_closure(check, selected)
        selected = {n: s for n, s in selected.items() if n in reached}
    elif assembly != ASSEMBLY_ALL:
        raise ValueError(
            f"assembly must be one of {ASSEMBLY_MODES}, got {assembly!r}"
        )
    input_dir = Path(content.source_root)
    if not input_dir.is_dir():
        raise FileNotFoundError(
            f"The content of {content.label} is not a directory: {input_dir}"
        )

    if root is None:
        root = Path(
            tempfile.mkdtemp(
                prefix=AGENTIC_RUNTIME_PREFIX,
                dir=parent if parent is not None else tempfile.gettempdir(),
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

        # The content is copied whole, minus what the caller excludes. For
        # mmQC's benchmark that is any nested answer key: a document-level
        # example's `content/` holds its figure sub-examples, each with its
        # own `checks/`. `_assert_sealed` catches a leak afterwards; the
        # exclusion is the copier honouring the rule rather than relying on
        # the alarm.
        shutil.copytree(
            input_dir,
            staging / AGENTIC_INPUT_SUBDIR,
            symlinks=False,
            ignore=(
                shutil.ignore_patterns(*content.exclude)
                if content.exclude else None
            ),
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
            example=content.label,
            input_parts=_rebase_parts(content.parts),
        )
        _write_input_manifest(staging, content.files)
        shutil.copy2(
            AGENTIC_CLAUDE_TEMPLATE, staging / AGENTIC_ORIENTATION_FILENAME
        )

        _assert_sealed(staging)
        os.replace(staging, root)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise

    logger.info(
        "Assembled runtime for %s/%s on %s at %s (%d skills, %s)",
        checklist_dir.name, check, content.label, root, len(selected),
        assembly,
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
    * There are **no file tools at all**. The example's content travels with
      the request, and no skill in any checklist reaches for a supporting
      file, so a ``Read`` -- even one scoped to the runtime -- would be an
      unused capability that an experiment could come to depend on by
      accident. Without it, what the model saw is exactly what it was sent.

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
        # What it may use without prompting. There are no path rules because
        # there are no file tools: the content arrives in the request and the
        # runner serialises the structured result, so nothing the session
        # does touches the filesystem.
        "allowed_tools": list(AGENTIC_ALLOWED_TOOL_NAMES),
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
    # Images carried in the request are not files in the runtime. Added only
    # when present, so a key for an all-file example is what it always was.
    inline = [
        hashlib.sha256(part["data"]).hexdigest()
        for part in layout.input_parts
        if part.get("kind") == "image" and "data" in part
    ]
    if inline:
        parts["inline_images"] = inline
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

