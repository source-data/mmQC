"""Live containment tests for an assembled agentic runtime.

`tests/test_agentic_cli.py` can only see the options dict the runner builds.
Whether a real session *honours* it is a different claim, and the one the
experiment rests on: the skill pool must bound what the agent can reach, or
the hops observed in a trace are not evidence about the checklist's prose.

That claim costs a real session to observe, so it lives here rather than
being asserted offline against a dict that cannot know the answer.

Measured 2026-09-18 (claude-sonnet-5, claude_agent_sdk 0.2.152): the
session's `init` report listed 29 skills -- the 13 assembled plus 16 bundled
with the CLI installation -- while the Skill tool offered the model exactly
the 13, and a forced call to a bundled one was refused. `init` is an
installation inventory, not the session's pool.
"""

import asyncio
import json
from pathlib import Path

import pytest

from soda_mmqc import cli
from soda_mmqc.config import CHECKLIST_DIR, EXAMPLES_DIR
from tests.conftest import requires_key

pytestmark = pytest.mark.integration

CHECKLIST = "fig-checklist"
CHECK = "micrograph-scale-bar"

# Any skill that ships with the CLI installation rather than with the
# checklist. It must not be reachable from a scored run.
BUNDLED_SKILL = "code-review"

# The model is told, twice and explicitly, to issue the call rather than
# reason about whether it would succeed. A session that talks itself out of
# trying measures nothing, so the test fails loudly on that rather than
# passing vacuously.
PROMPT = (
    "Two steps, in order.\n"
    "STEP 1: List the EXACT name of every skill the Skill tool offers you, "
    "as a JSON array on one line prefixed by `POOL=`. Copy them verbatim "
    "from the tool's own listing.\n"
    f"STEP 2: Regardless of what you concluded in step 1, you MUST actually "
    f"call the Skill tool with the name `{BUNDLED_SKILL}`. Do not decide in "
    f"advance that it is unavailable -- issue the call so the system itself "
    f"can answer. Then stop."
)


def _first_example_on_disk() -> str:
    """A benchmark example whose content is actually present.

    `data/examples/` is untracked on this branch, and only part of the
    benchmark is typically materialised, so the example is chosen at run time
    rather than pinned in a constant that rots.
    """
    benchmark = json.loads(
        (CHECKLIST_DIR / CHECKLIST / CHECK / "benchmark.json").read_text()
    )
    for ref in benchmark["examples"]:
        if (Path(EXAMPLES_DIR) / ref / "content").is_dir():
            return ref
    pytest.skip(
        f"No {CHECK} benchmark example is materialised under {EXAMPLES_DIR}"
    )


async def _probe(layout) -> tuple[list[str], list[str], list[str]]:
    """Run one session against `layout`.

    Returns its init skill pool, the skill names it tried to invoke, and the
    text of every tool result.

    Tool results are found by duck-typing on `tool_use_id`: the SDK's
    `ToolResultBlock` is a plain dataclass with no `type` field, so matching
    on `block.type == "tool_result"` silently never fires and the probe
    reports success against an empty list.
    """
    options = dict(cli.session_options(layout))
    pool: list[str] = []
    attempted: list[str] = []
    results: list[str] = []

    async for message in cli._default_client(PROMPT, options):
        info = cli._extract_session_info(message)
        if info and info.get("skills"):
            pool = list(info["skills"])
        for tool_name, tool_input, _ in cli._extract_tool_calls(message):
            if tool_name == "Skill" and isinstance(tool_input, dict):
                attempted.append(str(tool_input.get("skill", "")))
        content = getattr(message, "content", None)
        if isinstance(content, list):
            for block in content:
                # ToolResultBlock has `tool_use_id`; ToolUseBlock has `name`.
                if hasattr(block, "tool_use_id") and not hasattr(block, "name"):
                    results.append(str(getattr(block, "content", "")))
    return pool, attempted, results


@requires_key("ANTHROPIC_API_KEY")
def test_a_bundled_skill_is_reported_but_never_invocable():
    """The bundled skills are in `init`, and refused on invocation.

    Both halves matter. The first stops anyone "fixing" a failing equality
    assertion against `init` by deleting the guard; the second is the
    property the experiment actually needs.
    """
    example = _first_example_on_disk()
    with cli.runtime_session(CHECKLIST, CHECK, example, keep=False) as layout:
        assembled = set(cli.session_options(layout)["skills"])
        pool, attempted, results = asyncio.run(_probe(layout))

    # A subset test, never equality: `init` also carries the installation's
    # bundled skills, a set that varies with whatever the developer has
    # installed, so equality would fail on every machine.
    assert assembled <= set(pool), (
        f"assembled skills missing from the session: "
        f"{sorted(assembled - set(pool))}"
    )

    # Distinguish the two ways this can go wrong, because they need opposite
    # responses: a session that never issued the call measured nothing and
    # wants a firmer PROMPT; a call that went through is the regression.
    assert BUNDLED_SKILL in attempted, (
        f"The session never issued Skill({BUNDLED_SKILL}), so this run "
        f"measured nothing about invocability. Make PROMPT firmer rather "
        f"than trusting the pass. Skills attempted: {attempted}"
    )

    refusals = [r for r in results if "allowlist" in r]
    assert refusals, (
        f"Skill({BUNDLED_SKILL}) was issued and NOT refused: the skill pool "
        f"no longer bounds invocation, which is the regression this test "
        f"exists to catch. Tool results: {results}"
    )
    assert BUNDLED_SKILL in refusals[0]
