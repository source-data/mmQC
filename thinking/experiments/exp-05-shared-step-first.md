---
title: exp-05 — the shared step first, by design
date: 2026-10-07
status: done           # planned | running | done | abandoned
kind: experiment
extends: exp-04
tags: [experiment, skills, dag, entry-point, shared-step, tokens]
---

# exp-05 — the shared step first, by design

*Preregistration, written before the full run. The draft it grew from
(2026-10-06) is in this file's history; its decisions are recorded under*
Preparation.

## Question

Should the entry skill run the shared step itself — panel identification and
classification, once — and only then dispatch the checks, which take the panel
classification as given?

exp-03 and exp-04 chained the skills from the bottom: D names the checks, and
each check either does the shared step inline (`A|B|C_i ← D`) or calls it
(`A|B ← C_i ← D`, `A ← B ← C_i ← D`). The model kept undoing that order. Under
D, `classify-panels` was reached once per session and never once per check
(exp-03); and under the panel-major contract, which asks D for the panel
classes directly, D took the shared step on itself and, in 20 sessions, then
answered without invoking any check (exp-04). exp-05 makes the order the model
reaches for the designed one:

```
[A|B, {C_i}] ← D        D invokes classify-panels (A|B) once, then each check
```

## Paper claim

That in a skill DAG whose checks share an upstream step, **the shared step
belongs to the entry point**: run once, at the top, before dispatch, it costs
the checks nothing in accuracy and saves the work of reaching it from below.
exp-04 found the opposite arrangement — each check reaching the shared step for
itself — partly undone by the model; this asks whether doing it on purpose
holds up.

