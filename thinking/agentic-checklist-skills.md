---
title: Agentic checklist skills (design brief)
date: 2026-07-22
tags: [agentic, skills, checklist, anthropic, evaluation, mcp]
status: draft
---

# Agentic checklist skills — design brief

Planning only. No implementation in this note.

## Goal

Replace the current one-prompt-per-check model call (`run_model` → `generate_response` with prompt + schema) with a **hierarchy of nested skills** per checklist (dependencies form a directed acyclic graph, or DAG):

- Skills can be **chained and reused** (e.g. panel identification → applicability → leaf analysis).
- Skills may invoke **Python tools** (and later MCP).
- **CLI surface of `run.py` / `evaluate` stays the same** for running checks on examples.
- **Evaluation is split out** into a separate CLI (cleaner than today’s combined run+score path).
- First runtime: **Anthropic Claude Agent SDK**; later **OpenAI Agents**, behind a small code layer.

## Current state (baseline)

Today a check is a directory under `soda_mmqc/data/checklist/{checklist}/{check}/` with:

| Asset | Role |
|-------|------|
| `prompts/prompt.N.txt` | Single monolithic instruction |
| `schema.json` | Structured output contract (OpenAI wrapper or inner schema) |
| `eval-manifest.json` | Scoring policy for flat leaf eval |
| `model_config.json` | Optional provider tools / reasoning (mostly OpenAI-shaped) |
| `benchmark.json` | Which examples under `data/examples/` to run |

`run.py` discovers checks, loads examples, caches by key, calls the model once per example+prompt, then scores. See [README](../README.md) and [run.py](../soda_mmqc/scripts/run.py).

There is already a check named `external-data-url-validation-agentic`, but it is still a **single prompt**, not a skill graph.

## Decisions (locked for this brief)

| Topic | Decision |
|-------|----------|
| What owns the skill graph? | The **checklist** (scope of related reusable nested skills) |
| What is a check? | A **leaf skill** in that hierarchy (a skill with no checklist-local dependents; it owns `schema.json`) |
| Leaf contents | Folder with `SKILL.md` + `schema.json` (+ `eval-manifest.json`, `benchmark.json` as today) |
| Intermediate skills | Folder with `SKILL.md`; **may** have a `schema.json` as a **runtime / chaining contract** (not an eval gold target). See “Schemas and evaluation” below. |
| Eval / gold / FlatEvaluator | **Leaves only** — same as today: score final check JSON vs `expected_output.json` + leaf `eval-manifest.json`. Do **not** nest upstream schemas into the scored document. |
| Graph source of truth | each `SKILL.md` **frontmatter** declares `requires` / `produces` to define DAG edges |
| Hierarchy for humans/tools | **Generated** `dag.yaml` + README from skill metadata (not hand-edited) |
| Example / cache loop | **Python orchestrator (A)** — deterministic batching; agent runs **per example** |
| Evaluation | **Separate CLI** from check execution |
| Model/agent config | Skill declares **capability needs**; **checklist-level defaults** are the practical primary config; runner maps needs → Anthropic/OpenAI agent settings |
| Provider priority | Anthropic Agent SDK first; OpenAI Agents later via same abstraction |
| Skill versioning | **Checklist versioning manifest** pins every skill. Runner default = all pinned. CLI may **unpin exactly one** skill; runner sweeps that skill’s versions against the pins. Skill store + runtime assembly; agent sees one version per name. Cache per expanded SkillSet. Langfuse exposes the pinned (production) manifest. |
| Production exposure | **Langfuse remains the surface** that applications use to pull the **production** prompt/skill (as today). Repo/git holds all versions; Langfuse labels/points at what is production for runtime apps. |
| Agent working directory | **Outside the repo**, one per example; skills **copied** into `<runtime>/.claude/skills/`; `setting_sources=["project"]`, `skills=[explicit names]` |
| Example inputs | **Staged** into the runtime dir against a stable workspace contract — not exposed in place via `add_dirs` |
| Gold isolation | Structural: `checks/` is on no path the agent has, plus Bash removed, a deny rule and a `PreToolUse` hook |
| Subagents | **Suppressed** (tool removed, allowlist, no `agents=`, `SubagentStart` alarm). Nested *skills* are unaffected — they run in-session |

## Skill versioning and Langfuse

### The problem

We need all of:

| Consumer | Needs |
|----------|--------|
| Apps (production) | One labeled “production” resolution (today: Langfuse) |
| Benchmarking | Compare skill revisions (`prompt.1` vs `prompt.2` today) — **including** changing one skill in a chain while holding others fixed |
| Agent runtime | **Exactly one** body per skill name (no `SKILL.1` + `SKILL.2` in view) |
| Cache | Correct, non-mysterious keys when a leaf depends on three versioned upstream skills |

**Pure “edit one `SKILL.md`; git history = versions” is not enough** for comparative evaluation: you cannot conveniently pin “leaf@4 + identify-panels@2” vs “leaf@4 + identify-panels@3” and report them side by side the way we do with prompt versions today.

**Side-by-side files in the agent-visible tree** confuse the agent.

So we need an explicit **skill store** (many versions) plus a **runtime assembly** step (one coherent view).

### What a “skill version” is

An immutable, addressable object: `{skill_name, version_id}` → folder contents (`SKILL.md`, and for leaves usually `schema.json` / related contracts).

`version_id` can be an integer, semver, or content hash — the important part is **addressability**, not that it equals a git commit (though the store may live *in* git).

### Proposed model: skill store + runtime assembly

