---
title: exp-09 — the panels inline, A|B|C_i ← D, against the shared skill
date: 2026-10-22
status: planned        # draft | planned | running | done | abandoned
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

**Smoke test, 2026-10-22.** `s44318-026-00715-1` content/1–3, one replicate,
3 sessions, none failed, Sonnet 5.5 throughout: all eleven checks in 3 of 3,
in order, no skill outside the closure and `classify-panels` never invoked —
it is not assembled; 26 turns, $0.21–0.29 per session, above exp-07's
$0.16 for `A|B ← C_i ← D`.

## Gold this is scored against

**`gold-v6`**.

## Status and next

Planned 2026-10-22. Next: P3, then the run.
