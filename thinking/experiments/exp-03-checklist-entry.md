---
title: exp-03 — does running the checks through one entry skill degrade them?
date: 2026-09-27
status: planned        # planned | running | done | abandoned
kind: experiment
extends: exp-02
tags: [experiment, skills, dag, entry-point, non-inferiority]
---

# exp-03 — does running the checks through one entry skill degrade them?

## Question

When the three checks of exp-02 are reached through a single entry skill in
one session — rather than each being dispatched on its own, one session per
check — does any check's result get **worse**? And what does the fan-out save
in cost and time, now that the figure and caption are sent once per figure
rather than once per check?

## Paper claim

That a checklist can be run from **one entry point** at the top of the DAG
without paying for it in accuracy. exp-02 asked whether one check can be split
into a chain of shared skills; every session there still started at the check
and did nothing else. A checklist in production is invoked once, for all its
checks, and that is the first time checks share a session: they read one
another's work, they can reuse one `classify-panels` answer, and the model
carries three sets of instructions at once.

As in exp-02 this is a **non-inferiority** question, not a claim that the entry
point helps. Sharing a session could plausibly go either way — a shared
classification could make three checks agree with one another, or one check's
reading of the figure could leak into the next — and nothing yet says which.

The accuracy claim has a companion that is the practical reason to fan out at
all: **efficiency**. Dispatched per check, a figure's content travels with every
session, three times for three checks; under D it travels once. If the fan-out
is not worse, what it saves is part of the case for it, and is measured here
rather than assumed.

## Hypothesis

**The fan-out is not worse.** Each check, run under the entry skill, is
non-inferior to the same check dispatched on its own — its per-check baseline —
on layer S, on layer 1 and on layer 2, for both arrangements of the check
beneath it.

Secondary, with a stated direction: **the fan-out costs less per figure** than
the three per-check sessions it replaces, because the figure and caption are
sent once. Reported with an interval, not gated (see *Cost and time*).

The entry skill is **D**, `do-fig-checklist`. It names the three checks and
nothing else. Below it, each check `C_i` is in one of the two arrangements
from exp-02 that keep panel identification and classification together:

| fan-out condition | what runs under D | per-check control |
|---|---|---|
| **A\|B\|C_i ← D** | each check at v1, the monolith | **A\|B\|C_i** — the check at v1, alone |
| **A\|B ← C_i ← D** | each check at v3, calling `classify-panels` v1 | **A\|B ← C_i** — the check at v3, alone |

for `C_i` ∈ {`micrograph-scale-bar`, `individual-data-points`,
`error-bars-defined`}.

**Both sides are run in this experiment**, from byte-identical skills, and
neither carries `identify-panels` (see *Why the controls are re-run*). Six
comparisons — three checks × two arrangements — each its own claim. What differs
between a fan-out condition and its control is exactly the entry point and what
comes with it (see *What the entry point unavoidably perturbs*).

What would count as being wrong: a check degrading by more than the margin at
any gate. The mechanism that would make it true is **interference**: three
checks in one context, where a later check works from an earlier check's
reading of the figure rather than from the figure, or where the model's
attention is split three ways over instructions it read once each.

## Decision criteria

Written before the run, so the threshold cannot drift to meet the data.

### Endpoints

The gate sequence is exp-02's, unchanged, and for the same reason: each layer
conditions the next, so a later gate only means anything if the earlier one
holds.

| # | endpoint | statistic | what it catches |
|---|---|---|---|
| **0** | **dispatch** | see below — **reported, not a gate** | whether D actually dispatches to the checks |
| **1** | **layer S** | `correct_row` as a fraction of gold rows, per check | a check's panel inventory shaped by another check's |
| **2** | **layer 1** | `correct_applicable` + `correct_NA` over all profiled instances, per check | applicability decided once and reused across checks |
| **3** | **layer 2** | `mean_score` per property, on applicable instances, paired by example | the check-specific judgement under a shared context |