```text
┌──────────────────────────── Skill store (many versions) ────────────────────────────┐
│  skills-store/identify-panels/v1/SKILL.md                                            │
│  skills-store/identify-panels/v2/SKILL.md                                            │
│  skills-store/micrograph-scale-bar/v3/SKILL.md + schema.json                         │
│  skills-store/micrograph-scale-bar/v4/...                                            │
└─────────────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      │  resolve SkillSet (lock / CLI)
                                      ▼
┌──────────────────────── Runtime view (one version per name) ────────────────────────┐
│  <runtime>/.claude/skills/identify-panels      ← copy of store/.../v2               │
│  <runtime>/.claude/skills/micrograph-scale-bar ← copy of store/.../v4               │
│  cwd = <runtime>, outside the repo; agent sees only this tree + CLAUDE.md           │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

- **Store:** all versions coexist; humans and eval tooling can list/compare them; git still versions the store.
- **SkillSet (lockfile):** explicit map of `skill_name → version_id` for a run, e.g.

  ```yaml
  # skillset.yaml (per evaluate run or checked-in “profiles”)
  leaf: micrograph-scale-bar
  skills:
    identify-panels: 2
    micrograph-scale-bar: 4
  ```

- **Assembly:** orchestrator builds a temp runtime directory so the agent sees one `SKILL.md` per name. **Copies, not symlinks** — see “Runtime assembly: copy, don’t symlink”. The versioning model is unaffected; only the mechanism changed.
- **Comparative eval:** run the same examples under SkillSet A vs SkillSet B (two assemblies, two prediction dirs). Reporting keys off SkillSet id, not a single “prompt version” integer.

Langfuse `production` becomes a **named SkillSet** (or a pointer to one): apps fetch that resolution; they do not browse the store.

### Combinatorial explosion (3 × 4 ≠ “run 12”)

If `skill_1` has 3 versions and `skill_2` has 4, the store contains **12 possible** pairings. That does **not** mean evaluation runs the cartesian product.

### Checklist versioning manifest (proposed workflow)

One **versioning manifest** per checklist pins **every** skill in that checklist’s DAG to exactly one version.

```yaml
# fig-checklist/version-manifest.yaml  (name TBD)
skills:
  identify-panels: 2
  applicability-micrograph: 1
  micrograph-scale-bar: 4
  # ... every skill in the checklist must appear with a pin
```

**Rules:**

1. **Complete pins.** The manifest must list every skill in the checklist; each has a pinned version. Creating a new skill requires adding it to the manifest (CI/check fails otherwise).
2. **Pre-run validation (required).** Before assembling the runtime or calling the agent, the orchestrator **validates** the manifest against the checklist skill inventory (from `requires`/`produces` / generated `dag.yaml`):
   - every skill in the DAG appears in the manifest with a pin;
   - every pin resolves to an existing version in the skill store;
   - no unknown skill names in the manifest (orphan pins);
   - if `--unpin` is set: that skill exists, and each version to sweep exists in the store.
   Fail fast with a clear error if any pin is missing or invalid — do not run partially.
3. **Baseline run.** `evaluate` with no unpin → assemble runtime from the manifest as-is (one SkillSet). This is the default / production-shaped run.
4. **Unpin via CLI, one skill only.** e.g. `--unpin micrograph-scale-bar` (or `--unpin micrograph-scale-bar --versions 3,4` if we want a subset).
5. **What the runner expands.** With one skill unpinned, “combinations” means: **for each version of that skill** (or each version you list), run once with **all other skills still at manifest pins**.  
   - Unpin leaf with 4 versions → **4** runs, not a grid.  
   - Unpinning two skills at once is **rejected** (keeps eval 1-dimensional).
6. **Agent view.** Each of those runs still gets one assembled tree (symlinks); the agent never sees other versions.

So: inventory can grow per skill; eval cost is `1` (baseline) or `N` (versions of the single unpinned skill).

**Policy summary:** versions are inventory; the **manifest** is the pinned baseline; **unpin one skill** is how you compare; never grid-search the DAG.

### Hard rules

1. **Agent never sees the store** — only the assembled runtime tree.
2. **One name → one version** per assembly.
3. **Manifest is complete** — every checklist skill pinned; new skills must be registered.
4. **Validate before run** — missing/invalid pins abort the run; no partial execution.
5. **At most one unpinned skill per run** — runner expands that skill’s versions against the manifest pins.
6. **No cartesian eval** across multiple unpinned skills.

### Caching: the chain-version mess (and how to make it boring)

Worry: leaf check + three chained skills at independent versions → combinatorial cache nightmare **if** we treated every pairing as a first-class eval target or tried clever partial reuse across the matrix.

**Mitigation — treat the SkillSet as an atomic unit (and keep the set of SkillSets small):**

| Do | Don’t |
|----|--------|
| Cache key includes `skillset_hash = hash(sorted(skill→version→content_hash))` | Cache “leaf only” and hope upstream matches |
| One prediction artifact per `(example, skillset_hash, model, config)` | Reuse a leaf result when only an upstream skill version changed |
| Store `skillset.yaml` + content hashes next to predictions for provenance | Infer versions from filenames after the fact |
| Optional later: cache **intermediate** `produces` artifacts keyed by `(skill, version, input_hash)` if worth the complexity | Build a clever partial-reuse graph in v1 |
| Run baseline + 1D variants | Nested loops over all skill versions |

v1 recommendation: **session-level cache only** (whole check run for one example under one expanded SkillSet from manifest ± one unpin). Intermediate skill caches deferred.

**No second hash needed.** Removing the pre-run closure walk does not touch `skillset_hash`: it hashes the checklist's pinned version manifest (± one unpin), which fixes every skill's version regardless of whether, or how many times, the agent actually invokes a given skill for a particular example — “the agent never sees multiple versions” already guarantees that *if* a skill is called, it resolves to the one pinned version. What changes with agent-driven discovery is only *which skills get exercised*, never *which version they'd resolve to* — so the pre-run cache key is unaffected and stays exactly `(example, skillset_hash, model, config)`. The skill-invocation log (“Logging skill invocations” above) is still worth keeping, but purely as a **debugging artifact**: comparing two examples' logs directly (e.g. “did the leaf skip its declared `requires`?”) is more informative than comparing a hash of them, and there is no caching decision a trace hash would improve on what `skillset_hash` already provides.

Comparative reporting: baseline manifest vs each version of the unpinned skill (same idea as today’s prompt.1 vs prompt.2, with the rest of the chain held fixed).

### Langfuse’s role

- **Not** the multi-version store (the repo skill store is).
- **Is** the app-facing **production** view of the checklist **versioning manifest** (all pins).
- Benchmark against production = run with no unpin (or explicitly use the published manifest).
- Experiments = `--unpin <skill>` locally without publishing.

### Still open

- Store layout on disk (`skills-store/<name>/vN/` vs content-addressed `sha256/…` with names as tags).
- Whether `version_id` is author-chosen (`v4`) or content hash (tags for human names).
- CLI shape: `--unpin SKILL` and optional `--versions 1,2,4` vs always sweep all versions of the unpinned skill.
- Promote: publish versioning manifest → Langfuse (multi-skill payload or bundled closure for legacy apps).
- ~~Symlink vs copy on Windows / sandbox.~~ **Resolved 2026-09-04: copy** (hardlink for bulk inputs) — see “Runtime assembly: copy, don’t symlink”.
- Manifest filename / whether unused skills outside a leaf’s closure must still be pinned (lean yes: whole-checklist manifest).

## Recommended architecture

```text
CLI (evaluate CHECKLIST [--check LEAF] [--model ...] ...)
        │
        ▼
