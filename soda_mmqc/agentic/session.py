"""Running one session against an assembled runtime, and watching what it did.

The session is given the runtime, the entry point and the example's content,
and nothing else. Every assembled skill's description is loaded and the runner
preselects nothing, so which skills fire has to be found by the agent -- that
trace is the instrument, which is why the audit log and the skill trace are
written on every call rather than only on success.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import (
    Any, Dict, Iterator, List, Mapping, Optional, Sequence, Set, Tuple,
)

from soda_mmqc import logger
from soda_mmqc.config import (
    AGENTIC_DEFAULT_MODEL,
    AGENTIC_FORBIDDEN_TOOLS,
    AGENTIC_INPUT_MANIFEST_FILENAME,
    AGENTIC_INPUT_SUBDIR,
    AGENTIC_MAX_BUFFER_BYTES,
)
from soda_mmqc.agentic.pinning import SkillSet, checklist_pins
from soda_mmqc.agentic.render import render_anthropic
from soda_mmqc.agentic.runtime import (
    RuntimeLayout,
    _leaf_schema,
    assemble_runtime,
    effective_session_options,
    session_options,
)
from soda_mmqc.agentic.skills import (
    _FRONTMATTER,
    SKILL_FILENAME,
    SKILL_TOOL,
    Skill,
    _read_json,
    invoked_skills,
    load_skills,
    select_versions,
    validate_skills,
)

#: Directory of debug sidecars beside each prediction, and the scratch
#: directory the harness writes them into during a run.
INTERMEDIATES_DIRNAME = "intermediates"

#: Name of the file holding one example's final leaf JSON.
PREDICTION_FILENAME = "prediction.json"

#: Sidecars written beside every prediction.
SKILL_TRACE_FILENAME = "skill_trace.json"
TOOL_AUDIT_FILENAME = "tool_audit.json"
SKILL_SET_FILENAME = "skill_set.json"

__all__ = [
    "runtime_session",
    "SkillTraceRecorder",
    "ToolAuditLog",
    "make_pretooluse_hook",
    "interactive_approver",
    "validate_against_schema",
    "compare_declared_and_observed",
    "load_skill_file",
    "INTERMEDIATES_DIRNAME",
    "PREDICTION_FILENAME",
    "SKILL_TRACE_FILENAME",
    "TOOL_AUDIT_FILENAME",
    "SKILL_SET_FILENAME",
]


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

    from soda_mmqc.agentic.render import render_anthropic

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


def _extract_usage(message: Any) -> Optional[Dict[str, Any]]:
    """Pull cost, turns and token usage out of the SDK's result message.

    The SDK reports all of it and the harness was keeping only `result`. It
    is the only place the numbers exist: a provider bills per call, and
    nothing downstream can reconstruct what a session spent.
    """
    def get(obj, key):
        if isinstance(obj, Mapping):
            return obj.get(key)
        return getattr(obj, key, None)

    fields = ("total_cost_usd", "num_turns", "duration_ms", "usage")
    captured = {key: get(message, key) for key in fields}
    if all(value is None for value in captured.values()):
        return None
    return {key: value for key, value in captured.items() if value is not None}


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
        "PreToolUse": [
            make_pretooluse_hook(audit, approver)
        ]
    }

    read_paths: Set[str] = set()
    result_text: Optional[str] = None
    async for message in run(_session_message(layout), options):
        info = _extract_session_info(message)
        if info:
            audit.note_session(info)
        spent = _extract_usage(message)
        if spent:
            audit.note_usage(spent)
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
        #: What the session cost, from the SDK's result message: dollars,
        #: turns, wall time and token usage. Deciding how many replicates an
        #: experiment can afford is a question about cost, and a run that
        #: does not record it cannot answer it. Empty rather than zero when
        #: the provider reports nothing, so a free-looking run is
        #: distinguishable from an unreported one.
        self.usage: Dict[str, Any] = {}
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
                {
                    "session": self.session_info,
                    "usage": self.usage,
                    "calls": self.entries,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    def note_session(self, info: Mapping[str, Any]) -> None:
        self.session_info = dict(info)
        self._flush()

    def note_usage(self, info: Mapping[str, Any]) -> None:
        self.usage = dict(info)
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

    The hook only ever *narrows*: an approver can deny a call the profile
    allowed, and
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
    from soda_mmqc.agentic.openai_driver import RuntimeTools, make_openai_client

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
