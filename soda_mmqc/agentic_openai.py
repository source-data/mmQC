"""An OpenAI-backed client for agentic checklist sessions.

Why this exists
---------------
The repository runs on OpenAI: ``API_PROVIDER=openai``, a working
``OPENAI_API_KEY``, and a default model of ``gpt-5-mini``. The Claude Agent
SDK adopted at human gate 4A cannot use that key -- it drives Claude Code,
which authenticates against Anthropic, Bedrock, Vertex or Foundry. Adopting it
therefore means a second model provider and a second billing relationship,
which gate 4A did not surface and which left the project unable to run at all.

This module is the alternative: the same experiment, driven through the
provider the project already has. It is deliberately an *additional* client
rather than a replacement, so gate 4A's decision stands and either path can be
taken once credentials exist for both.

What it must preserve
---------------------
The premise under test is **delegated discovery**: the model decides which
skill to invoke, from descriptions alone. That is why an agent is used instead
of walking the DAG in Python, and it is what gate 4D measures. So:

* every assembled skill's ``name`` and ``description`` is put in front of the
  model, and nothing else about the graph;
* the entry point is named, its dependencies are **not**;
* invoking a skill returns that skill's instructions, exactly as the SDK's
  ``Skill`` tool does -- the body is loaded on invocation, not up front;
* the runner never calls a skill on the model's behalf.

Containment
-----------
Better than the SDK path rather than worse, because the tools are implemented
here instead of negotiated with someone else's permission model. ``Read`` is
confined to the runtime directory by resolving the path and refusing anything
outside -- no rule syntax, no evaluation order, no surprise defaults. There is
no shell, no subagent and no network tool, because none is implemented, and no
writable location: `218fe013` took the write tool off the SDK path and this
one had kept offering it, so the two providers were not running the same
session.
"""

from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

from soda_mmqc import logger

#: Images the vision models accept. Anything else is offered as a filename
#: only -- a figure we cannot render is a fact the session should know rather
#: than a crash.
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

#: Hard ceiling on model turns. A session that has not produced an answer in
#: this many turns is looping, and looping silently is the expensive failure.
MAX_TURNS = 40


class RuntimeTools:
    """The tool implementations, scoped to one assembled runtime.

    Every path is resolved and checked against the runtime root before any
    access. Containment is therefore a property of this class rather than of
    a configuration someone else interprets.
    """

    def __init__(self, root: Path, artifacts: Optional[Path] = None):
        self.root = Path(root).resolve()
        #: Accepted and ignored: nothing in the runtime is writable. The
        #: parameter stays until the artifacts apparatus comes out with
        #: `--all-checks` (2026-09-20-dismantle-cross-check-cache.md).
        self.artifacts = Path(artifacts).resolve() if artifacts else None

    def _resolve(self, raw: str, *, inside: Path) -> Path:
        """Resolve a model-supplied path, refusing anything outside ``inside``.

        ``..`` and absolute paths are handled by resolving first and comparing
        afterwards, so there is no pattern to outwit.
        """
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        candidate = candidate.resolve()
        if candidate != inside and inside not in candidate.parents:
            raise PermissionError(
                f"{raw!r} is outside {inside}; the session may not reach it"
            )
        return candidate

    def read(self, path: str) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Return a file's text, or an image part the model can see.

        Reading a `SKILL.md` directly is refused. The file is *in* the
        runtime and readable in principle, but routing skill access through
        the `Skill` tool is what makes the trace a complete record of which
        skills fired -- and that trace is the whole instrument for gate 4D. A
        skill body fetched by `Read` would be invisible to it.
        """
        resolved = self._resolve(path, inside=self.root)
        if resolved.name == "SKILL.md":
            return (
                "Skill instructions are not readable as files. Use the "
                f"`Skill` tool with name {resolved.parent.name!r} instead.",
                None,
            )
        if not resolved.is_file():
            raise FileNotFoundError(f"No such file in the runtime: {path}")
        if resolved.suffix.lower() in IMAGE_SUFFIXES:
            mime = mimetypes.guess_type(resolved.name)[0] or "image/png"
            payload = base64.b64encode(resolved.read_bytes()).decode()
            return (
                f"(image {resolved.name} supplied below)",
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{payload}"},
                },
            )
        return resolved.read_text(encoding="utf-8", errors="replace"), None

    def listing(self) -> str:
        """Files the session should know about.

        Includes each skill's `schema.json` -- the orientation points at the
        output contract by path, and a listing that omitted it would
        contradict the instruction the session is given. Excludes `SKILL.md`,
        which is reachable only through the `Skill` tool so that the trace
        stays complete.
        """
        def visible(p: Path) -> bool:
            if not p.is_file() or p.name == "SKILL.md":
                return False
            return ".claude" not in p.parts or p.name == "schema.json"

        return "\n".join(
            sorted(
                str(p.relative_to(self.root))
                for p in self.root.rglob("*")
                if visible(p)
            )
        )


def _tool_schemas(skill_names: List[str]) -> List[Dict[str, Any]]:
    """The tools the model may call.

    ``Skill`` takes a free-form name rather than an enum of the assembled
    skills. That is deliberate: an enum would let the model pick a valid skill
    by construction, and the trace would then record our schema's constraint
    rather than the model's choice. A wrong name must be *possible* for a
    right one to be evidence.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "Skill",
                "description": (
                    "Invoke another skill by name and receive its "
                    "instructions. Use this when a skill's text tells you to."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "The skill to invoke.",
                        }
                    },
                    "required": ["name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "Read",
                "description": "Read a file from this run's directory.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
    ]