┌─────────────────────── Python orchestrator ───────────────────────┐
│  resolve checklist / leaf(s)                                      │
│  load benchmark examples                                          │
│  cache get/set                                                    │
│  for each example:                                                │
│      run_agent_session(leaf, example, checklist_config)  ─────────┼──► Agent
│  write raw outputs (predictions)                                  │
└───────────────────────────────────────────────────────────────────┘

Separate CLI (e.g. score / evaluate-outputs):
        │
        ▼
  load predictions + expected_output + leaf schema + eval-manifest
  FlatEvaluator → analysis.json / reports
```

### Per-example agent session

1. Load checklist context (`CLAUDE.md` / project instructions describing `soda_mmqc/data`).
2. Invoke the agent with the target leaf as the instruction (e.g. “run check `micrograph-scale-bar` on this example”). **Skill discovery is the agent's responsibility, per example** — there is no pre-run closure walk. The agent reads the leaf's `SKILL.md`, which states its `requires` as an instruction (e.g. “call `identify-panels` first”), and invokes upstream skills itself via nested `Skill` tool calls, passing artifacts via `produces` contracts. `requires`/`produces` frontmatter remains the source of truth for the *generated* `dag.yaml` (docs, manifest validation, CI drift-check) — it is read by tooling, not walked by the runner at execution time.
3. Enforce / request structured output against the **leaf** `schema.json`.
4. Return JSON to the runner for caching and later scoring, together with the per-example skill-invocation log — see “Logging skill invocations” below.

### Logging skill invocations (per example)

Because skill discovery and ordering now happen inside the agent session rather than as a pre-run closure walk, the *actual* sequence of skills a given example exercised is no longer known in advance — it must be observed. This is needed for downstream analysis and debugging (e.g. “did this leaf actually call `identify-panels`, and in what order, for example #42?”), independent of any caching concern.

**Mechanism:** a `PostToolUse` hook (Claude Agent SDK) attached to each per-example session. The hook fires on every tool call with structured `{tool_name, tool_input, tool_use_id}`, taken from the API's own `tool_use` blocks — not from the model's prose. Filtering `tool_name == "Skill"` isolates skill invocations; `tool_input` carries the invoked skill's name/args, `tool_use_id` lets Pre/Post events be correlated if both are needed.

Do **not** use:
- The agent's own natural-language description of what it did (self-report is not verifiable and drifts under prompt/model changes).
- The on-disk Claude Code session transcript (`~/.claude/projects/.../<session-id>.jsonl`) — documented as an internal format that changes between releases; not meant to be parsed by scripts.

**Output:** one skill-invocation log per example run, e.g. `intermediates/<example_id>/skill_trace.json` — an ordered list of `{skill, version, tool_input, timestamp}` entries, written as the hook fires (so it exists even if the session errors out mid-run). This sits alongside the existing intermediate sidecar dumps (see “Schemas and evaluation” above) and is not itself scored by `FlatEvaluator`.

**Use cases:**
- Debugging an unpin sweep: confirm the swept skill was actually invoked (and at the pinned version) rather than assuming it from the manifest.
- Detecting drift: a leaf whose `SKILL.md` declares `requires: [identify-panels]` but whose trace shows it wasn't called is a bug in the skill body, not the runner.
- Comparing two runs of the same configuration directly, if their behavior is ever suspected to differ — see “Caching” below for why this is a log-diffing job, not a hashing one.

### On-disk sketch (illustrative)

```text
soda_mmqc/data/checklist/fig-checklist/
  CLAUDE.md                 # or repo-root CLAUDE.md pointing here
  model_defaults.json       # checklist-level agent defaults (needs → settings)
  dag.yaml                  # GENERATED — do not hand-edit
  README.md                 # GENERATED hierarchy view
  skills/
    identify-panels/
      SKILL.md              # requires: [] ; produces: [panels]
    micrograph-scale-bar/   # LEAF = check
      SKILL.md              # requires: [identify-panels] ; produces: [scale_bar_report]
      schema.json
      eval-manifest.json
      benchmark.json
