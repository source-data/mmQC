---
title: exp-06 — the full figure checklist, fanned in from one entry point
date: 2026-10-11
status: done           # draft | planned | running | done | abandoned
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
| P4 | Runner: both arrangements, concurrency 50; closures 13 and 14 skills | `4ad9b9691` |
| P5 | Smoke test: both arrangements on 3 figures | below |
| P6 | `panels.py` generalised to any list of checks (exp-04's three by default); the notebook during the run | this commit |

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|
| 2026-10-11 | smoke, both arrangements | `run.py --smoke` | $1.59 | `experiments/runs/exp-06-full-checklist/smoke/` (not committed) |
| 2026-10-11 | both arrangements | `python experiments/exp-06-full-checklist/run.py` | $87.66 | `experiments/runs/exp-06-full-checklist/` |

The estimate is the smoke test's mean, $0.27 per session, over 370 sessions.

**Smoke test, 2026-10-11.** Both arrangements × 3 figures (`s44318-026-00715-1`
content/1–3), one replicate, 6 sessions, none failed, $1.59.

- **Dispatch**: all eleven checks in 6/6 sessions, always in D's order; no
  skill outside the closure.
- **The shared step**: `A|B ← C_i ← D` invoked `classify-panels` once in one
  session and not at all in two — classified inline, as exp-04 saw; `A ← B ←
  C_i ← D` invoked `classify-panels` once or twice and `identify-panels` once
  in every session. Never once per check.
- **Answers**: every one valid against the contract; within a session the
  eleven check lists name the same panels (no partly-missing panel). The deep
  arrangement split one panel on content/3 — the figure exp-04's smoke test
  split too.
- **Size**: 26–32 turns, 9,800–28,700 output tokens, 75–236 s and $0.17–0.36
  per session. Within no turn limit, so none is needed.

## Findings

Run 2026-10-11 at concurrency 50: 370 sessions, **none failed**, $87.66.
Analysis in `notebooks/experiments/exp-06-full-checklist.ipynb`, against
`gold-v5`. `individual-data-points · explanation` is unscored (convention C3;
fixed in the contract before scoring, `e8901a1a8`).

### Numbers

**Dispatch — all or nothing, almost always all.**

| | all eleven checks | no check | partial | `classify-panels` reached | `identify-panels` reached | in D's order |
|---|---|---|---|---|---|---|
| `A\|B ← C_i ← D` | **184/185** | 1 | 0 | 64/185, never twice | — | 185/185 |
| `A ← B ← C_i ← D` | **182/185** | 3 | 0 | 109/185 (twice in 3) | 130/185 | 185/185 |

No session stopped partway, so no check was dropped for its position in D's
list. A session that invoked no check still answered all eleven from the
schema. No skill outside the closure. **One empty answer**, in
`A ← B ← C_i ← D`: all eleven checks empty.

**The four sessions that invoked no check**, each beside the same figure's
other replicates in the same arrangement, which all dispatched (layer S and
layer 1 pooled over the eleven checks; at layer 2, errors on the eleven
decisions listed under Layer 2, counted, not averaged across properties):

| arrangement · figure | what the figure shows | layer S found / both | layer 1 | decision errors / instances | turns | cost |
|---|---|---|---|---|---|---|
| `A\|B ← C_i ← D` · `s44320-025-00092-7` Fig. 1 | mostly schematics | 1.000 / 1.000 — 1.000 / 1.000 | **0.912** — 1.000 | 0 — 0.25 / 18 | 5 — 27.5 | $0.33 — $0.20 |
| `A ← B ← C_i ← D` · `embor.2009.217` Fig. 4 | western blots | 1.000 / 1.000 — 1.000 / 1.000 | **0.951** — 0.997 | 0 — 0.75 / 28–36 | 4 — 28 | $0.12 — $0.15 |
| `A ← B ← C_i ← D` · `s44319-025-00415-7` Fig. 2 | mostly cartoons | 1.000 / 0.857 — 1.000 / 0.917 | **0.936** — 0.963 | **3.9** — 0.7 / 15 | 8 — 29.5 | $0.13 — $0.27 |
| `A ← B ← C_i ← D` · `s44319-025-00432-6` Fig. 7 | FACS only | 1.000 / 1.000 — 1.000 / 1.000 | **0.902** — 0.984 | 0 — 0 / 35 | 4 — 27 | $0.16 — $0.16 |

(no-check session — mean of the figure's four dispatched sessions.) Layer S
does not move: every panel found, and the 11 spurious rows in `00415-7` are
one spurious panel in all eleven lists, which the dispatched sessions state
too (8.25 rows on average). **Layer 1 is lower in all four**, by 0.03 to 0.09:
the loss is in deciding whether a check applies. Where the session and the
gold agree that it does, the decisions are right — no decision error in three
of the four, against 0 to 0.75 in the dispatched sessions — except in
`00415-7`, with 3.9 errors in 15 against 0.7. Pooled over the four, layer 1
falls most in `replication-reporting` (0.77 against 0.93), then `stat-test`,
`error-bars-defined`, `plot-gap-labeling` and `individual-data-points`. The
four figures have little in common — schematics, western blots, cartoons,
FACS — and no pattern shows.
A no-check session takes 4–8 turns instead of about 28; its cost is not
consistently lower. Four sessions: cases, not an estimate.

**Layer S**, per check (`found` = correct ÷ (correct + missing); `both` also
counts spurious rows):

| | `A\|B ← C_i ← D` found / both | `A ← B ← C_i ← D` found / both |
|---|---|---|
| most checks | 0.997 / 0.992 | 0.992 / 0.987 |
| `individual-data-points` | 0.996 / 0.990 | 0.992 / 0.987 |
| `stat-significance-level`, `stat-test` | 0.996 / 0.991 | 0.992 / 0.987 |
| `plot-axis-units` | 0.991 / 0.983 | 0.985 / 0.977 |

**Panels across the eleven lists**: 6 spurious panels in each arrangement;
missing 2 (`A|B ← C_i ← D`) against 10 (`A ← B ← C_i ← D`); **partly missing
2 in 185 sessions** — one panel inventory holds across eleven check lists, as
it held across three in exp-04.

**Layer 1**, `A|B ← C_i ← D`: `image-annotation-defined` 0.997,
`single-channel-for-overlay` 0.996, `micrograph-scale-bar` 0.989,
`panel-image-matches-caption` 0.985, `stat-significance-level` 0.983,
`individual-data-points` 0.983, `error-bars-defined` 0.982,
`plot-gap-labeling` 0.982, `stat-test` 0.979, `replication-reporting` 0.971,
`plot-axis-units` 0.963.

**Layer 2**, `A|B ← C_i ← D`: most properties at 0.93 or above, most
decisions 0.95–1.00. The weakest:

| check · property | mean_score | figures |
|---|---|---|
| `plot-axis-units · unit_definition_as_provided[].definition` | 0.77 | 28 |
| `replication-reporting · replicate_statements` | 0.79 | 37 |
| `plot-axis-units · units_provided[].answer` | 0.83 | 34 |
| `stat-significance-level · symbol_definition` / `symbols_defined` / `significance_level_symbols_on_image` | 0.84 / 0.86 / 0.87 | 37 |
| `error-bars-defined · from_the_caption` | 0.87 | 28 |
| `panel-image-matches-caption · discrepancies` | 0.90 | 5 |
| `single-channel-for-overlay · all_channels_shown_separately`, `number_of_single_channel_images_shown` | 0.92 | 13 |
| `individual-data-points · individual_values` | 0.93 | 34 |
| `plot-axis-units · decision` | 0.94 | 34 |
| `replication-reporting · decision` | 0.96 | 33 |
| `stat-significance-level · decision` | 0.95 | 33 |

**Each check's decision on its own** (one decision-like property per check,
not averaged with the others; `A|B ← C_i ← D`, mean over figures): 0.92
`single-channel-for-overlay · all_channels_shown_separately` (13 figures,
interval down to 0.77), 0.94 `plot-axis-units`, 0.95 `stat-significance-level`,
0.96–0.97 `replication-reporting`, `individual-data-points`,
`panel-image-matches-caption · image_matches_caption`,
`image-annotation-defined · annotation_defined_in_caption` and
`micrograph-scale-bar · scale_bar_defined_in_caption`, 0.99–1.00 `stat-test`,
`error-bars-defined`, `plot-gap-labeling`. The arrangements differ by no more
than 0.03 on any of them, intervals overlapping.

**The arrangements side by side**, `A ← B ← C_i ← D` minus `A|B ← C_i ← D`:
lower at layer S for every check (about −0.005, intervals [−0.016, 0.000]) and
at layer 1 for every check (−0.001 to −0.008; `micrograph-scale-bar`'s interval
wholly below 0); at layer 2 mostly small negative differences, intervals
including 0. Reported, not tested.

**Cost and time per figure** (concurrency 50): `A|B ← C_i ← D` $0.235
[0.216, 0.253], `A ← B ← C_i ← D` $0.239; about 17,600 output tokens, 27
turns and 169 s per session. The 370 sessions took under an hour.

**Replicate variance**: planned five-against-five half-widths at layer S
0.0075 (`A|B ← C_i ← D`) and 0.017 (`A ← B ← C_i ← D`) — the deeper arrangement
is the noisier.

### Reading

*Interpretation, separable from the numbers above.*

**One session can run the whole checklist.** Eleven checks did not break
dispatch: when D dispatched it dispatched all eleven, in order, and position in
the list cost nothing. The inventory held across eleven lists. The failure mode
that remains is the one exp-03 named — a session answering every check without
invoking any — at 1–3 sessions in 185. It costs little at the panel level and
something at applicability: such a session finds the same panels, and its
decisions are mostly right where a check applies, but it decides less well
whether a check applies — consistently in the four cases, most in
`replication-reporting` — as if answering from the schema instead of from the
check's instructions. The four figures share nothing obvious.

**`A|B ← C_i ← D` is the baseline.** It is ahead of `A ← B ← C_i ← D` on
dispatch, layer S, layer 1 and panel completeness, at the same cost, and its
replicate variance is lower — as in exp-04 with three checks.

**Where to improve is concentrated.** The checks judge applicability well
(layer 1 ≥ 0.96 everywhere) and most verdicts are right; what is weakest is
text taken from the figure or caption — unit definitions, replicate
statements, significance definitions, error-bar definitions — and the per-axis
and per-symbol lists. The error analysis starts from the verdicts, which are
what a reader acts on, and leaves the text extractions for later.

## Gold this was scored against

**`gold-v5`**.

## Status and next

Run and analysed. **Next: the error analysis**, starting — as decided with the
author, 2026-10-11 — from each check's verdict (`decision`, or its equivalent
where a check has none), and putting aside the text extractions scored by
semantic comparison.