Statistics, bootstrap and verdict rules are exp-02's: per-example rate
differences, seeded percentile bootstrap over the 38 examples, 10,000
resamples, **non-inferior** if the 95% CI's lower bound is above −δ,
**degraded** if the CI lies entirely below −δ, **inconclusive** if it straddles
−δ. Fixed-sequence testing within each comparison; nothing corrected across the
six, which are six claims and not a family to pick a winner from.

### Margins

**Provisionally exp-02's**: δ_S = 0.0125, δ₁ = 0.02, δ₂ = 0.02, at five
replicates. They are confirmed or tightened by prep step P2 below *before* this
note is committed as the preregistration, and not afterwards.

The reason they may move: exp-02 sized its margins from exp-01's variance,
because that was the only data it had. exp-03 has something closer — the
observed between-replicate variance of exp-02's `pinned` and `<check>@v3` arms,
five replicates each, which are the same two arrangements of the same skills.
Both sides of every exp-03 comparison are new runs, so the variance of a paired
difference is

```
Var(d_e) = σ²_fan-out,e / 5 + σ²_per-check,e / 5
```

with both terms assumed equal to exp-02's observed `σ²_e` for that
arrangement. For the control that is close to a measurement — the same
arrangement, minus one idle description. For the fan-out it is the assumption
exp-02 also made, that the new arrangement is no noisier than its reference, and
it is reported against the observed exp-03 variance afterwards.

#### P2 result, 2026-09-28

Measured on exp-02's `pinned` and `<check>@v3` arms, five replicates, all 38
examples, re-scored against the current gold (after the `emboj.2009.340` label
fix) under the per-check contracts. Half-width = `1.96 · sqrt(mean_e(2σ²_e/5) / n_e)`.

| gate | δ | largest planned half-width | clears |
|---|---|---|---|
| layer S | 0.0125 | 0.0253 — `micrograph-scale-bar`, A\|B ← C; every other check ≤ 0.0033 | **5 of 6** |
| layer 1 | 0.02 | 0.0111 — `error-bars-defined`, A\|B ← C | 6 of 6 |
| layer 2 | 0.02 | 0.0198 — `micrograph-scale-bar · scale_bar_defined_in_image`, A\|B\|C | all 34 property × arrangement cells |

**One layer-S cell does not clear**, and the reason is specific. In exp-02's
`micrograph-scale-bar@v3` arm, **3 of 190 sessions answered `outputs: []`** on
figures with 13–15 panels, having invoked the check and `classify-panels`
normally; `pinned` had none. Non-response scores as a fully missing row set, so
on each of those three examples one replicate reads 0 and four read 1, and that
is the whole of the variance. It is heavy-tailed, rare, and real — not
measurement jitter that more replicates would average away at any affordable n.

**Decided: δ_S stays 0.0125 for every comparison**, and
`micrograph-scale-bar`'s A\|B ← C_i ← D comparison at layer S is
**pre-declared as expected to be uninformative** at this margin. If its
observed interval is wider than δ_S it is reported as uninformative rather than
counted — exactly as exp-02 handled `individual-data-points · plot` — and if the
fan-out's variance there turns out small enough that the interval clears, it is
read like any other. A wider margin for that one comparison was the alternative,
and was not taken: a margin moved to fit a measurement is what preregistration
exists to prevent, and δ_S was chosen for what a real degradation looks like,
not for one arm's rare empty answers.

`scale_bar_defined_in_image` at 0.0198 clears by 0.0002, which is as thin as
exp-02's `plot`; if its observed half-width exceeds 0.02 it is reported as
uninformative on the same terms.

### Endpoint 0: what "D dispatched" means

Read from `skill_trace.json`, per session:

- **dispatch** — all three check skills invoked. Reported per condition and per
  check, since a check can be skipped on its own.
- **reach** — in A\|B ← C_i ← D, `classify-panels` invoked for a check. A call
  is attributed to the check invoked most recently before it — an inference
  from order, not something the trace records.