```

The agent does **not** read this tree directly. Skills are **copied** into a per-example runtime directory outside the repo, at `<runtime>/.claude/skills/<name>/`, with `cwd` pointed there — see “Agent runtime and session isolation (Claude Agent SDK)” above for why symlinks and in-repo working directories were rejected.

### Skill frontmatter (illustrative)

```yaml
---
name: micrograph-scale-bar
description: Check scale bars on micrograph panels.
kind: leaf   # or intermediate
requires: [identify-panels]
produces: [scale_bar_report]
needs: []    # e.g. [web, code] — usually empty; checklist defaults apply
---
```

`needs` is read by **our** runner (unioned into session options). The Agent SDK does apply `allowed-tools` frontmatter for project skills, but not model/effort/budget or the isolation controls — see “Note: frontmatter is only partly provider-enforced (SDK)” under Config model.

`schema.json` on a **leaf** remains the **eval/curation contract**. Upstream skills may also declare a schema — see next section.

## Agent runtime and session isolation (Claude Agent SDK)

Added 2026-09-04, after reading the current [Agent SDK skills](https://code.claude.com/docs/en/agent-sdk/skills) and [permissions](https://code.claude.com/docs/en/agent-sdk/permissions) docs. This section makes the “agent runs per example” line of the architecture concrete, and supersedes the earlier symlink sketch in “On-disk sketch”.

The governing constraint: **a benchmark run must depend on nothing but the checklist, the example and the model.** Anything else the session can see — a developer’s personal skills, a repo-level settings file, the gold labels, an untraced subagent — is a source of score variance that will not show up as an error, only as a number nobody can reproduce.

### Skills are discovered from the filesystem, not registered

There is no programmatic skill API. The SDK inherits Claude Code’s discovery: `.claude/skills/<name>/SKILL.md` under `cwd` **and every parent directory up to the repository root**, plus `~/.claude/skills/`, plus each `add_dirs` entry — all gated by `setting_sources` (default `["user", "project"]`). Claude Code also ships **bundled** skills (`code-review`, `verify`, …) that are discoverable regardless of the filesystem.

Three consequences:

| Risk | Control |
|------|---------|
| A future repo-root `.claude/` joins every run invisibly (parent traversal) | Runtime dir lives **outside the repo**, so no ancestor `.claude/` is ever in scope |
| A developer’s `~/.claude/skills/` makes runs machine-dependent | `setting_sources=["project"]` — drops the user source |
| Bundled skills pollute the run and the skill trace | `skills=[explicit checklist names]` — the DAG is the sole authority on what may **run**. **Measured 2026-09-05:** this gates *invocation* only; ~16 bundled/plugin skills still appear in the `init` `skills` array on every setting. See [agentic-m2-spike-findings.md](agentic-m2-spike-findings.md) → C1 |

Note that `skills=[…]` does not restrict `/name` dispatch, and a *listed but absent* skill is not an error, so the runner still validates its own inventory against the generated `dag.yaml`. Because the `init` array also carries the installation's bundled skills, that validation is a **subset** check (`set(expected) <= set(init.skills)`), never equality.

### Runtime assembly: copy, don’t symlink

Earlier drafts assumed symlinking store versions into `.runtime/<run_id>/skills/`. Two problems: the docs do not say whether discovery follows symlinked **directories**, and a symlink inside the workspace resolves to a realpath in the repo, which re-opens containment. A `SKILL.md` is a few KB.

**Copy** each skill folder into `<runtime>/.claude/skills/<name>/`. The copied tree is also a self-contained provenance artifact that can be archived beside the predictions. **Hardlink** (not symlink) large read-only inputs such as data-checklist source-data tables — a hardlink is a real directory entry inside the workspace, not a link out of it.

This does not change the versioning model: the store still holds many versions, the manifest still resolves exactly one per name, and `skillset_hash` is unaffected. Only the assembly mechanism changes.

### Example staging and the agent workspace contract

The agent reads files rather than receiving content blocks, so examples must reach it as files. Two options were considered: expose the repo directory via `add_dirs`, or stage inputs into the runtime dir. **Staging wins**, for a reason that is about authoring rather than cost:

**Skills are prompts.** Any path a `SKILL.md` names becomes frozen contract. Pointing skills at `data/examples/{doc}/content/{fig}/content/` would make every future reorganisation of the examples tree a prompt migration requiring re-benchmarking. Staging inserts an adapter, so `data/examples/` stays free to be organised for curation and human readability — which is what it is for — while the agent sees a stable, designed workspace:

```text
<runtime>/                          # cwd; the ONLY workspace root
├── CLAUDE.md
├── .claude/skills/<name>/SKILL.md  # copied
└── example/
    ├── example.json                # example_id, example_class, source path, inventory
    ├── figure.<ext>                # stem normalised so skills can glob figure.*
    ├── caption.txt
    └── source_data/…               # only when the check enables it
```

Word examples substitute `example/manuscript.html` (the docx→HTML conversion already happens in memory; the agent cannot usefully read a `.docx`). `example.json` lets a skill know what exists instead of probing, and carries `example_id` so the submit tool and the skill trace correlate without the model echoing anything back.

**Authoring rule:** skill bodies address the workspace contract, never `data/examples/…`. Worth a lint.

### Benchmark integrity: the gold must be unreachable

Gold lives at `<fig>/checks/{check}/expected_output.json` — a **sibling of** `<fig>/content/`. Exposing the figure directory would put the answer key inside the agent’s workspace. Not a malicious-agent scenario, just a capable one that lists its working directory; and the failure mode is *suspiciously good scores*, not an error.

Staging makes this structural rather than configurational: `checks/` is on no path the agent has, instead of being excluded by pointing one level down. Defence in depth on top:

- **`disallowed_tools=["Bash"]`** — a bare-name deny rule *removes the tool definition from the request*; the model never sees it. This matters because `Read`/`Edit` rules take **path** patterns (`//abs/**`) but `Bash` rules take **command-string** patterns only — Bash is not confined to `cwd`/`add_dirs` and can read anything the OS user can.
- **`disallowed_tools=["Read(//**/checks/**/expected_output.json)"]`** — deny rules are evaluated before the permission mode and hold even under `bypassPermissions`, so this survives future config loosening.
- **`permission_mode="dontAsk"`** — anything not pre-approved is denied rather than falling through to a `canUseTool` callback we do not supply. Never `bypassPermissions`: it ignores `allowed_tools` entirely.
- A **`PreToolUse` hook** denying the same paths and *recording the attempt* — hooks run first and a hook deny holds in every mode. An attempt is itself a signal worth seeing.

### No subagents

