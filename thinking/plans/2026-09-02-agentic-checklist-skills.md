# Agentic Checklist Skills Implementation Plan

> **For Copilot:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Convert all active `fig-checklist` prompts into versioned Markdown skills and run the assembled, manifest-pinned SkillSet through `soda_mmqc/cli.py`, with agent-driven per-example skill discovery and leaf-only scoring.

**Architecture:** `SKILL.md` frontmatter is the graph source of truth; a complete checklist manifest pins every skill version. `cli.py` validates the full graph, expands at most one unpinned skill, assembles a runtime containing exactly one version per skill name, and deterministically batches examples. Within each per-example Claude Agent SDK session, the agent reads the requested leaf and invokes required skills using the `Skill` tool; the runner does not precompute or enforce a runtime closure. A PostToolUse hook writes a structured invocation trace; prediction caching keys on the full SkillSet rather than the observed trace.

**Tech Stack:** Python 3.12, existing PyYAML, pytest, existing `ModelCache` and `FlatEvaluator`, official Anthropic Claude Agent SDK, Langfuse for production-manifest exposure only.

---

## Constraints

- Markdown and YAML own skill instructions, dependencies, version pins, defaults, and generated documentation.
- Add one production Python module: `soda_mmqc/cli.py`. Keep helpers private there for v1.
- `soda_mmqc/scripts/run.py` retains the `evaluate` CLI and delegates agentic checklists to `cli.py`; it must not implement a second DAG runner.
- `cli.py` validates the complete graph and manifest, but it does not walk a leaf closure for runtime execution. Skill discovery/order belongs to the agent per example.
- The runtime agent sees the assembled skill tree only, never `skills-store` or sibling versions.
- Preserve existing leaf `schema.json`, `eval-manifest.json`, and `benchmark.json` unchanged. Score leaf JSON only; intermediate artifacts and traces are debug sidecars.
- Do not add OpenAI Agents, MCP, intermediate caches, parallel sessions, or a shared image/micrograph classifier in this implementation.

## Target Layout

```text
soda_mmqc/data/checklist/fig-checklist/
  CLAUDE.md                         # agent orientation
  version-manifest.yaml             # complete checked-in SkillSet pins
  model-defaults.yaml               # provider-neutral defaults
  dag.yaml                          # generated; never hand-edit
  README.md                         # generated; never hand-edit
  skills-store/
    identify-panels/v1/SKILL.md
    identify-panels/v1/schema.json
    classify-quantitative-plot/v1/SKILL.md
    classify-quantitative-plot/v1/schema.json
    micrograph-scale-bar/v1/SKILL.md
    micrograph-scale-bar/v1/schema.json
    micrograph-scale-bar/v1/eval-manifest.json
    micrograph-scale-bar/v1/benchmark.json
```

`SKILL.md` frontmatter must include `name`, `description`, `kind`, `requires`, `produces`, and `needs`. A leaf additionally owns its existing evaluation files. `requires` informs generated graph documentation and manifest validation, then becomes an explicit instruction in the leaf body to call dependencies with the `Skill` tool.

## Fig-Checklist Conversion Map

Convert all 11 active leaves. Select the newest prompt revision as initial source and preserve it in `metadata.source_prompt`; never expose multiple prompt revisions in the runtime tree.

| Leaf | Initial source | Runtime dependencies | Leaf retains |
|---|---|---|---|
| `error-bars-defined` | `prompt.4.txt` | `identify-panels`, `classify-quantitative-plot` | Error/box plot detection and caption decision |
| `individual-data-points` | `prompt.4.txt` | `identify-panels`, `classify-quantitative-plot` | Point requirement, visibility, and decision |
| `plot-axis-units` | `prompt.2.txt` | `identify-panels`, `classify-quantitative-plot` | Axis unit logic and extraction |
| `plot-gap-labeling` | `prompt.2.txt` | `identify-panels`, `classify-quantitative-plot` | Tick gap detection and marking |
| `replication-reporting` | `prompt.3.txt` | `identify-panels`, `classify-quantitative-plot` | Replicate reporting and decision |
| `stat-test` | `prompt.4.txt` | `identify-panels`, `classify-quantitative-plot` | Significance gate, test extraction, decision |
| `stat-significance-level` | `prompt.3.txt` | `identify-panels`, `classify-quantitative-plot` | Symbol definition and decision |
| `micrograph-scale-bar` | `prompt.2.txt` | `identify-panels` | Micrograph applicability and scale-bar extraction |
| `image-annotation-defined` | `prompt.2.txt` | `identify-panels` | Image applicability and annotation definitions |
| `single-channel-for-overlay` | `prompt.2.txt` | `identify-panels` | Overlay/channel completeness |
| `panel-image-matches-caption` | `prompt.2.txt` | `identify-panels` | Panel/caption comparison |

