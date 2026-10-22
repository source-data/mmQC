---
title: exp-10 — check-major against panel-major, revisited on eleven checks
date: 2026-10-22
status: done           # draft | planned | running | done | abandoned
kind: experiment
extends: exp-04
tags: [experiment, contracts, check-major, panel-major, sonnet, non-inferiority]
---

# exp-10 — check-major against panel-major, revisited on eleven checks

*A non-inferiority test, committed before the run.*

## Question

On the configuration the series settled on — `A|B ← C_i ← D`, the eleven
checks of `fig-checklist`, Sonnet 5.5 — is the **check-major** answer
(`{<check>: [rows]}`, what production returns) **not worse** than the
**panel-major** one (`{"outputs": [{panel_label, panel_classes, <check>:
{…}}]}`), which states each panel once?

## Why

exp-04 (2026-10-05) chose check-major on three checks, Sonnet 5 and `gold-v4`.
Panel-major was no less accurate there, but:

- **it changed how the skills were called**: asked for `panel_classes`, the
  entry point took on the panel classification itself, and in 33 of 570
  sessions answered every check without invoking any (against 2 of 570
  check-major);
- **it cost more**: about 1,670 more output tokens per session, 20–25% more;
- **it did not reduce spurious panels**, the gain it was proposed for.

Since then the series has moved under that choice: eleven checks in one
session, every skill call naming the `Skill` tool (exp-07), which cut the
no-check failure, Sonnet 5.5, and the gold through `gold-v7`. exp-07 to exp-09
all ran check-major. Whether the reasons hold on the configuration they now
serve is worth knowing before the contract shape is taken as settled.

## Design

| | |
|---|---|
| Checklist | **`fig-checklist-exp10`**: `fig-checklist-exp07`'s pins (exp-07's skills, `A\|B ← C_i ← D`), plus a second entry point |
| Entry points | `do-fig-checklist-cm` v2 and **`do-fig-checklist-pm` v1** — the same text, but for its name (the builder refuses otherwise) |
| Contracts | derived, never authored (`experiments/exp-10-panel-major-revisited/build_contract.py`): check-major is exp-06's derivation; panel-major is exp-04's shape for eleven checks, `panel_label` once per panel, `panel_classes` asked for and unscored (decided with the author, as in exp-04), each check's row fields under its name, `plot-axis-units`' per-axis lists keeping their alignment |
| Verification | both contracts score every check as its own contract does, on answers made from the gold; the builder refuses otherwise |
| Model, provider | `claude-sonnet-5-5`, `claude-sdk` 0.2.165 (CLI 2.1.294) |
| Gold | **`gold-v7`**: `gold-v6` with `embor.2009.233` Fig. 2's panel C one panel in every check (below), and both merged golds |
| Figures | exp-07's 37 |
| Replicates | 5 per shape, **both run the same day** (decided with the author: no reused arm, no drift check) |
| Concurrency | 50 |
| Sessions | 2 × 37 × 5 = **370** |

### The gold change, `gold-v7`

A panel-major gold needs every check to name the same panels. One figure did
not: `embor.2009.233` Fig. 2, where `plot-axis-units` split the single
label C — over two unlabelled plots — into "C top" and "C bottom", and the
other ten checks did not. Decided with the author (2026-10-22): **only
sub-parts the figure labels are split** (as `s44321-025-00219-1` Fig. 1's Ai
and Aii); an unlabelled composite is one panel — `classify-panels`' own rule,
and what all three models answered in exp-07. `plot-axis-units`' two rows are
merged into one C, keeping the 3-D chart's axes, the only axis with a unit.
Recorded in `experiments/curation/plot-axis-units-2026-10-22.md`.

## What is measured