**Nested skills are not subagents, and suppressing subagents costs the skill DAG nothing.** A `Skill` call runs in the same session: the skill body loads into the current context and the call is visible to the `PostToolUse` trace hook. A subagent runs in its own context, and the skills it invokes never reach that hook.

That is the decisive argument, beyond the obvious ones about unbounded fan-out, cost and latency: the brief’s observability claim (“Logging skill invocations”, above) is that the trace records *the actual sequence of skills an example exercised*. With subagents available, the trace would silently become **wrong** rather than error. Subagent privilege inheritance compounds it — a subagent inherits the parent’s permission mode, and an `AgentDefinition` may override it except under `bypassPermissions`/`acceptEdits`/`auto`.

Four layers, all cheap:

1. `disallowed_tools=["Task", "Agent"]` — bare-name deny removes the definition. Both names listed because the current tool name needs confirming from the session’s `init` message; listing both costs nothing.
2. An explicit `tools=[…]` allowlist that omits it — independent of which name is right.
3. The runtime dir never gets a `.claude/agents/` directory, and `agents=` is never passed.
4. A `SubagentStart` hook that **fails the example loudly** if one starts anyway. A benchmark that quietly scores a run produced through an untraced path is worse than one that errors.

### Session options (the load-bearing configuration)

```python
ClaudeAgentOptions(
    cwd=runtime_dir,                       # outside the repo: no ancestor .claude/
                                           # no add_dirs — everything is staged under cwd
    setting_sources=["project"],           # drops ~/.claude/skills
    skills=[leaf, *upstream_names],        # excludes bundled skills
    tools=["Read", "Glob", "Skill"],       # "Skill" must be listed explicitly when tools is set
    disallowed_tools=[
        "Bash",
        "Task", "Agent",
        "Read(//**/checks/**/expected_output.json)",
    ],
    permission_mode="dontAsk",
    output_format={"type": "json_schema",  # corrected 2026-09-05: replaces the
                   "schema": leaf_inner},  # submit_check_result MCP tool
    env={"CLAUDE_CONFIG_DIR": runtime_dir / "agent-home"},   # hermetic: transcript
                                           # and memory stay inside the runtime
    hooks={"PreToolUse": [...], "PostToolUse": [...], "SubagentStart": [...]},
    model=..., max_turns=..., max_budget_usd=...,
    # agents= is never passed
)
```

Two further mechanics worth recording:

- **Structured output.** ~~does not exist on the Agent SDK~~ — **corrected 2026-09-05**: `ClaudeAgentOptions.output_format={"type": "json_schema", "schema": …}` exists in SDK 0.2.152 and is enforced (see [agentic-m2-spike-findings.md](agentic-m2-spike-findings.md) → C2), so the original justification below no longer holds. **Measured against the real leaf schema, `output_format` wins**: enum-level enforcement, and the two claimed benefits of the MCP tool are illusory — correlation is free with one session per example, and `output_format` already emits a `StructuredOutput` call into the trace. An in-process MCP server insulates against nothing (same process, same trust boundary). **Use `output_format`; keep the MCP tool in reserve** only for constraints JSON Schema cannot express. Force the contract with an in-process MCP tool `submit_check_result` whose `input_schema` **is** the leaf `schema.json` inner schema; the session’s answer is that payload, not `ResultMessage.result`. Validate with `jsonschema` afterwards, one bounded retry on failure, then record an error — never silently drop the example.
- **Dispatch by name, and assert before working.** The prompt is `/{leaf_name} {example_ref}` rather than prose; skills support `$ARGUMENTS`/`$1`, so the example is a real parameter. The `system`/`init` message carries a `skills` array of what actually loaded — check the expected names are present and fail fast, or a silent discovery failure shows up only as bad scores. (Skills marked `user-invocable: false` load but do not appear in that array, so keep intermediates user-invocable.)

### ~~Unverified~~ — **resolved 2026-09-05**, see [agentic-m2-spike-findings.md](agentic-m2-spike-findings.md)

All three answered as hoped: copied-skill discovery works, the repo is unreachable *and enforced* (a forced `Read` is denied, not merely declined), and no subagent tool is present. The `system_prompt` fallback is not needed. Three corrections and one addition (`CLAUDE_CONFIG_DIR` for hermetic runs) are in that note.

Original questions, for the record:

1. Does a **copied** `.claude/skills/` tree outside any repo get discovered with `setting_sources=["project"]`? Assert via the `init` message’s `skills` array.
2. Is the repo genuinely unreachable from a staged workspace? Ask a session to read an absolute path into `data/examples/**/checks/**/expected_output.json` and assert denial.
3. What is the subagent tool actually called in the current build? Read the `init` tool list.

**Fallback if (1) fails**, costing nothing downstream: inline the leaf `SKILL.md` into `system_prompt` and expose upstream skills as MCP tools running nested sessions. The trace hook then filters `mcp__mmqc__*` instead of `Skill`; predictions, scoring, curation and versioning are untouched.

## Schemas and evaluation: are upstream structures “lost”?

### Short answer

**No for the agent session; mostly yes for FlatEvaluator (by design).**

~~Upstream skills still emit **structured artifacts** (e.g. a `panels` JSON list).~~ **Corrected 2026-09-06 — they do not, and cannot.** Measured: a `Skill` call returns `"Launching skill: <name>"` and nothing else. It *injects the skill's body into the current context* rather than running it and returning a value. All bodies accumulate into one context, and the session emits exactly **one** `structured_output` — the leaf's.

So an upstream artifact such as `panels` is real but **contextual**: it exists as the model's reasoning, not as a document. Nothing serialises it, nothing validates it, and an intermediate `schema.json` would claim an enforcement that does not exist. Intermediates therefore carry no schema (`dag.py` makes one an error), and what a skill should produce is stated in its body, where the model reads it.

This is a consequence of the in-session nesting chosen two sections above so the skill trace stays honest: one session, one `output_format`. Per-skill structured output would require one session per skill — the fallback the spike made unnecessary — and it would take nested skills out of the trace.

