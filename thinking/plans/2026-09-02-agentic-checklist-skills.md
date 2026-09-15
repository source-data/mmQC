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

## Gate Protocol

Every milestone ends with an **automatic gate** (a named pytest command that must pass). Human gates are *not* only end-of-milestone reviews: they sit wherever the next step is irreversible, unfalsifiable by a test, or spends money or trust. A gate is a **stop point** — the implementing agent halts, presents the named artifact, and waits. It does not proceed on assumption, and it does not "provisionally continue while awaiting confirmation."

Each human gate below states three things:

- **Decision** — the single question the person is answering. If the answer is not yes, work stops at that gate.
- **Artifact** — exactly what the person is handed to look at. A gate without a concrete artifact is theatre; the agent must produce it before asking.
- **Blocks** — what may not start until the decision is recorded.

Record each decision (date, who, verdict, any conditions) in the milestone's section of this plan as it happens, so a later reader can see what was actually approved rather than what was planned.

A gate is warranted where one of these is true, and only there:

1. **The change is hard to reverse or silently breaks others** — data-shape and enumeration semantics, retiring legacy assets.
2. **Only a human can judge the quality** — prose, `description` wording, whether a converted skill lost meaning.
3. **It is a security or containment boundary** — the permission allowlist, the runtime root.
4. **It commits resources or third parties** — adding a runtime dependency, using credentials, live model spend.
5. **It is a design fork the plan deliberately left open** — whether Group B needs a shared plot skill.
6. **It is a go/no-go on the project's core premise** — whether delegated discovery actually works, and whether agentic scores are acceptable enough to scale.

Do not start milestone N+1 before every gate of milestone N passes.

### Human gates at a glance

| Gate | Sits before | Decision |
|---|---|---|
| 1A | changing `list_checks()` | Does the contracts-own-the-directory rule reproduce today's check list exactly? |
| 1B | Milestone 2 | Are analysis JSON and the exported report byte-identical to before? |
| 2A | writing the leaf skill | Is the merged `identify-panels` prose complete and is its `description` unambiguous? |
| 2B | Milestone 3 | Did the leaf conversion lose nothing check-specific and read naturally? |
| 3A | implementing assembly | Is the chosen runtime root outside the repo and off every synced/backed-up path? |
| 3B | opening any session | Is the permission allowlist exactly right, with no shell and no subagent? |
| 3C | Milestone 4 | Does a real assembled runtime contain no route out? |
| 4A | adding the dependency | Is this the SDK package, version, and auth model we commit to? |
| 4B | requesting credentials | Is the mock prediction and trace shape right? |
| 4C | the first live run | Approve credentials, model, and a capped example budget. |
| 4D | Milestone 5 | Did delegated discovery reach the right skill — continue, re-author, or rethink? |
| 5A | converting any further leaf | Are the pilot's agentic scores acceptable against the legacy path? |
| 5B | Group A conversion | Is legacy `evaluate` behaviour unchanged for real callers? |
| 5C | Group B design | Group A delta review; may the legacy prompts be retired? |
| 5D | writing a plot skill | Does Group B need a shared plot skill, and what exactly does it own? |
| 5E | Milestone 6 | Group B delta review. |
| 6A | pinning production | Are the initial version pins and model defaults the ones we want exposed? |
| 6B | trusting generated docs | Is the first generated `dag.yaml`/`README.md` a faithful picture of the graph? |
| 6C | close-out | Do failure messages name the offending file, and do two versions score comparably? |

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

**The hierarchy is not encoded in the directory layout.** Every skill — leaf or intermediate — is a flat sibling directory in one namespace, addressed by name. The DAG exists only because one skill's own `SKILL.md` calls another skill; nothing about a skill's depth, role, or dependencies may be inferred from where its directory sits. There is no `_shared/`, no `leaves/`, no nesting of a dependency underneath its caller. This keeps a skill relocatable and reusable — including across checklists later — without rewriting the graph, and it prevents the two representations from drifting apart.

Leaf evaluation contracts stay at the skill level; only `SKILL.md` is versioned.

```text
soda_mmqc/data/checklist/fig-checklist/
  version-manifest.yaml             # SkillSet pins (added in Milestone 6)
  model-defaults.yaml               # provider-neutral defaults
  dag.yaml                          # generated; never hand-edit
  README.md                         # generated; never hand-edit
  micrograph-scale-bar/             # leaf: an existing check dir, unmoved
    schema.json                     # shared by all versions of this skill
    eval-manifest.json              # shared by all versions
    benchmark.json                  # shared by all versions
    prompts/                        # legacy; retired only after parity
    v1/SKILL.md
    v2/SKILL.md
  identify-panels/                  # intermediate skill: a sibling, not nested
    schema.json                     # runtime contract only, no eval assets
    v1/SKILL.md
```

`identify-panels` sits beside `micrograph-scale-bar` rather than under it precisely because several leaves call it; the fact that it is upstream is a property of the calls, not of the path.

**The only on-disk difference between a leaf and a shared skill is the evaluation contracts.** A leaf carries `schema.json`, `eval-manifest.json`, and `benchmark.json`; a shared skill does not. Nothing else distinguishes them — same level, same shape, no name convention, no marker file, and no `kind` discriminator in frontmatter. Two discriminators would eventually disagree, so there is exactly one, and it is the thing that already has to be true: a check is a directory that owns an evaluation contract.

`SKILL.md` carries the calling relationship in the skill's own file, in two places with two different jobs:

- **Frontmatter** (`name`, `description`, `requires`, `produces`, `needs`) is runner-owned metadata: it is what `cli.py` reads to render the DAG, detect cycles, and validate the manifest. The agent never reads it as a call sequence. `description` is the exception that the agent *does* consume — it is what makes a skill findable during discovery.
- **Prose** in the body is what actually executes — a sentence instructing the agent to call the named skill with the `Skill` tool.

A validation test asserts the two agree: every skill named in `requires` also appears in the prose, and no skill invoked in prose is missing from `requires`. Frontmatter documents the graph; prose runs it.

## Two Different Discoveries

The word covers two unrelated mechanisms, and conflating them produces exactly the wrong design.