`identify-panels` produces a stable `panels` artifact containing panel label, region notes, and caption excerpt/span. `classify-quantitative-plot` consumes it and produces `quantitative_plot_panels` with the label, `is_quantitative_plot`, and evidence. This is the only additional shared skill in v1; visual image/micrograph type gates remain leaf-local because their criteria differ.

## Gates

| Gate | Exit criterion |
|---|---|
| G0 | All 13 skills and complete manifest are Markdown/YAML assets, with copied leaf evaluation contracts |
| G1 | `cli.py graph` validates the complete graph, resolves pins, and renders deterministic docs |
| G2 | `cli.py run --mock` assembles the full SkillSet and writes prediction, intermediate, and trace sidecars |
| G3 | `cli.py score` scores stored leaf predictions only; `evaluate` delegates agentic lists to `cli.py` |
| G4 | Claude session invokes skills dynamically and persists SDK-hook traces |

## Phase 0: Convert Markdown Assets (G0)

### Task 1: Audit and lock shared-skill boundaries

**Files:**
- Create: `soda_mmqc/data/checklist/fig-checklist/skills-store/README.md`
- Modify: `docs/plans/2026-09-02-agentic-checklist-skills.md`

**Step 1:** Create a source inventory from the conversion map: selected prompt revision, extracted shared procedure, and leaf-only decision procedure for every leaf.

**Step 2:** Confirm every extracted step has identical enough inputs and artifact output for reuse. Do not extract a decision policy merely because its prose resembles another leaf.

**Step 3:** Document why `identify-panels` and `classify-quantitative-plot` are shared and why image/micrograph classification remains leaf-local.

**Step 4:** Review the inventory. Do not edit legacy prompts or write runtime code.

### Task 2: Write shared skill contracts

**Files:**
- Create: `soda_mmqc/data/checklist/fig-checklist/skills-store/identify-panels/v1/SKILL.md`
- Create: `soda_mmqc/data/checklist/fig-checklist/skills-store/identify-panels/v1/schema.json`
- Create: `soda_mmqc/data/checklist/fig-checklist/skills-store/classify-quantitative-plot/v1/SKILL.md`
- Create: `soda_mmqc/data/checklist/fig-checklist/skills-store/classify-quantitative-plot/v1/schema.json`

**Step 1:** Write `identify-panels` with the universal panel-identification procedure and a JSON Schema for `panels`.

**Step 2:** Write `classify-quantitative-plot` with `requires: [identify-panels]`, an instruction to invoke that skill through the `Skill` tool, and a schema for `quantitative_plot_panels`.

**Step 3:** Keep both schemas runtime-only. Do not add expected outputs or evaluation manifests.

### Task 3: Convert all leaf prompts

**Files:**
- Create: `soda_mmqc/data/checklist/fig-checklist/skills-store/<leaf>/v1/SKILL.md` for each listed leaf
- Copy: each leaf's current `schema.json`, `eval-manifest.json`, and `benchmark.json` into its `v1` directory
- Create: `tests/fixtures/agentic/fig-checklist-skill-inventory.json`

**Step 1:** Convert the seven plot/stat leaves. State the required `Skill` calls in each leaf body, then retain only leaf-specific analysis and final-schema requirements.

**Step 2:** Convert the four image/cross-cutting leaves. Require `identify-panels`, preserve each leaf's own applicability logic, and keep final output limited to sibling `schema.json`.

**Step 3:** Verify every copied evaluation asset matches its legacy source:

```bash
cmp soda_mmqc/data/checklist/fig-checklist/<leaf>/schema.json \
  soda_mmqc/data/checklist/fig-checklist/skills-store/<leaf>/v1/schema.json
```

Repeat for `eval-manifest.json` and `benchmark.json`.

**Step 4:** Add the expected 13-skill inventory fixture: names, kinds, requirements, produces, and source prompts.

**Step 5:** Review leaf instructions against their source prompt: shared steps removed, leaf decisions retained, dependency invocation instruction explicit.

### Task 4: Add checklist metadata and generated views

**Files:**
- Create: `soda_mmqc/data/checklist/fig-checklist/CLAUDE.md`
- Create: `soda_mmqc/data/checklist/fig-checklist/version-manifest.yaml`
- Create: `soda_mmqc/data/checklist/fig-checklist/model-defaults.yaml`
- Create: `soda_mmqc/data/checklist/fig-checklist/dag.yaml`
- Create: `soda_mmqc/data/checklist/fig-checklist/README.md`