- **reuse** — in the same condition, how many times `classify-panels` is
  invoked per session: once means one classification served all three checks,
  three means each check asked for its own. This is the concrete payoff a DAG
  promises in a checklist and is reported whatever it shows. No hypothesis
  rests on it.
- **order** — the order in which the checks were first invoked. D lists them
  without prescribing one, so order is observed rather than set.
- **spontaneous** — any skill invoked that the condition never named, on either
  side.

Interpretation follows exp-02's table: a check that is non-inferior with
partial dispatch is **safe but optional**, never relabelled as though D had
dispatched every time; a check that degrades is read *with* its dispatch rate.

A new failure mode sits under dispatch and is worth naming: a session can fill a
check's part of the combined output **without invoking that check's skill**,
working from the schema's field names and D's list alone. Dispatch is what
detects it, and a session that does it is not the condition it claims to be.

### Non-response and failures

As in exp-02: `outputs: []` — here, an empty list under a check's key — scores
as a fully missing row set, and failed sessions are counted and reported per
condition. One difference matters here — **a failed fan-out session loses all
three checks at once**, so failures are correlated across checks in a way the
controls' are not. Failures are reported per session as well as per check, and
a failure-rate difference of more than 5% between a fan-out condition and its
control is a finding in its own right.

### Secondary, reported, not a gate

Whether the entry point changes exp-02's own contrast: `(A|B ← C_i ← D) − (A|B|C_i ← D)`
against `(A|B ← C_i) − (A|B|C_i)`. A difference-in-differences of per-example
rates, per check, for layers S and 1. It asks whether delegating classification
matters more — or less — once three checks could share the result.

### Cost and time

Every session records what it spent — `total_cost_usd`, `num_turns`,
`duration_ms` and the token breakdown including cache creation and cache reads
— in `intermediates/tool_audit.json`.

The unit is **one figure**, because that is what a fan-out session and its
baseline both produce: all three checks' answers for one example.

| quantity | fan-out | per-check baseline |
|---|---|---|
| cost | the one fan-out session | sum of the three per-check sessions, same example, same arrangement |
| tokens | input (fresh + cache creation + cache read), cache read, output | the same, summed |
| turns | `num_turns` | summed |
| time, serial | `duration_ms` | sum of the three |
| time, parallel | `duration_ms` | max of the three |

Replicates are averaged per `(condition, example)` before the ratio is taken.
Replicate indices are not paired across the two run types — replicate 2 of the
fan-out and replicate 2 of a control are unrelated samples — so the pairing is
by example only, as at every other endpoint.

**Two time baselines, deliberately.** The per-check sessions are independent
and could run concurrently, so a fan-out that beats their *sum* may still lose
to their *max*. Summed time is what the work costs; the max is how long a
figure takes if the per-check sessions are run at once. Reporting only one
would flatter one side.

Reported as the mean of per-figure ratios, fan-out ÷ baseline, with a
percentile bootstrap over the 38 examples, per arrangement. **Predicted below 1
for cost and input tokens.** Not predicted for time or output tokens: three
checks' worth of reasoning is still produced, and a longer context re-read at
every turn may offset what sending the figure once saves.

What would count as being wrong: a cost ratio whose interval lies at or above 1.
That would mean the saving on the figure is eaten by the context growing across
three checks, and the fan-out's case would rest on accuracy and convenience
alone.

This endpoint is **secondary and not gated**. A cheaper fan-out that degrades a
check is still a degraded check, and the accuracy gates are read first.

## Design

| | |
|---|---|
| Starting point | `fig-checklist-exp02`, every reused file **byte-identical** |
| Fan-out checklist | `fig-checklist-exp03` — D, the three checks, `classify-panels` |
| Control checklist | `fig-checklist-exp03-per-check` — the three checks with their exp-02 contracts, `classify-panels` |
| Entry skill | `do-fig-checklist` v1 — the only leaf of the fan-out checklist |
| Checks | `micrograph-scale-bar`, `individual-data-points`, `error-bars-defined` |
| Conditions | the four in the table above |
| Held fixed | skills, gold, examples, model, provider, replicate count |
| Model | `claude-sonnet-5`, pinned by exact name |
| Provider | `claude-sdk` |
| Replicates | 5 |
| Examples | 38 — the same 38 for all three checks |
| Sessions | 1,520: 380 fan-out, 1,140 per-check |
| Contract builder | `experiments/exp-03-checklist-entry/build_contract.py` |
| Runner | `experiments/exp-03-checklist-entry/run.py` |