From [exp-04's findings](exp-04-panel-major.md#findings):

- `A|B ← C_i ← D` under the check-major contract was the most accurate of
  exp-04's six conditions at layer S counting both errors (0.997);
- the panel-major contract pulled the shared step up to D: `classify-panels`
  reached in 95–97% of PM sessions against 68–76% under CM, and 33 PM sessions
  answered without invoking a check;
- PM wrote 31–44% more output tokens than CM, unaccounted for by the answer or
  by resubmissions; one untested explanation is that a panel-major answer must
  be transposed from check-by-check work.

## Hypotheses

Both contract shapes, each against the **same shape** under exp-04's
`A|B ← C_i ← D` (exp-04's CM-2 and PM-2, reused):

1. **Non-inferior.** Under `[A|B, {C_i}] ← D`, every check is no worse at
   layers S, 1 and 2. Six comparisons — three checks × two shapes — each its
   own claim.
2. **Fewer output tokens under PM.** PM under `[A|B, {C_i}] ← D` writes fewer
   output tokens per figure than exp-04's PM `A|B ← C_i ← D`. If the shared step
   is settled once, up front, by the skill that owns the panel rows, less is
   written to assemble them. One claim; CM's output tokens are reported beside
   it without a direction.

What would count as being wrong: a check degrading, which would say the checks
need to make or fetch the classification themselves; or PM's output tokens
unchanged, which would say its extra writing is not about where the shared step
sits.

**Dispatch is read first, and carries a named risk**: having classified the
panels itself, D may answer every check without invoking one — exp-04's PM
failure mode, which this arrangement could make easier. Nothing in D v2 guards
against it (decided 2026-10-06): exp-05 measures the arrangement as written.

## Decision criteria

Written before the run, so the threshold cannot drift to meet the data.

### Endpoints

| # | endpoint | statistic | gate? |
|---|---|---|---|
| **0** | **dispatch** | see below | reported, not a gate |
| **1** | **layer S** | `correct_row / (correct_row + missing_row)` per check | non-inferiority, δ_S |
| **2** | **layer 1** | `correct_applicable + correct_NA` over all profiled instances, per check | non-inferiority, δ₁ |
| **3** | **layer 2** | `mean_score` per property, on applicable instances, paired by example | non-inferiority, δ₂ |
| **H2** | **PM output tokens** | per-figure ratio, exp-05 PM ÷ exp-04 PM-2 | directional |

Both shapes are scored per check on the same instances as in exp-04 — PM's
shared `panel_label` and row set counted towards every check. Layer S is also
reported as `correct / (correct + missing + spurious)`, and spurious and missing
panels per figure are reported, without a direction.

### Statistics and verdicts

exp-04's, unchanged: per-example differences, exp-05 − exp-04 of the same
shape; replicates averaged per example first; seeded percentile bootstrap over
the 38 examples, 10,000 resamples (layer 2: `difference ± 1.96·se`, as in exp-02
to exp-04). **Non-inferior** if the 95% CI's lower bound is above −δ,
**degraded** if the CI lies entirely below −δ, **inconclusive** otherwise. Fixed
sequence within each comparison, S → 1 → 2. Replicate indices are not paired
across experiments; pairing is by example only.

**Hypothesis 2**: per figure, PM output tokens averaged over replicates, in
exp-05 and in exp-04's PM-2; the mean of per-figure ratios, exp-05 ÷ exp-04,
with a percentile bootstrap over the 38 figures. **Fewer** if the 95% interval
lies below 1, **more** if above, **inconclusive** otherwise. Cost, input tokens,
turns and time are reported beside it, for both shapes, without a direction.

### Margins

**δ_S = 0.0125, δ₁ = 0.02, δ₂ = 0.02**, exp-04's. exp-04's observed replicate
variance plans half-widths of 0.002–0.005 at layer S and up to 0.006 at layer 1
for a five-against-five comparison, well inside them; at layer 2 its observed
half-widths were ≤ 0.015 but for properties applicable to few figures.
**Pre-declared as expected to be uninformative**: `micrograph-scale-bar ·
from_the_image` at layer 2 (10 examples, half-width 0.025–0.035 in exp-04),
reported, not counted, if its interval is wider than δ₂.

### Endpoint 0: dispatch

From `skill_trace.json`, per session, as exp-04, plus:

- **shared step first** — `classify-panels` invoked before any check, the
  designed order; and how many times;
- **no check invoked** — sessions that answered without invoking a check skill,
  against exp-04's reference of the same shape (in `A|B ← C_i ← D`: CM 0
  of 190; PM 7 of 190, and 2 more invoking only some checks).

A check that is non-inferior with partial dispatch is **safe but optional**, as
in exp-03 and exp-04.

### Non-response and failures

As exp-04: an empty answer scores as a fully missing row set for every check,
and failures are reported per session and condition.

### The sanity rerun

exp-04's PM `A|B ← C_i ← D`, rerun once on every figure from the frozen
`fig-checklist-exp04`: its output tokens per figure and its layer-S and layer-1
rates are reported beside exp-04's five replicates. **Not a gate, and no
decision rests on it**: one replicate against five is a look, not a test.

## Design

| | |
|---|---|
| Checklist | `fig-checklist-exp05`, a copy of `fig-checklist-exp04` with new versions; exp-04's stays frozen |
| Entry skills | `do-fig-checklist-cm` and `-pm` **v2**: invoke `classify-panels`, then each check; identical but for the name |
| Checks | `micrograph-scale-bar`, `individual-data-points`, `error-bars-defined` at **v4** |
| Shared skill | `classify-panels` v1 (A\|B) |
| Contracts, gold | exp-04's, byte for byte; `gold-v4` |
| Model, provider | `claude-sonnet-5`, `claude-sdk` |
| Assembly | closure: D, `classify-panels` and the three checks; nothing else |
| Replicates, examples | 5; exp-04's 38 figures |
| Sessions | 418: 190 CM, 190 PM, 38 sanity |
| References | exp-04's CM-2 and PM-2, `experiments/runs/exp-04-panel-major/` |
| Runner | `experiments/exp-05-shared-step-first/run.py` |

### The skills

Written as exp-04's were, one at a time, proposed by Claude and edited by the
author:

- **D v2** adds `classify-panels` to `requires`, a step "Before running any
  check, invoke the `classify-panels` skill once…", and states the check order.
  Nothing tells D not to answer the checks itself.
- **The checks at v4** are v3 with the "Classify figure panels" section removed
  and `requires` empty. Nothing replaces it: the classification is in the
  session's context from D's call, and the checks' remaining references —
  "a panel whose classification includes …", "cross-check with the panel
  classification" — read it (decided 2026-10-06).
- **`classify-panels` v1** identifies and classifies and calls nothing.

## Preparation

| # | step | done |
|---|---|---|
| P1 | `fig-checklist-exp05` copied from exp-04, byte-identical | `44f7d5875` |
| P2 | D v2 and the checks at v4, reviewed | `5b51b0812`, `8593f3df3` |
| P3 | Closures: D, `classify-panels`, the three checks; `identify-panels` reached by nothing | `8593f3df3` |
| P4 | Contracts byte-identical to exp-04's | `8593f3df3` |
| P5 | Runner, with the sanity rerun | `run.py` |
| P6 | Smoke test | below |
| P7 | Notebook, run on the smoke sessions | `notebooks/experiments/exp-05-shared-step-first.ipynb` |

Decisions settled 2026-10-06: reuse exp-04's references, with one sanity rerun
instead of a drift check with a decision rule; `classify-panels` first, then
exp-04's check order; no section in the checks saying where the classification
comes from; no guard in D against answering without dispatching.

**Smoke test, 2026-10-07.** Both shapes × 3 figures (`s44318-026-00715-1`
content/1–3), one replicate, 6 sessions, none failed, $0.56. In 6/6, D invoked
`classify-panels` once, **before any check**, then all three checks in the
listed order; no skill outside the closure; every answer valid against its
contract. Output tokens 3,672–6,304 (CM) and 3,643–8,235 (PM). The notebook ran
end to end on these sessions beside exp-04's references.

**Known before the run, from exp-04's traces** (counted while writing the
notebook): in exp-04's PM `A|B ← C_i ← D`, D invoked `classify-panels` before
any check in **148 of 190** sessions; under CM, in none. Under PM, the designed
order of exp-05 was already the commonest behaviour of its reference, which
narrows what PM's comparison can show.

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|
| 2026-10-07 | smoke, both shapes | `run.py --smoke` | $0.56 | `experiments/runs/exp-05-shared-step-first/smoke/` (not committed) |
| 2026-10-07 | CM, PM, sanity | `python experiments/exp-05-shared-step-first/run.py` | $35.48 | `experiments/runs/exp-05-shared-step-first/` |

