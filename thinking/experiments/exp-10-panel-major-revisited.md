---
title: exp-10 — check-major against panel-major, revisited on eleven checks
date: 2026-10-22
status: planned        # draft | planned | running | done | abandoned
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
| P6 | Notebook: exp-09's, two shapes, plus spurious panels and output tokens | |

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|
| 2026-10-22 | smoke, both shapes | `run.py --smoke` | $1.25 | `experiments/runs/exp-10-panel-major-revisited/smoke/` (not committed) |

**Smoke test, 2026-10-22.** `s44318-026-00715-1` content/1–3, one replicate
per shape, 6 sessions, none failed: all eleven checks in 6 of 6, every answer
in its shape. Check-major invoked `classify-panels` once per session;
**panel-major never** — the panels classified in the answer, where exp-04 saw
the entry point invoke it more often under panel-major. 28 against 26 turns;
$0.21–0.25 against $0.17–0.25; output tokens 9,800–16,200 against
9,600–17,300.

## Gold this is scored against

**`gold-v7`**.

## Status and next

Planned 2026-10-22. Next: P1 to P5, then the run.
