---
title: exp-07 — three models on the full checklist
date: 2026-10-12
status: planned        # draft | planned | running | done | abandoned
kind: experiment
extends: exp-06
tags: [experiment, models, full-checklist, baseline]
---

# exp-07 — three models on the full checklist

*A comparison with a rule fixed in advance: for each pair of models and each
primary endpoint, the run says better, equivalent or undecided, and undecided
pairs decide whether the run is extended. The note is committed before the
run, so that the endpoints, the margin and the extension rule are fixed before
any number exists.*

## Question

On exp-06's baseline configuration — all eleven checks, check-major
`A|B ← C_i ← D`, one session per figure — how do **Claude Opus 5.5, Sonnet 5.5
and Haiku 5.5** compare, per check and per layer, and at what cost and time?

## Why

exp-06 measured the configuration with one model, `claude-sonnet-5`. Which
model runs it is the largest remaining lever on accuracy and cost, and the
first one to settle before skills are tuned further: a skill improvement
measured on one model may not carry over to another, and a cheaper model that
is equivalent would change what production runs.

exp-06 is not one of the arms. It ran `claude-sonnet-5`, which is not Sonnet
5.5: the CLI reports each name as itself (2026-10-12, `modelUsage`), where an
alias would report what it resolved to. And since exp-06, two things have
changed that the comparison has to hold fixed: `individual-data-points` v4
(`plot` → `is_a_plot_with_axes`) and the gold, `gold-v6`. So all three models
are run afresh, and nothing is compared with exp-06.

## Design

| | |
|---|---|
| Checklist | `fig-checklist-exp06`, as pinned now: exp-06's skills with `individual-data-points` **v4** |
| Arrangement | **`A\|B ← C_i ← D`** only — the pins: each check invokes `classify-panels` v1 |
| Entry skill | `do-fig-checklist-cm` v1, the eleven checks in exp-06's order |
| Contract | exp-06's, rebuilt for v4 (`build_contract.py`, 2026-10-11) |
| Gold | **`gold-v6`** |
| Figures | exp-06's 37 |
| Models | **`claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`**, provider `claude-sdk` |
| Assembly | closure |
| Replicates | **3**, extended to **5** for all three models by the rule below |
| Concurrency | 50, as exp-06; the models run one after another, not side by side |
| Sessions | 3 models × 37 figures × 3 replicates = **333**; **555** if extended |
| Turn limit | none, as exp-06 |

Running the models one after another keeps each model's wall time free of the
others' load, so time per figure is comparable between models.

## What is measured

As exp-06, per model, with percentile bootstrap intervals over the 37
figures, replicates averaged per figure first: dispatch; failures and empty
answers; layer S and panels across the eleven lists; layer 1 per check;
layer 2 per check and property; each check's decision on its own (the eleven
decision-like properties of exp-06's notebook); cost, tokens, turns and time
per figure.

Each session also records **the model that answered**, from the CLI's
per-model usage (P2), so that every session documents its model and not only
the one requested. The CLI's background model (`claude-haiku-4-5` in
2026-10-12's check) appears in every session's cost; it is reported apart.

## The comparison

### Primary endpoints

Per figure, replicates averaged:

| | endpoint | how many |
|---|---|---|
| E1 | layer S, `correct / (correct + missing + spurious)`, rows pooled over the eleven checks | 1 |
| E2 | layer 1, correct applicability calls / all, pooled over the eleven checks | 1 |
| E3 | each check's decision, `mean_score` on applicable instances, one per check | 11 |

E1 and E2 pool counts of the same quantity across checks; E3 is not pooled,
because the eleven decisions are different properties. Everything else —
dispatch, the other properties, cost — is reported, not classified.

### For each pair, on each endpoint

The paired difference over figures, with a 95% percentile bootstrap interval,
for Opus − Sonnet, Sonnet − Haiku and Opus − Haiku:

- **better**: the interval excludes 0;
- **equivalent**: the interval lies within **±0.02** (decided with the author,
  2026-10-12);
- **undecided**: neither.

An interval that excludes 0 and also lies within ±0.02 is both: a real
difference too small to matter, reported as such.

### Extension to five replicates

After three replicates, the run is extended to five — for all three models —
if, for any pair:

- E1 or E2 is undecided; or
- more than three of the eleven E3 decisions are undecided.

A few undecided decisions do not trigger it: those applicable to few figures
are bounded by the figures, not the replicates. In exp-06's data, going from 3
to 5 replicates narrowed the paired interval on the decisions by about 13%
(mean half-width ±0.016 → ±0.014) and on layer 1 by about 33% (±0.012 →
±0.008); `single-channel-for-overlay`, on 13 figures, stayed near ±0.045 —
wider than the margin at any replicate count.

The rule says whether to extend; **the author decides** (2026-10-12): when it
fires, the classification after three replicates is reported to the author,
and the two further replicates run only on their go-ahead.

If extended, every reported number uses all five replicates, and the report
says the extension was conditional. It is decided once; there is no third
round.

## Threats to validity

- **The skills were written with Sonnet.** Every skill in the series was
  drafted, read and tuned on Sonnet models; the comparison may favour Sonnet
  5.5 over the others for that reason alone.
- **Many intervals.** 13 endpoints × 3 pairs = 39 classifications at 95%; about
  two would exclude 0 by chance if no model differed. They are read together,
  not one at a time.
- **Conditional extension.** Deciding to extend after seeing three replicates
  is a mild form of optional stopping; the rule is fixed here, applied once,
  and the report says whether it fired.
- **37 figures** bound every per-check estimate, whatever the replicate count.
- **The order is fixed**, as in exp-06, so position and check are confounded —
  equally for the three models.
- **Cost includes the CLI's background model**, the same for each model; it
  narrows cost ratios slightly.
- **Haiku may not dispatch.** A model that answers without invoking the checks
  (exp-06: 1 session in 185) is measured as it is; dispatch is read first so
  that its scores are not misread.

## Preparation

| # | step | done |
|---|---|---|
| P1 | `individual-data-points` v4 pinned; contract and merged gold rebuilt; `gold-v6` | `ac4fa2e80` |
| P2 | Runner records the CLI's per-model usage in each session's `tool_audit.json` | |
| P3 | `experiments/exp-07-models/run.py`: the three models in turn, replicates 3, `--extend` to 5, concurrency 50 | |
| P4 | Smoke test: each model on exp-06's three smoke figures, one replicate | |
| P5 | Notebook: exp-06's, per model, with the pairwise classification | |

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|

## Gold this is scored against

**`gold-v6`**.

## Status and next

Planned, reviewed with the author 2026-10-12. Next: P2 to P4, then the run.