def _system_prompt(
    orientation: str, descriptions: Mapping[str, str], listing: str
) -> str:
    """What the model is told before it starts.

    Carries every skill's description and **no** information about which one
    the entry point needs. Discovering that is the thing being measured.
    """
    catalogue = "\n".join(
        f"- `{name}`: {description}"
        for name, description in sorted(descriptions.items())
    )
    return (
        "You are running one quality-control check on one scientific figure.\n\n"
        f"{orientation}\n\n"
        "## Skills available to you\n\n"
        "Invoke any of these with the `Skill` tool when the instructions you "
        "are reading tell you to. Calling one returns its full instructions.\n\n"
        f"{catalogue}\n\n"
        "## Files in this run\n\n"
        f"{listing}\n\n"
        "Begin by invoking the entry-point skill named in the orientation "
        "above, then follow its instructions exactly."
    )


def _assistant_message(response_message) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "role": "assistant",
        "content": response_message.content,
    }
    if response_message.tool_calls:
        payload["tool_calls"] = [
            {
                "id": call.id,
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": call.function.arguments,
                },
            }
            for call in response_message.tool_calls
        ]
    return payload


def make_openai_client(
    skill_bodies: Mapping[str, str],
    descriptions: Mapping[str, str],
    tools: RuntimeTools,
    orientation: str,
    *,
    model: str,
    max_turns: int = MAX_TURNS,
):
    """Build a client with the same contract as the Agent SDK adapter.

    Yields mapping-shaped messages carrying tool-call blocks, which is what
    the session runner's extractor and the trace recorder already understand,
    so neither needed changing to support a second provider.
    """
    from openai import OpenAI

    from soda_mmqc.agentic_render import render_openai

    async def client(
        parts: Sequence[Mapping[str, Any]], options: Mapping[str, Any]
    ):
        openai_client = OpenAI()
        hook = (options.get("hooks") or {}).get("PreToolUse", [None])[0]

        # The checklist's `model-defaults.yaml` reaches us through the session
        # options, the same route the Agent SDK path takes. Reading it here
        # rather than binding it at construction is what makes the setting
        # actually govern this loop: it is a cost ceiling, and a cost ceiling
        # that parses, validates and documents cleanly while having no effect
        # is worse than not offering one.
        turn_ceiling = int(options.get("max_turns") or max_turns)

        messages: List[Dict[str, Any]] = [
            {
                "role": "system",
                "content": _system_prompt(
                    orientation, descriptions, tools.listing()
                ),
            },
            {"role": "user", "content": render_openai(parts, tools.root)},
        ]
        schemas = _tool_schemas(sorted(skill_bodies))
        nudged = False

        for turn in range(turn_ceiling):
            response = openai_client.chat.completions.create(
                model=model, messages=messages, tools=schemas
            )
            message = response.choices[0].message
            messages.append(_assistant_message(message))

            if not message.tool_calls:
                # A model that answers in chat has done the work but not the
                # last step. Push back once on the output contract -- this
                # says nothing about *which* skills to use, so it does not
                # touch what gate 4D measures.
                if not nudged:
                    nudged = True
                    logger.info("Session answered in chat; asking for JSON")
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                "Answer as JSON conforming to the check's "
                                "schema, and nothing else. Do not reply with "
                                "prose."
                            ),
                        }
                    )
                    continue
                yield {"content": [], "text": message.content}
                return

            # Surface the calls in the shape the session runner reads, so the
            # skill trace is recorded by the same code on both providers.
            yield {
                "content": [
                    {
                        "name": call.function.name,
                        "input": _safe_args(call.function.arguments),
                        "id": call.id,
                    }
                    for call in message.tool_calls
                ]
            }

            pending_images: List[Dict[str, Any]] = []
            for call in message.tool_calls:
                arguments = _safe_args(call.function.arguments)
                if hook is not None:
                    decision = await hook(
                        {
                            "tool_name": call.function.name,
                            "tool_input": arguments,
                            "tool_use_id": call.id,
                        },
                        call.id,
                        None,
                    )
                    specific = (decision or {}).get("hookSpecificOutput", {})
                    if specific.get("permissionDecision") == "deny":
                        messages.append(
                            _tool_result(
                                call.id,
                                "Denied: "
                                + specific.get(
                                    "permissionDecisionReason", "not permitted"
                                ),
                            )
                        )
                        continue

                text, image = _dispatch(
                    call.function.name, arguments, skill_bodies, tools
                )
                messages.append(_tool_result(call.id, text))
                if image is not None:
                    pending_images.append(image)

            # Images go in as a separate user turn, and only once every
            # tool_call has been answered: the API requires an assistant
            # message carrying tool_calls to be followed *immediately* by one
            # tool message per call, so interleaving them mid-loop is a 400.
            if pending_images:
                messages.append({"role": "user", "content": pending_images})

        logger.warning("Session hit the %d-turn ceiling", turn_ceiling)

    return client


def _safe_args(raw: str) -> Dict[str, Any]:
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {"_unparsed": raw}
    return parsed if isinstance(parsed, dict) else {"_value": parsed}


def _tool_result(call_id: str, content: str) -> Dict[str, Any]:
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def _dispatch(
    name: str,
    arguments: Mapping[str, Any],
    skill_bodies: Mapping[str, str],
    tools: RuntimeTools,
) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Run one tool call, returning its result for the model.

    Every failure is returned as text rather than raised. A session that asks
    for a skill that does not exist, or a file outside the runtime, should
    learn that and continue -- both are observations worth having in the
    trace, and neither is a reason to lose the run.
    """
    try:
        if name == "Skill":
            wanted = str(arguments.get("name", "")).lstrip("/")
            if wanted not in skill_bodies:
                return (
                    f"No skill named {wanted!r}. Available: "
                    f"{', '.join(sorted(skill_bodies))}",
                    None,
                )
            return skill_bodies[wanted], None
        if name == "Read":
            return tools.read(str(arguments.get("path", "")))
        return f"No tool named {name!r}.", None
    except (PermissionError, FileNotFoundError, OSError) as exc:
        return f"{type(exc).__name__}: {exc}", None
