---
title: exp-06 — the full figure checklist, fanned in from one entry point
date: 2026-10-11
status: draft          # draft | planned | running | done | abandoned
kind: experiment
extends: exp-04
tags: [experiment, skills, dag, entry-point, baseline, full-checklist]
---

# exp-06 — the full figure checklist, fanned in from one entry point

*A baseline, not a test: it has no hypothesis to accept or reject. The note is
still written, and committed, before the run, so that what is measured and how
it is read are fixed before any number exists.*

## Question

How does the figure checklist perform — all eleven checks, run by one entry
skill in one session per figure — in the arrangement exp-04 found best, and in
the deeper one beside it? Per check, per layer and per property, and at what
cost and time?

## Why

exp-03 to exp-05 ran three checks. exp-04 found check-major
`A|B ← C_i ← D` the most accurate arrangement for them (layer S, counting both
errors, 0.997; every check dispatched in 190/190 sessions; no empty answer),
and exp-05 found that moving the shared step up to D, by design, broke
dispatch. Production runs eleven checks. exp-06 extends the winning
configuration to all of them and measures it **as the baseline the series
improves from**: every later change to a skill, a contract or the
orchestration is compared with it.

No session has yet held more than three checks. Eleven multiply the
instructions in one context, the number of dispatches D has to make, and the
places a session can stop short — so dispatch is read first, in detail.

## Design

