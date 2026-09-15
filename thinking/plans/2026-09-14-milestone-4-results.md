---
title: Milestone 4 results — per-example agent session writing predictions
date: 2026-09-14
tags: [agentic, milestone, sdk, runner, results]
plan: 2026-09-02-agentic-checklist-skills.md
status: 4A ACCEPTED, 4B PASSED, 4C AUTHORISED but blocked on credentials; two containment defects found by the attempted run
---

# Milestone 4 Results

Outcome record for **Milestone 4: Per-Example Agent Session Writing
Predictions** of
[`2026-09-02-agentic-checklist-skills.md`](2026-09-02-agentic-checklist-skills.md).

**Deliverable:** the priority runner — for each example of one check, assemble
the runtime, run one agent session, and write a schema-valid prediction plus a
diagnostic trace.

> ## Gate status
>
> | Gate | Status |
> |---|---|
> | **4A** — the dependency | **ACCEPTED 2026-09-14** — `claude-agent-sdk==0.2.152` pinned in `pyproject.toml` |
> | Automatic (Step 8) | **passed** — 207 tests, `--mock` run over the pilot, suite failure set unchanged at 62 lines |
> | **4B** — the mock output shape | **PASSED 2026-09-14** |
> | **4C** — authorisation for the first live run | **AUTHORISED 2026-09-14**; attempted, **failed at authentication, nothing spent** |
> | **4D** — did delegated discovery work? | **still unanswered** — no session reached the model |
>
> **Gate 4A is open and the dependency has been backed out of
> `pyproject.toml`.** The gate guards that file specifically, so leaving an
> unapproved pin there would have been presumptuous. Nothing breaks: the mock
> path and all 207 tests drive the session through a fake client and never
> import the SDK.
>
> The reviewer also noted feeling that the work was *"drifting off (SDKs
> etc.)"*. That is addressed in
> [the handoff](2026-09-14-agentic-handoff.md#the-drifting-off-concern-addressed-honestly);
> the short version is that the `mcp` conflict flagged at gate 4A was
> **manufactured ambiguity and is withdrawn**.
>
> **Nothing has been run against a real model and nothing has been spent.**
> Gate 4C is the point where this work commits money and credentials, and it
> is a stop the agent must not cross on its own. A live-capable `run` path
> exists but refuses to execute: `run` without `--mock` exits 2 with a message
> naming the gate.
>
> A key **is** present in `.env` and `config.py` auto-loads it, so a session
> would have authenticated. That made the stop a real one rather than a
> theoretical one.

- **Branch:** `agentic`, uncommitted in the working tree
- **Measured:** 2026-09-14, Python 3.12.14

---

## Human gate 4A — the dependency

**Decision:** is this the package, version, and auth model we commit to?

**Status: artifact complete; taken on the recommended option with the reviewer
absent. Decision OPEN.**

| | |
|---|---|
| **Distribution** | `claude-agent-sdk` (PyPI) |
| **Version** | `0.2.152`, pinned `==` |
| **License** | MIT |
| **Requires-Python** | `>=3.10`; repo requires `>=3.12` |
| **Primary documentation** | [Agent SDK reference — Python](https://code.claude.com/docs/en/agent-sdk/python) |

### API surface the runner uses

`query(prompt=..., options=ClaudeAgentOptions(...))`, which returns an async
iterator of messages and creates a new session per call — exactly the
one-session-per-example shape this milestone needs. `ClaudeSDKClient` is the
alternative and is not used: it exists for multi-turn conversations, which
this runner does not have.

Hooks are used for the `Skill` trace (Step 5) and, from the Milestone 3 gate 3B
answer, for the `PreToolUse` audit.

### Credentials

`ANTHROPIC_API_KEY` in the process environment. The SDK does **not** read
`.env` itself, but `soda_mmqc/config.py` calls `load_dotenv()` at import, so a
key in `.env` reaches `os.environ` before the SDK looks — which is how the
repository already behaves for its other providers.

Bedrock, Claude Platform on AWS, Vertex and Foundry are supported through
environment flags if routing through an existing cloud contract is preferred.
Anthropic explicitly disallows claude.ai login for SDK-built agents, so API-key
authentication is the sanctioned path.

### Transitive footprint

Measured by dry-run resolution against the actual environment — **6 new
packages**:

```
claude-agent-sdk 0.2.152   mcp 2.2.0        mcp-types 2.2.0
cryptography 50.0.1        pyjwt 2.14.0     sse-starlette 3.4.11
```

`anyio`, `jsonschema` and `sniffio` were already present. `jsonschema` is
incidentally useful: Step 4 needs exactly it to validate the leaf output.

### Three things flagged for the decision, not smuggled past it

1. **`mcp` arrives, and the plan's Constraints say "Do not add … MCP."** The
   reading taken is that the constraint prohibits MCP *as an architecture* — no
   MCP servers are defined or called — while the package lands unavoidably as
   an SDK dependency, bringing `mcp-types`, `sse-starlette`, `pyjwt` and the
   compiled `cryptography` with it. That is a literal conflict with a written
   constraint and is recorded as such. **If the constraint was meant
   literally, this dependency cannot be used at all**, and the milestone needs
   rethinking rather than patching.
2. **Wheels are ~90 MB**, because each bundles a native Claude Code binary.
   There is **no ARM64 Windows wheel**: that platform falls back to the 0.3 MB
   sdist and needs Claude Code installed separately on `PATH`. A real asterisk
   on the OS-independence required at gate 3A — macOS (arm64, x86_64), Linux
   (x86_64, aarch64) and Windows x64 are all covered.
3. **It moves fast and is `0.x`.** Eight releases in the sampled window and no
   semver promise. Pinned `==0.2.152` rather than floated, because a silently
   updated agent runtime makes scores non-comparable between runs — which is
   the one property Milestones 5 and 6 depend on. Bumping it should be a
   deliberate change.

### The Milestone 3 carry-forward, partly closed

Gate 3B could not produce "the full tool set the SDK reports, and the diff".
With the package installed, the checkable half is now closed:

| Claim | Result |
|---|---|
| `ClaudeAgentOptions` accepts `cwd`, `setting_sources`, `skills`, `allowed_tools`, `disallowed_tools`, `permission_mode` | **All six verified** against the real dataclass (48 fields); zero unrecognised keys |
| `dontAsk` is a valid permission mode | **Verified** — `PermissionMode` is `('default', 'acceptEdits', 'plan', 'bypassPermissions', 'dontAsk', 'auto')` |
| The SDK's *reported* tool set, diffed against the allowlist | **Still outstanding** |

The last one is only available in the session `init` message, which requires
opening a session. The bundled CLI has no `--list-tools` equivalent
(`--help` and the subcommand list were checked). **It therefore moves to gate
4C**, to be produced from the first authorised session before any result is
trusted.

---

## Steps 3–7: what shipped

| Capability | Where | Note |
|---|---|---|
| `run --mock` | `run_check_mock()` | Writes each example's gold as its prediction plus a deterministic trace sidecar |
| Session runner | `_run_agent_session()` | Fake-client seam; validates before returning |
| Skill trace | `SkillTraceRecorder` | Appends to disk as calls occur |
| Declared vs observed | `compare_declared_and_observed()` | Diagnostic only, never enforcement |
| Intermediate validation | `validate_intermediates()` | Against the producing skill's schema |
| Options + `needs` | `effective_session_options()` | May narrow the profile, never widen |
| Session cache key | `session_cache_key()` | Keyed on inputs, never on the observed trace |

### `--mock` is genuinely offline

Milestone 1's gate 1B recorded that the legacy `evaluate --mock` is *not*
offline: it validates the model against the provider first and aborts without a
key, which made a credential-free gate impossible. This implementation does not
repeat that. Two tests pin it: one runs with `ANTHROPIC_API_KEY` and
`OPENAI_API_KEY` deleted, and one asserts in a subprocess that
`claude_agent_sdk` is **never imported** on the mock path — a credential-free
run must not need the 200 MB bundled binary.

### Finding: gold is not a valid prediction

Writing gold verbatim as the mock prediction produced **schema-invalid output**.
Gold records carry curation metadata — `updated_at` — and the leaf schema sets
`additionalProperties: false`, so:

```
ValueError: Output does not match the schema:
  <root>: Additional properties are not allowed ('updated_at' was unexpected)
```

This matters beyond the mock: **anything that assumes "gold is a valid
prediction" is wrong** — a fixture, a doc example, a future replay harness.
`_as_prediction()` now projects gold onto the schema's declared properties, and
`test_gold_carries_metadata_the_schema_forbids` pins the underlying fact about
the data rather than just the workaround.

### Finding: the first cache key could never hit

The permission rules embed the runtime's absolute path, which is a fresh temp
directory every run. Hashing the options verbatim gave every assembly a unique
key, so the cache would have hit **zero times** while appearing to work. The
runtime root is now replaced by a placeholder before hashing, leaving what
actually constrains behaviour: which tools, scoped to which position inside the
runtime. Caught by `test_the_cache_key_ignores_the_runtime_path`.

### Design notes worth keeping

- **The prompt names the entry point and nothing else.** No dependency list, no
  ordering, no closure. Naming `identify-panels` there would make the Milestone
  4 trace a measurement of that string rather than of the skills' prose, which
  is the entire question. Pinned by `test_no_closure_is_supplied_to_the_session`
  and by a mutation that adds "First call identify-panels" to the prompt.
- **The trace is written as calls occur**, so a session that dies halfway still
  leaves its record — usually the session whose trace matters most.
- **A missing intermediate is not an error.** Whether a shared skill ran at all
  is gate 4D's question; failing the run would convert that observation into a
  crash and destroy the evidence.
- **`needs` may narrow the profile but never widen it.** A skill requesting a
  capability is a request, not a grant; honouring it silently would let any
  future skill author widen containment by editing frontmatter.
- **Mock trace entries carry `source: "mock"`.** They are generated from
  frontmatter, so comparing them against frontmatter is circular. The marker
  keeps them out of gate 4D, which only a live run can answer.

---

## Automatic gate (Step 8)

**Command:** `pytest tests/test_agentic_cli.py -v`, plus a `--mock` run over the
pilot check.

```
207 passed
Wrote 38 mock prediction(s)
```

177 before this milestone, **207 after** — 30 new tests. Whole suite: the
sorted `FAILED`/`ERROR` line set is **62 lines**, unchanged from the Milestone
1, 2 and 3 baseline.

### Mutation testing

| Mutation | Caught by |
|---|---|
| Schema validation moved after the prediction is returned | 2 tests |
| Trace flushed only at the end, so a dying session loses it | `test_the_trace_is_written_as_calls_occur` |
| Prompt names the dependency, supplying a closure | `test_no_closure_is_supplied_to_the_session` |
| Mock writes gold verbatim | `test_the_mock_prediction_satisfies_the_leaf_schema` |

---

## Human gate 4B — the mock output shape

**Decision:** are the prediction layout, the `skill_trace.json` shape, and the
declared-versus-observed report the artifacts we want to reason about in the
live run?

**Status: OPEN.** Artifact below.

### Console output

```
$ python -m soda_mmqc.cli run fig-checklist --check micrograph-scale-bar --mock
INFO - Wrote 38 mock prediction(s) to /tmp/gate4b
predictions: /tmp/gate4b
```

### One complete prediction directory

```text
<predictions>/10.1038_s44321-025-00219-1/content/1/
    prediction.json
    intermediates/
        skill_trace.json
```

The example's relative source path is the directory key, which is what
`load_predictions()` already expects from Milestone 1, so `run` output feeds
`score` with no adapter.

### `prediction.json`

```json
{
  "outputs": [
    { "panel_label": "Ai",  "micrograph": "yes", "scale_bar_on_image": "yes",
      "scale_bar_defined_in_caption": "no", "from_the_caption": "",
      "scale_bar_defined_in_image": "yes", "from_the_image": "2 μm" },
    { "panel_label": "Aii", "micrograph": "yes", ... },
    ...
  ]
}
```

Schema-valid, and carrying the `Ai`/`Aii` labels decided at gate 2A.

### `intermediates/skill_trace.json`

```json
[
  {
    "skill": "identify-panels",
    "version": "v1",
    "tool_input": { "name": "identify-panels" },
    "tool_use_id": "mock-0000",
    "timestamp": null,
    "source": "mock"
  }
]
```

A live trace differs in three fields: `timestamp` is an ISO instant rather than
`null`, `tool_use_id` is the SDK's id rather than `mock-NNNN`, and `source` is
`"hook"`. **That last field is the one to look at first in any report** — it is
what distinguishes a trace that observed a session from one generated out of
frontmatter.

### Declared versus observed

`compare_declared_and_observed()` returns four lists: `declared`, `observed`,
`declared_not_observed`, `observed_not_declared`. Diagnostic only — a missing
hop is a prompt-authoring problem to fix in the skill text, never something the
runner repairs by calling the skill itself.

### Open questions for the reviewer

1. **Is the sidecar layout right?** `intermediates/` sits beside
   `prediction.json` and is ignored by `load_predictions()`. Intermediate
   artifacts such as `panels.json` will land there too in a live run.
2. **Should the mock trace exist at all?** It is generated from frontmatter and
   therefore proves nothing about discovery. It is there so the shape can be
   reviewed before spending money, and marked `source: "mock"` so it cannot be
   mistaken for evidence. The alternative is an empty trace.
3. **Is `timestamp: null` acceptable in mock**, or should it be a fixed
   sentinel so mock output is byte-stable across runs?

---

## Human gate 4C — NOT REACHED

**Decision:** may this run against a real model, with which credentials, which
model, and how many examples?

**Status: NOT REACHED. This is where the work stops.**

Everything up to the session boundary is built and tested. The next action
spends money and uses credentials, and the plan reserves that for a person.
`run` without `--mock` returns exit code 2 rather than proceeding.

When this gate is taken it needs:

- the exact command, the example count (*a handful — never the full
  checklist*), the model identifier, and a rough cost estimate;
- confirmation that the credential in `.env` is the intended one;
- **and the outstanding half of gate 3B**: the SDK's reported tool set from the
  first session's `init` message, diffed against the allowlist, checked before
  any result from that session is trusted.

---

## The gate 3B follow-through, now built

Gate 3B asked *"what can we do to have more human input here?"*. The answer
recorded there — that it has to be a `PreToolUse` hook rather than
`canUseTool`, because the SDK never calls `canUseTool` under `dontAsk` and
skips it for auto-approved tools in every mode — is now implemented.

| Piece | Behaviour |
|---|---|
| `ToolAuditLog` | Records **every** tool call attempted, with the decision and reason, flushed to disk per call. Always on |
| `make_pretooluse_hook()` | The hook. Records, and optionally consults an approver. Only ever *narrows*: it can deny what the profile allowed, never allow what the profile denied |
| `interactive_approver()` | Asks before each call. `a` = always-for-this-tool, so a supervised run stays finishable |
| `run --approve-tools` | Opt-in flag, for the handful of examples gate 4C would authorise |

Two instruments now exist and they answer different questions. The **skill
trace** answers *did discovery work* — it records only `Skill` calls. The
**audit** answers *what did the session try to do* — a `Read` aimed outside
the runtime is invisible in the first and obvious in the second. Written to
`intermediates/tool_audit.json` beside the trace.

Three mutations confirm the behaviour is load-bearing: suppressing denials
from the audit, treating an empty answer as consent, and letting "always" leak
across tools each fail a named test. The empty-answer one matters most —
**silence is not consent.**

The hook travels through `session_options()` as a plain callable and only
becomes an SDK `HookMatcher` at the client boundary, so the permission profile
stays reviewable and testable without importing the SDK.

## Where this leaves Milestone 5

| Item | Why |
|---|---|
| **Gate 4C, then the reported-tool-set diff** | The containment argument rests on `dontAsk` and the scoped rules behaving as documented; both are verified as *accepted values*, neither yet as *observed behaviour* |
| **Build the `PreToolUse` audit hook** | Promised at gate 3B as the answer to "more human input"; `canUseTool` cannot serve under `dontAsk` |
| Wire `--approve-tools` for the supervised first run | Same gate; scoped to the handful of examples 4C authorises |
| Decide whether the `mcp` constraint conflict is acceptable | Gate 4A, question 1 — the one answer that could invalidate the dependency |
| ARM64 Windows needs a separate Claude Code install | Gate 4A, question 2 |


---

## The attempted live run (gate 4C)

**Authorised:** *"yes, do a small run"*. **Outcome: all three examples failed at
authentication. Nothing was spent, and no session reached the model.**

```
run fig-checklist --check micrograph-scale-bar --keep-runtime
    --example 10.1038_emboj.2009.340/content/3
    --example 10.1038_s44321-025-00219-1/content/1
    --example 10.15252_emmm.201404392/content/3
```

Examples chosen deliberately rather than taken off the top of the benchmark:
all three have micrograph panels (so the check does something), PNG/JPG rather
than `.webp`, and short captions. One is the `Ai`/`Aii` figure from gate 2A, so
it would also have exercised the sub-panel rule.

### Why it failed

`ANTHROPIC_API_KEY` is present in `.env` **but empty** — length 0. The bundled
CLI fell back to this machine's personal Claude Code OAuth session, which has
expired:

```
Failed to authenticate: OAuth session expired and could not be refreshed
```

**A correction to the record.** At the 4C stop this document previously stated
that "a key **is** present in `.env` … so a session would have authenticated".
That was wrong: the check behind it was `grep -c ANTHROPIC_API_KEY .env`, which
counts the *line*, not its value. The stop was still real — nothing was run —
but the evidence given for it was not.

OAuth is not the path regardless of expiry: Anthropic's SDK documentation
states that claude.ai login is not permitted for third-party SDK agents. A real
`ANTHROPIC_API_KEY`, or a Bedrock/Vertex/Foundry configuration, is required.

### What the run proved anyway

The plumbing worked end to end up to the auth boundary: runtime assembled per
example, session started, the failure recorded per example **without ending the
batch**, no prediction written for a failed session, runtimes kept for
inspection. The failure was clean and diagnostic rather than a crash.

---

## Two containment defects the attempted run exposed

The session reported its own configuration in the `init` message before dying,
which is the evidence **gate 3B asked for and could not obtain**. It was worth
the attempt on its own.

### Defect 1 — twenty tools present where the profile named three

| | |
|---|---|
| Allow-listed | `Read`, `Edit`, `Skill` |
| **Actually granted** | **20 tools** |

The bare-name denials *worked*: `Bash`, `BashOutput`, `KillShell`,
`NotebookEdit`, `Task`, `Agent`, `WebFetch`, `WebSearch` were all absent. But
17 tools nobody had considered were in the model's context:

```
CronCreate  CronDelete  CronList  DesignSync  EnterWorktree  ExitWorktree
Glob  Grep  ListAgents  Monitor  PushNotification  ReportFindings
ScheduleWakeup  SendMessage  ToolSearch  Workflow  Write
```

**`SendMessage`, `PushNotification`, `ScheduleWakeup` and `CronCreate` are the
serious ones**: egress for gold-derived content, and the ability to act after
the run has ended. All are now denied by bare name.

`Write` is deliberately **not** denied: the session must create
`prediction.json`, the SDK documents `Edit(path)` as governing every
file-writing tool, and `Edit` alone cannot create a file that does not yet
exist. It stays in context, confined by the scoped `Edit` rule.

### Defect 2 — eighteen skills in the discovery pool

```
ours    : identify-panels, micrograph-scale-bar
FOREIGN : deep-research, design-sync, dataviz, update-config, verify, debug,
          code-review, simplify, batch, fewer-permission-prompts, doctor,
          loop, claude-api, workflow-authoring, run, run-skill-generator
```

Sixteen skills bundled with Claude Code itself. `setting_sources=["project"]`
excludes `~/.claude/skills`, which was the Milestone 3 finding — but **not
skills that ship with the CLI**.

This breaks the constraint stated at gate 4D — *"the agent MUST ONLY find the
leaf's prose alone. nothing else"* — because sixteen foreign descriptions were
competing for attention inside the one measurement this milestone exists to
make. Had the run succeeded, its trace would have been uninterpretable.

**Fixed** by passing `skills` as the explicit list of assembled skill names
rather than `"all"`. This is not preselection: every skill of the checklist is
listed and they all still compete with each other, which is what the plan
requires. It removes contamination, not choice.

### The general lesson

Every value in the permission profile was correct as written, and the
containment was still wrong in two ways. Neither was visible from the
configuration, from the assembled directory, or from any test that did not open
a session. **That is the argument for gate 3B insisting on the SDK's *reported*
tool set rather than the configured one** — and it only paid out because an
authentication failure still produced an `init` message.

---

## What gate 4D still needs

A credential. Everything else is in place, and the two defects above are fixed,
so the next attempt is the first one whose trace would mean anything.
