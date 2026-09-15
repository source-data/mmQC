---
title: Milestone 5 results — score the pilot, then convert by group
date: 2026-09-15
tags: [agentic, milestone, conversion, results]
plan: 2026-09-02-agentic-checklist-skills.md
status: COMPLETE - all five gates decided 2026-09-15
---

# Milestone 5 Results

Outcome record for **Milestone 5: Score the Pilot, Then Convert by Group** of
[`2026-09-02-agentic-checklist-skills.md`](2026-09-02-agentic-checklist-skills.md).

**Deliverable:** the pilot check scores through the unchanged `FlatEvaluator`,
`evaluate` delegates agentic checklists to `cli.py`, and the remaining leaves
are converted group by group.

> ## Gate status
>
> | Gate | Status |
> |---|---|
> | **5A** — pilot quality | **PASSED 2026-09-14**, Çağatay Gürsoy |
> | **5B** — legacy compatibility | **PASSED 2026-09-15 with a requirement:** *"Agentic pipeline should not revert back to legacy prompts."* |
> | **5C** — Group A review + retirement | **PASSED 2026-09-15:** *"do not retire legacy prompts yet"* |
> | **5D** — the Group B design fork | **decided on evidence 2026-09-15** |
> | **5E** — Group B review | **ACCEPTED 2026-09-15:** *"For this initial construction stage, this is acceptable"* |
>
> **All eleven `fig-checklist` leaves are converted.** The graph is three
> levels and acyclic across 13 skills.

- **Branch:** `agentic`, uncommitted
- **Measured:** 2026-09-15, `gpt-4o` on both paths

---

## The headline number

Both paths run on **the same two examples with the same model**, Langfuse
pinned off so the legacy prompt source is local.

| check | agentic | legacy | delta |
|---|---|---|---|
| `micrograph-scale-bar` | 0.810 | 0.810 | — |
| `single-channel-for-overlay` | 1.000 | 1.000 | — |
| `panel-image-matches-caption` | 1.000 | 1.000 | — |
| `error-bars-defined` | 0.667 | 0.667 | — |
| `individual-data-points` | 0.567 | 0.567 | — |
| `plot-gap-labeling` | 0.306 | 0.306 | — |
| **`plot-axis-units`** | 0.762 | 0.833 | **−0.071** |
| **`stat-test`** | 0.548 | 0.595 | **−0.048** |
| `stat-significance-level` | 0.714 | *no legacy run* | n/a |
| **mean over the 8 comparable** | **0.707** | **0.722** | **−0.015** |

**Six of eight leaves are identical to the legacy path. Two regress slightly.
The overall delta is −0.015.**

Read that against gate 5A, which measured `micrograph-scale-bar` at 1.000 vs
0.980 on five *different* examples. The two examples used here are harder for
both paths — `micrograph-scale-bar` scores 0.810 here versus 1.000 there — so
these absolute numbers are not comparable with 5A's. The *deltas* are what this
table is for.

**Caveats, the same three as gate 5A and still true.** Two examples per leaf is
a small sample; they were chosen because they are the only two with gold across
nine leaves, not at random; and one run each means variance is unmeasured. A
−0.015 mean delta is well inside what two examples can resolve.

---

## Human gate 5B — legacy compatibility

**Decision:** does the delegation change anything for someone who runs the
legacy commands the way they run them today?

**Status: PASSED 2026-09-15, Çağatay Gürsoy — with a requirement.**