The independent variable in one sentence: **whether a check is dispatched on
its own, or reached through an entry skill that dispatches all three.**

### Why the controls are re-run

An earlier version of this note used exp-02's `pinned` and `<check>@v3` arms as
the controls, since the skills are byte-identical. It was changed for one
reason: **exp-02's skill pool carried `identify-panels`**, and its description
alone drew calls that no prose asked for. In exp-02's `A|B ← C` arm — where
`classify-panels` v1 already does panel identification itself —
`identify-panels` was invoked in **9/190** `error-bars-defined`, **9/190**
`individual-data-points` and **22/190** `micrograph-scale-bar` sessions. In
`A|B|C` it was invoked in none.

No arrangement here calls A on its own, so `identify-panels` has no place in
either checklist. Dropping it from the fan-out alone would have made the
fan-out and its exp-02 controls differ in the skill pool as well as the entry
point. So it is dropped from both, and the controls are run again alongside the
fan-out. This also removes the time gap between treatment and control that
borrowing exp-02's arms would have left.

The two checklists hold only what a condition pins — each check at v1 and v3,
`classify-panels` v1 — and every one of those files is a byte copy of its
exp-02 original, checked with `cmp`. The skill pools differ by exactly one
description: D's.

### One contract, owned by D

A session returns one structured output, validated against one leaf schema.
`do-fig-checklist` is therefore **the only leaf** of `fig-checklist-exp03`, and
the only skill there that owns contracts. The three checks carry their
`SKILL.md` versions and nothing else.

D's contract is **derived from the three per-check contracts**, not authored, so
that scoring cannot differ from the controls' by anything but a key:

| file | contents |
|---|---|
| `schema.json` | an object with three required properties named after the checks, each holding that check's `outputs` array schema verbatim; strict, `additionalProperties: false` |
| `eval-manifest.json` | the shared `defaults` (identical across the three), `list_alignment` keyed by check on `panel_label`, and every `fields` profile re-keyed from `outputs[].x` to `<check>[].x` |
| `benchmark.json` | the 38 examples, identical, in the same order, in all three checks' benchmarks |
| gold | per example, each check's gold rows under that check's key |

**Each check's rows sit directly under its name.** A first version nested them
as `<check>.outputs`, and scored every check as empty: the scorer's schema
discovery finds a list nested in a plain object, but its row lookup reads a list
only at the document root or inside a list row. Three root-level lists need no
change to the scorer and lose nothing — every source schema's only top-level
property is `outputs`. The disagreement between discovery and lookup is a scorer
defect worth fixing separately; this experiment does not depend on it.

**The equivalence is verified, not assumed.** Before writing anything,
`build_contract.py` scores exp-02's committed predictions — replicate 0 of both
arrangements, all 38 examples — once per check under that check's own contract
and once combined under D's, and refuses unless every instance and every layer-S
row set agree: **228 of 228 identical**. The check has been shown to fail: a
corrupted row-matching threshold in the combined manifest is caught. `--check`
reports drift between the committed files and what the script would build.

Gold carries curation metadata (`updated_at`) that the strict schema forbids and
the scorer never reads; it is projected away for validation, as
`runner._as_prediction` does, and not carried into the merged gold.

**The schema repeats `panel_label` per check**, and that is deliberate. A
panel-major contract — one row per panel carrying every check's fields, perhaps
one shared classification — would change the output task along with the entry
point, and would turn layer S into one shared row set, so gate 1 could no longer
be read per check. It is a different question, *does sharing the intermediate in
the output help*, and a candidate for its own experiment. The golds make it
feasible: the three checks' gold panel lists agree, in order, on all 38
figures — once a trailing space in one `error-bars-defined` label (`B ` on
`emboj.2009.340/content/3`) was fixed in curation on 2026-09-28.