**Step 1:** Pin all 13 skills at `v1`. A missing or extra pin is invalid.

**Step 2:** Add provider-neutral defaults: model, maximum tokens, and allowed tool families. `needs` remains runner metadata, not provider-enforced frontmatter.

**Step 3:** Orient the agent in `CLAUDE.md`: it sees only assembled skills, must invoke dependencies through the `Skill` tool, validates artifacts before handoff, and returns final leaf JSON only.

**Step 4:** Create the first generated `dag.yaml` and README from pinned frontmatter; mark both generated.

**Step 5: Gate G0:** Review the full graph and copied leaf contracts before production Python work.

## Phase 1: Add Markdown Graph CLI (G1)

### Task 5: Validate manifests and render graph views

**Files:**
- Create: `soda_mmqc/cli.py`
- Create: `tests/test_agentic_cli.py`

**Step 1: Write failing tests** for invalid frontmatter, duplicate names, unknown requirements, cycles, missing pins, orphan pins, and non-existent versions. Test that the full manifest validates even though execution will not pre-walk a leaf closure.

**Step 2: Verify failure:** `pytest tests/test_agentic_cli.py -v`

**Step 3: Implement minimal private helpers:**

```python
def _load_skill(version_dir: Path) -> dict: ...
def _load_manifest(checklist_dir: Path) -> dict[str, str]: ...
def _validate_inventory(checklist_dir: Path, manifest: dict[str, str]) -> None: ...
def _expand_skillsets(manifest: dict[str, str], unpin: str | None) -> list[dict]: ...
def _skillset_hash(skillset: dict) -> str: ...
```

Use `yaml.safe_load` and canonical JSON. Validation reads the full pinned inventory to enforce manifest completeness, but execution does not call a closure function.

**Step 4:** Implement:

```bash
python -m soda_mmqc.cli graph fig-checklist
python -m soda_mmqc.cli graph fig-checklist --write
```

The normal command checks generated-file drift. `--write` writes deterministic graph docs.

**Step 5: Verify pass:** `pytest tests/test_agentic_cli.py -v`

### Task 6: Add one-dimensional unpin selection

**Files:** Modify `soda_mmqc/cli.py` and `tests/test_agentic_cli.py`.

**Step 1:** Write failing tests for pinned baseline, `--unpin micrograph-scale-bar`, optional `--versions v1,v2`, unknown skill/version, and multiple unpinned skills.

**Step 2:** Implement `--unpin SKILL` and `--versions VERSION[,VERSION...]`. Expand only the selected skill's available versions; all others remain manifest-pinned. Each complete SkillSet stores sorted `{name, version, content_hash}`.

**Step 3: Verify pass:** `pytest tests/test_agentic_cli.py -v`

**Step 4: Gate G1:** Run `cli.py graph` against `fig-checklist` and review failure messages for deliberate malformed fixtures.

## Phase 2: Execute and Score Without Precomputed Closures (G2-G3)

### Task 7: Assemble full runtime and implement mock execution

**Files:**
- Modify: `soda_mmqc/cli.py`
- Modify: `soda_mmqc/config.py`
- Modify: `tests/test_agentic_cli.py`

**Step 1: Write failing tests** that a selected SkillSet assembles `data/.runtime/<skillset_hash>/skills/<name>` for all 13 pinned skills, one version per name, with symlink/copy fallback. Assert the assembled tree cannot expose sibling store versions.

**Step 2:** Add `AGENTIC_RUNTIME_DIR`. Implement atomic assembly with generated runtime `CLAUDE.md`; it names the leaf, full skills root, artifacts root, and final schema. Do not select or execute a graph closure here.

**Step 3:** Add `run --mock`. For each benchmark example, write expected leaf output as the prediction and an ordered `skill_trace.json` sidecar with deterministic mock entries. Write intermediate placeholder/fixture data separately.

**Step 4:** Cache whole sessions by `(example_content_hash, skillset_hash, model, effective_config_hash, leaf_schema_hash)`. Do not hash or key cache reuse on observed traces; a full SkillSet fixes all possible versions regardless of agent invocation choices.

**Step 5: Verify pass:** `pytest tests/test_agentic_cli.py -v`

### Task 8: Add a separate scoring command

