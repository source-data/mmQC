---
title: exp-09 — the panels inline, A|B|C_i ← D, against the shared skill
date: 2026-10-22
status: done           # draft | planned | running | done | abandoned
kind: experiment
extends: exp-08
tags: [experiment, skills, dag, arrangements, sonnet, non-inferiority]
---

# exp-09 — the panels inline, A|B|C_i ← D, against the shared skill

*A non-inferiority test, committed before the run.*

## Question

On exp-07's configuration — `fig-checklist`'s eleven checks, Sonnet 5.5,
`gold-v6` — is the production arrangement, `A|B ← C_i ← D`, in which every
check invokes one shared skill to list and classify the panels, **not worse**
than `A|B|C_i ← D`, in which every check does that itself?

## Why

exp-08 compared production with the deeper `A ← B ← C_i ← D` and found
production ahead, on dispatch. The other neighbour, with no shared skill at
all, was last measured in exp-04 — three checks, Sonnet 5 and the gold of the
time — where it came last on layer S (0.979, against 0.997). With eleven
checks the trade-off may differ: each inline check carries the panel
instructions again, eleven times in one session, but there is one hop less
for the agent to take or skip. If production is not worse, the shared skill
earns its place by sharing alone; if it is, the hierarchy costs accuracy.

## Design

| | |
|---|---|
| Model, provider | `claude-sonnet-5-5`, `claude-sdk` 0.2.165 (CLI 2.1.294) |
| Gold | `gold-v6` |
| Figures | exp-07's 37 |
| Concurrency | 50, as exp-07 and exp-08 |

### Three arrangements

| arrangement | arm | source | replicates |
|---|---|---|---|
| **`A\|B\|C_i ← D`** | `inline` | **run here**: `fig-checklist-exp09` | 5 |
| **`A\|B ← C_i ← D`** | exp-07's Sonnet 5.5 run | reused (2026-10-12), subject to the drift check | 5 |
| `A ← B ← C_i ← D` | exp-08's run | reused (2026-10-12), reported beside, not tested | 5 |
| `A\|B ← C_i ← D`, again | `drift` | **run here**: `fig-checklist-exp07` | 2 |

**The inline checks.** Each is its exp-07 version with one change: the
paragraph that invoked `classify-panels` — "Before you do anything else,
invoke the `classify-panels` skill with the `Skill` tool to list every panel
and classify it by content type" — becomes "Before you do anything else, list
every panel and classify it by content type, as follows. Proceed step-by-step
and be accurate", followed by `classify-panels` v1's five sections verbatim,
as sub-sections; "the calling skill" becomes "this check", and `requires`
is empty. Drafted on `micrograph-scale-bar` and reviewed with the author
(2026-10-22), then applied to the other ten. They sit in `fig-checklist-exp07`
as each check's next version, unpinned, and are pinned in
`fig-checklist-exp09`, a copy of `-exp07` that differs only in those pins. The
entry point, its contract and the gold are exp-07's.

### The drift check

Ten days separate exp-07 and exp-08 (2026-10-12) from this run. The SDK and
CLI are pinned, but the model behind the name may have moved. The `drift`
arm reruns `A|B ← C_i ← D` exactly as exp-07 ran it, on the same day as the
`inline` arm, and is compared with exp-07's arm on E1 and E2 (and the eleven
decisions):

- **no drift** — E1 and E2 equivalent (intervals within ±0.02) and no
  decision better or worse: the hypothesis is tested against exp-07's five
  replicates, and the drift arm is reported;
- **drift** — anything else: reported to the author, who decides whether to
  take the drift arm to five replicates (`run.py --extend-drift`); the
  hypothesis is then tested against it, same-day only, and exp-08's deeper
  arm is reported with that caveat.

## What is measured

As exp-07 and exp-08, per arrangement: dispatch first — all eleven checks,
partial, none; `classify-panels` invocations (none by design in `inline`) —
failures, fallback, layer S and panels across the eleven lists, layer 1,
layer 2 per property, each check's decision, cost and time.

## The hypothesis

**`A|B ← C_i ← D` is non-inferior to `A|B|C_i ← D`.** For E1 (layer S, both
errors, pooled over the checks) and E2 (layer 1, pooled): the paired
difference over figures, `A|B ← C_i ← D` minus `A|B|C_i ← D`, has a 95%
bootstrap interval whose lower bound is above **−0.02**.

- Both hold: non-inferior.
- Either lower bound at or below −0.02 while the interval includes 0:
  inconclusive.
- Either interval wholly below 0 and reaching past −0.02: inferior.

**Secondary**: E3, each check's decision, classified the same way — reported,
not part of the verdict. Also reported: whether `A|B|C_i ← D` is better or
equivalent on each endpoint, by exp-07's rule.

## Threats to validity

- **Reused arms**, if the drift check passes: anything that moved without
  showing in two replicates is confounded with the arrangement.
- **One model**, and the skills were written on Sonnet.
- **The inline text is longer**: eleven copies of the panel instructions in
  the session context. That is the arrangement, not a confound, but it means
  cost and context size differ with it.
- **37 figures**, and many intervals.

## Preparation