As exp-07 to exp-09, per shape: **dispatch first** — all eleven checks,
partial, none; `classify-panels` invocations per session, and whether the
entry point classifies the panels itself (exp-04's mechanism) — failures,
fallback, layer S, layer 1, layer 2 per property, each check's decision;
**spurious, missing and partly missing panels** per figure (exp-04's
`panels.py`: partly missing exists only check-major); **output tokens**, cost,
turns and time.

## The hypothesis

**Check-major is non-inferior to panel-major** (decided with the author: the
series has run check-major since exp-04, and this tests that it lost nothing
by it). For E1 (layer S, both errors, pooled over the checks) and E2 (layer
1, pooled): the paired difference over figures, **check-major minus
panel-major**, has a 95% bootstrap interval whose lower bound is above
**−0.02**.

- Both hold: non-inferior. Either lower bound at or below −0.02 with the
  interval including 0: inconclusive. Either interval wholly below 0 and past
  −0.02: inferior.
- **Secondary**, reported, not in the verdict: E3, the eleven decisions,
  classified the same way; panel-major against check-major by exp-07's rule
  (better, equivalent, undecided); spurious panels per figure; dispatch;
  output tokens and cost.

Layer S is read per check in both shapes: a panel-major row is one panel
for every check, so a spurious panel there counts once per check, as a
check-major one does in each list it appears in.

## Threats to validity

- **`panel_classes`** asks the panel-major answer for something the
  check-major one is not asked: kept, as in exp-04, because it is part of
  that shape as designed — and the mechanism exp-04 found runs through it.
- **One model**; the skills were written for, and tuned on, check-major
  answers since exp-04.
- **37 figures**, and many intervals.
- **The same prose** for two shapes: the shape is stated by the contract
  alone. That isolates it, and is also what exp-04 did.

## Preparation

| # | step | done |
|---|---|---|
| P1 | `gold-v7`: panel C merged; the check-major merged gold rebuilt | this commit |
| P2 | `fig-checklist-exp10`: exp-07's pins and `do-fig-checklist-pm` v1 | this commit |
| P3 | `build_contract.py`: both contracts, verified (6,919 scorings check-major, 2,442 panel-major, identical to each check's own); panel-major gold. It found a scorer bug: a list inside an object of a row (`outputs[].plot-axis-units.units_provided[]`) was never read; fixed in `core/evaluation.py`, with a test, affecting no earlier run | this commit |
| P4 | `run.py`: both shapes, 5 replicates, concurrency 50 | this commit |
| P5 | Smoke test: both shapes on 3 figures, one replicate | below |
| P6 | Notebook `notebooks/experiments/exp-10-panel-major-revisited.ipynb`: exp-09's, two shapes, a panel-major answer read per check (the panel row once for every check), `classify-panels` before the first check, spurious panels per figure; run on the smoke output during the run | this commit |

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|
| 2026-10-22 | smoke, both shapes | `run.py --smoke` | $1.25 | `experiments/runs/exp-10-panel-major-revisited/smoke/` (not committed) |
| 2026-10-22 | both shapes, 5 replicates | `caffeinate -i python experiments/exp-10-panel-major-revisited/run.py` | $58.31 ($29.72 + $28.59) | `experiments/runs/exp-10-panel-major-revisited/`; 370 of 370 answered |

**Smoke test, 2026-10-22.** `s44318-026-00715-1` content/1–3, one replicate
per shape, 6 sessions, none failed: all eleven checks in 6 of 6, every answer
in its shape. Check-major invoked `classify-panels` once per session;
**panel-major never** — the panels classified in the answer, where exp-04 saw
the entry point invoke it more often under panel-major. 28 against 26 turns;
$0.21–0.25 against $0.17–0.25; output tokens 9,800–16,200 against
9,600–17,300.

## Findings

Run 2026-10-22, both shapes the same day: 370 sessions, none failed, no
fallback, no refusal, no empty answer. Analysis in
`notebooks/experiments/exp-10-panel-major-revisited.ipynb`, against `gold-v7`.

### Numbers

**Dispatch.**

| | all eleven checks | partial | no check | `classify-panels` invoked | before the first check |
|---|---|---|---|---|---|
| check-major | 159/185 (86%) | 25: 23 after the first check, 2 after 4–5 | 1 | 129/185 | 0 |
| panel-major | **167/185 (90%)** | 16: 8 after the first check, 7 after 5, 1 after 3 | 2 | 106/185 | **2** |

**The hypothesis**, check-major minus panel-major:

| | check-major | panel-major | difference [95%] | verdict |
|---|---|---|---|---|
| E1 layer S | 0.994 | 0.996 | −0.002 [−0.012, +0.009] | **non-inferior** |
| E2 layer 1 | 0.981 | 0.983 | −0.002 [−0.006, +0.003] | **non-inferior** |
| E1, complete sessions | 0.998 | 1.000 | | |
| E2, complete sessions | 0.985 | 0.985 | | |

By exp-07's rule E1 and E2 are also **equivalent**. Secondary, the eleven
decisions: non-inferior on eight; inconclusive on `micrograph-scale-bar`
(−0.012 [−0.037, 0.000]) and `single-channel-for-overlay` (−0.015 [−0.046,
0.000], 13 figures); **inferior on `individual-data-points`**: 0.947 against
0.974, −0.027 [−0.052, −0.007]. Check-major's largest leads, intervals
including 0: `plot-axis-units` +0.020, `replication-reporting` +0.015.

**Panels per figure**: spurious 0.011 [0.000, 0.032] against 0.005 [0.000,
0.016] (2 and 1 in 185 sessions); missing 1 and 2; partly missing — named in
some check lists, not others — 26 check-major, none possible panel-major.

**Cost and size per figure**: $0.161 against $0.155; output tokens 9,430
against 9,640; input tokens 113,000 against 65,000; 25 and 26 turns; 55 s and
53 s.

### Reading

*Interpretation, separable from the numbers above.*

**The hypothesis holds: the series lost nothing by running check-major.** On
the panels and on applicability the shapes are equivalent, overall and on the
sessions that ran every check.

**But exp-04's reasons for check-major are gone.** With every skill call
naming the `Skill` tool, the panel-major entry point no longer takes on the
classification: `classify-panels` came before the first check in 2 sessions
in 185, and no session classified the panels and then skipped every check —
where exp-04 found the panel-major entry point taking on the shared step
(`classify-panels` reached in 95–97% of sessions) and, in 20 sessions,
answering every check without invoking one. It no longer writes more: output
tokens are level and cost is 4% lower, where exp-04 measured 20–25% more. And
it now dispatches slightly *better* (90% against 86%), with fewer stops after
the first check (8 against 23).

**Where the shapes differ, panel-major is ahead on one decision.**
`individual-data-points` is the one endpoint with an interval wholly on one
side, in panel-major's favour; the others are level or undecided, two leaning
each way. One interval in thirteen is within what chance gives.

**What it leaves open**: the choice between the shapes no longer rests on
accuracy, dispatch or cost — they are level, or near enough. It rests on what
production needs from the answer: check-major hands each check its own list,
as the checks produce it and as the curation and scoring of single checks
expect; panel-major states each panel once, so the eleven lists cannot
disagree about which panels exist (26 partly missing panels check-major,
none panel-major). For the author.

## Gold this is scored against

**`gold-v7`**.

## Status and next

Run and analysed, 2026-10-22. Check-major is non-inferior to panel-major and
stays production; panel-major no longer has the drawbacks exp-04 found. Next,
for the author: whether that changes the production shape.