| | |
|---|---|
| Checklist | `fig-checklist-exp06` |
| Entry skill | `do-fig-checklist-cm` v1, listing the eleven checks (order below) |
| Checks | the eleven of `fig-checklist`: exp-04's three at v3, the other eight ported from the production skills into the same form (2026-10-07 to 2026-10-11) |
| Shared skills | exp-04's: `identify-panels` v1 (A), `classify-panels` v1 (A\|B) and v2 (A ← B) |
| Contract | check-major, derived from the eleven production contracts (`experiments/exp-06-full-checklist/build_contract.py`) |
| Gold | `gold-v5` |
| Figures | 37: exp-04's 38 less `s41592-023-01987/content/4`, a Nature Methods guide on figure preparation, not a research figure |
| Model, provider | `claude-sonnet-5`, `claude-sdk` |
| Assembly | closure |
| Replicates | 5 |
| Concurrency | **50** (recorded in each session's `tool_audit.json`) |
| Sessions | 2 arrangements × 37 figures × 5 replicates = **370** |
| Turn limit | none (no `model-defaults.yaml`, as in exp-04) |

### Two arrangements

| arrangement | pins | each check |
|---|---|---|
| **`A\|B ← C_i ← D`** | the checklist's pins | invokes `classify-panels` v1, which lists and classifies the panels |
| **`A ← B ← C_i ← D`** | `classify-panels` → v2 | invokes `classify-panels` v2, which invokes `identify-panels` v1 to list the panels, then classifies them |

### The check order

D lists them as the author agreed: image checks, then plot checks, then the
check that reads every panel against the caption —
`micrograph-scale-bar`, `image-annotation-defined`,
`single-channel-for-overlay`, `individual-data-points`, `error-bars-defined`,
`plot-axis-units`, `plot-gap-labeling`, `stat-significance-level`, `stat-test`,
`replication-reporting`, `panel-image-matches-caption`.

### How the checks were written

From the production skills, one at a time, drafted by Claude and edited by the
author, into exp-04's form:

- **every check opens the same way** — "List and classify all figure panels:
  … invoke the `classify-panels` skill to list every panel and classify it by
  content type" — including exp-04's three, which deviate from exp-04's v3 by
  this paragraph;
- **applicability comes from the coarse classification**, and each check
  narrows it itself where it must (`is_a_plot_with_axes`,
  `multicolored_overlay_micrograph`, `involves_replicates`, the caption for
  `panel-image-matches-caption`), without check-specific lists of exceptions;
- what production took from `identify-panels`' caption mapping and
  `classify-plot-panels`' axis description, the checks now read themselves.

Contract changes on the way, in production and gold alike: `is_a_plot_with_axes`
(`plot-axis-units`, `plot-gap-labeling`), `statistical_significance_claim`
(`stat-test`), and `single-channel-for-overlay`'s counts — `not_applicable`
without an overlay — and its unscored `overlay_channels`.

## What is measured

All reported per arrangement, with percentile bootstrap intervals over the 37
figures, replicates averaged per figure first.

### 0. Dispatch, read first

From `skill_trace.json`, per session:

- **checks invoked**: how many of the eleven, and which are skipped — and
  whether skipping depends on position in D's list;
- **all dispatched**: sessions that invoked all eleven;
- **no check / partial**: sessions that answered checks they did not invoke;
- **the shared step**: how many times `classify-panels` was invoked per
  session (once, shared by every check, or up to once per check), and
  `identify-panels` in `A ← B ← C_i ← D`;
- **order**: whether checks run in D's order;
- **spontaneous**: any skill outside the closure.

### Failures and empty answers

Failed sessions, and empty answers per check — a session that fails loses all
eleven checks, and exp-05 saw empty answers that were possibly model-side.

### Layer S, and panels

- per check, `correct / (correct + missing)` and
  `correct / (correct + missing + spurious)`;
- per figure, **spurious, missing and partly-missing panels** across the eleven
  check lists (`experiments/exp-04-panel-major/panels.py`, generalised to
  eleven checks): whether one panel inventory holds across all of them, as it
  held across three in exp-04.

### Layers 1 and 2

- layer 1 per check;
- layer 2 **per check and per property**, as means with intervals, and
  plotted per check, one bar per property per arrangement.

### Cost and time

Per figure: cost, input, cache-read and output tokens, turns, wall time — at
concurrency 50, so comparable only with runs at the same concurrency.

### Replicate variance

Per arrangement, check and layer: the between-replicate variance per figure,
and the half-width a later five-against-five comparison would plan for. This
is what later experiments size their margins from.

### The arrangements side by side

`A ← B ← C_i ← D` against `A|B ← C_i ← D`, per check and layer, as paired
differences with intervals — **reported, not tested**: the baseline is the
pair.

## After the run: error analysis

The point of the baseline is to say what to improve. Before any skill or
contract is changed:

1. List, per check and property, the layer-2 disagreements with gold, and the
   layer-1 applicability errors, ranked by how often they occur across
   replicates.
2. Read the most frequent by hand, with the figure, and sort each into
   **model error** (the skill should change), **gold error** (the gold
   should be curated) or **ambiguous** (the contract or the rule should say
   more).
3. Record the sorting in the findings. Gold errors are curated and tagged as a
   new gold version before any comparison uses them.

## Threats to validity

- **No comparison with exp-04.** exp-06's three checks open differently from
  exp-04's v3, and exp-06 drops one of exp-04's figures; the numbers sit beside
  exp-04's, not against them.
- **Order is fixed**, so a check's position and its identity are confounded —
  and with eleven checks, position may matter more than it did with three.
- **37 figures** bound every per-check estimate; properties applicable to few
  figures have wide intervals.
- **Gold quality varies by check**: eight checks' gold was curated less recently
  than exp-04's three, which the error analysis is there to find.
- **No turn limit**: a session that loops runs until it stops; the smoke test
  and the turn counts are the guard.

## Preparation

| # | step | done |
|---|---|---|
| P1 | The eight checks ported, the three re-opened, D listing eleven | `afb1df70a`, `e05b44e75` |
| P2 | Contract derived and verified: 6,919 comparisons on 37 figures, identical | `fe710a20c` |
| P3 | Merged gold; `gold-v5` | `3aaa24734`, `45d664092` |
| P4 | Runner: both arrangements, concurrency 50 | |
| P5 | Smoke test: both arrangements on 3 figures | |
| P6 | `panels.py` generalised to eleven checks; the notebook | |

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|

## Findings

*To be written after the run.*

## Gold this was scored against

**`gold-v5`**.

## Status and next

Draft. Next: P4–P6, then the run.
