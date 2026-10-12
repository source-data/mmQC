---
title: exp-08 — the two arrangements again, on exp-07's configuration
date: 2026-10-12
status: done           # draft | planned | running | done | abandoned
kind: experiment
extends: exp-07
tags: [experiment, skills, dag, arrangements, sonnet]
---

# exp-08 — the two arrangements again, on exp-07's configuration

*A comparison with exp-07's rule: for each primary endpoint, better,
equivalent or undecided. The note is committed before the run.*

## Question

On exp-07's configuration — `fig-checklist-exp07`, Sonnet 5.5, `gold-v6` — is
check-major `A|B ← C_i ← D` still ahead of the deeper `A ← B ← C_i ← D`, in
which the panel inventory comes from its own skill?

## Why

exp-04 (three checks) and exp-06 (eleven) found `A|B ← C_i ← D` ahead of
`A ← B ← C_i ← D` on dispatch, layer S and layer 1, with Sonnet 5 and the
gold of the time. Since then the model, the gold, `individual-data-points`
and the wording of every skill call have changed. Before the series concludes
on `A|B ← C_i ← D`, the comparison is repeated on the configuration it now
stands on.

## Design

| | |
|---|---|
| Checklist | `fig-checklist-exp07` |
| Model, provider | `claude-sonnet-5-5`, `claude-sdk` 0.2.165 (CLI 2.1.294) |
| Gold | `gold-v6` |
| Figures | exp-07's 37 |
| Replicates | 5 |
| Concurrency | 50 |
| Sessions | **185** new; the other arm's 185 are exp-07's |

### Two arrangements

| arrangement | arm | each check |
|---|---|---|
| **`A\|B ← C_i ← D`** | **exp-07's Sonnet 5.5 run, reused** (`experiments/runs/exp-07-models/claude-sonnet-5-5/pinned/`) | invokes `classify-panels` v1, which lists and classifies the panels |
| **`A ← B ← C_i ← D`** | `classify-panels@v3`, run here | invokes `classify-panels` v3, which invokes `identify-panels` v1 **with the `Skill` tool** to list the panels, then classifies them |

`classify-panels` v3 is v2 with one change, the one every other skill call
got in exp-07: "invoke the `identify-panels` skill **with the `Skill`
tool**". It is not pinned, so exp-07's sessions are unchanged by it.

**Reusing exp-07's arm** is sound only while nothing else differs: same
checklist pins, SDK and CLI, runtime `CLAUDE.md`, gold and concurrency. The
run is made the same day, 2026-10-12, with nothing changed in between but
`classify-panels` v3.

## What is measured

As exp-07, per arrangement: dispatch first — all eleven checks, partial, none;
`classify-panels` and `identify-panels` invocations per session — failures,
fallback, layer S and panels across the eleven lists, layer 1, layer 2 per
property, each check's decision, cost and time.

## The comparison

exp-07's primary endpoints — E1 layer S (both errors, pooled over the
checks), E2 layer 1 (pooled), E3 the eleven decisions — as paired differences
over figures, `A ← B ← C_i ← D` minus `A|B ← C_i ← D`, with 95% bootstrap
intervals: **better** if the interval excludes 0, **equivalent** if it lies
within ±0.02, **undecided** if neither. Five replicates from the start; no
extension.

## Threats to validity

- **One arm is reused**, run some hours earlier: anything that changed on the
  provider's side in between is confounded with the arrangement.
- **One model**: what holds for Sonnet 5.5 need not hold for the others.
- **37 figures**, and the many-intervals caveat of exp-07.

## Preparation

| # | step | done |
|---|---|---|
| P1 | `classify-panels` v3 in `fig-checklist-exp07`, not pinned | this commit |
| P2 | `experiments/exp-08-arrangements-sonnet/run.py` | this commit |
| P3 | Smoke test: 3 figures, one replicate | below |
| P4 | Notebook `notebooks/experiments/exp-08-arrangements-sonnet.ipynb`: exp-07's, two arrangements, each a run root and an arm; run on the smoke output during the run | this commit |

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|
| 2026-10-12 | smoke, `A ← B ← C_i ← D` | `run.py --smoke` | $0.59 | `experiments/runs/exp-08-arrangements-sonnet/smoke/` (not committed) |
| 2026-10-12 | `A ← B ← C_i ← D`, 5 replicates | `caffeinate -i python experiments/exp-08-arrangements-sonnet/run.py` | $27.62 | `experiments/runs/exp-08-arrangements-sonnet/classify-panels@v3/`; 185 of 185 answered |