**Files:**
- Modify: `soda_mmqc/cli.py`
- Modify: `soda_mmqc/scripts/run.py`
- Modify: `tests/test_agentic_cli.py`
- Modify: `tests/test_run_analyze_results.py`
- Modify: `pyproject.toml`

**Step 1:** Write a failing test for:

```bash
python -m soda_mmqc.cli score fig-checklist --check micrograph-scale-bar --predictions PATH
```

It must load final leaf predictions and produce the existing `FlatEvaluator` `flat` result; intermediate JSON and traces must not change scoring.

**Step 2:** Reuse `analyze_results` and `save_analysis` from `soda_mmqc/scripts/run.py` without changing evaluator semantics. Add `score = "soda_mmqc.cli:main"` only after a `score` subcommand is stable.

**Step 3: Verify pass:** `pytest tests/test_agentic_cli.py tests/test_run_analyze_results.py -v`

### Task 9: Delegate `evaluate` agentic runs to `cli.py`

**Files:**
- Modify: `soda_mmqc/scripts/run.py`
- Modify: `tests/test_agentic_cli.py`
- Modify: `README.md`

**Step 1:** Write failing compatibility tests: legacy checks retain present behavior; a checklist with `version-manifest.yaml` dispatches `--mock`, `--check`, `--checks`, `--model`, and `--no-cache` to `soda_mmqc.cli.main(argv)`; agentic `--prompt-version` errors clearly.

**Step 2:** At the `run.py` CLI boundary, detect an agentic manifest, translate supported options, and delegate. Leave legacy `process_check` and prompt-version implementations untouched.

**Step 3: Verify pass:** `pytest tests/test_agentic_cli.py tests/test_run_analyze_results.py -v`

**Step 4: Gate G3:** Run one legacy mock command and agentic mock `evaluate fig-checklist --check micrograph-scale-bar`.

## Phase 3: Claude Agent Runtime and Traces (G4)

### Task 10: Integrate dynamic Skill-tool execution

**Files:**
- Modify: `pyproject.toml`
- Modify: `soda_mmqc/cli.py`
- Modify: `tests/test_agentic_cli.py`
- Modify: `README.md`

**Step 1:** Confirm the official, current Claude Agent SDK package/API from Anthropic primary documentation before adding it. Document the selected package/API version.

**Step 2: Write fake-client tests** for a private `_run_agent_session`: agent request uses the assembled runtime, target leaf and example inputs; no pre-run closure is supplied; final leaf JSON validates against leaf schema; invalid output fails before prediction write.

**Step 3:** Add an SDK `PostToolUse` hook. In test fixtures feed structured tool-use blocks, filter `tool_name == "Skill"`, and write entries as they occur to:

```text
data/predictions/<checklist>/<leaf>/<skillset_hash>/<model>/<example>/intermediates/skill_trace.json
```

Each entry contains `skill`, manifest-pinned `version`, `tool_input`, `tool_use_id`, and timestamp. Write incrementally, preserving traces when a session errors.

**Step 4:** Validate runtime intermediate artifacts against optional intermediate schemas before they are passed onward. Persist validated artifacts as sidecars. Do not parse Claude Code transcript JSONL or agent prose to infer calls.

**Step 5:** Map checklist defaults plus the union of declared `needs` to Agent SDK session options. Treat frontmatter as runner-owned metadata: SDK settings enforce tools/permissions.

**Step 6: Verify pass:** `pytest tests/test_agentic_cli.py -v`

**Step 7: Credentials-enabled smoke test after approval:**

```bash
python -m soda_mmqc.cli run fig-checklist --check micrograph-scale-bar --model <claude-model> --no-cache
```

Confirm a valid leaf prediction and `skill_trace.json`; inspect that `identify-panels` was actually invoked. This trace is diagnostic only, not part of cache identity or scoring.

## Acceptance Checklist

- All 11 active figure prompts are represented by 11 leaf `SKILL.md` files, with legacy evaluation assets preserved.
- The 13-node graph is documented and fully pinned; invalid manifests fail before assembly or provider calls.
- `cli.py` owns DAG metadata validation, SkillSet resolution, runtime assembly, batching, and agentic execution.
- The agent, not the runner, discovers and calls skills for each example through structured `Skill` tool use.
- Runtime trees expose exactly one version per skill name and never expose the store.
- A per-example hook trace records actual `Skill` invocations incrementally; it is not scored or hashed for cache reuse.
- Cache identity is exactly example content, full SkillSet, model, effective config, and leaf schema.
- `score` applies the unchanged FlatEvaluator to final leaf JSON only.
- Legacy `evaluate` behavior remains available and delegates agentic checklists to `cli.py`.