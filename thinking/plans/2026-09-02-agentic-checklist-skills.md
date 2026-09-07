# Agentic Checklist Skills Implementation Plan

> **For Copilot:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert active `fig-checklist` prompts into versioned Markdown skills **organized as a hierarchical DAG** — so that shared upstream procedures are written once, reused by many leaves, and provably free of cycles — and run them per example through a new `soda_mmqc/cli.py` runner with agent-driven skill discovery and leaf-only scoring.

**Architecture:** A skill invokes its sub-skills **in its own prose**, by instructing the agent to call the `Skill` tool. That prose is the only orchestration mechanism; there is no generated or templated call-graph execution. `SKILL.md` frontmatter (`requires`, `produces`) is **documentation and validation metadata owned by the runner** — useful to render the DAG, detect cycles, and catch inconsistencies between what a skill declares and what its prose actually calls — and is **ignored by the agent at runtime**. A checklist manifest pins skill versions; `cli.py` validates the graph and manifest, assembles a runtime tree containing exactly one version per skill name **outside the repository**, and runs one agent session per example. The runner does not precompute or enforce a runtime closure: discovery and ordering belong to the agent. A `PostToolUse` hook writes a structured invocation trace for diagnostics; prediction caching keys on the pinned SkillSet, never on the observed trace.

**Tech Stack:** Python 3.12, existing PyYAML, pytest, existing `ModelCache` and `FlatEvaluator`, official Anthropic Claude Agent SDK, Langfuse for production-manifest exposure only.

**Background:** Design rationale, alternatives considered, and open questions live in [`thinking/agentic-checklist-skills.md`](../agentic-checklist-skills.md). Read it before starting a milestone; this plan is the schedule, that document is the reasoning.

---

## Delivery Order (why the milestones are ordered this way)

The highest-value, highest-risk unknown is **not** prompt conversion — it is whether an agent can be run in a clean, sealed runtime directory and produce a schema-valid prediction per example. Converting eleven prompts before knowing that would be a large investment made blind.

So the order is:

1. **Separate `run` from `evaluate` first**, and prove scoring/reporting still work. This is pure regression safety and unlocks everything else.
2. **Pilot one check** — `micrograph-scale-bar` — as a two-level hierarchy (`identify-panels` → leaf). Validate the layout on a real example before scaling.
3. **Build the runner**: assemble the sealed runtime dir, invoke the agent per example, write predictions. This is the priority deliverable.
4. **Score the pilot** with the unchanged `FlatEvaluator`.
5. **Convert the remaining checks in branch groups** (micrograph/image first, then plots).
6. **Add version pinning, unpin expansion, and generated graph docs last.** Versioning is real but it is the least risky part and must not gate the runner.

Every milestone has two gates: an **automatic gate** (a named pytest command that must pass) and a **human gate** (something a person inspects or runs and signs off on). Do not start milestone N+1 before both gates of milestone N pass.

## Constraints

- Markdown and YAML own skill instructions, dependencies, version pins, defaults, and generated documentation.
- Add one production Python module: `soda_mmqc/cli.py`. Keep helpers private there for v1.
- `soda_mmqc/scripts/run.py` retains the `evaluate` CLI and delegates agentic checklists to `cli.py`; it must not implement a second DAG runner.
- **Do not break existing scoring, reporting, or curation modules.** Every milestone runs the existing test suite, not just its own tests.
- Sub-skill invocation is written in skill prose. `requires`/`produces` frontmatter is validation metadata only; no code turns frontmatter into a call sequence, and the agent never reads it as one.
- `cli.py` validates the complete graph and manifest, but does not walk a leaf closure for execution. Skill discovery and ordering belong to the agent, per example.
- **The runtime directory is assembled outside the repository**, in a temporary directory, with the skills *and* the example inputs copied into it. Nothing else is reachable.
- The runtime agent sees the assembled skill tree and the current example only — never the skill store, sibling versions, `benchmark.json`, expected outputs, or any other example.
- **`schema.json`, `eval-manifest.json`, and `benchmark.json` are per-check, shared across all versions of that check's skill.** They live above the version directories. Duplicating them per version would make versions incomparable and break scoring.
- Score leaf JSON only. Intermediate artifacts and traces are debug sidecars.
- **The agent gets no shell and cannot spawn agents.** No `Bash`, and no subagent creation of any kind — no `Task`/`Agent` tool, no nested sessions. Permissions are deny-by-default and explicitly enumerated (see Milestone 3).
- Do not add OpenAI Agents, MCP, intermediate caches, parallel sessions, or a shared image/micrograph classifier in this implementation.