What we still *avoid* is making the **scored** model output a nested mega-document of every skill's schema: that would break today's evaluation model and explode gold curation when you unpin an upstream skill.

### Three options

| | A. Informal upstream only | B. Nested mega-schema (all skills in one scored tree) | C. Dual role (recommended) |
|--|---------------------------|------------------------------------------------------|----------------------------|
| Upstream structure | Prose / ad hoc JSON | Part of final scored JSON | ~~Validated JSON per skill schema~~ → **contextual**: stated in the skill body, held in context, never serialised (measured 2026-09-06) |
| Agent chaining | Fragile | Strong | Strong |
| FlatEvaluator / gold | Unchanged (leaf only) | Must score nested tree; gold includes intermediates | **Unchanged (leaf only)** |
| Unpin upstream skill | Leaf gold still valid | Gold shape may change with upstream | Leaf gold still valid; optional debug dumps of intermediates |
| Complexity | Low | High | Medium |

**Reject B for v1.** Nesting every skill schema into one “overall generated response” couples evaluation-scoring to the whole DAG, forces nested `expected_output`, and makes 1D unpin experiments rewrite gold.

### Recommended: C — contract schemas vs eval schemas

1. **Leaf `schema.json` + `eval-manifest.json` + `expected_output.json`**  
   - Exactly today’s contract for scoring and curation.  
   - Final agent answer for a check **must** validate against the leaf schema.  
   - FlatEvaluator compares **only** that leaf JSON to gold.

2. **Intermediate `schema.json` (optional but encouraged for shared skills like `identify-panels`)**  
   - Runtime contract: validate the artifact before handing it to the next skill.  
   - Documented by `produces: panels` → schema defines `panels`.  
   - **Not** listed in benchmark gold; **not** scored by FlatEvaluator in v1.  
   - May be written to a debug/sidecar path (`intermediates/identify-panels.json`) for inspection when unpinning upstream skills.

3. **Composition is sequential, not nested-in-the-scored-output**  
   - Session state: `{ panels: {...}, panels_with_kind: {...}, leaf: {...} }`.  
   - Persisted prediction for eval: **`leaf` only** (plus metadata: skillset hash, optional intermediate digests).

### Implication for evaluation-scoring

- [evaluation-scoring.md](evaluation-scoring.md) stays focused on **leaf** predictive fields.  
- No change to layer S / leaf primitives because of nesting.  
- Measuring upstream quality (e.g. “did identify-panels miss panel C?”) is a **separate** concern later: either dedicated gold for that skill, or qualitative debug — not by folding panels into every check’s `expected_output`.

### What “lost” would actually mean

| If we only had leaf schemas and no intermediate contract | Risk |
|----------------------------------------------------------|------|
| Downstream skills re-derive panels ad hoc | Panel label drift across checks |
| No validation of upstream JSON | Silent shape bugs |
| No sidecar dump | Hard to debug unpin of `identify-panels` |

Hence: **keep structure in the session (+ optional intermediate schemas); keep scoring flat at the leaf.**

## Approaches considered

### 1. Orchestration: Python loop vs top-level agent

| | Python loop (chosen) | Top-level agent |
|--|----------------------|-----------------|
| Batching / cache / resume | Deterministic, cheap | Fragile, expensive |
| Agentic value | Skill chaining **inside** each example | Also decides which examples to run |
| Fit for benchmarking | Strong | Weak for CI |

**Rejected for v1:** top-level agent owning the example loop. Optional later as a thin wrapper over the same tools.

### 2. Graph representation: `dag.yaml` vs skills-only vs FS tree

| | Hand-maintained `dag.yaml` as SoT | Skills SoT + **generated** `dag.yaml` (chosen) | FS tree as graph |
|--|-----------------------------------|-----------------------------------------------|------------------|
| Reuse (multi-parent) | Easy | Easy | Awkward |
| Drift | High (edges edited twice) | Low if generated + CI check | Medium |
| Visualize | Good | Good (generated README / dag) | Local only |

**Rejected:** filesystem tree as the graph; **hand-edited** `dag.yaml` as the source of truth.

**Chosen:** each skill’s `requires` / `produces` is SoT. A **generated** `dag.yaml` (plus README) is a derived view — never edited by hand; regenerate or CI-fail on drift.

**Purpose of generated `dag.yaml`:** human/tooling convenience only — visualize the hierarchy, validate the versioning manifest against the full skill inventory, debug closures, and document the checklist. The runner may read it as a cache of the same graph it could rebuild by walking skill frontmatter; it must not be a second place people maintain edges.

### 3. Schema placement

| | Leaf schema for **eval** (chosen) | Nested mega-schema for eval | Schema only in prompt text |
|--|-----------------------------------|-----------------------------|----------------------------|
| Eval/curation | Natural path to leaf dir | Gold must nest; brittle under unpin | Brittle |
| Reuse of upstream skills | Unaffected | Couples all leaves to upstream shape | N/A |
| Upstream structure | Session + optional intermediate schema | Inside scored tree | Ad hoc |

**Chosen for scoring:** leaf folders only. **Chosen for chaining:** optional intermediate `schema.json` as runtime contract (not gold). See “Schemas and evaluation.”

### 4. Code layer: in-process Python tools vs MCP

Needed so skills can call deterministic helpers (load figure, parse caption, validate URL, etc.).

| | In-process tools (SDK tool defs) | MCP server wrapping same functions |
|--|----------------------------------|-------------------------------------|
| Anthropic Agent SDK | First-class | Also supported |
| OpenAI Agents later | Map tool registry | Same MCP or dual adapter |
| Local/CI | Simple | Extra process |
| External clients (Cursor, etc.) | Harder | Natural |

**Recommendation:** implement a **small Python tool registry** first (functions the agent can call). Expose the **same registry via MCP** as a thin adapter so Cursor/other hosts can use checklist skills without forking logic. Do not invent two implementations of “load example” / “read schema”.

## Config model (needs + checklist defaults)

