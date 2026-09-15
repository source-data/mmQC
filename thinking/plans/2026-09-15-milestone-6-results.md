# Milestone 6 — Version Pinning and Generated Graph Views

Results and gate artifacts for Milestone 6 of
[`2026-09-02-agentic-checklist-skills.md`](2026-09-02-agentic-checklist-skills.md#milestone-6-version-pinning-and-generated-graph-views).

Date: 2026-09-15. Branch: `agentic`, uncommitted.

---

## What shipped

| thing | where |
|---|---|
| `version-manifest.yaml` | `soda_mmqc/data/checklist/fig-checklist/version-manifest.yaml` |
| `model-defaults.yaml` | `soda_mmqc/data/checklist/fig-checklist/model-defaults.yaml` |
| `dag.yaml` (generated) | `soda_mmqc/data/checklist/fig-checklist/dag.yaml` |
| `README.md` (generated) | `soda_mmqc/data/checklist/fig-checklist/README.md` |
| manifest loading/validation, `SkillSet`, expansion | `soda_mmqc/cli.py` |
| `graph <checklist> [--write]` | `soda_mmqc/cli.py` |
| `run --unpin SKILL [--versions v1,v2]` | `soda_mmqc/cli.py` |
| cache key on the SkillSet digest | `soda_mmqc/cli.py:session_cache_key` |
| 59 new tests | `tests/test_agentic_cli.py` |

`tests/test_agentic_cli.py`: **296 passed**. Whole suite (minus the five
stale modules that import the removed `JSONEvaluator`): **62 `FAILED`/`ERROR`
lines — byte-identical to the baseline carried since Milestone 1.**

---

## Human gate 6A — the production pins and defaults

> **Decision:** are these the version pins and model defaults we are willing
> to expose as the production manifest, and is the expansion warning
> threshold set where a person would actually want to be warned?

### `version-manifest.yaml`, in full

```yaml
checklist: fig-checklist

skills:
  # Shared skills. Called by leaves through prose, never by the runner.
  classify-plot-panels: v1
  identify-panels: v1

  # Checks.
  error-bars-defined: v1
  image-annotation-defined: v1
  individual-data-points: v1
  micrograph-scale-bar: v1
  panel-image-matches-caption: v1
  plot-axis-units: v1
  plot-gap-labeling: v1
  replication-reporting: v1
  single-channel-for-overlay: v1
  stat-significance-level: v1
  stat-test: v1
```

Every pin is `v1` because every skill *has* only `v1`. There is no judgement
being exercised on any individual pin, and that is worth saying plainly
rather than dressing up: **this manifest is not yet a choice, it is a
record.** Its value today is the three rules it makes enforceable —
completeness, no orphans, no phantom versions — and the fact that adding a
`v2` directory tomorrow changes nothing until someone edits this file.

### `model-defaults.yaml`, in full

```yaml
models:
  openai: gpt-5-mini
  claude-sdk: sonnet

session:
  max_turns: 24
```

- **`openai: gpt-5-mini`** is the model every Milestone 5 delta was measured
  on. Changing it invalidates the comparison table in
  [`2026-09-15-milestone-5-results.md`](2026-09-15-milestone-5-results.md),
  which is the reason the file says so in a comment.
- **`claude-sdk: sonnet`** is the existing `AGENTIC_DEFAULT_MODEL`, unchanged.
  It has never been exercised — there is no `ANTHROPIC_API_KEY` in this
  environment — so it is a default, not a recommendation.
- **`max_turns: 24`** is a **reduction** from the `MAX_TURNS = 40` hard-coded
  in `agentic_openai.py`, moved where a checklist can see it. Observed
  sessions finish in well under 24. An independent review caught that this
  setting was **inert on the OpenAI path** — parsed, validated, documented in
  two files, and never reaching the loop, which ran to 40 regardless. Fixed:
  the client now reads `max_turns` from the session options at call time, the
  same route the Agent SDK path already took.

The loader **refuses** the file outright if it tries to set `allowed_tools`,
`disallowed_tools`, `permission_mode`, `setting_sources`, `cwd` or `skills`.
`effective_session_options` already warned-and-dropped those, but a warning in
a log is easy to miss and this is a file a person edits by hand.

### The SkillSet it resolves to

```
digest: c975706bbc94a3dfcfe07c9f0a8d432ef5275032444b52481d18bdf21f6018c0

  classify-plot-panels           v1  5bae9500527a…
  error-bars-defined             v1  ff48887559b4…
  identify-panels                v1  e4b9b18b99f4…
  image-annotation-defined       v1  6f4144d259c9…
  individual-data-points         v1  af650cb0f898…
  micrograph-scale-bar           v1  9a87da34d4a6…
  panel-image-matches-caption    v1  ce11c419e3ae…
  plot-axis-units                v1  ebed6c31d8f1…
  plot-gap-labeling              v1  a41c87235274…
  replication-reporting          v1  8c6c542fb981…
  single-channel-for-overlay     v1  6ff1ae841c1a…
  stat-significance-level        v1  8358b5c01961…
  stat-test                      v1  eac0d3c9bfb4…
```

The digest covers **content**, not just version labels. A version number is a
claim about content; the hash is the content. Both are carried so a mismatch
can be explained rather than merely reported.

### The threshold, with counts and cost

`AGENTIC_SKILLSET_WARN_THRESHOLD = 4`. It **warns; it never refuses** —
refusing would be the runner making a spending decision that belongs to the
operator.

Sessions run = SkillSets × examples. Measured cost: the gate 6C comparison was
**4 sessions in 4m31s** on `gpt-5-mini` with figure images.

| expansion | SkillSets | × 2 examples | × 38 (pilot benchmark) | warns? |
|---|---|---|---|---|
| no `--unpin` | 1 | 2 sessions | 38 | no |
| 1 skill × 2 versions | 2 | 4 (~4.5 min, measured) | 76 | no |
| 1 skill × 3 versions | 3 | 6 | 114 | no |
| 2 skills × 2 versions | **4** | 8 | 152 | no (at) |
| 2 skills × 2 and 3 | 6 | 12 | 228 | **yes** |
| 3 skills × 2 versions | 8 | 16 | 304 | **yes** |

4 is where an expansion stops being a comparison and starts being a sweep. At
4 sets over a small scope the run is something a person watches finish; the
next step up is not.

**Open question for this gate:** the threshold counts *SkillSets*, not
sessions. An unpinned run over the full 38-example benchmark is 38 sessions
and is silent, while a 6-set run over 2 examples is 12 sessions and warns.
Counting sessions would be more honest about cost. It was left on SkillSets
because that is what the plan specifies and because `--limit`/`--example` are
already required for any live run.

---

## Human gate 6B — the generated documentation baseline

> **Decision:** is the first generated `dag.yaml` and `README.md` a faithful
> picture of the graph as the authors understand it?

### How the edges are derived

Edges come from the **prose**, via `invoked_skills()`, not from `requires`.
`validate_skills` has already asserted the two agree, so both sources give the
same answer — but the prose is what actually runs, and a generated picture
should be drawn from the thing that runs. This is asserted as a test
(`test_the_dag_edges_match_the_prose`), so gate 6B's property does not decay
into a one-time human read.

### The rendered call graph

```
- error-bars-defined            → classify-plot-panels → identify-panels
                                → identify-panels
- image-annotation-defined      → identify-panels
- individual-data-points        → classify-plot-panels → identify-panels
                                → identify-panels
- micrograph-scale-bar          → identify-panels
- panel-image-matches-caption   → identify-panels
- plot-axis-units               → classify-plot-panels → identify-panels
                                → identify-panels
- plot-gap-labeling             → classify-plot-panels → identify-panels
                                → identify-panels
- replication-reporting         → classify-plot-panels → identify-panels
                                → identify-panels
- single-channel-for-overlay    → identify-panels
- stat-significance-level       → classify-plot-panels → identify-panels
                                → identify-panels
- stat-test                     → classify-plot-panels → identify-panels
                                → identify-panels
```

11 checks, 2 shared skills, 18 edges. Read against the prose: every one of the
seven Group B leaves asks for `classify-plot-panels` **and** `identify-panels`
directly, which is why `identify-panels` appears twice under each. That is not
a rendering artifact — it is what the prose says, and it is deliberate: a leaf
needs the panel inventory for its own per-panel loop regardless of what the
plot classifier returns.

### Determinism

No timestamps, no absolute paths, no filesystem-dependent ordering. Writing
twice a second apart cannot catch a timestamp, so there is a separate test
(`test_the_views_carry_nothing_environmental`) asserting the rendered text
contains neither the checklist path nor the current year. A drift check that
reports noise on someone else's machine teaches people to ignore it, which is
the only way a drift check can fail completely.

### What a reader should check before accepting this baseline

Once committed, the drift check treats these files as truth. The one thing a
machine cannot check is whether the *descriptions* in the README table are the
descriptions we want competing for the agent's attention — they are copied
verbatim from frontmatter, and frontmatter `description` is the only thing the
agent reads during discovery.

---

## Human gate 6C — failure messages and version comparability

> **Decision:** does a person hitting each failure mode learn what to fix, and
> do two versions of one skill remain genuinely comparable?

### Part 1: `graph fig-checklist` against deliberately malformed fixtures

Nine fixtures, each a full copy of the real checklist with one thing broken.
All nine exit **1**. Paths abbreviated to `<fixture>`.

| fixture | message |
|---|---|
| **invalid frontmatter** | `<fixture>/fig-checklist/identify-panels/v1/SKILL.md: no YAML frontmatter. A SKILL.md must open with a '---' line, the frontmatter, and a closing '---' line` |
| **duplicate names** | `Two files declare skill 'identify-panels' version 'v1': <fixture>/…/copy-of-identify-panels/v1/SKILL.md and <fixture>/…/identify-panels/v1/SKILL.md. A skill's identity comes from its frontmatter, not its directory, so renaming one of the directories does not resolve this -- change one file's `name`, or delete it` |
| **unknown requirement** | `2 problem(s) …: requires unknown skill 'identify-panles'; known skills are classify-plot-panels, …` + `prose invokes 'identify-panels' but it is missing from requires` |
| **cycle** | `the skill graph has a cycle: identify-panels -> micrograph-scale-bar -> identify-panels` |
| **missing pin** | `<fixture>/…/version-manifest.yaml: 1 problem(s): 'identify-panels' has no pin; every skill of the checklist must be pinned (available: v1)` |
| **orphan pin** | `'identify-panels-old' is pinned but is not a skill of this checklist; it was renamed, moved or removed and the manifest did not follow` |
| **non-existent version** | `'micrograph-scale-bar' is pinned to 'v4', which does not exist; available: v1` |
| **missing manifest** | `<fixture>/fig-checklist: no version-manifest.yaml. Every checklist run agentically needs one, pinning exactly one version of every skill, because it is the identity results are attributed to. Create <fixture>/…/version-manifest.yaml with a 'skills:' mapping of 'skill-name: vN' covering: classify-plot-panels, …` |
| **hand-edited `dag.yaml`** | unified diff of the offending lines, then `1 generated view(s) disagree with the skills. Run `python -m soda_mmqc.cli graph fig-checklist --write` and commit the result.` |

**Two messages were defective on the first pass and were fixed:**

1. *Missing manifest* read `…/version-manifest.yaml: no version-manifest.yaml`
   — the filename twice — and told the reader to run `graph --write`, which
   **does not generate a manifest**. A confidently wrong instruction is worse
   than none. It now names the directory, explains why the file exists, and
   lists the skills that need pinning.
2. *Duplicate names* blamed whichever file `rglob` reached second, which is
   walk order, not fault. It now names both files and says why renaming a
   directory will not help — the thing a reader would try first, and the thing
   the design specifically makes useless.

**Known wrinkle, not fixed:** the two `load_skills` failures (invalid
frontmatter, duplicate names) stop at the first problem, while the four
`validate_skills` and three manifest failures batch everything. Someone fixing
frontmatter across several files gets one error per run. Fixing it means
restructuring `load_skills` to collect; the gate's stated bar — every message
names the offending file and the reason — is met either way.

### Part 2: version comparability

`micrograph-scale-bar` has only `v1`, so a **temporary** `v2` was written as a
fixture, used, and removed. It was deliberately not committed: v1 has no
defect to fix (it scored 1.000 agentic vs 0.980 legacy at gate 5A), and
inventing a production version to satisfy a gate artifact is the drift this
plan was warned about at gate 4A. The fixture differed in one substantive way
— `requires: []` and prose telling the agent to build the panel list itself
instead of calling `identify-panels`.

**Three properties were demonstrated before any session ran:**

1. Adding `v2` to the directory changed **nothing**: `graph fig-checklist`
   still reported in sync, because the views render the *pinned* version. A
   new version is inert until its pin moves. That is the one job the manifest
   exists to do.
2. `expand_skill_sets` produced exactly two sets, labelled `pinned`
   (`c975706b…`) and `micrograph-scale-bar@v2` (`349a17b3…`).
3. The existing suite *failed* with `v2` present —
   `test_every_leaf_that_needs_panels_delegates_for_them` — which is the
   invariant working, and an independent argument against committing it.

**The live comparison:** `run --unpin micrograph-scale-bar --versions v1,v2
--limit 2`, 4 sessions, 4m31s, `gpt-5-mini`.

| SkillSet | example | instances | mean |
|---|---|---|---|
| `pinned` (v1) | `…00715-1/content/2` | 105 | **1.000** |
| `micrograph-scale-bar@v2` | `…00715-1/content/2` | 105 | **1.000** |
| `micrograph-scale-bar@v2` | `…00715-1/content/1` | 56 | 1.000 |

**Comparability holds.** On the example both sets produced, the two versions
scored against the same `schema.json` and the same `eval-manifest.json`, and
the evaluator emitted the **same 105 instances across the same 7 fields** —
same alignment, same denominators, directly comparable. Delta `+0.000`.

### Two findings from the comparison that matter more than the numbers

**1. A version cannot ablate a sibling skill.** `v2` declared `requires: []`
and its prose never mentions `identify-panels` — and the agent called
`identify-panels` anyway, on **both** examples (trace: `micrograph-scale-bar
v2 → identify-panels v1`). The shared skill is still assembled into the
runtime and its description still competes, so it was found from the task
alone. This is strong evidence *for* description-driven discovery. It is also
a limit on what a version comparison can measure: **two versions of one skill
share the same assembled skill pool**, so a version cannot remove a sibling
from competition. An ablation study would need a different mechanism than
`--unpin`.

**2. A real defect, found and fixed.** The first `pinned` example failed:

```
Intermediate panels.json produced by 'identify-panels' does not match its
schema: … 'panel_label_region' was unexpected …
```

The session had produced a **valid leaf answer**. It was thrown away because a
*debug sidecar* was malformed. `validate_intermediates` justified raising as
catching a bad artifact "before a downstream skill consumes it" — but it only
ever runs **after the session has closed**, so by the time it looks, every
downstream skill has already consumed the artifact and the leaf has already
answered. The stated purpose was unreachable from where the check sits; its
only actual effect was to discard completed work. The same docstring already
argues that a *missing* intermediate must not crash the run for exactly this
reason.

Fixed: the runner calls it with `strict=False`, which logs the violation,
records it in the report as `invalid_intermediates`, and keeps the prediction.
`strict=True` remains the default for direct callers. Covered by
`test_an_invalid_intermediate_does_not_discard_the_prediction`; the previously
failing example was re-run live and now completes.

---

## Three defects an independent code review found after the gates

All three were invisible to a green 296-test suite, and all three live in the
seam Milestone 6 opened: **once more than one version of a skill can exist,
every place that resolved "the" version by convention becomes a latent bug.**

### 1. Hops were compared against the wrong version (high)

`run_check_live` passes `pins=versions` to `runtime_session`, so the session
genuinely ran the pinned version — but `compare_declared_and_observed` called
`select_versions(skills)` with no pins, resolving to `max(versions)`. The
moment a check has two versions — i.e. **exactly the `--unpin
micrograph-scale-bar --versions v1,v2` comparison this milestone exists to
enable** — every `v1` session would be scored against `v2`'s declared hops,
inventing both missing and extra hops out of nothing. That field is the gate
4D evidence, printed by `main` and stored in the report. `_mock_trace` had the
same defect and additionally ignored the manifest entirely.

Fixed: both take pins, falling back to the manifest before the highest
version.

### 2. The turn ceiling was inert on the default provider (medium)

`model-defaults.yaml`'s `session.max_turns` was parsed, validated, folded into
the session options, documented in the repo README *and* in the file itself —
and never read by the OpenAI loop, which bound its ceiling at construction
from `MAX_TURNS = 40`. On the `claude-sdk` path it worked; on the `openai`
path — the argparse default, and the only provider with credentials here — it
did nothing. A cost ceiling that validates cleanly and has no effect is worse
than not offering one. This document also claimed 24 *was* the existing
ceiling; it was 40.

Fixed: the client reads `max_turns` from the options at call time.

### 3. A single-variant `--unpin` overwrote the baseline (medium)

The per-set output directory was chosen by `len(skill_sets) == 1` —
cardinality, not whether anything was unpinned. `--unpin X --versions v2`
expands to exactly **one** set, so its predictions were written straight into
the baseline directory, silently overwriting the pinned run's answers with a
different SkillSet's. The README documents the opposite contract. Nothing on
disk recorded which SkillSet produced a prediction, either: the digest lived
only in the in-memory report, which `main` prints and discards.

Fixed: the directory is keyed on the **label**, and every prediction now
carries a `skill_set.json` sidecar with the digest and the full entry list — a
directory name is not evidence.

Each fix was falsified by reverting it and confirming the new tests fail.
Test count: **306**.

---

## Deviations from the plan, stated

- **Step 6 (cache key) was implemented before gate 6A cleared.** Gate 6A
  blocks Step 6 because the manifest is what Langfuse attributes results to.
  The cache-key change depends on the *shape* of a SkillSet, not on the
  *content* of the manifest, so nothing downstream of the gate's actual
  decision was prejudged. Flagging it rather than hiding it.
- **`--unpin` lives on `run`, not on `graph`.** `graph` is metadata-only and
  must stay fast; an expansion is a thing you execute, not a thing you render.
- **`session_cache_key` gained an optional `skill_set` argument** rather than a
  required one. With none supplied it derives one from the assembled runtime,
  so the pre-existing property — editing a `SKILL.md` inside a runtime changes
  the key — survives unweakened.

## Carry-forwards

Unchanged from Milestone 5, plus:

- The threshold counts SkillSets, not sessions (gate 6A open question above).
- `load_skills` reports one malformed file at a time.
- Whether to commit a real `micrograph-scale-bar` v2 — and whether the
  "delegated vs self-contained" question is worth a milestone of its own,
  given finding 1 above shows `--unpin` cannot answer it.
- Work remains **uncommitted** on branch `agentic`.