| # | step | done |
|---|---|---|
| P1 | The eleven inline checks in `fig-checklist-exp07`, unpinned; `fig-checklist-exp09` pinning them | this commit |
| P2 | `experiments/exp-09-inline-panels/run.py`: `inline` 5 replicates, `drift` 2, `--extend-drift` | this commit |
| P3 | Smoke test: `inline` on 3 figures, one replicate | below |
| P4 | Notebook `notebooks/experiments/exp-09-inline-panels.ipynb`: exp-08's, four conditions (each a run root, arm and checklist), the drift check, the non-inferiority verdict, the arrangements side by side; run on the smoke output during the run | this commit |

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|
| 2026-10-22 | smoke, `inline` | `run.py --smoke` | $0.76 | `experiments/runs/exp-09-inline-panels/smoke/` (not committed) |
| 2026-10-22 | `inline` 5 replicates, `drift` 2 | `caffeinate -i python experiments/exp-09-inline-panels/run.py` | $50.50 ($38.29 + $12.21) | `experiments/runs/exp-09-inline-panels/`; 259 of 259 answered |

**Smoke test, 2026-10-22.** `s44318-026-00715-1` content/1–3, one replicate,
3 sessions, none failed, Sonnet 5.5 throughout: all eleven checks in 3 of 3,
in order, no skill outside the closure and `classify-panels` never invoked —
it is not assembled; 26 turns, $0.21–0.29 per session, above exp-07's
$0.16 for `A|B ← C_i ← D`.

## Findings

Run 2026-10-22: 259 sessions, none failed, no fallback, no refusal. Analysis
in `notebooks/experiments/exp-09-inline-panels.ipynb`, against `gold-v6`.

### The drift check

The `drift` arm (2 replicates, 2026-10-22) against exp-07's (5 replicates,
2026-10-12):

| | drift − exp-07 | verdict |
|---|---|---|
| E1 layer S | −0.003 [−0.008, 0.000] | equivalent |
| E2 layer 1 | −0.003 [−0.007, +0.002] | equivalent |
| `panel-image-matches-caption` decision | −0.013 [−0.026, −0.003] | exp-07 better |
| the other ten decisions | | 5 equivalent, 5 undecided |

All eleven checks in 63 of 74 drift sessions (85%), against 168 of 185 (91%).
**The rule fired** on one decision, and was put to the author, who decided not
to extend the drift arm (2026-10-22): one interval in thirteen excluding zero
is within chance, and the verdict below holds against either arm. The
hypothesis is tested against exp-07's arm, as planned for no drift; the test
against the drift arm is reported beside it.

### Numbers

**Dispatch.**

| | all eleven checks | partial | `classify-panels` invoked |
|---|---|---|---|
| **`A\|B\|C_i ← D`** | **181/185 (98%)** | 4, each after 2 checks | — (not assembled) |
| `A\|B ← C_i ← D` (exp-07) | 168/185 (91%) | 17, 14 after the first check | 95/185 |
| `A ← B ← C_i ← D` (exp-08) | 126/185 (68%) | 57, all after the first check (and 2 with none) | 115/185 |

**The hypothesis**, `A|B ← C_i ← D` minus `A|B|C_i ← D`:

| production arm | E1 layer S | E2 layer 1 | verdict |
|---|---|---|---|
| exp-07's (as planned) | +0.002 [0.000, +0.005] | −0.000 [−0.004, +0.003] | **non-inferior** |
| `drift`, 2 replicates | −0.001 [−0.003, 0.000] | −0.003 [−0.006, −0.000] | **non-inferior** |

Means: E1 0.997 against 0.995, E2 0.981 against 0.982. Secondary, the eleven
decisions: **non-inferior on nine**; inconclusive on `micrograph-scale-bar`
(−0.010 [−0.030, 0.000]) and `stat-significance-level` (−0.007 [−0.022,
+0.003]).

**The three arrangements**, E1 and E2 overall and on the sessions that
invoked all eleven checks:

| | E1 | E2 | E1, complete | E2, complete |
|---|---|---|---|---|
| `A\|B\|C_i ← D` | 0.995 | 0.982 | 0.995 | 0.983 |
| `A\|B ← C_i ← D` | 0.997 | 0.981 | 0.997 | 0.984 |
| `A ← B ← C_i ← D` | 0.977 | 0.970 | 0.999 | 0.984 |

**Cost and size per figure**: `A|B|C_i ← D` $0.207, `A|B ← C_i ← D` $0.157,
`A ← B ← C_i ← D` $0.149; input tokens 156,000, 84,000 and 101,000; output
tokens about 9,500 in each; 26, 25 and 21 turns.

### Reading

*Interpretation, separable from the numbers above.*

**The shared skill costs nothing in accuracy.** `A|B ← C_i ← D` is
non-inferior to every check doing its own panels, on the panels found and on
applicability, against both its earlier arm and today's; on the sessions that
run every check, the three arrangements are level. What the checks judge does
not depend on where the panel inventory is made.

**What the arrangement changes is dispatch and cost.** With the panels inline
the agent almost always runs all eleven checks (98%, against 91% and 68%):
the stop after the first check — the hop to `classify-panels` being where the
session stops — nearly disappears when there is no hop. In exchange each
session carries the panel instructions eleven times, nearly twice the input,
and costs a third more. Here the accuracy is the same, so production keeps
`A|B ← C_i ← D`; but the inline arrangement's dispatch is the clearest lead yet
on the open problem, partial dispatch.

## Gold this is scored against

**`gold-v6`**.

## Status and next

Run and analysed, 2026-10-22. `A|B ← C_i ← D` is non-inferior and stays
production. Next, for the author: whether partial dispatch is attacked with
what the inline arrangement suggests — fewer hops between the entry point and
a check's first step — and the error analysis on the decisions.
