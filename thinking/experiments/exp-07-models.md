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
| Checklist | **`fig-checklist-exp07`**, copied from `fig-checklist-exp06` (which stays as it ran), with two changes below |
| Arrangement | **`A\|B ← C_i ← D`** only — the pins: each check invokes `classify-panels` v1 |
| Entry skill | `do-fig-checklist-cm` **v2**, the eleven checks in exp-06's order |
| Contract | exp-06's derivation, into `fig-checklist-exp07` (`experiments/exp-07-models/build_contract.py`) |
| Harness | `claude-agent-sdk` 0.2.165, bundled CLI 2.1.294 (exp-06: 0.2.152, CLI 2.1.259, which does not run Opus 5.5) |
| Runtime `CLAUDE.md` | "Whenever a skill mentions another skill, invoke that skill with the `Skill` tool" (2026-10-12; exp-06: "If it names another skill, invoke that skill") — harness-wide, not pinned by the checklist |
| Gold | **`gold-v6`** |
| Figures | exp-06's 37 |
| Models | **`claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`**, provider `claude-sdk` |
| Assembly | closure |
| Replicates | **3**, extended to **5** for all three models by the rule below |
| Concurrency | 50, as exp-06; the models run one after another, not side by side |
| Sessions | 3 models × 37 figures × 3 replicates = **333**; **555** if extended |
| Turn limit | none, as exp-06 |
| Thinking | the models' default (adaptive, not displayed). Summarized display was tried in smoke 5 and works; switched off again, as the summaries add little (decided with the author, 2026-10-12) |

### Two changes from exp-06's skills

- **`individual-data-points` v4**: `plot` → `is_a_plot_with_axes`, as in
  `plot-axis-units`, with heat maps not plots with axes; scored against
  `gold-v6` (2026-10-11).
- **Every skill call names the `Skill` tool** (2026-10-12, decided with the
  author after the first smoke test): `do-fig-checklist-cm` v2 says to run
  each check "by invoking its skill with the `Skill` tool, one at a time",
  and each check's next version invokes `classify-panels` "with the `Skill`
  tool". With exp-06's wording, Sonnet 5.5 invoked no check in 3 of 3 smoke
  sessions and Opus 5.5 in 1 of 3, answering from the schema in 4 turns; Haiku
  5.5 dispatched in 3 of 3. The wording is the only change; each skill is
  otherwise its exp-06 version.

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
the one requested; and, per assistant message, the model that wrote it and
whether a subagent did, so that a change of model mid-session is dated.

**Safety-classifier fallback is allowed and recorded** (decided with the
author, 2026-10-12). Claude Code re-runs a request its classifier flags on a
fallback model and continues there: on Opus 5.5, biology to Opus 5 and
cybersecurity to Opus 4.8; on Sonnet 5.5, cybersecurity to Sonnet 5 and
biology ends in a refusal; Haiku 5.5 is not listed
(code.claude.com/docs/en/model-config, "Automatic model fallback", read
2026-10-12). Every session's models are reported per model arm: how many
switched, to what, and when; and refusals, from the stop reason. The
CLI's background model (`claude-haiku-4-5` in
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
| P1 | `individual-data-points` v4; contract and merged gold rebuilt; `gold-v6` | `ac4fa2e80` |
| P1b | `fig-checklist-exp07` from `fig-checklist-exp06`, restored to its run state; D v2 and the checks' next versions name the `Skill` tool; SDK 0.2.165 | this commit |
| P2 | Runner records the CLI's per-model usage in each session's `tool_audit.json` | this commit |
| P3 | `experiments/exp-07-models/run.py`: the three models in turn, replicates 3, `--extend` to 5, concurrency 50; the smoke report names the model that answered | this commit |
| P4 | Smoke test: each model on exp-06's three smoke figures, one replicate | |
| P5 | Notebook: exp-06's, per model, with the pairwise classification | |

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|
| 2026-10-12 | smoke 1, three models, exp-06 wording, SDK 0.2.152 | `run.py --smoke` | $3.88 | Opus 5.5 refused by CLI 2.1.259; Sonnet 5.5 no check in 2/3 |
| 2026-10-12 | smoke 2, SDK 0.2.165, exp-06 wording | `run.py --smoke` | $1.37 | no check: Sonnet 5.5 3/3, Opus 5.5 1/3, Haiku 5.5 0/3 |
| 2026-10-12 | smoke 3, `fig-checklist-exp07` | `run.py --smoke` | $2.08 | below |

**Smoke 3, 2026-10-12.** Each model on `s44318-026-00715-1` content/1–3, one
replicate, 9 sessions, none failed.

- **Dispatch**: Opus 5.5 all eleven checks in 3/3; Sonnet 5.5 in 2/3 — on
  content/2 it invoked `micrograph-scale-bar` (and `classify-panels`) and then
  answered all eleven in 8 turns; Haiku 5.5 in 2/3 — on content/1 it skipped
  `single-channel-for-overlay` alone. Always in D's order; nothing outside the
  closure. Partial dispatch, which exp-06 never saw, appears in two models.
- **The model that answered**: in one Opus 5.5 session (content/1), most of
  the output — 8,874 of 10,381 tokens, $0.36 of $0.57 — came from
  `claude-opus-5`, not `claude-opus-5-5`; the runner sets no fallback model.
  The CLI's background model is `claude-haiku-5-5`.
- **Size**: Opus 28–29 turns, $0.39–0.57; Sonnet 26 turns, $0.17 (8 turns,
  $0.19 for the partial one); Haiku 26–28 turns, $0.014–0.022, with 15,000–
  28,000 output tokens. Costs are the CLI's estimates.

**Smoke 4 and 5, 2026-10-12: Opus 5.5 alone, runtimes kept.** Without, then
with summarized thinking; 3 sessions each, all eleven checks in 6/6, Opus 5.5
throughout (no fallback; content/1, which fell back in smoke 3, did not), $1.26
and $1.30. With the default display the transcripts' thinking blocks were
empty; with `display: summarized` each session had 5–8 thinking summaries of
80–780 characters, at the same cost and turns.

## Gold this is scored against

**`gold-v6`**.

## Status and next

Planned, reviewed with the author 2026-10-12. Next: P2 to P4, then the run.