**Smoke test, 2026-10-12.** `s44318-026-00715-1` content/1–3, one replicate,
3 sessions, none failed, Sonnet 5.5 throughout, every one assembled with
`classify-panels` v3 and `identify-panels` v1.

- `identify-panels` invoked in 1 of 3 sessions (content/1); in the other two
  `classify-panels` listed the panels itself, as exp-06 saw Sonnet 5 do in 55
  of 185 sessions.
- All eleven checks in 2 of 3; content/3 invoked `micrograph-scale-bar` only
  and answered the rest in 8 turns — exp-07's partial dispatch.
- 28–30 turns and $0.19–0.27 for the full sessions.

## Findings

Run 2026-10-12, the same day as exp-07's Sonnet 5.5 arm, which it is set
beside; 185 new sessions, none failed, no fallback, no refusal. Analysis in
`notebooks/experiments/exp-08-arrangements-sonnet.ipynb`, against `gold-v6`.

### Numbers

**Dispatch.**

| | all eleven checks | partial (all: only the first check) | no check | `classify-panels` invoked | `identify-panels` invoked |
|---|---|---|---|---|---|
| `A\|B ← C_i ← D` | 168/185 | 17 (14) | 0 | 95/185 | — |
| `A ← B ← C_i ← D` | **126/185** | **57 (57)** | 2 | 115/185 | **27/185** |

In `A ← B ← C_i ← D`, `classify-panels` v3 reached `identify-panels` in 27
sessions; in the others it listed the panels itself. Panels missing from some
check lists but not others: 0 against 142 — the partial sessions' lists.

**Primary endpoints**, `A ← B ← C_i ← D` minus `A|B ← C_i ← D`:

| | `A\|B ← C_i ← D` | `A ← B ← C_i ← D` | difference [95%] | verdict |
|---|---|---|---|---|
| E1 layer S | 0.997 | 0.977 | −0.020 [−0.037, −0.005] | **`A\|B ← C_i ← D` better** |
| E2 layer 1 | 0.981 | 0.970 | −0.011 [−0.021, −0.002] | **`A\|B ← C_i ← D` better** |
| E1, complete sessions only | 0.997 | 0.999 | | |
| E2, complete sessions only | 0.984 | 0.984 | | |
| E3, eleven decisions | | | all within ±0.01 | **9 equivalent**, 2 undecided (`individual-data-points`, `replication-reporting`) |

**Cost and time per figure**: $0.149 against $0.157; 21 turns against 25;
54 s against 60 s — the partial sessions are short.

### Reading

*Interpretation, separable from the numbers above.*

**`A|B ← C_i ← D` stays the baseline, for the same reason as before:
dispatch.** On the sessions that ran all eleven checks the two arrangements
are level — layer S 0.999 against 0.997, layer 1 0.984 both — and nine of
eleven decisions are equivalent. But the deeper arrangement stops after the
first check in nearly a third of its sessions (57 of 185, against 14), and
that is what lowers its layer S and layer 1. A shared step two levels down
makes the session more likely to treat the first check as the whole job.

**The panel inventory skill is rarely used even when it is there.** Named
with the `Skill` tool, `identify-panels` was invoked in 27 of 185 sessions;
`classify-panels` lists the panels itself the rest of the time, as it does in
`A|B ← C_i ← D` when it is invoked at all (95 of 185). Splitting the
inventory into its own skill does not, with Sonnet 5.5, make the inventory a
separate step.

## Gold this is scored against

**`gold-v6`**.

## Status and next

Run and analysed, 2026-10-12. The series' configuration stands:
`A|B ← C_i ← D`, Sonnet 5.5. Partial dispatch is the open problem in both
arrangements.