### D, as authored

`do-fig-checklist` v1 is deliberately thin: it names the three checks and asks
for all three to be run on the figure. It restates nothing a check already says,
does not order the checks, and does not mention the output keys — the schema
carries those.

Its wording is the lever exp-02's pilot found mattered most. There the call
instruction moved invocation from 47% to 80% once it became imperative and gave
a reason. D says *run* the checks rather than *invoke* them, and the smoke test
showed that is enough: D dispatched to all three checks in 6 of 6 sessions.

**D is frozen as it stands, and the nested invocation is not tuned.** The smoke
test found that checks reached through D mostly do not reach `classify-panels`
(below). That could be chased with more wording, but every round of tuning makes
the experiment measure the tuning. What a thin entry skill does to the skills
beneath it is the finding, and it is tested as found.

The documentation does not settle why. The Agent Skills docs describe each skill
as a self-contained module selected by its description, and say nothing about
skills invoking other skills. The nearest guidance is about *files*, not skills:
the authoring best practices advise keeping references "one level deep from
SKILL.md", because Claude may only partially read a file referenced from another
referenced file
([best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#avoid-deeply-nested-references)).
A skill named inside a skill reached from another skill is the same shape one
level up, so the observation is consistent with that guidance — but that is an
analogy, not something the docs state. For orchestration they point to
subagents, which run in isolated contexts and in parallel
([subagents](https://code.claude.com/docs/en/sub-agents)).

### What the entry point unavoidably perturbs

Measured against its per-check control, a fan-out session differs in:

- **the entry point** — the request names `do-fig-checklist`, not the check;
- **D's description** in the pool, beside the four the control also has;
- **two other checks** in the same context, before or after this one;
- **the output contract** — the check answers as one part of a combined object
  rather than as the whole of its own.

None of these can be removed without removing the entry point, so what this
measures is the entry point **plus** what comes with it — which is what running
a checklist from one entry point actually costs.

### Prep work

| # | step | state |
|---|---|---|
| P1 | per-example layer S / layer 1 frames for exp-02's `pinned` and `<check>@v3` arms | **done**, re-scored on current gold |
| P2 | observed between-replicate variance of those arms; confirm or tighten δ_S, δ₁, δ₂; confirm no layer-2 property falls below its floor at n = 5 | **done** — all hold but one layer-S cell, see *P2 result* |
| P3 | commit the margins in this note | **done**, with this note |

P2 uses exp-02's variance only, not its arm contrasts, for exp-02's own reason:
the contrast is the answer to exp-02's question and has no bearing on this one.

### What has been built

| # | artefact | path | state |
|---|---|---|---|
| 1 | Fan-out checklist: D, checks v1 and v3, `classify-panels` v1 | `…/fig-checklist-exp03/` | **done**, 7 copied files `cmp`-identical |
| 2 | Control checklist: checks v1 and v3 with their contracts, `classify-panels` v1 | `…/fig-checklist-exp03-per-check/` | **done**, 16 files `cmp`-identical |
| 3 | The entry skill | `…/fig-checklist-exp03/do-fig-checklist/v1/SKILL.md` | **drafted** |
| 4 | `version-manifest.yaml` for both | both checklists | **done** |
| 5 | Contract builder, and its output: `schema.json`, `eval-manifest.json`, `benchmark.json`, 38 merged golds | `experiments/exp-03-checklist-entry/build_contract.py` | **done**, 228/228 verified |
| 6 | Generated views (`README.md`, `dag.yaml`) | both checklists | **done**, in sync |
| 7 | Runner | `experiments/exp-03-checklist-entry/run.py` | **done**, `--smoke`, `--dry-run`, `--part` |
| 8 | Smoke test: every condition, 3 examples, 1 replicate | `experiments/runs/exp-03-checklist-entry/smoke/` | **done**, 24/24 sessions |
| 9 | Analysis | `notebooks/experiments/exp-03-checklist-entry.ipynb` | **written**, runs end to end on the smoke test |
| 10 | Runs | `experiments/runs/exp-03-checklist-entry/` | — |

The second fan-out arm is one unpin that moves all three checks to v3 together,
`{micrograph-scale-bar: (v3,), individual-data-points: (v3,),
error-bars-defined: (v3,)}` — a product of singletons, so exactly one SkillSet.
Each control is `{<check>: (v1, v3)}`, the pin and the delegating version.

### The smoke test, 2026-09-27: D dispatches, nested delegation mostly does not

24 sessions — every condition, the first 3 examples, one replicate — all
completed, none failed. The notebook ran end to end on them.

**D dispatched to all three checks in 6/6 fan-out sessions**, and always in the
order its prose lists them: `micrograph-scale-bar` > `individual-data-points` >
`error-bars-defined`. No skill was invoked that a condition did not name.

**Inside the fan-out, the v3 checks mostly skipped `classify-panels`.**

| condition | check invocations that reached `classify-panels` |
|---|---|
| `A\|B ← C_i`, per check | **9/9** |
| `A\|B ← C_i ← D`, fan-out | **1/9** — one session, attributed to `error-bars-defined` |

The same v3 check files that delegate every time on their own nearly never do
under D. So the arrangement labelled `A|B ← C_i ← D` ran, in 8 of 9 check
invocations, **without the B block** — v3 does not carry it, and nothing
supplied it. For `individual-data-points` and `error-bars-defined` this could be
exp-02's "caller's own prose suffices" pattern, since their C blocks carry
panel-type terms of their own (8 and 5, per exp-02's pilot). It cannot be that
for `micrograph-scale-bar`, whose C block gates on a type it does not define —
exp-02's pilot found that check always asks, and on its own here it asked 3/3.
Under D it asked 0/3.

Two readings, which the smoke test cannot separate: the model, having already
looked at the figure for an earlier check, treats classification as done; or a
skill reached from inside another skill is followed less literally than one
dispatched directly. Either way it is exactly what endpoint 0 exists to catch,
and at n = 9 the direction is clearer than the rate.

**Cost fell as predicted, time did not.** Per figure, fan-out ÷ per-check, 3
examples:

| | cost | input tokens | output tokens | time vs sum | time vs max |
|---|---|---|---|---|---|
| `A\|B\|C_i ← D` | 0.83 | 0.63 | 1.27 | 1.16 | 2.89 |
| `A\|B ← C_i ← D` | 0.60 | 0.42 | 0.98 | 0.84 | 2.18 |

The delegating arm's larger saving is partly the skipped `classify-panels`
calls, not only the figure sent once. Against per-check sessions run in
parallel, the fan-out takes two to three times as long.

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|
| 2026-09-27 | smoke | `run.py --smoke` | $1.33 | `experiments/runs/exp-03-checklist-entry/smoke/` |
| | all four | `python experiments/exp-03-checklist-entry/run.py` | est. $90–110 | `experiments/runs/exp-03-checklist-entry/` |

1,520 sessions. exp-02 averaged about $0.04 per session over 2,280, which puts
the 1,140 control sessions near $45 and the per-check cost of a figure near
$0.12. The fan-out is estimated at about that per figure — whether it costs
less is what the cost endpoint measures — so 380 sessions near $45–60.

## Findings

*Not yet run.*

## Threats to validity

- **The entry point is measured with everything it brings.** Entry prompt, D's
  description, shared context and combined contract move together, and nothing
  here separates them. A degradation says running under D costs something, not
  which of the four is responsible.
- **Order is observed, not controlled.** D does not prescribe one, so if the
  model settles on a fixed order, a check's position and its identity are
  confounded: a check that always runs last and degrades cannot be told apart
  from a check that is sensitive to the setup. Endpoint 0 reports the order so
  that this is visible.
- **A skipped check is still answered.** A session can fill a check's part of
  the combined output without invoking that check's skill. Dispatch catches it
  per session; a score is not read without it.
- **Failures are correlated across checks.** One failed fan-out session removes
  all three of its checks, so the three checks' failure counts are not
  independent and should not be summed as though they were.
- **Descriptions compete.** exp-02 showed `identify-panels` drawing calls from its
  description alone, which is why it is gone. D adds one description to the
  fan-out's pool and, more importantly, puts the three checks' descriptions in
  front of a session that is working on all of them; a check can be reached by
  discovery as well as by D.
- **The combined contract is derived, not native.** The pairing depends on it
  scoring each check exactly as the per-check contract does. That is verified
  on 228 exp-02 scorings, not on exp-03's own predictions, whose shapes could in
  principle exercise a path exp-02's did not.
- **Variance sized from exp-02, assumed for exp-03.** Both sides are new runs; if
  either is noisier than exp-02's arms the intervals are wider than planned and a
  gate may return inconclusive. Observed half-widths are reported beside planned
  ones.
- **Fan-out and controls are not interleaved.** The runner runs the fan-out, then
  the controls, each arm's examples in sequence. A drift in the provider over the
  hours of a run would fall between them. The harness numbers replicates from
  zero on every call, so interleaving by replicate would need a harness change;
  the order is recorded in the run log instead.
- **Cost depends on prompt caching, and caching depends on run order.** A
  cache read is billed far below a fresh input token, and whether a session
  finds a warm cache depends on what ran just before it, within the cache's
  lifetime. Both sides run each arm's examples back to back, so both see the
  same pattern of warm caches, and the token breakdown is reported beside the
  cost so that a difference can be traced to fewer tokens or to cheaper ones.
- **Timing is wall-clock on a shared provider.** `duration_ms` includes queueing
  and provider load. Time is reported, and read with more caution than cost or
  tokens, which do not depend on load.
- **Gold is shared across checklists and experiments.** Gold lives per check in
  the examples tree, so a curation fix reaches exp-02's scores as well as
  exp-03's. The `B ` → `B` fix on `emboj.2009.340/content/3`
  (`error-bars-defined`) was made before any full exp-03 run, and D's merged
  gold was rebuilt from it; the exp-03 notebook treats an analysis older than
  its gold as stale. exp-02's notebook checks predictions only, so its local
  scores for that example predate the fix until they are re-scored.
- **Carried over from exp-02**: three checks and no tally across them;
  `micrograph-scale-bar` near its ceiling; bootstrap over 38 examples;
  one model and one provider; skills authored by the person who holds the
  hypothesis.

## Status and next

Preregistered. Both checklists, D's contract and gold, the runner and the
notebook are built, the smoke test has run, D is frozen as it stands, and the
margins are fixed. This note is committed before any full run, so

```bash
git log --oneline --reverse -- \
  thinking/experiments/exp-03-checklist-entry.md \
  experiments/runs/exp-03-checklist-entry/
```

shows the prediction predating the data.

**An open design question, for later:** whether a check that delegates should
name the skill it calls in its frontmatter `description`, not only in its body.
The description is the one part of every skill the model sees before invoking
anything, so it is where a dependency would be visible before the call rather
than only after it. It would change the v3 check files, which this experiment
holds byte-identical, so it belongs to a follow-up.

**Next, not here:** if the fan-out holds but nested delegation stays reluctant,
the natural follow-up replaces skill-in-skill calls with **parallel subagents**,
each check run in its own context with explicit input and output — closer to a
function call than to a skill read in place. That is a different mechanism, and
a separate experiment. The note is committed as the
preregistration once both are fixed, and before any run beyond the smoke test.

What it settles if it holds: that a checklist can be entered from the top of
its DAG at no loss of accuracy, which is the configuration it would ship in —
and, from the cost endpoint, what that configuration saves per figure. What it
opens if it does not: whether the cost is interference between checks — which
the order and reuse endpoints would point at — or the entry point itself.