## Findings

Run 2026-10-07 00:19–05:30 under closure assembly: 418 sessions, **none
failed**, $35.48. Analysis in `notebooks/experiments/exp-05-shared-step-first.ipynb`,
against `gold-v4`, beside exp-04's CM and PM `A|B ← C_i ← D`.

### Numbers

**Endpoint 0 — dispatch.**

| | all three checks | only `micrograph-scale-bar` (+ one after two) | no check | `classify-panels` first |
|---|---|---|---|---|
| CM exp-05 | **166/190** | 19 (+1) | 4 | 190/190 |
| PM exp-05 | **180/190** | 4 | 6 | 190/190 |
| CM exp-04 | 190/190 | 0 | 0 | 0/190 |
| PM exp-04 | 181/190 | 1 (+1) | 7 | 148/190 |

D did the shared step first in every exp-05 session, once, as designed; no
skill outside the closure. But it stopped before the last check more often than
either reference — **CM in 24 sessions against none in exp-04** — most often
after the first check.

**Non-response.** **CM exp-05: 10 sessions** invoked `classify-panels` and
`micrograph-scale-bar` only, answered that check, and returned **empty lists**
for `individual-data-points` and `error-bars-defined`; 9 more stopped at the
same point and filled the other two checks without invoking them. **PM exp-05:
2 sessions** answered `outputs: []`, short answers of 391 and 480 output tokens.
exp-04's references had no empty answer in 380 sessions.

**Hypothesis 1 — non-inferiority**, exp-05 − exp-04 of the same shape:

| | layer S (δ 0.0125) | layer 1 (δ 0.02) | layer 2 (δ 0.02) | stops at |
|---|---|---|---|---|
| CM `micrograph-scale-bar` | non-inferior, +0.000 [0.000, 0.000] | non-inferior | inconclusive | layer 2 |
| CM `individual-data-points` | **degraded**, −0.053 [−0.089, −0.021] | inconclusive, −0.043 | inconclusive | **layer S** |
| CM `error-bars-defined` | **degraded**, −0.053 [−0.089, −0.021] | inconclusive, −0.036 | inconclusive | **layer S** |
| PM, each check | inconclusive, −0.010 [−0.026, 0.001] | non-inferior (`micrograph-scale-bar`) / inconclusive | non-inferior / inconclusive | layer S |