1. **Checklist** `model_defaults.json` (name TBD): provider-agnostic defaults used in practice — effort, max tokens, allowed tool families, etc.
2. **Skill** `needs: […]`: rare overrides when a skill truly requires web/code/etc.
3. **Runner** maps `(defaults ∪ needs ∪ CLI --model)` → Anthropic Agent SDK session config (v1) or OpenAI Agents config (later). For a multi-skill closure in one session, effective permissions are the **union** of checklist defaults and every skill’s `needs`.
4. **Cache key** includes: leaf id, skill closure hash (or content hashes), example id, model id, effective config hash, schema hash.

Avoid shipping OpenAI-shaped `model_config.json` as the long-term skill contract; keep migration shims if needed.

### Note: frontmatter is only partly provider-enforced (SDK)

**Corrected 2026-09-04.** An earlier version of this section stated that the Claude Agent SDK ignores `allowed-tools` frontmatter. That is no longer true — the current [skills docs](https://code.claude.com/docs/en/agent-sdk/skills) say: *“For project and personal skills, Claude Code applies the `allowed-tools` frontmatter field in SDK sessions.”* Skills synced from claude.ai follow their own rules.

| Surface | Honors skill-level tool restrictions in `SKILL.md`? |
|---------|-----------------------------------------------------|
| Claude Code **CLI** | Yes — `allowed-tools` frontmatter applies |
| Claude **Agent SDK** | Yes for project and personal skills — but only for **tool restriction**. Model, effort, budget, `setting_sources`, `skills`, `permission_mode` and deny rules are session options only |
| OpenAI Agents / Codex skills | Frontmatter is mainly `name` / `description`; optional `agents/openai.yaml` covers UI / invocation policy / MCP deps — **not** a portable session permission or model-config contract. Tools/permissions are set on the agent/run in code |

So the conclusion stands with a narrower justification: skill `needs` (and any richer frontmatter we invent) is **orchestrator-owned metadata**, because the things it must express — model, effort, budget, and the isolation controls in “Agent runtime and session isolation” — have no frontmatter equivalent and are not portable to OpenAI. Per-skill *tool* narrowing may now live in frontmatter if that reads better. Prefer checklist `model_defaults.json` for the common session profile; use per-skill `needs` only for rare exceptions.

## CLAUDE.md role

**Revised 2026-09-06.** There is **one** `CLAUDE.md`, shipped as
`soda_mmqc/agents/CLAUDE.example.md` and copied into each runtime dir. It is a
prompt -- Claude Code loads it automatically from `cwd`, so it sits in front of
the model on every example of every run -- and it is therefore a reviewed file,
not a string in `runtime.py`.

There is **no repo-level or checklist-level `CLAUDE.md`**. Two files in one
session would interact in ways nobody can predict from reading either, and the
authored, versioned, reviewable prompt surface is already `SKILL.md`. Checklist
guidance belongs there.

The original bullets below are struck because staging made them wrong, and two
of them dangerous:

- ~~Layout of `soda_mmqc/data/`~~ — the agent never sees a repo path. Staging
  exists precisely so a prompt never names one.
- ~~Where schemas, benchmarks, expected outputs live~~ — pointing the session
  at the gold is the opposite of the isolation the rest of this section builds.
- ~~How to invoke Python/MCP tools~~ — M5, and per-tool, not ambient.
- Meaning of a **skill** vs **leaf/check** — generic, so it lives in the one file.
- Output discipline — now enforced by `output_format`, not by asking.

What remains is orientation to the *workspace*: where the staged example is,
that nothing outside it exists, and that a named skill should be invoked rather
than reimplemented.

## CLI split

| Command (names TBD) | Responsibility |
|---------------------|----------------|
| Existing `evaluate` / `run.py` (compat) | Discover examples, run agent sessions, write predictions, cache |
| New `score` (or similar) | Load predictions + gold + leaf schema + eval-manifest → analysis |
| Existing `curate` / `init` | Continue to read leaf `schema.json` for fields to curate |

Keep argument names of the run CLI stable where possible (`CHECKLIST_NAME`, `--check`, `--model`, `--no-cache`, …).

## Migration sketch (not scheduled here)

1. Introduce `skills/` layout alongside existing check dirs (or gradually rename).
2. Convert one pilot checklist (e.g. subset of `fig-checklist`) to skills + one shared upstream skill.
3. Generator: skills → `dag.yaml` + README; CI fails on drift.
4. Swap `run_model` path for agent session behind a flag / provider.
5. Split scoring into new CLI; `evaluate` stops writing analysis or shells out.
6. Retire monolithic `prompts/prompt.N.txt` once leaves are skills; versions live in the skill store; production SkillSet published to Langfuse.

## Rewriting fig-checklist into nested skills

### What today’s prompts already share

Almost every active fig-checklist prompt repeats the same opening:

1. **Identify panels** — labels (A, B, …), layout quirks, composite panels, map panel → caption span.
2. **Applicability / type gate** — is this a quantitative plot? micrograph? image data? overlay? (wording differs per check).
3. **Check-specific analysis** — error bars, scale bars, annotations, stats, etc.
4. **Leaf JSON** — per-panel fields + PASS/FAIL/N/A (today inlined in the prompt; target: leaf `schema.json` only).

Duplication of (1) is the main rewrite target. (2) is partially shared (several “is this a plot?” checks) but criteria are not identical (e.g. image-annotation’s `image_data` vs micrograph-scale-bar’s `micrograph`).

### Target shape

```text
                    identify-panels          ← shared entry (no leaf schema)
                           │
                           ▼
              classify-panel-kind            ← optional shared mid skill
                           │
        ┌──────────────────┼──────────────────┐
        ▼                  ▼                  ▼
   plot leaves      image/micrograph     caption/layout leaves
   (error-bars,     (scale-bar,          (panel-image-matches-
    axis-units,      annotations,         caption, …)
    gap, stats,      single-channel)
    individual-
    points,
    replication…)
```

- **Entry skill** `identify-panels`: produce a stable artifact, e.g. list of `{panel_label, caption_excerpt, region notes}`. No check `schema.json`.
- **Optional mid skill** `classify-panel-kind`: attach coarse kinds (`plot`, `micrograph`, `image`, `schematic`, `blot`, `composite`, …) so leaves do not re-argue “what is a panel.”
- **Leaf skills** = today’s checks: consume upstream artifacts; contain only applicability nuances + analysis; **own** `schema.json` / `eval-manifest.json` / `benchmark.json`.

`requires` / `produces` example:

| Skill | requires | produces |
|-------|----------|----------|
| `identify-panels` | — | `panels` |
| `classify-panel-kind` | `panels` | `panels_with_kind` |
| `micrograph-scale-bar` | `panels_with_kind` (or `panels`) | leaf JSON per schema |
| `error-bars-defined` | `panels_with_kind` | leaf JSON per schema |

### How to split an existing prompt (recipe)

For each current check (start with one pilot, e.g. `micrograph-scale-bar`):

1. **Cut** the “Identify all figure panels” section → contribute to / reuse `identify-panels` (merge the best wording once; do not keep N copies).
2. **Extract** the type gate into either:
   - shared `classify-panel-kind` + a short leaf rule (“only panels with kind micrograph”), or
   - leaf-local applicability if the definition is idiosyncratic (document why).
3. **Keep** in the leaf `SKILL.md` only: detection rules, caption extraction rules, decision/PASS-FAIL logic, examples tied to that check.
4. **Move** the JSON example block out of prose into `schema.json` (leaf already has this; skill text should say “conform to schema.json” rather than paste a full example, or keep one short example).
5. **Pin** new/shared skills in the checklist versioning manifest.

### Suggested first DAG for fig-checklist (concrete)

**Shared (non-leaf)**

- `identify-panels` — entry for all figure checks.
- `classify-panel-kind` — recommended once two+ leaves need “is plot / is micrograph / is image.”

**Leaves (checks; keep current names)**

| Branch | Leaves |
|--------|--------|
| Plot-oriented | `error-bars-defined`, `individual-data-points`, `plot-axis-units`, `plot-gap-labeling`, `stat-test`, `stat-significance-level`, `replication-reporting` |
| Image / micrograph | `micrograph-scale-bar`, `image-annotation-defined`, `single-channel-for-overlay` |
| Cross-cutting | `panel-image-matches-caption` (panels + caption alignment; may skip kind classification) |

Do **not** force every leaf through the same mid skill if it adds noise; `requires` can point at `identify-panels` only.

### Authoring pitfalls

- **Drift in panel lists:** if each leaf re-identifies panels, labels disagree across checks on the same figure. Shared `identify-panels` is what makes the DAG worth it.
- **Over-shared classification:** one global ontology that fights check-specific nuance (e.g. “is a kymograph a micrograph?”). Prefer a coarse shared kind + leaf overrides.
- **Monolithic leaf again:** resist pasting the whole old prompt into `SKILL.md`; the leaf should assume upstream artifacts exist.
- **Gold / expected_output:** panel labels must stay consistent with `identify-panels` versions — unpinning that skill is high-impact; treat it as a carefully pinned baseline.

### Pilot order (recommended)

1. Extract `identify-panels` from the best current wording (error-bars / scale-bar / image-annotation share nearly the same §1).
2. Convert **one** leaf (`micrograph-scale-bar`) to `requires: [identify-panels]` and drop duplicated §1.
3. Convert a second leaf on the same branch (`image-annotation-defined` or `single-channel-for-overlay`).
4. Only then introduce `classify-panel-kind` if both leaves still duplicate type gates.
5. Roll plot leaves similarly.

### Open choice for this rewrite

**A.** Two levels only: `identify-panels` → leaves (leaves keep their own applicability text). Faster migration.  
**B.** Three levels: add `classify-panel-kind` early. More modular; more design work on the kind taxonomy.

Lean **A** for the pilot, introduce **B** when the second leaf shows painful duplication of type gates.

## Open questions

1. **Manifest + CLI:** filename; `--unpin` / optional `--versions`; replace `--prompt-version`.
2. **Git → Langfuse promote:** publish versioning manifest / closure.
3. **Intermediate schemas:** encourage `schema.json` on shared upstream skills as **runtime contracts**; still **no** nested mega-schema for FlatEvaluator (see “Schemas and evaluation”). Whether to ever score intermediates separately remains open.
4. **Shared skills across checklists:** global store vs per-checklist store (manifest still per checklist).
5. **Parallelism:** Python may run multiple example agent sessions concurrently — rate limits and cache atomicity.
6. **Mock mode:** `--mock` should short-circuit agent and return expected leaf JSON (keep for CI).
7. **Langfuse tracing:** whole agent session vs per-skill spans (separate from Langfuse-as-production-surface).
8. **When (if ever) to cache intermediate skill outputs** — deferred; v1 session-level only.
9. **fig-checklist rewrite depth:** two-level (`identify-panels` → leaf) vs three-level (+ `classify-panel-kind`) for the pilot.
10. ~~**Spike items**~~ — **done 2026-09-05**, all three answered as hoped; see [agentic-m2-spike-findings.md](agentic-m2-spike-findings.md).
11. **Workspace contract stability:** `example.json` field set and the normalised `figure.<ext>` convention become an interface skills are authored against — worth freezing deliberately rather than by accretion.

## Non-goals (this brief)

- Implementing the Agent SDK integration.
- Rewriting all existing prompts to `SKILL.md` in one shot (pilot first; see rewrite section).
- Freezing the panel-kind taxonomy before a second leaf needs it.
- Replacing `FlatEvaluator` scoring semantics.
- Committing to MCP-only (MCP is an adapter, not the only tool surface).

## Related

- Data layout today: [README — Checklists and checks](../README.md)
- Evaluation scoring: [evaluation-scoring.md](evaluation-scoring.md)
- Orchestration code: [soda_mmqc/scripts/run.py](../soda_mmqc/scripts/run.py)
