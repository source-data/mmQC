---
title: exp-08 — the two arrangements again, on exp-07's configuration
date: 2026-10-12
status: planned        # draft | planned | running | done | abandoned
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
| P4 | Notebook: exp-07's, two arrangements | |

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|
| 2026-10-12 | smoke, `A ← B ← C_i ← D` | `run.py --smoke` | $0.59 | `experiments/runs/exp-08-arrangements-sonnet/smoke/` (not committed) |

**Smoke test, 2026-10-12.** `s44318-026-00715-1` content/1–3, one replicate,
3 sessions, none failed, Sonnet 5.5 throughout, every one assembled with
`classify-panels` v3 and `identify-panels` v1.

- `identify-panels` invoked in 1 of 3 sessions (content/1); in the other two
  `classify-panels` listed the panels itself, as exp-06 saw Sonnet 5 do in 55
  of 185 sessions.
- All eleven checks in 2 of 3; content/3 invoked `micrograph-scale-bar` only
  and answered the rest in 8 turns — exp-07's partial dispatch.
- 28–30 turns and $0.19–0.27 for the full sessions.

## Gold this is scored against

**`gold-v6`**.

## Status and next

Planned 2026-10-12. Next: P3, the run, the notebook.