**Runner-side check enumeration** is bookkeeping. `list_checks()` in [run.py:1143](../../soda_mmqc/scripts/run.py#L1143) currently treats *every* subdirectory of a checklist as a check, which with shared skills as flat siblings would report `identify-panels` as a phantom check and break existing runs and reports. The fix follows directly from the layout rule above: a directory is a check when it owns the evaluation contracts. Shared skills have none, so they are not checks — not because they are filtered out, but because there is nothing to score. Resolve this in Milestone 1, with a test, before adding any shared skill.

**Agent-side skill discovery** is the substance of this project, not a hazard to engineer around. Every skill in the assembled runtime — leaves and shared skills alike — has its `description` loaded into the session. The runner preselects nothing and prunes nothing. It names one check, and the agent enters at that leaf and walks down through prose triggers:

```text
micrograph-scale-bar          entry point; its prose asks the agent to classify panels
  → classify-panel-kind       its prose asks the agent to work on individual panels
      → identify-panels       root of the DAG; produces the shared panels artifact
```

Each hop happens because the skill the agent is currently reading tells it, in prose, to do something that another skill's `description` matches. That three-hop shape is the mechanism in general; the Milestone 2 pilot deliberately starts with the two-hop version (`micrograph-scale-bar` → `identify-panels`) and only adds a middle skill once a second leaf shows the duplication that would justify it. **Delegating that chaining is the entire reason for using an agent instead of walking the DAG deterministically in Python.** So whether the chain fires correctly — with all descriptions competing for the agent's attention — is what Milestones 2 and 4 are built to test, and the `Skill` invocation trace is how we observe it. A runner that precomputed the closure would be measuring its own control flow instead.

The corollary for authoring: a skill's `description` is load-bearing. It has to be specific enough that the intended caller's prose reaches it and vague neighbours do not. That is a real failure mode to watch in the pilot — a wrong or missing hop shows up in the trace, not in a Python error.

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

**Step 1:** Write failing tests: a `score` entry point loads stored predictions plus gold, and produces the same `FlatEvaluator` `flat` result the current `evaluate` path produces for at least one existing check. Add tests for check enumeration: a sibling directory owning the evaluation contracts is a check, one without them is not, and every current `fig-checklist` check is still enumerated exactly as today.

**Step 2:** Verify failure: `pytest tests/test_agentic_cli.py -v`

**Step 3:** Implement `python -m soda_mmqc.cli score <checklist> --check <check> --predictions PATH`, reusing `analyze_results` and `save_analysis` from `run.py` verbatim. Do not change evaluator semantics, thresholds, or output shape.

**Step 4: Human gate 1A — enumeration semantics, before any change to `list_checks()`.**

- **Decision:** does "a check is a directory that owns the evaluation contracts" reproduce today's check list exactly, and does nothing downstream depend on the old every-subdirectory rule?
- **Artifact:** a printed side-by-side of the checks enumerated today versus under the proposed rule for every checklist in the repo — not just `fig-checklist` — plus a short list of the call sites of `list_checks()` and what each does with the result (reporting, curation, export).
- **Blocks:** Step 5. This one changes what the rest of the system believes exists; a wrong answer shows up later as a missing check in a report rather than as a test failure, which is why a person confirms the inventory rather than a test asserting the rule against itself.

> **Decision recorded — 2026-09-09, Çağatay Gürsoy: PASSED WITH A FINDING, fix applied.**
>
> *Enumeration:* exact match. 31 checks, identical under both rules on all four
> checklists (`fig` 11, `doc` 11, `data` 3, `Retired` 6). Nothing dropped or added.
>
> *Downstream:* **the second question was answered no.** `list_checks()` has
> three call sites, all safe, but two modules enumerate checks without it.
> `reporting/load.py` and `visualize.py` walk `EVALUATION_DIR` and are safe
> structurally (a shared skill is never scored, so it can never appear there).
> **`curation.load_checklist()` walked the checklist directory itself** and
> skipped a subdirectory only when a contract file existed *but was invalid* —
> a missing `benchmark.json` was not a skip. On the Milestone 2 shape it
> returned `['identify-panels', 'micrograph-scale-bar']`, i.e. the shared skill
> would have appeared as a selectable entry in the curation check selector.
>
> *Condition of the pass:* fix curation now rather than defer. Done —
> `EVALUATION_CONTRACT_FILES` and `owns_evaluation_contracts()` moved to
> `soda_mmqc/config.py`, imported by both enumerators (`run.py` re-exports them,
> so existing imports are unaffected). This **changes curation behaviour**,
> which the milestone constraint otherwise forbids; accepted explicitly. Two
> pre-existing `tests/test_curation.py` tests asserting the permissive rule were
> updated. Accepted consequence: a check with `schema.json` but no
> `benchmark.json` yet is invisible in curation — on disk it is
> indistinguishable from a shared skill. No existing check is affected (all 31
> own both contracts).
>
> *Process note:* this gate was produced **after** Step 5, not before it, because
> the gates were added to the plan after Milestone 1 was implemented. Run in its
> specified position it would have caught the curation enumerator before the
> code was written.
>
> Full artifact: [`2026-09-09-milestone-1-results.md`](2026-09-09-milestone-1-results.md#human-gate-1a--enumeration-semantics).

**Step 5:** Make `list_checks()` enumerate directories that own the evaluation contracts, rather than every subdirectory, so a shared skill sitting beside the checks cannot become a phantom check. No name convention and no marker file.

**Step 6: Automatic gate:** `pytest tests/ -v` — the whole suite, including reporting, curation, and evaluation tests, passes unchanged.

**Step 7: Human gate 1B — regression parity, before Milestone 2.**

- **Decision:** is existing behaviour genuinely unchanged?
- **Artifact:** run one real legacy command (`evaluate fig-checklist --check micrograph-scale-bar --mock`) plus the existing report export, and produce a diff of the analysis JSON and the exported report against output captured before the change.
- **Blocks:** Milestone 2. An empty diff is the pass condition; any non-empty diff must be explained and accepted explicitly, not waved through as cosmetic.

> **Decision recorded — 2026-09-09, Çağatay Gürsoy: PASSED.**
>
> Run at `60f73b22` versus the working tree, same interpreter and dataset, 38
> examples each side, `EVALUATION_DIR` redirected to temp. Nothing in the
> evaluated path stubbed. Re-confirmed after the gate 1A curation fix.
>
> - `analysis.json`: **byte-identical**, 2,890,658 bytes, MD5 `b35f5a0d…`.
> - Exported report: file set identical; one `index.html` differed on 10 lines.
> - **Diff explained, not waved through:** those 10 lines carry exactly 5 random
>   plotly `<div id>` UUIDs. After normalising them the files are byte-identical
>   with zero residual. A control run — exporting twice from the *same*
>   `analysis.json` — also yields 0 UUID overlap, proving the UUIDs are exporter
>   nondeterminism and not change-induced.
>
> *Two environmental findings, neither blocking, both needing action:*
> 1. **`--mock` is not offline.** `process_checklist()` calls
>    `validate_model_for_provider()` first, which does a live `models.list()`.
>    Without credentials the run aborts before the mock branch. This makes gate
>    4B ("is the mock output shape right?") impossible to run *before* gate 4C
>    authorises credentials, which is the ordering Milestone 4 specifies.
>    Validation should be skipped when `--mock` is set.
> 2. **The command writes nothing when Langfuse is configured.** Benchmark
>    config is sourced from Langfuse, whose `micrograph-scale-bar` entry has no
>    `examples`; the local `benchmark.json` has 38. The gate was run on the
>    local-config path, pinned identically on both sides. Future regression
>    gates must pin the config source or they are not reproducible.
>
> Full artifact: [`2026-09-09-milestone-1-results.md`](2026-09-09-milestone-1-results.md#human-gate-1b--regression-parity).

## Milestone 2: Pilot the Hierarchy on One Check

**Deliverable:** `micrograph-scale-bar` is an entry-point leaf whose prose reaches one shared skill, `identify-panels` — hand-authored and reviewed, with its evaluation contracts untouched and shared across versions.

**Files:**
- Create: `soda_mmqc/data/checklist/fig-checklist/identify-panels/v1/SKILL.md`
- Create: `soda_mmqc/data/checklist/fig-checklist/identify-panels/schema.json`
- Create: `soda_mmqc/data/checklist/fig-checklist/micrograph-scale-bar/v1/SKILL.md`
- Modify: `tests/test_agentic_cli.py`

**Step 1:** Extract `identify-panels` from the best existing wording (the panel-identification sections of `error-bars-defined`, `micrograph-scale-bar`, and `image-annotation-defined` are nearly identical). Merge once; do not keep N variants. Write `schema.json` as the runtime contract for `panels` — no eval manifest, no benchmark, no expected outputs, which is also what keeps it from being enumerated as a check.

Write its `description` deliberately: it is the string the agent matches against when the leaf's prose asks for panels, so it must claim panel identification unambiguously and claim nothing else.

**Step 2: Human gate 2A — the shared skill's wording, before any leaf depends on it.**

- **Decision:** does the merged `identify-panels` prose preserve everything the three source sections said, and is its `description` specific enough to win the intended hop and narrow enough not to attract unrelated ones?
- **Artifact:** the three source panel-identification sections quoted side by side with the merged `SKILL.md`, the proposed `description` on its own line, and the draft `panels` `schema.json`.
- **Blocks:** Step 3. This is the one asset every other leaf will inherit, and its two failure modes — a dropped instruction and a vague `description` — are both invisible to the test suite. Fixing it after four leaves point at it means re-reviewing four leaves.

> **Decision recorded — 2026-09-11, Çağatay Gürsoy: PASSED, with one gold
> correction executed.**
>
> *The spelling fork:* **`Ai`/`Aii` — "makes more sense. Force everything into
> this."** This is the form the caption itself uses (`(Ai–ii)`), the form the
> shared skill already emitted under its own "report the labels the figure
> actually carries" rule, and the form twelve of the sixteen gold files for that
> figure already had. The shared skill needed **no change**; the gold did.
>
> *Executed:* four gold files for `10.1038_s44321-025-00219-1/content/1`
> normalized — `micrograph-scale-bar`, `panel-label-detection` and
> `panelisation-and-classification` carried `A i`/`A ii`, and
> `replicates-defined` carried `Aii` twice with byte-identical content and no
> `Ai` at all, which was the missing first sub-panel. All sixteen gold files for
> the figure now read `['Ai', 'Aii', 'B', 'C']`. Dataset-wide there are no
> spaced sub-panel labels left.
>
> *The composite-panel rule* that this gate's preparation found wrong was
> corrected before the decision: labelled sub-parts get one entry each,
> unlabelled composites stay one entry, and inventing a separator is forbidden.
>
> *Conditions and carry-forward:* two further instances of the same class of
> gold — a curator sub-dividing a panel the figure does not sub-label — remain
> and were **not** touched, because they are a different judgement than the
> `Ai`/`Aii` one: `C top`/`C bottom` in `plot-axis-units` (a Group B leaf, so
> it lands in Milestone 5) and `B (H1.1)`/`B (RCC1)`/`B (H1t)` in `n_larger-two`
> (not `fig-checklist`). The shared skill will emit `C` and `B` for these, so
> they will mis-align until decided.
>
> ⚠️ *`soda_mmqc/data/examples/` is gitignored*, so this gold edit has no diff
> and no git undo. The exact inverse is recorded in
> [`2026-09-10-milestone-2-results.md`](2026-09-10-milestone-2-results.md#the-gold-correction-executed-at-this-gate).
>
> Full artifact: [`2026-09-10-milestone-2-results.md`](2026-09-10-milestone-2-results.md#human-gate-2a--the-shared-skills-wording).

**Step 3:** Convert `micrograph-scale-bar/prompt.2.txt` into `v1/SKILL.md`: delete the duplicated panel-identification section, add a sentence in the prose instructing the agent to call `identify-panels` with the `Skill` tool, and keep only the micrograph applicability rule, scale-bar extraction rules, and the decision logic. Point the output requirement at the check's existing `schema.json` rather than pasting a full JSON example.

**Step 4:** Leave `schema.json`, `eval-manifest.json`, and `benchmark.json` exactly where they are. Assert with a test that no version directory contains a copy of them.

**Step 5:** Write tests for skill loading and consistency: frontmatter parses; `requires` names an existing skill; the graph is acyclic; every name in `requires` also appears in the prose body, and no skill invoked in prose is missing from `requires`. Add a test that the resolved graph is unchanged when a skill directory is renamed or moved to a different parent — the edges come from the calls, not the paths.

**Step 6: Automatic gate:** `pytest tests/test_agentic_cli.py tests/test_micrograph_scale_bar_manifest.py -v`

> **Automatic gate passed — 2026-09-10, re-run 2026-09-11.** 121 passed (58
> before, +63 new). Whole suite unaffected: the sorted `FAILED`/`ERROR` line set
> is identical (62 lines) with and without this milestone's files, and unchanged
> again after gate 2A's gold correction. The new tests were verified
> failing-first by eight mutations. Full artifact:
> [`2026-09-10-milestone-2-results.md`](2026-09-10-milestone-2-results.md#automatic-gate).

**Step 7: Human gate 2B — the leaf conversion, before Milestone 3.**

- **Decision:** did the conversion lose anything check-specific, leave anything shared duplicated, or turn the sub-skill call into a template?
- **Artifact:** `identify-panels/v1/SKILL.md` and `micrograph-scale-bar/v1/SKILL.md` read side by side with `prompt.2.txt`, plus a line-level account of every rule in the prompt and where it went (kept in the leaf, moved to the shared skill, or deliberately dropped).
- **Blocks:** Milestone 3. Also confirm the leaf's dependency is legible from the skill text alone, without reference to where either directory sits — if a reader has to look at the filesystem to see the edge, the prose is wrong.

> **Decision recorded — 2026-09-11, Çağatay Gürsoy: PASSED, no changes
> required.**
>
> All three parts of the gate's question are answered *no defect*, and none of
> them rests on a reading alone:
>
> - *Nothing check-specific lost.* The 71-line account covers every line of
>   `prompt.2.txt`; a mechanical sweep of all 115 of its content words found 13
>   absent from leaf-plus-shared, every one a tokenization artifact
>   (`three-dimensional` is one token), a prompt typo the skills fixed
>   (`itsself`, `tyipcally`, `systematical`), a morphological variant, or a
>   synonym (`sub-panels` → `sub-parts`).
> - *Nothing shared duplicated.* The leaf's §1 asks for the inventory and never
>   restates how to find panels. Pinned by `TestNoLeafRestatesTheSharedSkill`,
>   which is the guard that matters in Milestone 5.
> - *The call is prose, not a template.* One sentence naming the skill, the
>   tool and a reason.
>
> *Exactly one rule moved* (§1) and *exactly one thing was dropped* (the JSON
> example, which Step 3 requires). The drop turned out to be a **net
> improvement**: the example showed every panel's scale bar defined in exactly
> one place, while gold has 15 rows defined in both and 16 in neither — 38% of
> micrograph rows are shapes it never demonstrated. The leaf's replacement prose
> states the independence explicitly.
>
> *Accepted as-is, deliberately not changed:* the `from_the_image` "number and
> unit" rule, which 2 gold rows exceed by carrying several bars per panel
> (`5 µm; 2 µm`). Writing a rule the prompt never made is the drift this gate
> exists to catch; it is a one-line addition whenever it is wanted.
>
> *Questions raised and closed at this gate:* **kymographs need no action** —
> the pilot's one kymograph figure (`10.1038_s44318-026-00715-1/content/3`,
> panel H) has gold marking it `micrograph: yes`, so the leaf's rule is what its
> own gold does, and `image-annotation-defined` has no gold for that figure, so
> the two leaves disagree only in prompt text.
>
> *Carried into Milestone 5:* nine gold rows in
> `10.1038_s44319-025-00631-1` describe where a scale bar sits rather than what
> it reads (a curation matter); `C top`/`C bottom` in `plot-axis-units` must be
> settled before Group B; and the preamble repeats across both skills.
>
> Full artifact: [`2026-09-10-milestone-2-results.md`](2026-09-10-milestone-2-results.md#human-gate-2b--the-leaf-conversion).

## Milestone 3: Sealed Runtime Directory Outside the Repository

**Deliverable:** `cli.py` assembles a self-contained runtime directory in a temp location outside the repo, containing exactly the skills and the one example the agent may see — with tests proving the agent cannot reach anything else.

**Files:**
- Modify: `soda_mmqc/cli.py`
- Modify: `soda_mmqc/config.py`
- Modify: `tests/test_agentic_cli.py`

**Step 1:** Write failing tests for assembly: the runtime root is outside the repository tree; skills are placed where the Agent SDK discovers them; **every skill of the checklist is present, leaves and shared skills alike, so all of their descriptions load** — the runner preselects nothing and prunes nothing to the named check; exactly one version per skill name is present; the store and sibling versions are absent; only the current example's inputs are present; `benchmark.json`, `eval-manifest.json`, and expected outputs are **absent**.

**Step 2:** Add `AGENTIC_RUNTIME_DIR` to `config.py`, defaulting to a system temp location, never a path inside the repo. Document why: the Agent SDK discovers skills by convention under `.claude`, and a runtime rooted in the repo would let repo-level skills, other checklists, and the gold data leak into the session. Copy inputs in rather than mapping the repo in.

**Step 3: Human gate 3A — the runtime root, before assembly is implemented.**

- **Decision:** is the chosen default root acceptable on the machines this will actually run on?
- **Artifact:** the resolved absolute path on each target environment (developer laptop, CI), with confirmation that it is outside the repository, outside any cloud-synced or backed-up directory, and on a filesystem where the cleanup in Step 5 genuinely removes data.
- **Blocks:** Step 4. "Outside the repo" is testable; "not inside a synced folder that quietly uploads gold-derived intermediates" is not — a person has to look at the actual machine.

> **Decision recorded — 2026-09-14, Çağatay Gürsoy: OS-INDEPENDENCE REQUIRED, delivered.**
>
> *"Runtime should be independent on OS. This should run on any given OS."* The
> original artifact answered for one laptop (`tmutil`, a POSIX mode bit), which
> is evidence about a machine rather than about the design. The guarantees now
> live in portable code: the default is `tempfile.gettempdir()` with **no
> per-OS branching**; the repo-containment check is **case-insensitive**, since
> macOS and Windows would otherwise let a differently-cased path past a rule
> their own filesystem treats as identical; `CLOUD_SYNC_MARKERS` refuses
> Dropbox/OneDrive/Google Drive/iCloud/Box/pCloud/Nextcloud/Yandex paths on
> every platform; and orientation text and permission rules render POSIX
> separators. Nine tests cover it, and reverting the case-insensitive check
> fails one.
>
> Retained as illustration — resolved root on the developer laptop: `/private/var/folders/rk/…/T` via
> `tempfile.gettempdir()`, overridable by `SODA_MMQC_AGENTIC_RUNTIME_DIR`.
> Outside the repo (and `resolve_agentic_runtime_root()` raises on a
> repo-internal path — verified firing); no cloud-sync directory exists on the
> machine at all; `tmutil isexcluded` reports **`[Excluded]`**; local APFS, so
> removal genuinely removes; mode `drwx------`.
>
> **This gate's scope needs widening, and that is the milestone's main
> finding.** Per Anthropic's Agent SDK documentation, default options load
> skills from `~/.claude/skills/` *as well as* the cwd and its parents — so the
> user scope leaks in **regardless of which root is chosen**, and no root can
> exclude it. On a machine with personal skills installed, foreign descriptions
> would join a scored run silently and differently per machine, corrupting
> exactly what Milestone 4 measures. Resolved by pinning
> `AGENTIC_SETTING_SOURCES = ("project",)` and documenting any widening as a
> containment change. That is a third containment surface, alongside the root
> and the tool allowlist, which the plan text does not cover.
>
> Also open: macOS reaps `/private/var/folders` on a schedule, so a
> `--keep-runtime` directory kept overnight may vanish; and the CI path is a
> prediction, since `ci.yml` does not run these tests today.
>
> Full artifact: [`2026-09-14-milestone-3-results.md`](2026-09-14-milestone-3-results.md#human-gate-3a--the-runtime-root).

**Step 4:** Implement atomic assembly plus a generated runtime orientation file naming the target leaf as the entry point, the skills root, the artifacts root, and the final schema. Name the entry point only — do not list its dependencies, do not order them, and do not compute or execute a graph closure. Finding the rest is the agent's job.

**Step 5:** Add `--keep-runtime` (default: remove the directory after the session; keep it for debugging). Test both paths, including cleanup after an exception.

**Step 6:** Define the permission profile explicitly, deny-by-default, and test it. Allowed: reading the copied example, reading the assembled skills, writing artifacts under the runtime artifacts root, and the `Skill` tool. Denied, with a test asserting each is absent from the session's tool set:

- **`Bash`** and any other shell or code execution — it would let the session escape the runtime directory.
- **Subagent creation** — no `Task`/`Agent` tool, no nested sessions. A spawned agent negotiates its own context and permissions, which reopens the containment problem from another direction and makes the per-example `Skill` trace unreliable.
- Network access, web fetch, and web search, unless a skill's `needs` justifies it and the justification is recorded.

Frontmatter does not enforce any of this on the Agent SDK path, so the runner sets it on the session options and asserts the resulting tool set matches the profile exactly — an allowlist comparison, not a denylist, so a future SDK tool cannot silently appear.

**Step 7: Human gate 3B — the permission allowlist, before any code path can open a session.**

- **Decision:** is this allowlist exactly what the agent may do, and is every `needs`-justified exception acceptable?
- **Artifact:** the literal allowlist as it will be passed to the session options, the full tool set the SDK reports for that configuration, and the diff between them; plus the recorded justification for any network capability requested by a skill's `needs`.
- **Blocks:** Step 8 and all of Milestone 4. Approve the allowlist before a session can be opened, not after one has run — a containment failure reviewed retrospectively has already happened. Any later widening of this list is a new gate, not an implementation detail.

> **Decision recorded — 2026-09-14, Çağatay Gürsoy: PASSED on scope, WITH A
> CORRECTION the review itself produced.**
>
> *(1) "Read/Write/Skill is sufficient"* — accepted, no `Glob`/`Grep`.
> *(2) `skills="all"` "reasoning should hold, if required revisit in Milestone
> 4"* — accepted with the revisit carried forward. *(3) "We might need a
> stricter mode here; what can we do to have more human input?"* — **correct,
> and the original profile was the weakest option available.**
>
> Re-reading the SDK permission docs found two defects. `allowed_tools` is
> **not** an allowlist — "any other tool not listed is still available" — so
> `permission_mode` had to become **`dontAsk`**, the documented lockdown
> pairing. And the tools were **not scoped to paths**: a bare `Read`
> auto-approves reading anything on disk, including the repo and the gold.
> Rules are now `Read(//<root>/**)`, `Edit(//<artifacts>/**)`, `Skill` — `Edit`
> because a `Write(path)` rule "is never matched by the file permission
> checks", and `//` because a single slash anchors at the working directory.
>
> **On human input there is a real tension:** under `dontAsk` the SDK never
> calls `canUseTool`, and auto-approved tools skip it in any mode — so it would
> give false assurance. Oversight must come from a **`PreToolUse` hook**, which
> runs before every other step in every mode. Proposed for Milestone 4: an
> always-on audit hook (sharing the machinery the `Skill` trace already needs)
> plus an opt-in `--approve-tools` interactive hook for the supervised examples
> gate 4C authorises.
>
> *Still outstanding from the original artifact:*
>
> Allowlist: `["Read", "Write", "Skill"]`, compared for **equality** rather than
> as a denylist, so a future SDK tool fails the check instead of being granted.
> Denied with a named test each: `Bash`/`BashOutput`/`KillShell`/`NotebookEdit`
> (shell escapes the runtime), `Task`/`Agent` (a subagent reopens containment
> *and* its skill calls never appear in this session's trace), and
> `WebFetch`/`WebSearch`. **No skill declares any `needs`**, so there is no
> network exception to justify — asserted by a test that fails the moment one
> appears, forcing the justification back to a gate.
>
> **The gate also asks for the full tool set the SDK reports and the diff
> against the allowlist. That half is not produced**, because the SDK is not a
> dependency until Milestone 4 Step 1, behind gate 4A, and adding it early to
> satisfy this gate would invert the plan's ordering. **It must be completed at
> Milestone 4 before the first session opens.** Recorded as a gap rather than
> papered over.
>
> Open: whether `Read`/`Write`/`Skill` suffices without `Glob`/`Grep`;
> `skills="all"` (bounded by what was assembled, and pruning would make the
> Milestone 4 trace measure our own control flow); and `permission_mode:
> "default"` for an unattended session.
>
> Full artifact: [`2026-09-14-milestone-3-results.md`](2026-09-14-milestone-3-results.md#human-gate-3b--the-permission-allowlist).

**Step 8: Automatic gate:** `pytest tests/test_agentic_cli.py -v`

> **Automatic gate passed — 2026-09-14.** 158 passed (121 before, +37 new).
> Whole-suite `FAILED`/`ERROR` line set unchanged at 62 lines. Three mutations
> verified failing-first; the one that made the assembler copy a whole example
> directory was caught by `_assert_sealed()` *refusing to build the runtime*,
> not by a test noticing afterwards.

**Step 9: Human gate 3C — a real assembled runtime, before Milestone 4.**

- **Decision:** does an actual runtime directory contain a route out?
- **Artifact:** a runtime assembled for one example with `--keep-runtime`, walked manually — including following symlinks and any relative parent references — plus the permission profile as printed by the runner.
- **Blocks:** Milestone 4. Confirm there is no route to the repo, to gold data, or to another example, and that the printed profile matches what was approved at gate 3B — in particular that neither a shell nor a subagent tool is present.

> **Question clarified and re-walked — 2026-09-14.**
>
> *"Why does the runtime directory should contain a route out? I think this is
> unsafe."* **It should not, and it does not.** The gate's wording is a
> question to investigate, not a requirement; its own Blocks clause says
> "confirm there is **no** route". Poor phrasing, no escape hatch intended.
>
> **The instinct found something a directory walk never could, though.** The
> runtime *directory* had no route out; the *permission profile* did — an
> unscoped `Read` reaches the whole disk, and `"default"` mode left unlisted
> tools reachable. Both fixed at 3B above. The lesson: containment has two
> surfaces and only one of them shows up in a `find` listing.
>
> Re-walked against the corrected profile: identical tree, 13 entries, 0
> symlinks, 0 gold or contract files, 0 repo-path references.
>
> Original walk —
>
> A real runtime was assembled with `--keep-runtime` and walked. **Thirteen
> entries, hidden files included, and nothing else**: two skills under
> `.claude/skills/<name>/` with `SKILL.md` and `schema.json`, the generated
> `ORIENTATION.md`, an empty `artifacts/`, and `input/` holding the one figure's
> caption, image and source file.
>
> Route-out checks all clean: **0 symlinks**, no hard links with `nlink > 1`, no
> file mentioning the repository path, **0 occurrences** of
> `expected_output.json`, `benchmark.json`, `eval-manifest.json`, `checks/` or
> `prompts/`, no other example, and **no `.claude` in any ancestor** of the
> runtime from its root up to `/`. `~/.claude/skills` does not exist on this
> machine — and is excluded by setting sources regardless, so the guarantee does
> not rest on that.
>
> The printed profile matches what 3B *proposes*, but this gate asks whether it
> matches what was **approved** at 3B — and 3B is not yet approved. **The two
> must be taken in order**, even though the artifacts were produced together.
>
> Reproduce with:
> `python -m soda_mmqc.cli assemble fig-checklist --check micrograph-scale-bar --example 10.1038_s44321-025-00219-1/content/1 --keep-runtime`
>
> Full artifact: [`2026-09-14-milestone-3-results.md`](2026-09-14-milestone-3-results.md#human-gate-3c--a-real-assembled-runtime).

## Milestone 4: Per-Example Agent Session Writing Predictions

**Deliverable:** the priority runner — for each example of one check, assemble the runtime, run one agent session, and write a schema-valid prediction plus a diagnostic trace. Versioning is deliberately not part of this milestone.

**Files:**
- Modify: `soda_mmqc/cli.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_agentic_cli.py`

**Step 1:** Confirm the official, current Claude Agent SDK package and API from Anthropic primary documentation before adding the dependency. Record the selected package and API version in the plan and in `pyproject.toml`.

**Step 2: Human gate 4A — the dependency, before it enters `pyproject.toml`.**

- **Decision:** is this the package, version, and auth model we commit to?
- **Artifact:** the exact distribution name and pinned version, a link to the primary Anthropic documentation it was confirmed against, the API surface the runner will use, how credentials are supplied, and what the transitive dependency footprint adds.
- **Blocks:** Step 3. A runtime dependency with an auth model is an organisational commitment, not a code change; picking the wrong package here is discovered months later when it is expensive to swap.

> **Decision recorded — 2026-09-14, Çağatay Gürsoy: ACCEPTED.**
>
> `claude-agent-sdk==0.2.152` is pinned in `pyproject.toml`. The `mcp`
> constraint concern raised below was **withdrawn as manufactured ambiguity**:
> the plan's "Do not add … MCP" sits in a list of *architectures not to build*,
> beside "parallel sessions" and "a shared classifier", so a transitive package
> of that name is not what it prohibits.
>
> `claude-agent-sdk==0.2.152` (PyPI, MIT, requires-python >=3.10), confirmed
> against [the primary Python reference](https://code.claude.com/docs/en/agent-sdk/python).
> API used: `query()` + `ClaudeAgentOptions`, plus hooks. Auth:
> `ANTHROPIC_API_KEY`; the SDK does not read `.env` but `config.py` already
> calls `load_dotenv()`. Bedrock/Vertex/Foundry available via env flags.
> Transitive footprint measured by dry-run: **6 new packages** —
> `claude-agent-sdk`, `mcp`, `mcp-types`, `cryptography`, `pyjwt`,
> `sse-starlette`.
>
> **Three things flagged rather than assumed.** (1) **`mcp` lands, and the
> plan's Constraints say "Do not add … MCP."** Read as prohibiting MCP *as an
> architecture* — none is defined or called — while the package arrives
> unavoidably. That is a literal conflict with a written constraint; if it was
> meant literally the dependency cannot be used at all. (2) Wheels are ~90 MB
> (bundled Claude Code binary) and **there is no ARM64 Windows wheel**, so that
> platform needs Claude Code installed separately — an asterisk on the
> OS-independence required at gate 3A. (3) `0.x`, ships frequently, so pinned
> `==` — a silently updated agent runtime makes scores non-comparable, which
> Milestones 5 and 6 depend on.
>
> *Milestone 3 carry-forward, partly closed:* all six option names verified
> against the real `ClaudeAgentOptions` dataclass, and `dontAsk` confirmed a
> valid `PermissionMode`. **The reported-tool-set diff is still outstanding** —
> it lives in the session `init` message and the bundled CLI has no
> `--list-tools`, so it moves to gate 4C.
>
> Full artifact: [`2026-09-14-milestone-4-results.md`](2026-09-14-milestone-4-results.md#human-gate-4a--the-dependency).

**Step 3:** Implement `run --mock` first: for each benchmark example, write the expected leaf output as the prediction plus a deterministic `skill_trace.json` sidecar. This keeps CI able to exercise the whole path without credentials.

**Step 4:** Write fake-client tests for a private `_run_agent_session`: the session uses the assembled runtime, the target leaf, and the example inputs; every skill description in the checklist is visible to the client while only the entry point is named in the request; no closure is supplied; the final leaf JSON validates against the leaf `schema.json`; invalid output fails **before** any prediction is written.

**Step 5:** Add an SDK `PostToolUse` hook. Filter `tool_name == "Skill"` and append entries incrementally to `intermediates/skill_trace.json` under the prediction directory — `skill`, resolved `version`, `tool_input`, `tool_use_id`, timestamp. Write as calls occur so a failed session still leaves its trace. Never parse transcript JSONL or agent prose to infer calls.

The trace is the only instrument that shows whether the prose actually reached the intended skill, so treat it as the milestone's primary observation. Report the observed chain per example alongside the prediction, and compare it against the `requires` frontmatter to surface hops that were declared but never fired, or fired but never declared. That comparison is diagnostic reporting, not enforcement: a missing hop is a prompt-authoring problem to fix in the skill text, never something the runner should paper over by calling the skill itself.

**Step 6:** Validate intermediate artifacts against the optional intermediate schemas before they are handed onward, and persist them as sidecars.

**Step 7:** Map checklist defaults plus the union of declared `needs` onto SDK session options, subject to the Milestone 3 permission profile — which the union may narrow but never widen past the profile's allowlist. Cache whole sessions by `(example_content_hash, skills_content_hash, model, effective_config_hash, leaf_schema_hash)`. Do not key cache reuse on the observed trace.

**Step 8: Automatic gate:** `pytest tests/test_agentic_cli.py -v`, plus a `--mock` run over the pilot check.

> **Automatic gate passed — 2026-09-14.** 207 passed (177 before, +30), plus a
> `--mock` run writing 38 predictions over the pilot. Whole-suite
> `FAILED`/`ERROR` set unchanged at 62 lines. Four mutations verified
> failing-first. Two defects found and fixed along the way: **gold is not a
> valid prediction** (it carries `updated_at`, which the leaf schema forbids
> under `additionalProperties: false`), and **the first cache key could never
> hit** (the scoped permission rules embed the per-run temp path).

**Step 9: Human gate 4B — the mock output shape, before credentials are requested.**

- **Decision:** are the prediction layout, the `skill_trace.json` shape, and the declared-versus-observed report the artifacts we want to reason about in the live run?
- **Artifact:** one complete mock prediction directory, including the trace sidecar and the intermediates, plus the console output of the run.
- **Blocks:** Step 10. Fixing the diagnostic format is free in mock and costs a paid rerun afterwards; more importantly, gate 4D is only answerable if the trace already shows what a person needs to see.

> **Decision recorded — 2026-09-14, Çağatay Gürsoy: PASSED.** *"Looks good."*
>
> The prediction layout, the trace shape and the declared-versus-observed
> report are accepted as the artifacts to reason about in a live run. The three
> open questions (sidecar layout, whether a mock trace should exist, whether
> `timestamp: null` should be a stable sentinel) are accepted as-is.
>
> One complete prediction directory (`prediction.json` plus
> `intermediates/skill_trace.json`), the console output, and the
> declared-versus-observed shape. Mock trace entries carry `source: "mock"`
> because they are generated from frontmatter and prove nothing about
> discovery; a live entry reads `source: "hook"` with a real timestamp and
> tool_use_id. Open: whether the sidecar layout is right, whether a mock trace
> should exist at all, and whether `timestamp: null` should be a stable
> sentinel.
>
> Full artifact: [`2026-09-14-milestone-4-results.md`](2026-09-14-milestone-4-results.md#human-gate-4b--the-mock-output-shape).

**Step 10: Human gate 4C — authorisation for the first live run.**

- **Decision:** may this run against a real model, with which credentials, which model, and how many examples?
- **Artifact:** the exact command to be executed, the number of examples it will process, the model identifier, and a rough cost estimate; plus confirmation that the credentials to be used are the intended ones and are not committed anywhere.
- **Blocks:** Step 11. Scope this to a handful of examples — never the full checklist — so a debugging cycle stays minutes, not hours. Each subsequent widening of the example count is its own approval, not an implied continuation of this one.

> **Decision recorded — 2026-09-14, Çağatay Gürsoy: AUTHORISED** (after an
> initial refusal the same day). *"yes, do a small run."*
>
> Scope: 3 of 38 examples, model `sonnet`, chosen for micrograph content,
> PNG/JPG rather than `.webp`, and short captions.
>
> **Attempted; failed at authentication on all three. Nothing was spent and no
> session reached the model.** `ANTHROPIC_API_KEY` is present in `.env` but
> **empty**, so the bundled CLI fell back to the machine's personal Claude Code
> OAuth session, which has expired. OAuth is not the path regardless: Anthropic
> does not permit claude.ai login for third-party SDK agents. A real API key or
> a Bedrock/Vertex/Foundry configuration is required.
>
> **The attempt was still worth making.** The session reported its configuration
> in the `init` message before dying, which is the evidence gate 3B asked for
> and could not obtain — and it exposed **two containment defects**: 20 tools
> granted where the profile named 3 (including `SendMessage`,
> `PushNotification`, `ScheduleWakeup`, `CronCreate` — egress and post-run
> persistence), and **18 skills in the discovery pool**, ours plus 16 bundled
> with Claude Code. The second would have made any trace uninterpretable and
> directly violates gate 4D's constraint. Both fixed.
>
> Earlier context, retained with a correction —
>
> Everything up to the session boundary is built and tested; the next action
> spends money and uses credentials, which the plan reserves for a person.
> `run` without `--mock` exits 2 with a message naming this gate. A key **is**
> present in `.env` and `config.py` auto-loads it, so a session would have
> authenticated — the stop is real, not theoretical.
>
> This gate must also carry **the outstanding half of gate 3B**: the SDK's
> reported tool set from the first session's `init` message, diffed against the
> allowlist, checked before any result from that session is trusted.

**Step 11:** Run the pilot check live on the approved number of examples:

```bash
python -m soda_mmqc.cli run fig-checklist --check micrograph-scale-bar --model <claude-model> --no-cache --keep-runtime
```

**Step 12: Human gate 4D — did delegated discovery work? Go/no-go before Milestone 5.**

- **Decision:** continue as designed, re-author descriptions and rerun, or rethink the delegation premise entirely?
- **Artifact:** for the handful of live examples, each prediction beside its `skill_trace.json`, plus a per-example table of observed hops against declared `requires`.
> **Decision recorded — 2026-09-14: PASSED. Delegated discovery works.**
>
> First successful live run, `gpt-4o`, one example
> (`10.1038_s44321-025-00219-1/content/1`). Observed hops:
>
> ```
> Skill(micrograph-scale-bar)   entry point, named in the orientation
>   Skill(identify-panels)      <-- found from the leaf's prose ALONE
>   Read image, Read caption
>   Write artifacts/panels.json
> Skill(micrograph-scale-bar)   returned to the leaf
>   Read artifacts/panels.json  consumed the shared artifact
>   Write artifacts/prediction.json
> ```
>
> Nothing but the leaf's `SKILL.md` named `identify-panels` — the orientation
> file and the session prompt both refuse to, each pinned by a test and a
> mutation. Declared-versus-observed: **no missing hops**.
>
> **The prediction is byte-identical to gold** (`Ai`, `Aii`, `B`, `C`; scale
> bars 2/2/4 /2 μm), scoring **mean 1.000 across 28 instances** (24
> `correct_applicable`, 4 `correct_NA`). It independently reproduced the
> `Ai`/`Aii` sub-panel split decided at gate 2A.
>
> **Run on OpenAI, not the Claude Agent SDK.** The project has no Anthropic
> credentials and the SDK cannot use an OpenAI key; a second client was built
> so the experiment could run on the provider the repository already uses.
> Gate 4A's decision stands — `--provider` selects between them.
>
> *Constraint that produced this result — 2026-09-14, Çağatay Gürsoy:* *"the
> agent MUST ONLY find the leaf's prose alone. nothing else."*
>
> Taken as a hard requirement on the experiment, not a preference. It is what
> made the bundled-skills contamination a defect rather than a curiosity: 16
> foreign descriptions in the pool meant the agent had routes to a skill that
> were not the leaf's prose. Now enforced by naming the skill pool explicitly,
> and already enforced for the two other routes — `ORIENTATION.md` and the
> session prompt both refuse to name the dependency, each with a test and a
> mutation.
>
> **Still unanswered:** no session has reached a model.

- **Blocks:** Milestone 5. Confirm `identify-panels` was actually invoked from the leaf's prose — with every other skill description also loaded and competing — and that panel labels are consistent with the leaf output. This is the milestone's real question, and the only point in the plan where the answer could be that the approach itself is wrong. Also check the traces across examples for hops that fired inconsistently, which is the signal that a `description` is too vague or two of them overlap; inconsistent firing sends the work back to Milestone 2's prose, not forward.

## Milestone 5: Score the Pilot, Then Convert by Group

**Deliverable:** the pilot check scores through the unchanged `FlatEvaluator`, `evaluate` delegates agentic checklists to `cli.py`, and the remaining leaves are converted group by group.

**Files:**
- Modify: `soda_mmqc/cli.py`
- Modify: `soda_mmqc/scripts/run.py`
- Create: `soda_mmqc/data/checklist/fig-checklist/<leaf>/v1/SKILL.md` for the remaining leaves
- Modify: `tests/test_agentic_cli.py`, `tests/test_run_analyze_results.py`
- Modify: `README.md`

**Step 1:** Score the pilot's agentic predictions with the Milestone 1 `score` command. Assert intermediate JSON and traces change nothing about the score.

**Step 2: Human gate 5A — pilot quality, before converting any further leaf.**

- **Decision:** are the pilot's agentic scores good enough to justify converting ten more prompts?
- **Artifact:** the pilot's agentic scores against the legacy prompt path on the same examples, per metric, with every example where the two disagree listed individually rather than averaged away.
- **Blocks:** Step 3. This is the plan's largest commitment point: everything after it is bulk work whose cost is only worth paying if the pilot's quality holds. A tie or small regression may still be acceptable, but that is a judgement call about scientific acceptability, not a threshold a test can own.

> **Decision recorded — 2026-09-14, Çağatay Gürsoy: PASSED.** *"Yes, they are
> good enough. It is justified to convert all prompts."* The three caveats
> below (small non-random sample, `panel_label` unexercised, variance
> unmeasured) were presented and accepted.
>
> Both paths run on **the same 5 examples with the same model** (`gpt-4o`;
> the legacy default is `gpt-5-mini`, so it was overridden to make the
> comparison fair). Langfuse was pinned off so the prompt source is the local
> `prompt.2.txt` — the reproducibility condition recorded as debt at gate 1B.
>
> | field | agentic | legacy | delta |
> |---|---|---|---|
> | `panel_label` | 1.000 | 1.000 | — |
> | `micrograph` | 1.000 | 1.000 | — |
> | `scale_bar_on_image` | 1.000 | 1.000 | — |
> | `scale_bar_defined_in_image` | **1.000** | 0.905 | **+0.095** |
> | `scale_bar_defined_in_caption` | **1.000** | 0.952 | **+0.048** |
> | `from_the_image` | 1.000 | 1.000 | — |
> | `from_the_caption` | 1.000 | 1.000 | — |
> | **overall** | **1.000** | 0.980 | **+0.020** |
>
> 147 scored instances each. **The agentic path is perfect; the legacy path is
> not.**
>
> *The one disagreement, listed rather than averaged away* —
> `10.15252_emmm.201404392/content/3`, where legacy scored 0.914 and got three
> instances wrong:
>
> | panel | gold (image/caption) | agentic | legacy |
> |---|---|---|---|
> | A | `no`/`no` | `no`/`no` | **``**/`no` |
> | B | `yes`/`no` | `yes`/`no` | **`no`**/**`yes`** |
>
> Legacy left a field blank on panel A and inverted both fields on panel B —
> it decided the scale bar was defined in the caption when it is on the image.
> The agentic path got every panel right on all five figures.
>
> *Caveats a reviewer should weigh:* five examples of thirty-eight is a small
> sample and all five were chosen for having micrographs and readable PNG/JPG
> figures, so they are not a random draw; `panel_label` scored 1.000 on both,
> so this sample does not exercise the label-collision risk measured at gate
> 2A; and one run each means run-to-run variance is unmeasured.
>
> Full artifact: [`2026-09-14-milestone-4-results.md`](2026-09-14-milestone-4-results.md).

**Step 3:** Write failing compatibility tests, then implement delegation at the `run.py` CLI boundary: legacy checks keep present behavior; a checklist with an agentic layout dispatches `--mock`, `--check`, `--checks`, `--model`, and `--no-cache` to `soda_mmqc.cli.main(argv)`; agentic `--prompt-version` errors clearly. Leave `process_check` and the prompt-version implementation untouched.

**Step 4: Human gate 5B — legacy compatibility, before Group A conversion.**

- **Decision:** does the delegation change anything for someone who runs the legacy commands the way they run them today?
- **Artifact:** the legacy commands actually in use — including flag combinations the tests do not cover — run before and after, with their outputs diffed; plus the error text produced by agentic `--prompt-version`, read as a user would read it.
- **Blocks:** Step 5. The people who depend on the legacy path are not the people writing this code, and their invocations are not fully captured by the suite.

> Full artifact: [`2026-09-15-milestone-5-results.md`](2026-09-15-milestone-5-results.md#human-gate-5b--legacy-compatibility).

> **Artifact produced — 2026-09-14. Decision OPEN (reviewer absent).**
>
> **Deviation from the plan's wording, deliberate.** The plan says "a
> *checklist* with an agentic layout dispatches". That is right for a fully
> converted checklist and wrong during the conversion: `fig-checklist` has one
> converted leaf and ten that still have only prompts, so checklist-level
> dispatch would break ten working checks to route one. The discriminator is
> therefore **per check** — a check owning a `v*/SKILL.md` dispatches, one
> without keeps exactly its present behaviour. That satisfies the plan's own
> first clause, "legacy checks keep present behavior", and converges on its
> wording as the last leaf lands.
>
> Routing, observed:
>
> | command | routes to |
> |---|---|
> | `evaluate fig-checklist --check stat-test` | `process_check` — unchanged |
> | `evaluate fig-checklist --check micrograph-scale-bar` | agentic runner |
> | `evaluate fig-checklist` | agentic runner for the pilot **+** `process_checklist` for the other 10 |
> | `evaluate doc-checklist` | `process_checklist`, selection passed through untouched |
> | `evaluate fig-checklist --checks micrograph-scale-bar stat-test` | one each |
>
> *A gap found and fixed while producing this:* a whole-checklist run names no
> check, so the first implementation left the pilot falling through to its
> legacy prompt — producing a prompt-path score under an agentic check's name,
> the most confusing possible outcome. A no-check run now resolves to the full
> list before routing, and a checklist with no agentic checks still passes the
> caller's original selection through untouched.
>
> `--prompt-version` on an agentic check **exits 2** with: *"--prompt-version
> selects between prompt files and has no meaning for agentic check(s): …
> Skills are versioned by directory (v1, v2, ...) and pinned by manifest, not
> by this flag."* It still works normally for legacy checks.
>
> *Inherited, not introduced:* `evaluate` validates the model against the
> provider **before** any dispatch, and that validation calls the provider's
> models endpoint — the same behaviour Milestone 1 recorded as "`--mock` is
> not offline". Delegation inherits it; it was not changed here.
>
> Whole-suite `FAILED`/`ERROR` set unchanged at 62 lines.

**Step 5:** Convert the rest of Group A (image/micrograph), reusing `identify-panels` unchanged. Run and score each as it lands.

**Step 6: Human gate 5C — Group A review, before Group B is designed.**

- **Decision:** are the Group A deltas explained, did `identify-panels` hold up unchanged across four leaves, and may the legacy prompts now be retired?
- **Artifact:** per-leaf score deltas against the legacy path, the observed `Skill` traces for each leaf, and — for the retirement question — the list of `prompts/` directories proposed for removal and what still reads them.
- **Blocks:** Step 7. Unexplained regressions block the next group. Retirement is irreversible in practice and gets an explicit yes or no; the default is to keep the prompts until parity is agreed.

> **Artifact produced — 2026-09-15. Decision OPEN.** `identify-panels` served all four Group A leaves **unchanged**. Three of four are identical to legacy (`micrograph-scale-bar` 0.810/0.810, `single-channel-for-overlay` 1.000/1.000, `panel-image-matches-caption` 1.000/1.000); `image-annotation-defined` is unscoreable in both directions because it has no gold, which is a curation state rather than a defect. Retirement recommended **not yet** — the legacy path is the only comparison baseline and the deltas rest on two examples.
>
> Full artifact: [`2026-09-15-milestone-5-results.md`](2026-09-15-milestone-5-results.md#human-gate-5c--group-a-review).

**Step 7: Human gate 5D — the Group B design fork.**

- **Decision:** does Group B need a shared plot skill, and if so what exactly does it own — plot classification only, or axis identification and properties too?
- **Artifact:** the concrete duplication found across two real Group B leaves, quoted, with a proposed boundary for the shared skill and its `description`, plus the alternative of leaving the logic leaf-local.
- **Blocks:** Step 8. The plan deliberately left this open rather than deciding it from prompt text, and a wrongly drawn boundary here reproduces the duplication the project exists to remove. Design it against two real leaves, not against the prompt text alone.

> **Decided on evidence — 2026-09-15. Yes to a shared skill; no to the one
> proposed.**
>
> The conversion map suggested `classify-quantitative-plot` producing an
> `is_quantitative_plot` boolean. **The seven Group B prompts show that would be
> wrong**, because they disagree about the same panel on purpose:
>
> | leaf | pie chart / heatmap |
> |---|---|
> | `plot-axis-units` | *"Skip this check for schematics, pie charts, heat maps…"* — **not** a plot |
> | `stat-test` | *"…histograms, pie charts, box plots, heatmaps…"* — **is** quantitative data |
> | `individual-data-points` | *"heatmaps … and pie charts are automatic PASS"* — is a plot, needs no points |
>
> A shared boolean would force agreement where three different answers are each
> correct for their own check.
>
> **Built `classify-plot-panels` instead**, which reports *observations* and no
> verdict: the plot types present, whether drawn axes exist, and per axis the
> numeric/categorical scale, the tick labels verbatim, and the title. Each leaf
> keeps its own inclusion rule. That is the same shape as `identify-panels` —
> report facts, leave judgement to the caller — and it is why the skill is not
> named for the question it refuses to answer.
>
> *The gate's second half* — "plot classification only, or axis identification
> and properties too?" — is answered **both**: `plot-axis-units` and
> `plot-gap-labeling` both need axis facts, and `plot-gap-labeling` in
> particular needs tick labels transcribed rather than normalised, which is
> exactly the kind of thing worth doing once.

**Step 8:** Convert Group B. If a shared plot skill was approved, its wording and `description` get the same scrutiny as gate 2A before any leaf depends on it.

**Step 9: Automatic gate:** `pytest tests/ -v` after each group, plus a `--mock` run and a `score` run for every converted leaf.

**Step 10: Human gate 5E — Group B review, before Milestone 6.**

- **Decision:** are the Group B deltas explained and acceptable?
- **Artifact:** per-leaf score deltas against the legacy path on the same examples, plus the traces showing whether the plot skill — if one was created — fired consistently across leaves.
- **Blocks:** Milestone 6.

> **Artifact produced — 2026-09-15. Decision OPEN.** Four of six comparable Group B leaves are identical to legacy. Two regress: `plot-axis-units` **−0.071** and `stat-test` −0.048. The first was **−0.548** until a fix — the gate 2A empty-label fallback fired on a figure that plainly has labels, collapsing it to one row and destroying the alignment key. `stat-significance-level` has no legacy baseline (its benchmark references a missing content directory). Mean over all 8 comparable leaves: agentic 0.707 vs legacy 0.722, **−0.015**.
>
> Full artifact: [`2026-09-15-milestone-5-results.md`](2026-09-15-milestone-5-results.md#human-gate-5e--group-b-review).

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

**Step 5: Human gate 6A — the production pins and defaults.**

- **Decision:** are these the version pins and model defaults we are willing to expose as the production manifest, and is the expansion warning threshold set where a person would actually want to be warned?
- **Artifact:** the proposed `version-manifest.yaml` and `model-defaults.yaml` in full, the SkillSet they resolve to, and the threshold value with the example counts and rough cost of an expansion just under and just over it.
- **Blocks:** Step 6. The manifest is what Langfuse exposes downstream; a pin chosen by convenience becomes the thing other people's results are attributed to.

> **Artifact produced — 2026-09-15. Decision OPEN.** All 13 pins are `v1` because every skill *has* only `v1` — the manifest is not yet a choice, it is a record. Its value today is the three rules it makes enforceable (complete, no orphans, no phantom versions) and the fact that adding a `v2` directory changes nothing until this file is edited, which was demonstrated live at gate 6C. Defaults: `openai: gpt-5-mini` (the model every Milestone 5 delta was measured on), `claude-sdk: sonnet` (never exercised — no `ANTHROPIC_API_KEY`), `max_turns: 24`. Threshold **4 SkillSets**, warns and never refuses. **Open question raised, not resolved:** the threshold counts SkillSets, not sessions, so an unpinned 38-example run is silent at 38 sessions while a 6-set 2-example run warns at 12.
>
> Full artifact: [`2026-09-15-milestone-6-results.md`](2026-09-15-milestone-6-results.md#human-gate-6a--the-production-pins-and-defaults).
>
> **Deviation flagged:** Step 6 (cache key) was implemented before this gate cleared. It depends on the *shape* of a SkillSet, not the *content* of the manifest, so the gate's actual decision was not prejudged.

**Step 6:** Switch the Milestone 4 cache key from a raw skills hash to the SkillSet hash.

**Step 7: Automatic gate:** `pytest tests/ -v`

**Step 8: Human gate 6B — the generated documentation baseline.**

- **Decision:** is the first generated `dag.yaml` and `README.md` a faithful picture of the graph as the authors understand it?
- **Artifact:** the generated files read against the skills' actual prose — checking that every rendered edge corresponds to a call someone wrote, and that no call someone wrote is missing.
- **Blocks:** Step 9. Once these are committed, the drift check treats them as truth and every later disagreement is reported as drift from them; a wrong baseline turns the drift check into a machine for confirming a mistake.

> **Artifact produced — 2026-09-15. Decision OPEN.** 11 checks, 2 shared skills, 18 edges. Edges are rendered from the **prose** (`invoked_skills`), not from `requires` — validation has already asserted the two agree, but the prose is what runs. That property is now a test (`test_the_dag_edges_match_the_prose`), so gate 6B does not decay into a one-time human read. `identify-panels` appears twice under each Group B leaf because each of them genuinely calls it directly *and* through `classify-plot-panels`; that is the prose, not a rendering artifact. Generation is timestamp-free and path-free, asserted separately from the write-twice test, because writing twice a second apart cannot catch a timestamp.
>
> Full artifact: [`2026-09-15-milestone-6-results.md`](2026-09-15-milestone-6-results.md#human-gate-6b--the-generated-documentation-baseline).

**Step 9: Human gate 6C — failure messages and version comparability, close-out.**

- **Decision:** does a person hitting each failure mode learn what to fix, and do two versions of one skill remain genuinely comparable?
- **Artifact:** `graph fig-checklist` run against deliberately malformed fixtures — invalid frontmatter, duplicate names, unknown requirements, cycles, missing pins, orphan pins, non-existent versions — with each message read as a stranger would read it; then one unpinned comparison on the pilot check (`--unpin micrograph-scale-bar --versions v1,v2`) on a few examples.
- **Blocks:** close-out. Every failure message must name the offending file and the reason, and the two versions must score against the *same* shared `schema.json` and `eval-manifest.json` — if their scores are not comparable, the versioning scheme has failed at the one job it exists to do.

> **Artifact produced — 2026-09-15. Decision OPEN.** Nine malformed fixtures, all exiting 1, each naming the offending file and the reason. **Two messages were defective and were fixed:** *missing manifest* printed the filename twice and told the reader to run `graph --write`, which does not generate a manifest; *duplicate names* blamed whichever file `rglob` reached second, which is walk order, not fault. Known wrinkle left in place: `load_skills` failures stop at the first problem while the rest batch.
>
> **Comparability holds.** `micrograph-scale-bar` has only `v1`, so a temporary `v2` fixture was written, used, and removed — v1 has no defect to fix, and inventing a production version to satisfy a gate artifact is the drift flagged at gate 4A. Live: 4 sessions, 4m31s. On the example both sets produced, the two versions scored against the same contracts and the evaluator emitted the **same 105 instances across the same 7 fields** — same alignment, same denominators, delta `+0.000`.
>
> **Two findings that matter more than the numbers.** (1) `v2` declared `requires: []` and never mentions `identify-panels` in prose — and the agent called it anyway, on both examples. Strong evidence *for* description-driven discovery, and a hard limit on `--unpin`: two versions share the same assembled skill pool, so **a version cannot ablate a sibling skill**. (2) A real defect: a session produced a valid leaf answer and it was **thrown away** because a debug sidecar failed its schema. `validate_intermediates` justified raising as catching a bad artifact "before a downstream skill consumes it", but it only runs *after the session closes*, so that purpose is unreachable from where it sits. Fixed — the runner now records the violation and keeps the prediction.
>
> Full artifact: [`2026-09-15-milestone-6-results.md`](2026-09-15-milestone-6-results.md#human-gate-6c--failure-messages-and-version-comparability).

---

## Acceptance Checklist

- Running and scoring are separate commands; existing scoring, reporting, and curation behavior is unchanged and covered by the existing suite.
- All 11 active figure prompts are represented by leaf `SKILL.md` files organized as an acyclic hierarchy, converted in branch groups after a working pilot.
- Each leaf's `schema.json`, `eval-manifest.json`, and `benchmark.json` remain per-skill and shared across versions, so versions stay comparable.
- The hierarchy is carried entirely by skill-to-skill calls declared in each skill's own `SKILL.md`. All skills are flat siblings in one namespace; no directory encodes a skill's role, and a test proves renaming or moving a skill directory leaves the resolved graph unchanged.
- The only on-disk difference between a leaf and a shared skill is that the leaf owns the evaluation contracts. Check enumeration follows from that single fact — no name convention, no marker file, no `kind` discriminator.
- Every skill's `description` is loaded in every session. The runner names one entry-point leaf and nothing else; reaching the shared skills is delegated to the agent, which is the point of using an agent rather than walking the DAG in Python.
- The `Skill` trace is the instrument for whether delegated discovery worked. Declared-versus-observed hops are reported, never enforced; a missing hop is fixed in the skill prose, not compensated for by the runner.
- Sub-skill invocation happens through prose instructions and the `Skill` tool; `requires`/`produces` frontmatter documents and validates the graph and is never executed.
- One repository-level `CLAUDE.md` orients the agent; runtime orientation is generated per run, not checked in per check.
- The runtime directory is assembled outside the repository, exposes exactly one version per skill and only the current example, and is removed unless `--keep-runtime` is set.
- The agent's tool set matches an explicit allowlist: no `Bash` or other shell, **no subagent creation**, no unjustified network access, and no route to the repo, gold data, benchmarks, or other examples. Tests assert each prohibition.
- `cli.py` owns runtime assembly, per-example session execution, prediction writing, DAG validation, and SkillSet resolution.
- A per-example hook trace records actual `Skill` invocations incrementally; it is diagnostic only — never scored, never part of cache identity.
- Cache identity is exactly example content, SkillSet, model, effective config, and leaf schema.
- `score` applies the unchanged `FlatEvaluator` to final leaf JSON only.
- Legacy `evaluate` remains available and delegates agentic checklists to `cli.py`.
- Every human gate listed in the Gate Protocol has a recorded decision — date, who, verdict, conditions — in its milestone section. An unrecorded gate is an unpassed gate.
- No session was opened before the permission allowlist was approved, no dependency added before its gate, and no live run made before its example budget was authorised.

## Review Feedback Incorporated

Each review comment on the previous draft and where it now lives:

| Comment | Where addressed |
|---|---|
| Goal missing "hierarchical DAG for hierarchy, reuse, no cycles" | Goal |
| Frontmatter is not the orchestration source of truth; sub-skills called from prose; frontmatter is reference/validation only and ignored by the agent | Architecture, Constraints, Target Layout, Milestone 2 Step 5 |
| "At most one unpinned skill" is too strict | Milestone 6 Step 4 |
| Do not break existing scoring, reporting, curation | Constraints; Milestone 1; every milestone's automatic gate |
| `CLAUDE.md` should be top-level only, not per checklist/check | Target Layout |
| `schema.json` etc. must be common across versions or versions become incomparable | Constraints, Target Layout, Milestone 2 Step 4, Milestone 6 Step 9 |
| Phase order problematic — pilot before mass conversion | Delivery Order; Milestone 2 |
| `graph` over all of `fig-checklist` too slow; test on one or few checks | Delivery Order; Milestone 4 Steps 10–11; Milestone 6 Step 3 |
| Start by separating `run` from `evaluate`, verify scoring intact | Milestone 1 |
| Use `micrograph-scale-bar` as the pilot | Milestone 2 |
| Runtime dir must be outside the repo; SDK finds skills in `.claude`; repo-internal runtime leaks skills, examples, and benchmarks | Constraints; Milestone 3 Steps 1–2 |
| Crystal-clear permissions; no `Bash`; no subagent creation | Constraints; Milestone 3 Steps 6 and 7; Acceptance Checklist |
| Test agent confinement; keep or remove runtime dir per option | Milestone 3 Steps 1, 5, 9 |
| Additional material in the thinking document | Background link |
| Group conversion: micrographs/panels first, then plots/axes | Conversion Map Groups A and B; Milestone 5 Steps 5–8 |
| Priority is runtime dir + per-example agent + predictions; versioning last | Delivery Order; Milestone 4; Milestone 6 |
| Plan not progressive or gated enough; want milestones with unit-test gate plus human gate | Whole structure — six milestones, each with an automatic gate and multiple human gates; Gate Protocol |
| `_shared/` is wrong; hierarchy must be independent of directory layout and come from a skill calling another skill in its own file | Target Layout (flat sibling namespace, no `_shared/`); Milestone 1 Steps 1 and 5; Milestone 2 Steps 5 and 7 |
| No reserved-name filter; the only on-disk difference is that leaves own manifest/benchmark/schema | Target Layout; "Two Different Discoveries"; Milestone 1 Steps 1 and 5 (the `kind` discriminator is dropped) |
| All skill descriptions are loaded; the agent enters at the leaf and chains to intermediate then root skills through prose; that delegation is why we use an agent, and it is what we are testing | "Two Different Discoveries"; Milestone 2 Step 1; Milestone 3 Steps 1 and 4; Milestone 4 Steps 4, 5, and 12 |
| More human gates, placed where human input is absolutely necessary rather than only at milestone ends | Gate Protocol (criteria, artifacts, blocking semantics, at-a-glance table); 18 gates across the six milestones — notably 1A before enumeration semantics change, 2A before any leaf depends on the shared skill, 3A/3B before assembly and before any session opens, 4A/4C before the dependency and the first paid run, 5A before bulk conversion, 5D on the Group B design fork, 6A/6B before the manifest and generated docs become truth |
