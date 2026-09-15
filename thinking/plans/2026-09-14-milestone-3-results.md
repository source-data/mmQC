---
title: Milestone 3 results — sealed runtime directory outside the repository
date: 2026-09-14
tags: [agentic, milestone, runtime, containment, results]
plan: 2026-09-02-agentic-checklist-skills.md
status: implementation complete; 3A and 3B resolved with corrections applied 2026-09-14; 3C clarified and re-walked
---

# Milestone 3 Results

Outcome record for **Milestone 3: Sealed Runtime Directory Outside the
Repository** of
[`2026-09-02-agentic-checklist-skills.md`](2026-09-02-agentic-checklist-skills.md).

**Deliverable:** `cli.py` assembles a self-contained runtime directory in a temp
location outside the repo, containing exactly the skills and the one example the
agent may see — with tests proving the agent cannot reach anything else.

> ## Gate status
>
> | Gate | Status |
> |---|---|
> | Automatic (Step 8) | **passed** — 174 tests, suite failure set unchanged at 62 lines |
> | **3A** — the runtime root | **reviewed 2026-09-14; OS-independence required and delivered** |
> | **3B** — the permission allowlist | **reviewed 2026-09-14; two of three answered, the third produced a correction** |
> | **3C** — a real assembled runtime | **question clarified; re-walked after the 3B correction** |
>
> **The review changed the implementation.** Reviewer feedback on 3B/3C
> prompted a re-reading of the SDK's permission documentation, which showed
> the first profile was **not** the lockdown it claimed to be. Two defects
> were found and fixed — see
> [the permission correction](#the-permission-correction-what-the-review-turned-up).
> Gate 3C's walk was redone against the corrected profile.
>
> Milestone 4 remains blocked until the 3B sign-off is recorded against the
> corrected profile. No Agent SDK dependency was added and no code path opens
> a session.

- **Branch:** `agentic`, uncommitted in the working tree
- **Measured:** 2026-09-14, Python 3.12.14, macOS

---

## The finding that shaped this milestone

Before designing assembly I checked how the Agent SDK actually discovers
skills, against Anthropic's primary documentation. It defeats the plan's
containment assumption in a way the runtime root cannot fix:

> *"Skills are discovered through the filesystem setting sources. With default
> `query()` options, the SDK loads user and project sources, so skills in
> `~/.claude/skills/`, `<cwd>/.claude/skills/`, and `.claude/skills/` in any
> parent directory of `<cwd>` up to the repository root are available."*
> — [Agent SDK: Extend agents with skills](https://code.claude.com/docs/en/agent-sdk/skills)

The plan anticipated **repo-level** leakage and solved it by putting the runtime
outside the repo. It did not anticipate the **user scope**: `~/.claude/skills/`
loads regardless of where `cwd` sits, so no choice of root excludes it.

Why that matters more than it first appears: on a machine where an operator has
personal skills installed, those descriptions join a scored run — silently, and
differently on every machine. Milestone 4 exists to measure whether *our* prose
reaches *our* skills with only the intended descriptions competing. Foreign
descriptions in the pool corrupt that measurement without producing any error.

**Resolution, implemented and pinned:** `AGENTIC_SETTING_SOURCES = ("project",)`.
Omitting `"user"` is what excludes `~/.claude/skills/`; because the runtime root
is outside any repository, `"project"` then resolves to exactly the assembled
tree. Widening it is documented as a containment change requiring the same
scrutiny as widening the tool allowlist.

This is recorded as an **addition to gate 3A's scope**: it is a third
containment surface alongside the root and the tool allowlist, and the plan
names only the other two.

---

## What shipped

| File | Status | What |
|---|---|---|
| `soda_mmqc/config.py` | modified | `AGENTIC_RUNTIME_DIR` and the runtime subdirectory layout; `resolve_agentic_runtime_root()` with a repo-internal guard; `AGENTIC_SETTING_SOURCES`; the permission profile (`AGENTIC_ALLOWED_TOOLS`, `AGENTIC_FORBIDDEN_TOOLS`, `AGENTIC_PERMISSION_MODE`) |
| `soda_mmqc/cli.py` | modified | `RuntimeLayout`, `select_versions`, `assemble_runtime`, `_assert_sealed`, `runtime_session`, `session_options`, `describe_permission_profile`, and an `assemble` subcommand |
| `tests/test_agentic_cli.py` | modified | 43 new tests across six classes |

No Agent SDK dependency was added — that is Milestone 4 Step 1, behind gate 4A.
`session_options()` returns a plain dict, so the profile is reviewable and
testable now and becomes the SDK call site later.

### The assembled layout

```text
<runtime root>/
  ORIENTATION.md
  .claude/skills/
    identify-panels/SKILL.md          # version flattened away
    identify-panels/schema.json
    micrograph-scale-bar/SKILL.md
    micrograph-scale-bar/schema.json  # the final output contract
  input/
    caption.txt
    44321_2025_219_fig1_html.png
    10.1038-s44321-025-00219-1Figure1.pptx
  artifacts/                          # empty, the only writable location
```

Three deliberate choices:

- **Versions are flattened.** The SDK looks for `<name>/SKILL.md`, so a
  surviving `v1/` would mean the skill is not found at all. Exactly one version
  per name reaches the runtime; until Milestone 6's manifest exists, the default
  is the highest `vN`, and `select_versions()` already accepts pins so the
  manifest can drop in without reshaping assembly.
- **Only `content/` is copied.** An example directory also holds `checks/`,
  which is the answer key. The copy is scoped to the input subdirectory rather
  than filtered afterwards, so gold is never even walked.
- **`_assert_sealed()` runs on every assembly, in production.** It refuses to
  hand over a runtime containing a contract file, a `checks/` directory, or any
  symlink. This is redundant with the tests by design: the cost of a leak is a
  scored run that quietly saw the answer key, so the assembler checks its own
  output rather than trusting that the tests covered every path.

---

## The permission correction: what the review turned up

Gate 3B asked whether a stricter mode was needed and how to get more human
input; gate 3C asked, in effect, why a route out should exist at all. Both
questions sent me back to the SDK's permission documentation, and **the first
profile was not the lockdown it claimed to be.** Two defects, both real:

### Defect 1 — `allowed_tools` is not an allowlist

> *"`allowed_tools` and `disallowed_tools` add entries to the allow and deny
> rule lists. **Any other tool not listed in `allowed_tools` is still
> available to Claude**, and a call to it that needs approval falls through to
> the permission mode and `canUseTool`."*

The profile listed `["Read", "Write", "Skill"]` and called it "the complete
set of tools the session may use". It was not: it was a list of
*auto-approvals*, and every unlisted tool remained reachable, resolving
through a `canUseTool` callback that was never supplied.

**Fix:** `permission_mode: "dontAsk"`, which the documentation names as the
locked-down pairing — *"Any call that would otherwise prompt is denied."* The
mode is what makes the list total. The original `"default"` was the weakest
choice available.

This also vindicates the bare-name denials, which had looked like belt and
braces. They are not: even under `dontAsk`, *"tools like `Agent` that don't ask
before running"* still run, and *"to put a tool out of Claude's reach entirely,
add its bare name to `disallowedTools`"*. For `Agent` in particular the denial
is the only thing that works.

### Defect 2 — the tools were not scoped to paths

This is the one gate 3C's question points at. A bare `Read` auto-approves
reading **anything on disk** — the repository, the gold, `~/.ssh`. The *runtime
directory* had no route out, but the *permission profile* did, and a filesystem
walk could never have shown it.

**Fix:** scope the rules to paths built from the layout:

```
Read(//<runtime root>/**)
Edit(//<runtime artifacts>/**)
Skill
```

Two traps worth recording, both documented and both easy to walk into:

- **`Edit`, not `Write`.** *"`Edit(path)` rules govern all built-in tools that
  write files, including `Write` and `NotebookEdit`; a `Write(path)` rule is
  never matched by the file permission checks."* A scoped `Write(...)` rule
  silently matches nothing.
- **`//path`, not `/path`.** A single leading slash anchors the rule at the
  session's working directory rather than the filesystem root.

### The corrected profile

```python
{
  "cwd":              "<runtime root>",
  "setting_sources":  ["project"],
  "skills":           "all",
  "permission_mode":  "dontAsk",
  "allowed_tools":    ["Read(//<root>/**)", "Edit(//<artifacts>/**)", "Skill"],
  "disallowed_tools": ["Agent", "Bash", "BashOutput", "KillShell",
                       "NotebookEdit", "Task", "WebFetch", "WebSearch"],
}
```

Four mutations confirm each property is load-bearing: reverting the mode to
`default`, replacing the scoped read with a bare `Read`, using `Write(...)`
instead of `Edit(...)`, and reverting the case-insensitive repo check each fail
a named test.

---

## Human gate 3A — the runtime root

**Decision:** is the chosen default root acceptable on the machines this will
actually run on?

**Status: REVIEWED 2026-09-14 — "Runtime should be independent on OS. This
should run on any given OS."**

The original artifact answered for one laptop, with `tmutil` output and a POSIX
mode bit. That is evidence about a machine, not about the design. The
guarantees have been moved into portable code, and the per-OS evidence is now
illustration rather than the argument.

### What changed

| Before | Now |
|---|---|
| Root verified by hand on macOS | Default is `tempfile.gettempdir()` — already correct per platform (`/tmp`, `AppData\Local\Temp`, `/var/folders/...`) with **no branching** |
| Repo containment via `repo_root in root.parents` | Case-**insensitive** comparison. macOS and Windows would otherwise let a differently-cased path past a rule their own filesystem treats as the same place — a real hole, not a hypothetical one |
| Cloud-sync ruled out by looking at one `$HOME` | `CLOUD_SYNC_MARKERS` refuses Dropbox, OneDrive, Google Drive, iCloud, Box, pCloud, Nextcloud and Yandex paths **on every OS**, case-insensitively |
| Filesystem writability assumed | A test creates and removes a probe directory under the resolved root |
| Paths rendered natively | Orientation file and permission rules use POSIX separators, so Windows does not produce backslash surprises in the one file that tells the agent where things are |

The plan says a person must look at the machine because sync detection is not
testable. That holds for an *arbitrary* sync tool — but the common clients have
stable directory names on every platform, so the common case is now checked by
code and does not depend on who is looking or what they are running.

Nine tests cover this (`TestRuntimeRootIsOsNeutral`,
`TestRuntimeContentIsOsNeutral`), and reverting the case-insensitive check
fails one of them.

### Original artifact, retained as illustration

### Resolved path, developer laptop (macOS)

```
/private/var/folders/rk/2dnm42ws26x9p1xs9_wwd3tw0000gr/T
```

from `tempfile.gettempdir()`, i.e. the per-user `TMPDIR`. Overridable with
`SODA_MMQC_AGENTIC_RUNTIME_DIR`.

| Requirement | Evidence |
|---|---|
| Outside the repository | No shared ancestor with `/Users/cagataygursoy/Repos/mmQC`. `resolve_agentic_runtime_root()` raises if a configured root resolves inside the repo — verified firing |
| Outside cloud-synced directories | No `~/Library/Mobile Documents`, `~/Library/CloudStorage`, `~/Dropbox`, `~/OneDrive` or `~/Google Drive` exists on this machine at all |
| Outside backed-up directories | `tmutil isexcluded` → **`[Excluded]`** for this path. Note `/private/var/folders` itself reports `[Included]`, so the exclusion applies to the per-user `T` directory specifically — worth re-checking if the path template ever changes |
| Cleanup genuinely removes data | `/dev/disk3s1`, APFS, mounted `local`. Not a network mount, not an overlay |
| Not readable by other users | Mode `drwx------`, owner `cagataygursoy` |

### CI

`.github/workflows/ci.yml` runs `just qa` in `mmqc_utils` only, so **these tests
do not run in CI today**. On a GitHub `ubuntu-latest` runner the default would
resolve to `/tmp` — outside any checkout and ephemeral per job — but that is a
prediction, not a measurement. Wiring the agentic tests into CI is worth its own
task rather than being assumed.

### Open questions for the reviewer

1. **The setting-sources addition** described above. It belongs to this gate's
   decision because it changes what "sealed" means, and the plan's text does not
   cover it.
2. **macOS temp reaping.** `/private/var/folders` is cleaned by the OS on a
   schedule. Harmless for `--keep-runtime` debugging within a session, but a
   runtime kept overnight may vanish. Say so if that is surprising.
3. **CI is a prediction, not a measurement** — see above.

---

## Human gate 3B — the permission allowlist

**Decision:** is this allowlist exactly what the agent may do, and is every
`needs`-justified exception acceptable?

**Status: REVIEWED 2026-09-14.**

| Question | Answer | Outcome |
|---|---|---|
| 1. Is `Read`/`Write`/`Skill` sufficient? | *"Read/Write/Skill is sufficient"* | **Accepted.** No `Glob`/`Grep`. The set is now `Read`/`Edit`/`Skill` — `Edit` is the same capability under the name the SDK actually honours for writes |
| 2. `skills="all"` reasoning | *"This reasoning should hold, if required revisit in Milestone 4"* | **Accepted with a revisit condition**, recorded in the Milestone 4 carry-forward |
| 3. Stricter mode / more human input? | *"We might need a stricter mode here; what can we do to have more human input?"* | **Produced a correction** — see below and [the permission correction](#the-permission-correction-what-the-review-turned-up) |

### Answering question 3: the stricter mode, and the human-input tension

**Stricter mode: yes, and the original was wrong.** `permission_mode` is now
`dontAsk`, the SDK's documented lockdown pairing. Under `default`, unlisted
tools stayed reachable. Also added: path scoping, so `Read` and `Edit` are
confined to the runtime and its artifacts directory rather than the whole disk.

**Human input: there is a genuine tension, and it has to be chosen
deliberately.** Two mechanisms exist and they do not compose:

| Mechanism | Works under `dontAsk`? | Notes |
|---|---|---|
| `canUseTool` callback | **No** — *"`canUseTool` is never called"* | Also skipped for any auto-approved tool even in other modes, so it would give false assurance: the calls you most want to see are the ones it never receives |
| `PreToolUse` hook | **Yes** | *"hooks run before every other step, and a hook deny applies even in `bypassPermissions`"* — it sees **every** call in **every** mode and can allow, deny, or log |

So per-call human approval via `canUseTool` is incompatible with the strictest
mode. The way to get human oversight without weakening containment is a
`PreToolUse` hook. Recommended shape, for Milestone 4:

1. **An audit hook, always on.** Record every tool call — tool, resource,
   timestamp — under the runtime artifacts. Milestone 4 already requires a
   `PostToolUse` hook for the `Skill` trace, so this is the same machinery
   extended to a complete record rather than new infrastructure.
2. **An opt-in interactive hook** (`--approve-tools`) that prompts per call.
   Impractical across 38 examples, but exactly right for the handful of
   supervised examples gate 4C authorises for the first live run.

Neither is built here: hooks are SDK objects, and the SDK is not a dependency
until Milestone 4 Step 1 behind gate 4A. Building them now would smuggle in the
dependency this plan deliberately gates.

### Artifact

### The literal profile, as `session_options()` returns it

```python
{
  "cwd":              "<runtime root>",
  "setting_sources":  ["project"],
  "skills":           "all",
  "permission_mode":  "dontAsk",
  "allowed_tools":    ["Read(//<root>/**)", "Edit(//<artifacts>/**)", "Skill"],
  "disallowed_tools": ["Agent", "Bash", "BashOutput", "KillShell",
                       "NotebookEdit", "Task", "WebFetch", "WebSearch"],
}
```

*(Superseded the original `["Read", "Write", "Skill"]` / `"default"` profile —
see [the permission correction](#the-permission-correction-what-the-review-turned-up).)*

### Allowed — and why each is needed

| Rule | Why |
|---|---|
| `Read(//<root>/**)` | Read the copied caption and image, and the schema the answer must satisfy — **and nothing outside the runtime** |
| `Edit(//<artifacts>/**)` | Write the prediction and intermediates. `Edit` rather than `Write` because the SDK documents `Edit(path)` as governing every file-writing tool while `Write(path)` "is never matched by the file permission checks" |
| `Skill` | Invoke a sub-skill. This is the mechanism the whole project is testing |

### Denied, each with a reason and its own test

| Tool | Reason |
|---|---|
| `Bash`, `BashOutput`, `KillShell` | Shell access escapes the sealed runtime, which would make every other control cosmetic |
| `NotebookEdit` | Executes code |
| `Task`, `Agent` | A subagent negotiates its own context and permissions, reopening containment from another direction — **and its skill calls do not appear in this session's trace**, so the per-example record of which skills fired would be incomplete. That second reason is the one that matters for Milestone 4 |
| `WebFetch`, `WebSearch` | No skill's `needs` justifies network access. A fetch is both an exfiltration path for gold-derived content and a source of irreproducibility |

### `needs`-justified exceptions: none

`test_no_skill_requests_a_network_capability` asserts that **no skill in
`fig-checklist` declares any `needs` at all**. The network denial therefore
stands unconditionally today, and the test fails the moment a skill asks for
something — which forces the justification back to a gate rather than letting it
arrive as an implementation detail.

### The part of this gate that cannot be completed yet

The gate asks for *"the full tool set the SDK reports for that configuration,
and the diff between them."* **That half is not produced here**, because the SDK
is not a dependency until Milestone 4 Step 1 (behind gate 4A), and inventing the
dependency early to satisfy a gate would invert the plan's own ordering.

What exists instead is the allowlist, the denial reasons, and an equality test
on the allowlist. **The reported-tool-set comparison must be completed at
Milestone 4 before the first session is opened.** This is a real gap in the
evidence, recorded rather than papered over.

### Reviewer answers, recorded

1. **Sufficiency** — *"Read/Write/Skill is sufficient"*. Accepted; no `Glob` or
   `Grep`. If a session flails looking for the image, that is the first thing
   to revisit, and any widening is a new gate.
2. **`skills="all"`** — *"This reasoning should hold, if required revisit in
   Milestone 4"*. Accepted with the revisit condition carried forward.
3. **Stricter mode** — *"We might need a stricter mode here"*. Correct, and the
   original was the weakest available. Now `dontAsk` plus path-scoped rules.
   Human input has to come from a `PreToolUse` hook rather than `canUseTool`;
   see above.

---

## Human gate 3C — a real assembled runtime

**Decision:** does an actual runtime directory contain a route out?

**Status: QUESTION CLARIFIED; RE-WALKED 2026-09-14 against the corrected
profile.**

> *"Why does the runtime directory should contain a route out? I think this is
> unsafe. Let's discuss this."*

**It should not, and it does not.** The gate's wording is a question to
investigate, not a requirement — "does it contain a route out?" with the
expected answer **no**. The plan's own Blocks clause makes that explicit:
*"Confirm there is no route to the repo, to gold data, or to another example."*
Poor phrasing on the gate's part; nothing in the design wants an escape hatch.

**But the instinct behind the question was right, and it found something a
directory walk never could.** The runtime *directory* had no route out. The
*permission profile* did: an unscoped `Read` auto-approves reading anything on
disk, including the repository and the gold, and `permission_mode: "default"`
left unlisted tools reachable. Both are now fixed — see
[the permission correction](#the-permission-correction-what-the-review-turned-up).

The lesson worth keeping: **containment has two surfaces, and only one of them
is visible in a `find` listing.** This gate's artifact walks the directory; it
cannot see what the tools are permitted to reach. Both have to be checked, and
the second is the one that was wrong.

### Artifact

Produced with the command a reviewer can re-run:

```bash
python -m soda_mmqc.cli assemble fig-checklist \
    --check micrograph-scale-bar \
    --example 10.1038_s44321-025-00219-1/content/1 \
    --keep-runtime
```

### The complete tree, walked

```text
./.claude
./.claude/skills
./.claude/skills/identify-panels
./.claude/skills/identify-panels/SKILL.md
./.claude/skills/identify-panels/schema.json
./.claude/skills/micrograph-scale-bar
./.claude/skills/micrograph-scale-bar/SKILL.md
./.claude/skills/micrograph-scale-bar/schema.json
./ORIENTATION.md
./artifacts
./input
./input/10.1038-s44321-025-00219-1Figure1.pptx
./input/44321_2025_219_fig1_html.png
./input/caption.txt
```

That is every entry, hidden files included. Thirteen entries, no more.

### Route-out checks

| Check | Result |
|---|---|
| Symlinks anywhere | **0** |
| Hard links with `nlink > 1` | **none** |
| Files mentioning the repository path | **none** |
| `expected_output.json` / `benchmark.json` / `eval-manifest.json` / `checks/` / `prompts/` | **0 occurrences** |
| Another example present | No — only `content/1` inputs |
| `.claude` in any ancestor of the runtime | **none**, from the runtime root up to `/` |
| `~/.claude/skills` | **absent on this machine** — and excluded by setting sources regardless, so the guarantee does not depend on that luck |

**Re-walked 2026-09-14 against the corrected profile.** Identical tree — 13
entries, 0 symlinks, 0 gold or contract files, 0 files referencing the
repository path. The directory was never the problem; the profile was.

### The second surface: what the tools can reach

A `find` listing cannot answer this, which is why it is tabulated separately.

| Reach | Before | After |
|---|---|---|
| Read the repository / gold / `~/.ssh` | **permitted** — bare `Read` auto-approves any path | **denied** — `Read(//<runtime>/**)` |
| Write outside the runtime | **permitted** — bare `Write` | **denied** — `Edit(//<artifacts>/**)`; writes are confined to `artifacts/`, narrower than the read scope |
| Call an unlisted tool | **reachable** — fell through to a `canUseTool` that was never supplied | **denied** — `permission_mode: "dontAsk"` |
| Spawn a subagent | denied by bare name | denied by bare name — and the docs confirm this is the *only* thing that works, since `Agent` runs without asking even under `dontAsk` |

### The generated orientation file

```markdown
# This run

You are checking one figure against one quality-control check.

- **Entry point:** the `micrograph-scale-bar` skill. Start there.
- **Figure inputs:** `input/` — the caption and image for
  this figure, and nothing else.
- **Write results to:** `artifacts/` — the only writable
  location. Put the final answer in
  `artifacts/prediction.json`.
- **Final output schema:** `.claude/skills/micrograph-scale-bar/schema.json`.
  The answer must conform to it exactly.

Other skills are available to you. Read their descriptions and use the
`Skill` tool to call whichever the work needs.
```

It names the entry point and the roots and **stops there**. It does not name
`identify-panels`, does not order the hops, and does not describe the graph —
tested by `test_it_does_not_list_the_entry_points_dependencies`. Naming the
dependency here would make Milestone 4's trace a measurement of our own control
flow rather than of whether the prose works.

### Open question for the reviewer

The permission profile printed above matches what gate 3B proposes, but 3C asks
you to confirm it matches what was *approved* at 3B — and 3B is not yet
approved. **These two gates have to be taken in order**, even though the
artifacts were produced together.

---

## Automatic gate

**Command:** `pytest tests/test_agentic_cli.py -v`

```
158 passed in 3.20s
```

121 before this milestone, **158 after** — 37 new tests. Whole suite: the sorted
`FAILED`/`ERROR` line set is **62 lines**, identical to the Milestone 1 and 2
baseline. Nothing pre-existing moved.

### Mutation testing

| Mutation | Caught by |
|---|---|
| `AGENTIC_ALLOWED_TOOLS` widened with `Bash` | 3 tests, incl. the allowlist equality check and the named no-shell test |
| `AGENTIC_SETTING_SOURCES` restored to `("user", "project")` | 2 tests |
| The assembler copies the whole example directory instead of `content/` | 4 tests failed **and 18 errored** — because `_assert_sealed()` refused to build the runtime at all |

The third is the most informative: the production guard fires *before* a leaky
runtime exists, so the failure is a refusal rather than a test noticing
afterwards. That is the behaviour a containment check should have.

### Test coverage added (37)

| Class | n | Covers |
|---|---|---|
| `TestRuntimeRootIsOutsideTheRepo` | 3 | Default root outside the repo; a repo-internal root is refused; setting sources exclude the user scope |
| `TestRuntimeSkillPlacement` | 7 | Skills at `.claude/skills/<name>/SKILL.md`; **every** skill present, nothing pruned to the named check; the shared skill survives; one version per name; no `vN/` directory survives; no symlink and no copy of the store; each skill keeps its runtime schema |
| `TestRuntimeHoldsOneExampleAndNoGold` | 6 | Inputs copied; **no gold reaches the runtime**; `checks/` never copied; no other example; `prompts/` not copied; artifacts root exists and is empty |
| `TestRuntimeOrientation` | 4 | Generated; names the entry point and roots; **does not name the dependency**; leaks no repository path |
| `TestRuntimeLifecycle` | 5 | Removed by default; kept with `keep=True`; removed after an exception; kept after an exception; assembly is atomic — a failure leaves no half-built directory |
| `TestPermissionProfile` | 12 | Allowlist equality; a named test per forbidden tool (4 shell, 2 subagent, 2 network); no skill requests a network capability; allowed and forbidden never overlap; session rooted in the runtime not the repo; user scope excluded; every assembled skill stays invocable; the printed profile carries every tool and reason |

---

## Where this leaves Milestone 4

Milestone 4 runs one agent session per example. From this milestone it inherits:

- `session_options(layout)` — the exact dict to hand the SDK, already reviewed
  in shape if not yet in behaviour.
- `runtime_session(...)` — assembly plus guaranteed cleanup, including after a
  failure, with `--keep-runtime` for debugging.
- `layout.artifacts_root` as the only writable location, and
  `layout.schema_path` as the contract the final JSON must satisfy.

**Carried forward as work, not assumptions:**

| Item | Why it matters |
|---|---|
| **Complete gate 3B's missing half** — the SDK's reported tool set versus the allowlist, diffed — before the first session opens | The gate explicitly asks for it; it could not be produced without the dependency |
| **Build the `PreToolUse` audit hook**, and the opt-in `--approve-tools` interactive hook | Gate 3B's answer to "more human input". `canUseTool` cannot serve this under `dontAsk`, so the hook is the only mechanism. The audit hook shares machinery with the `Skill` trace Milestone 4 already requires |
| **Verify `dontAsk` and the scoped rules behave as documented** against the installed package | The whole containment argument now rests on `dontAsk` denying unlisted tools and on `Edit(...)` governing writes. Both are documented; neither is yet observed |
| Confirm the SDK accepts `setting_sources`/`skills`/`allowed_tools`/`permission_mode` under the names used here | `session_options()` keys follow the documented Python API but are unverified against the installed package |
| **Revisit `skills="all"` if needed** | Accepted at gate 3B with exactly this condition |
| Decide whether `Glob`/`Grep` are needed | Ruled out at gate 3B; any widening is a new gate |
| Wire the agentic tests into CI | They do not run there today |
| **Verify on a non-macOS platform** | The OS-neutrality work is by construction and unit-tested, but has only been *executed* on macOS |