The CM degradation is the 10 empty lists: an empty list scores as every row
missing, and `micrograph-scale-bar`, invoked in every session, is untouched.
PM's layer S is inconclusive by its 2 empty answers. **At layer 2 no property
degraded in either shape**; the largest negative point estimate is CM
`error-bars-defined · from_the_caption`, −0.011 [−0.022, 0.001].

Layer S counting both errors, `correct / (correct + missing + spurious)`:

| | `micrograph-scale-bar` | `individual-data-points` | `error-bars-defined` |
|---|---|---|---|
| CM exp-05 | 0.994 | 0.941 | 0.941 |
| PM exp-05 | 0.984 | 0.984 | 0.984 |
| CM exp-04 | 0.997 | 0.997 | 0.997 |
| PM exp-04 | 0.996 | 0.996 | 0.996 |

Spurious panels per figure, reported: CM 8 (exp-04: 3), PM 7 (exp-04: 5).

**Hypothesis 2 — PM output tokens: fewer.** Per figure, exp-05 ÷ exp-04,
**0.874 [0.837, 0.910]**. Reported beside it, per figure, exp-05 ÷ exp-04:

| | output tokens | cost | input tokens | turns | time |
|---|---|---|---|---|---|
| PM | **0.87** [0.84, 0.91] | 0.95 [0.92, 0.98] | 1.25 [1.20, 1.31] | 1.01 | 0.87 |
| CM | 0.92 [0.86, 0.98] | 0.97 [0.93, 1.01] | 1.16 [1.10, 1.21] | 1.00 | 0.92 |

**The sanity rerun** of exp-04's PM `A|B ← C_i ← D`, one replicate: output
tokens 0.99 [0.90, 1.07] of exp-04's; costs and time within 3%. But **one empty
answer in 38** (589 output tokens), where exp-04's 190 sessions of the same
condition had none, and so layer S 0.974 against 0.999.

### Reading

*Interpretation, separable from the numbers above.*

**The shared step first works as designed and saves output, and it costs
dispatch.** D classified once, first, in every session; PM wrote 13% fewer
output tokens and CM 8% fewer. But D stopped before the last check far more
often than in the arrangement where the checks reach the shared step
themselves, and under CM it left two checks' lists empty in 10 sessions. The
checks that ran judged as well as before — nothing degraded at layer 2 — so the
loss is in **dispatch, not in the checks**.

**Why CM stopped after the first check, and PM much less, is not explained.**
The arrangements are identical but for the contract, and nothing obvious in the
check-major schema invites stopping. The observation stands without a
mechanism.

**Empty answers may be partly model-side.** The sanity rerun of a condition
that answered every time in exp-04 gave one short empty answer in 38, like
exp-05's two PM ones. One session is no proof, and it is not investigated
further; but the PM empties should not be read as caused by the arrangement
alone. The CM pattern — stop after the first check, empty lists for the rest —
appears only under the new arrangement.

**What it settles**: `[A|B, {C_i}] ← D` is not used further; the topology the
model drifted towards in exp-04 is worse when imposed. Across exp-04 and
exp-05, **CM `A|B ← C_i ← D` is the configuration to keep**: the most accurate
at layer S counting both errors (0.997), all three checks dispatched in 190/190,
no empty answer — at about 9% more output tokens than exp-05's CM. **What it
does not**: why the imposed order breaks dispatch, and whether an explicit
instruction in D to invoke every check would recover it.

## Threats to validity

- **References from another run**, a day earlier, with the same model pinned
  by name; the sanity rerun looks at one of them, once.
- **Wording moves with the arrangement.** D v2 says more than D v1, and the
  checks at v4 say less than v3; the comparison is of arrangements as written,
  not of call order alone.
- **The named risk**: a D that classifies may answer without dispatching.
- **Hypothesis 2 has one explanation in mind** (transposition) and does not
  test it: fewer output tokens would be consistent with it, not proof of it.
- **PM's reference already did the shared step first** in 148 of 190
  sessions (see *Preparation*), so PM's contrast is partly between the
  designed order and the same order reached unprompted.
- **Order is fixed**, as in exp-03 and exp-04.

## Gold this was scored against

**`gold-v4`**, as exp-04.

## Status and next

Done. CM `A|B ← C_i ← D` (exp-04, `fig-checklist-exp04`, the checks at v3) is
the series' configuration going forward.