> *"Agentic pipeline should not revert back to legacy prompts."*
>
> Taken as a hard rule rather than an observation, and **enforced** rather than
> left as a property of the routing logic. See
> [No silent reversion](#no-silent-reversion-the-gate-5b-requirement).

### A deliberate deviation from the plan's wording

The plan says *"a **checklist** with an agentic layout dispatches"*. That is
right for a fully converted checklist and was wrong while converting:
`fig-checklist` had one converted leaf and ten prompt-only ones, so
checklist-level dispatch would have broken ten working checks to route one.

The discriminator is therefore **per check** — a check owning a `v*/SKILL.md`
dispatches, one without keeps exactly its present behaviour. That satisfies the
plan's own first clause, "legacy checks keep present behavior". Now that
`fig-checklist` is 11/11 converted, the two readings agree for it, and the
per-check rule still protects `doc-checklist`, `data-checklist` and
`Retired-checklist`.

### Routing, observed

| command | routes to |
|---|---|
| `evaluate doc-checklist --check AB-target-reagent-consistency` | `process_check` — unchanged |
| `evaluate fig-checklist --check micrograph-scale-bar` | agentic runner |
| `evaluate fig-checklist` | agentic runner for all 11 |
| `evaluate doc-checklist` | `process_checklist`, selection passed through untouched |
| mixed selection | one check to each path |

### A gap this gate caught

The first implementation only routed when `--check` was given. A whole-checklist
run names no check, so the pilot **fell through to its legacy prompt** — which
would have produced a prompt-path score filed under an agentic check's name,
the most confusing possible outcome. A no-check run now resolves to the full
check list before routing. A checklist with no agentic checks still passes the
caller's original selection through untouched.

This is the second time producing a gate artifact caught something the tests
did not, and both times it was because the gate asks for real commands to be
run rather than for the suite to be trusted.

### `--prompt-version` on an agentic check

Exits 2 with:

> `--prompt-version selects between prompt files and has no meaning for agentic check(s): micrograph-scale-bar. Skills are versioned by directory (v1, v2, ...) and pinned by manifest, not by this flag. Re-run without --prompt-version, or name only legacy checks.`

It still works normally for legacy checks.

### Inherited, not introduced

`evaluate` validates the model against the provider **before** any dispatch, and
that validation calls the provider's models endpoint. This is the same behaviour
Milestone 1 recorded as "`--mock` is not offline". Delegation inherits it; it
was not changed here.

### No silent reversion — the gate 5B requirement

*"Agentic pipeline should not revert back to legacy prompts."* Implemented as
an enforced rule, in three places rather than one:

| Control | Behaviour |
|---|---|
| **Guard in `process_check`** | A converted check raises rather than running its prompt, **whatever route reached it**. This is the funnel `process_checklist` also passes through, so one guard covers every path |
| **Exit code propagated** | `_dispatch_check` returns the agentic runner's code instead of discarding it. A failed agentic check reports failure and is logged as *"NOT re-run through the legacy prompt path"* |
| **Router narrowing** | Agentic checks are removed from the legacy selection before `process_checklist` sees it |

The guard matters because the router is **not** the only way in, and the
`prompts/` directories are deliberately still on disk (gate 5C). Without it,
deleting or renaming a `SKILL.md` would silently resume prompt-path scoring
under an agentic check's name.

```
>>> process_check(fig-checklist/stat-test, "fig-checklist")
ValueError: stat-test is an agentic check and must not be run through the
legacy prompt path. Run it with `python -m soda_mmqc.cli run <checklist>
--check stat-test`, or via `evaluate`, which routes it automatically.
```

Four tests cover it, including one asserting that a **failing** agentic run
does not hand the check back to the prompt path.

### What a reviewer should check

The gate asks for *"the legacy commands actually in use — including flag
combinations the tests do not cover"*. The table above is what I could
enumerate from the CLI; **the invocations real users actually type are not
known to me**, and that is precisely the gap this gate exists to close.

---

## Human gate 5C — Group A review

**Decision:** are the Group A deltas explained, did `identify-panels` hold up
unchanged across four leaves, and may the legacy prompts be retired?

**Status: PASSED 2026-09-15, Çağatay Gürsoy.** *"Yes, do not retire legacy
prompts yet."* The deltas are accepted and **no `prompts/` directory is
removed**. Retirement remains available as a later decision once the sample is
widened.

### Did `identify-panels` hold up unchanged? **Yes.**

Four Group A leaves were converted against it and **it required no change to
serve them** — the reuse claim the whole design rests on, now demonstrated
rather than asserted. (It was later amended for a defect found in Group B; see
below. That change was a correction, not an accommodation of a new leaf.)

### Deltas

| leaf | agentic | legacy | delta |
|---|---|---|---|
| `micrograph-scale-bar` | 0.810 | 0.810 | — |
| `single-channel-for-overlay` | 1.000 | 1.000 | — |
| `panel-image-matches-caption` | 1.000 | 1.000 | — |
| `image-annotation-defined` | **unscoreable** | **unscoreable** | n/a |

Three of four are identical to the legacy path. Nothing to explain.

### `image-annotation-defined` has no gold

Its benchmark lists 44 examples and **none has an `expected_output.json`** for
that check. It converts and runs, but cannot be scored in either direction.

This is **not a defect**: the check first appears at `d9d0d479` (2026-06-24),
fourteen months after established checks like `micrograph-scale-bar`
(2025-04-24), and its gold was simply never curated. `replication-reporting` is
in the same state. An un-benchmarked check is a normal stage in this
repository's lifecycle.

*(An earlier version of this record called it "debt". That framing was wrong and
is corrected in the log.)*

### The description-collision risk, measured

Gate 2A warned that `panel-image-matches-caption` would compete with
`identify-panels` because both concern panels and captions. Measured with the
embedding model already used for scoring, retrieving the leaf's masked hop
sentence against all skill descriptions:

| | margin over runner-up |
|---|---|
| before it had a description (gate 2A) | **+0.013** |
| after writing it to claim *comparison* and disclaim identification | **+0.113** |

It remains the runner-up for the other three leaves at **+0.015**, so the
margin is thin and stays a watch item. Note the proxy is pessimistic: across
every live session in this milestone the model chose correctly **every time**.

### The retirement question

`prompts/` is still present for all eleven leaves and nothing was removed.

My recommendation is **not yet**, for two reasons. The legacy path is the only
comparison baseline, and the deltas above rest on two examples — retiring the
prompts removes the ability to widen that sample later. And for
`image-annotation-defined` and `replication-reporting`, parity is unanswerable
in either direction, so there is no evidence on which to retire those two at
all.

---

## Human gate 5D — the Group B design fork

**Decision:** does Group B need a shared plot skill, and if so what exactly does
it own — plot classification only, or axis identification and properties too?

**Status: DECIDED ON EVIDENCE — 2026-09-15.**

### The plan's proposal would have been wrong

The conversion map suggested `classify-quantitative-plot`, producing an
`is_quantitative_plot` boolean. Reading the seven Group B prompts shows the
leaves **disagree about the same panel deliberately**:

| leaf | pie chart / heatmap |
|---|---|
| `plot-axis-units` | *"Skip this check for schematics, pie charts, heat maps and sequence alignment plots."* — **not** a plot |
| `stat-test` | *"…histograms, pie charts, box plots, heatmaps, area charts…"* — **is** quantitative data |
| `individual-data-points` | *"box plots, violin plots, line graphs, scatter plots, heatmaps, Kaplan-Maier curves and pie charts are automatic PASS"* |

A shared boolean would force agreement where three different answers are each
correct for their own check. The duplication is real, but it is duplication of
*observation*, not of *verdict*.

### What was built instead

**`classify-plot-panels`** reports observations and no judgement:

- `plot_types` — every plot type observed, named plainly;
- `has_axes`, and per axis: `scale` (numeric / categorical / unclear),
  `tick_labels` transcribed **verbatim**, and `axis_title`;
- `evidence`.

Each leaf keeps its own inclusion rule. This is the same shape as
`identify-panels` — report facts, leave verdicts to the caller — and it is why
the skill is not named for the question it refuses to answer.

**The gate's second half is answered "both".** Axis facts are included because
`plot-axis-units` and `plot-gap-labeling` both need them, and
`plot-gap-labeling` in particular needs tick labels transcribed rather than
normalised (`0, 10, 20, 30, 500` is the whole signal). That is exactly the kind
of thing worth doing once.

---

## Human gate 5E — Group B review

**Decision:** are the Group B deltas explained and acceptable?

**Status: ACCEPTED 2026-09-15, Çağatay Gürsoy.** *"For this initial
construction stage, this is acceptable."* The two regressions
(`plot-axis-units` −0.071, `stat-test` −0.048) and the thin two-example sample
are accepted as appropriate to a construction stage, not as a final quality
position.

### Deltas

| leaf | agentic | legacy | delta |
|---|---|---|---|
| `error-bars-defined` | 0.667 | 0.667 | — |
| `individual-data-points` | 0.567 | 0.567 | — |
| `plot-gap-labeling` | 0.306 | 0.306 | — |
| **`plot-axis-units`** | 0.762 | 0.833 | **−0.071** |
| **`stat-test`** | 0.548 | 0.595 | **−0.048** |
| `stat-significance-level` | 0.714 | *no legacy run* | n/a |
| `replication-reporting` | **unscoreable** | **unscoreable** | n/a |

### The two regressions, explained

**`plot-axis-units`, −0.071.** This one was **−0.548 before a fix**, and the
diagnosis is the most useful thing in this milestone.

The regression was entirely in `panel_label` (0.333 vs 1.000), which cascades
because `panel_label` is the evaluator's list-alignment key — every other field
mis-aligns with it. On `10.1038_embor.2009.217/content/4` the agentic path
returned **a single panel with an empty label** where gold and legacy both found
A, B, C, D.

That is the gate 2A fallback rule — *"unlabeled figure → one panel with an empty
label"* — firing on a figure that plainly has labels. It was the addition I
flagged at that gate as "the one most worth a reviewer's disagreement", and it
was worth disagreeing with. The trace shows `identify-panels` invoked **nine
times** in that session before settling on the empty label, while the caption
reads "(A) Human fibroblasts … ".

**Fixed** by making the caption evidence about labels, not only about content,
and by demoting the empty label to a last resort requiring *both* image and
caption to show none — with the consequence stated in the prose: it collapses
every panel into one row, so a wrong empty label destroys the whole figure
rather than degrading it. Labels are now `A, B, C, D` and the delta went
−0.548 → −0.071.

The residual −0.071 is one field on one example and is within what two examples
resolve.

**`stat-test`, −0.048.** Two instances on 42. Not diagnosed individually; at
this sample size it is indistinguishable from noise.

### `stat-significance-level` has no legacy baseline

Its legacy run failed: the benchmark references
`10.1038_s44318-026-00759-3/content/1`, whose content directory does not exist.
That check also lists **50** benchmark examples while only 38 have gold. A
pre-existing data inconsistency, unrelated to this milestone, but it means no
delta can be computed for it.

### Schema-shape defects found and fixed while converting

Four leaves failed validation on first run, all the same class — **prose
implying a shape the schema forbids**:

| leaf | what happened |
|---|---|
| `plot-axis-units` | I wrote three per-axis fields as scalars, then as string lists; the schema wants `{axis, answer\|definition\|explanation}` objects |
| `identify-panels` | prose said "name each element separately" while its own schema declares `panel_content` a **string** |
| `error-bars-defined` | the model put `not needed` in `error_bar_on_figure`, which permits only `yes`/`no` — the prose listed three fields that take `not needed` and the model over-generalised |

All were caught by validation before anything was written as a prediction, and
the `identify-panels` one by `validate_intermediates` before the artifact went
downstream. **The guards worked; the prose should not have needed them.** The
cheap lesson: read the full schema *including item types* before writing output
prose.

---

## Automatic gate (Step 9)

```
pytest tests/test_agentic_cli.py tests/test_micrograph_scale_bar_manifest.py
242 passed
```

Whole suite: `FAILED`/`ERROR` set **62 lines**, unchanged from the Milestone 1
baseline across all five milestones.

Delegation tests were repointed at `doc-checklist`, because `fig-checklist` no
longer contains a legacy check to contrast against — itself a small proof that
conversion is complete.

---

## The graph, as built

```
identify-panels                      (root; no requirements)
  ├── classify-plot-panels           (shared; requires identify-panels)
  │     ├── error-bars-defined
  │     ├── individual-data-points
  │     ├── plot-axis-units
  │     ├── plot-gap-labeling
  │     ├── replication-reporting
  │     ├── stat-significance-level
  │     └── stat-test
  ├── image-annotation-defined
  ├── micrograph-scale-bar
  ├── panel-image-matches-caption
  └── single-channel-for-overlay
```

13 skills, acyclic, **three levels** — the shape the plan sketched in "Two
Different Discoveries" and which had never actually fired until this milestone.
Verified live: `classify-plot-panels` → `identify-panels` → leaf.

---

## What Milestone 6 inherits

| Item | Why |
|---|---|
| **`C top`/`C bottom` in `plot-axis-units` gold** | Carried from gate 2A. A curator-invented sub-division the shared skill is forbidden to produce; it will mis-align whenever that figure is scored |
| **Two unscoreable checks** | `image-annotation-defined` and `replication-reporting` have no gold, so they cannot participate in any quality gate |
| **`stat-significance-level` benchmark** | Lists 50 examples, 38 have gold, and one references a missing content directory |
| **Widening the sample** | Every delta here rests on two examples. The conclusions are directionally useful and statistically thin |
| **The `+0.015` description margin** | `panel-image-matches-caption` is runner-up to `identify-panels` for three leaves. Live choice has been correct every time, but the margin is small |
| **Prompt retirement** | Deliberately not done. Recommended only after the sample is widened |