## Target Layout

Leaf evaluation contracts stay at the check level; only `SKILL.md` is versioned.

```text
soda_mmqc/data/checklist/fig-checklist/
  version-manifest.yaml             # SkillSet pins (added in Milestone 6)
  model-defaults.yaml               # provider-neutral defaults
  dag.yaml                          # generated; never hand-edit
  README.md                         # generated; never hand-edit
  micrograph-scale-bar/             # leaf: an existing check dir, unmoved
    schema.json                     # shared by all versions of this leaf
    eval-manifest.json              # shared by all versions
    benchmark.json                  # shared by all versions
    prompts/                        # legacy; retired only after parity
    v1/SKILL.md
    v2/SKILL.md
  _shared/                          # non-leaf skills
    identify-panels/
      schema.json                   # runtime contract only, no eval assets
      v1/SKILL.md
```

**Discovery hazard to resolve in Milestone 1:** `list_checks()` in [run.py:1143](../../soda_mmqc/scripts/run.py#L1143) treats *every* subdirectory of a checklist as a check. A new directory for shared skills would be picked up as a phantom check and break existing runs and reports. Resolve it explicitly — a reserved-name filter (`_`-prefixed directories are not checks) is the recommended fix — and cover it with a test before adding any shared-skill directory.

`SKILL.md` frontmatter carries `name`, `description`, `kind`, `requires`, `produces`, and `needs`. `requires` and `produces` are for generated graph documentation, cycle detection, and manifest validation. The actual dependency invocation is a sentence in the skill body telling the agent to call the named skill with the `Skill` tool. A validation test asserts these two stay consistent — every skill named in `requires` is also named in the prose, and vice versa — because prose is what executes and frontmatter is what documents.

There is **one repository-level `CLAUDE.md`** for agent orientation. It is not varied per checklist or per check: per-check variants multiply and interact unpredictably. Anything genuinely specific to a leaf belongs in that leaf's `SKILL.md`. The runtime directory gets a small generated orientation file naming the target leaf, the skills root, the artifacts root, and the final schema — that is generated per run, not checked in per check.

## Fig-Checklist Conversion Map

Eleven active leaves, converted in branch groups (see Milestone 5). Select the newest prompt revision as initial source and preserve it in `metadata.source_prompt`; never expose multiple prompt revisions in the runtime tree.

**Group A — micrograph/image (converted first; needs panel identification only):**

| Leaf | Initial source | Requires | Leaf retains |
|---|---|---|---|
| `micrograph-scale-bar` | `prompt.2.txt` | `identify-panels` | Micrograph applicability and scale-bar extraction |
| `image-annotation-defined` | `prompt.2.txt` | `identify-panels` | Image applicability and annotation definitions |
| `single-channel-for-overlay` | `prompt.2.txt` | `identify-panels` | Overlay/channel completeness |
| `panel-image-matches-caption` | `prompt.2.txt` | `identify-panels` | Panel/caption comparison |

**Group B — plots/statistics (converted second; may need plot classification and axis analysis):**

| Leaf | Initial source | Requires | Leaf retains |
|---|---|---|---|
| `error-bars-defined` | `prompt.4.txt` | `identify-panels`, `classify-quantitative-plot` | Error/box plot detection and caption decision |
| `individual-data-points` | `prompt.4.txt` | `identify-panels`, `classify-quantitative-plot` | Point requirement, visibility, and decision |
| `plot-axis-units` | `prompt.2.txt` | `identify-panels`, `classify-quantitative-plot` | Axis unit logic and extraction |
| `plot-gap-labeling` | `prompt.2.txt` | `identify-panels`, `classify-quantitative-plot` | Tick gap detection and marking |
| `replication-reporting` | `prompt.3.txt` | `identify-panels`, `classify-quantitative-plot` | Replicate reporting and decision |
| `stat-test` | `prompt.4.txt` | `identify-panels`, `classify-quantitative-plot` | Significance gate, test extraction, decision |
| `stat-significance-level` | `prompt.3.txt` | `identify-panels`, `classify-quantitative-plot` | Symbol definition and decision |

`identify-panels` produces a stable `panels` artifact: panel label, region notes, caption excerpt/span. Group B may additionally need a plot-side skill producing `quantitative_plot_panels` (label, `is_quantitative_plot`, evidence) and possibly axis properties — but that skill is designed **after** Group A is running end to end, informed by what the plot prompts actually duplicate. Visual image/micrograph type gates stay leaf-local because their criteria differ per leaf.

---

## Milestone 1: Separate `run` from `evaluate` Without Breaking Scoring

**Deliverable:** running a check and scoring a check are separate operations; existing behavior is unchanged.

**Files:**
- Modify: `soda_mmqc/scripts/run.py`
- Create: `soda_mmqc/cli.py`
- Create: `tests/test_agentic_cli.py`
- Modify: `tests/test_run_analyze_results.py`

**Step 1:** Write failing tests: a `score` entry point loads stored predictions plus gold, and produces the same `FlatEvaluator` `flat` result the current `evaluate` path produces for at least one existing check. Add a test that `list_checks()` ignores `_`-prefixed directories.

**Step 2:** Verify failure: `pytest tests/test_agentic_cli.py -v`

**Step 3:** Implement `python -m soda_mmqc.cli score <checklist> --check <check> --predictions PATH`, reusing `analyze_results` and `save_analysis` from `run.py` verbatim. Do not change evaluator semantics, thresholds, or output shape.

**Step 4:** Implement the reserved-name filter in `list_checks()`.

**Step 5: Automatic gate:** `pytest tests/ -v` — the whole suite, including reporting, curation, and evaluation tests, passes unchanged.

**Step 6: Human gate:** Run one real legacy command (`evaluate fig-checklist --check micrograph-scale-bar --mock`) plus the existing report export, and confirm by eye that analysis JSON and the exported report are identical to before the change.

## Milestone 2: Pilot the Hierarchy on One Check

**Deliverable:** `micrograph-scale-bar` exists as a two-level hierarchy — `identify-panels` → leaf — hand-authored and reviewed, with its evaluation contracts untouched and shared across versions.

**Files:**
- Create: `soda_mmqc/data/checklist/fig-checklist/_shared/identify-panels/v1/SKILL.md`
- Create: `soda_mmqc/data/checklist/fig-checklist/_shared/identify-panels/schema.json`
- Create: `soda_mmqc/data/checklist/fig-checklist/micrograph-scale-bar/v1/SKILL.md`
- Modify: `tests/test_agentic_cli.py`

**Step 1:** Extract `identify-panels` from the best existing wording (the panel-identification sections of `error-bars-defined`, `micrograph-scale-bar`, and `image-annotation-defined` are nearly identical). Merge once; do not keep N variants. Write `schema.json` as the runtime contract for `panels` — no eval manifest, no expected outputs.

**Step 2:** Convert `micrograph-scale-bar/prompt.2.txt` into `v1/SKILL.md`: delete the duplicated panel-identification section, add a sentence in the prose instructing the agent to call `identify-panels` with the `Skill` tool, and keep only the micrograph applicability rule, scale-bar extraction rules, and the decision logic. Point the output requirement at the check's existing `schema.json` rather than pasting a full JSON example.

**Step 3:** Leave `schema.json`, `eval-manifest.json`, and `benchmark.json` exactly where they are. Assert with a test that no version directory contains a copy of them.

**Step 4:** Write tests for skill loading and consistency: frontmatter parses; `requires` names an existing skill; the graph is acyclic; every name in `requires` also appears in the prose body, and no skill invoked in prose is missing from `requires`.

**Step 5: Automatic gate:** `pytest tests/test_agentic_cli.py tests/test_micrograph_scale_bar_manifest.py -v`

**Step 6: Human gate:** Read `identify-panels/v1/SKILL.md` and `micrograph-scale-bar/v1/SKILL.md` side by side with `prompt.2.txt`. Confirm nothing check-specific was lost, nothing shared was left duplicated, and the sub-skill call reads as a natural instruction rather than a template.

## Milestone 3: Sealed Runtime Directory Outside the Repository

**Deliverable:** `cli.py` assembles a self-contained runtime directory in a temp location outside the repo, containing exactly the skills and the one example the agent may see — with tests proving the agent cannot reach anything else.

**Files:**
- Modify: `soda_mmqc/cli.py`
- Modify: `soda_mmqc/config.py`
- Modify: `tests/test_agentic_cli.py`

**Step 1:** Write failing tests for assembly: the runtime root is outside the repository tree; skills are placed where the Agent SDK discovers them; exactly one version per skill name is present; the store and sibling versions are absent; only the current example's inputs are present; `benchmark.json`, `eval-manifest.json`, and expected outputs are **absent**.

**Step 2:** Add `AGENTIC_RUNTIME_DIR` to `config.py`, defaulting to a system temp location, never a path inside the repo. Document why: the Agent SDK discovers skills by convention under `.claude`, and a runtime rooted in the repo would let repo-level skills, other checklists, and the gold data leak into the session. Copy inputs in rather than mapping the repo in.

**Step 3:** Implement atomic assembly plus a generated runtime orientation file naming the target leaf, skills root, artifacts root, and final schema. Do not compute or execute a graph closure here.

**Step 4:** Add `--keep-runtime` (default: remove the directory after the session; keep it for debugging). Test both paths, including cleanup after an exception.

**Step 5:** Define the permission profile explicitly, deny-by-default, and test it. Allowed: reading the copied example, reading the assembled skills, writing artifacts under the runtime artifacts root, and the `Skill` tool. Denied, with a test asserting each is absent from the session's tool set:

- **`Bash`** and any other shell or code execution — it would let the session escape the runtime directory.
- **Subagent creation** — no `Task`/`Agent` tool, no nested sessions. A spawned agent negotiates its own context and permissions, which reopens the containment problem from another direction and makes the per-example `Skill` trace unreliable.
- Network access, web fetch, and web search, unless a skill's `needs` justifies it and the justification is recorded.

Frontmatter does not enforce any of this on the Agent SDK path, so the runner sets it on the session options and asserts the resulting tool set matches the profile exactly — an allowlist comparison, not a denylist, so a future SDK tool cannot silently appear.

**Step 6: Automatic gate:** `pytest tests/test_agentic_cli.py -v`

**Step 7: Human gate:** Assemble a runtime for one example with `--keep-runtime`, then walk the directory manually. Confirm there is no route from it to the repo, to gold data, or to another example, and that the permission profile printed by the runner matches the intent — in particular that neither a shell nor a subagent tool is present.

## Milestone 4: Per-Example Agent Session Writing Predictions

**Deliverable:** the priority runner — for each example of one check, assemble the runtime, run one agent session, and write a schema-valid prediction plus a diagnostic trace. Versioning is deliberately not part of this milestone.

**Files:**
- Modify: `soda_mmqc/cli.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_agentic_cli.py`

**Step 1:** Confirm the official, current Claude Agent SDK package and API from Anthropic primary documentation before adding the dependency. Record the selected package and API version in the plan and in `pyproject.toml`.

**Step 2:** Implement `run --mock` first: for each benchmark example, write the expected leaf output as the prediction plus a deterministic `skill_trace.json` sidecar. This keeps CI able to exercise the whole path without credentials.

**Step 3:** Write fake-client tests for a private `_run_agent_session`: the session uses the assembled runtime, the target leaf, and the example inputs; no closure is supplied; the final leaf JSON validates against the leaf `schema.json`; invalid output fails **before** any prediction is written.

**Step 4:** Add an SDK `PostToolUse` hook. Filter `tool_name == "Skill"` and append entries incrementally to `intermediates/skill_trace.json` under the prediction directory — `skill`, resolved `version`, `tool_input`, `tool_use_id`, timestamp. Write as calls occur so a failed session still leaves its trace. Never parse transcript JSONL or agent prose to infer calls.

**Step 5:** Validate intermediate artifacts against the optional intermediate schemas before they are handed onward, and persist them as sidecars.

**Step 6:** Map checklist defaults plus the union of declared `needs` onto SDK session options, subject to the Milestone 3 permission profile — which the union may narrow but never widen past the profile's allowlist. Cache whole sessions by `(example_content_hash, skills_content_hash, model, effective_config_hash, leaf_schema_hash)`. Do not key cache reuse on the observed trace.

**Step 7: Automatic gate:** `pytest tests/test_agentic_cli.py -v`, plus a `--mock` run over the pilot check.

**Step 8: Human gate (credentials, after approval):** run the pilot check live on a small number of examples:

```bash
python -m soda_mmqc.cli run fig-checklist --check micrograph-scale-bar --model <claude-model> --no-cache --keep-runtime
```

Inspect one prediction and its `skill_trace.json`, and confirm `identify-panels` was actually invoked and that panel labels are consistent with the leaf output. Scope this to a handful of examples — never the full checklist — so a debugging cycle stays minutes, not hours.

## Milestone 5: Score the Pilot, Then Convert by Group

**Deliverable:** the pilot check scores through the unchanged `FlatEvaluator`, `evaluate` delegates agentic checklists to `cli.py`, and the remaining leaves are converted group by group.

**Files:**
- Modify: `soda_mmqc/cli.py`
- Modify: `soda_mmqc/scripts/run.py`
- Create: `soda_mmqc/data/checklist/fig-checklist/<leaf>/v1/SKILL.md` for the remaining leaves
- Modify: `tests/test_agentic_cli.py`, `tests/test_run_analyze_results.py`
- Modify: `README.md`

**Step 1:** Score the pilot's agentic predictions with the Milestone 1 `score` command. Assert intermediate JSON and traces change nothing about the score.

**Step 2:** Write failing compatibility tests, then implement delegation at the `run.py` CLI boundary: legacy checks keep present behavior; a checklist with an agentic layout dispatches `--mock`, `--check`, `--checks`, `--model`, and `--no-cache` to `soda_mmqc.cli.main(argv)`; agentic `--prompt-version` errors clearly. Leave `process_check` and the prompt-version implementation untouched.

**Step 3:** Convert the rest of Group A (image/micrograph), reusing `identify-panels` unchanged. Run and score each as it lands.

**Step 4:** Only now decide whether Group B needs a shared plot skill, based on what those prompts actually duplicate — plot classification, and possibly axis identification and properties. Design it against two real leaves, not against the prompt text alone.

**Step 5:** Convert Group B.

**Step 6: Automatic gate:** `pytest tests/ -v` after each group, plus a `--mock` run and a `score` run for every converted leaf.

**Step 7: Human gate:** For each group, compare scores from the agentic path against the legacy prompt path on the same examples and review the deltas. Unexplained regressions block the next group.

## Milestone 6: Version Pinning and Generated Graph Views

**Deliverable:** versions are pinned by manifest, alternative versions can be compared, and the DAG documentation is generated and drift-checked. Scheduled last because it is the least risky part and must not gate the runner.

**Files:**
- Create: `soda_mmqc/data/checklist/fig-checklist/version-manifest.yaml`
- Create: `soda_mmqc/data/checklist/fig-checklist/model-defaults.yaml`
- Create: `soda_mmqc/data/checklist/fig-checklist/dag.yaml` (generated)
- Create: `soda_mmqc/data/checklist/fig-checklist/README.md` (generated)
- Modify: `soda_mmqc/cli.py`, `tests/test_agentic_cli.py`

**Step 1:** Write failing tests for invalid frontmatter, duplicate names, unknown requirements, cycles, missing pins, orphan pins, and non-existent versions. Test that a complete manifest validates even though execution never pre-walks a closure.

**Step 2:** Implement the private helpers — skill loading, manifest loading, inventory validation, SkillSet expansion, and SkillSet hashing — using `yaml.safe_load` and canonical JSON. Pin every skill; a missing or extra pin is invalid.

**Step 3:** Implement `graph <checklist>` (drift check) and `graph <checklist> --write` (deterministic docs). Keep the graph command metadata-only so it stays fast; it must not touch examples or run sessions.

**Step 4:** Implement unpin selection: `--unpin SKILL` with optional `--versions v1,v2`. Expand the selected skill's versions while all others stay pinned. **Multiple unpinned skills are permitted** — the constraint is that the resulting SkillSet count stays deliberate and each set is complete and hashed as sorted `{name, version, content_hash}`. Warn, rather than refuse, when an expansion crosses a configured size threshold.

**Step 5:** Switch the Milestone 4 cache key from a raw skills hash to the SkillSet hash.

**Step 6: Automatic gate:** `pytest tests/ -v`

**Step 7: Human gate:** Run `graph fig-checklist` against deliberately malformed fixtures and confirm every failure message names the offending file and the reason. Then run one unpinned comparison on the pilot check (`--unpin micrograph-scale-bar --versions v1,v2`) on a few examples and confirm the two versions score comparably against the *same* shared `schema.json` and `eval-manifest.json`.

---

## Acceptance Checklist

- Running and scoring are separate commands; existing scoring, reporting, and curation behavior is unchanged and covered by the existing suite.
- All 11 active figure prompts are represented by leaf `SKILL.md` files organized as an acyclic hierarchy, converted in branch groups after a working pilot.
- Each leaf's `schema.json`, `eval-manifest.json`, and `benchmark.json` remain per-check and shared across versions, so versions stay comparable.
- Sub-skill invocation happens through prose instructions and the `Skill` tool; `requires`/`produces` frontmatter documents and validates the graph and is never executed.
- One repository-level `CLAUDE.md` orients the agent; runtime orientation is generated per run, not checked in per check.
- The runtime directory is assembled outside the repository, exposes exactly one version per skill and only the current example, and is removed unless `--keep-runtime` is set.
- The agent's tool set matches an explicit allowlist: no `Bash` or other shell, **no subagent creation**, no unjustified network access, and no route to the repo, gold data, benchmarks, or other examples. Tests assert each prohibition.
- `cli.py` owns runtime assembly, per-example session execution, prediction writing, DAG validation, and SkillSet resolution.
- A per-example hook trace records actual `Skill` invocations incrementally; it is diagnostic only — never scored, never part of cache identity.
- Cache identity is exactly example content, SkillSet, model, effective config, and leaf schema.
- `score` applies the unchanged `FlatEvaluator` to final leaf JSON only.
- Legacy `evaluate` remains available and delegates agentic checklists to `cli.py`.

## Review Feedback Incorporated

Each review comment on the previous draft and where it now lives:

| Comment | Where addressed |
|---|---|
| Goal missing "hierarchical DAG for hierarchy, reuse, no cycles" | Goal |
| Frontmatter is not the orchestration source of truth; sub-skills called from prose; frontmatter is reference/validation only and ignored by the agent | Architecture, Constraints, Target Layout, Milestone 2 Step 4 |
| "At most one unpinned skill" is too strict | Milestone 6 Step 4 |
| Do not break existing scoring, reporting, curation | Constraints; Milestone 1; every milestone's automatic gate |
| `CLAUDE.md` should be top-level only, not per checklist/check | Target Layout |
| `schema.json` etc. must be common across versions or versions become incomparable | Constraints, Target Layout, Milestone 2 Step 3, Milestone 6 Step 7 |
| Phase order problematic — pilot before mass conversion | Delivery Order; Milestone 2 |
| `graph` over all of `fig-checklist` too slow; test on one or few checks | Delivery Order; Milestone 4 Step 8; Milestone 6 Step 3 |
| Start by separating `run` from `evaluate`, verify scoring intact | Milestone 1 |
| Use `micrograph-scale-bar` as the pilot | Milestone 2 |
| Runtime dir must be outside the repo; SDK finds skills in `.claude`; repo-internal runtime leaks skills, examples, and benchmarks | Constraints; Milestone 3 Steps 1–2 |
| Crystal-clear permissions; no `Bash`; no subagent creation | Constraints; Milestone 3 Step 5; Acceptance Checklist |
| Test agent confinement; keep or remove runtime dir per option | Milestone 3 Steps 1, 4, 7 |
| Additional material in the thinking document | Background link |
| Group conversion: micrographs/panels first, then plots/axes | Conversion Map Groups A and B; Milestone 5 Steps 3–5 |
| Priority is runtime dir + per-example agent + predictions; versioning last | Delivery Order; Milestone 4; Milestone 6 |
| Plan not progressive or gated enough; want milestones with unit-test gate plus human gate | Whole structure — six milestones, each with an automatic and a human gate |
