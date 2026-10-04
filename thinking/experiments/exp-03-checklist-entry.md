---
title: exp-03 — does running the checks through one entry skill degrade them?
date: 2026-09-27
status: done           # planned | running | done | abandoned
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
exp-02 original, checked with `cmp`.

### Amendment, 2026-09-28: each session holds its closure, not the checklist

*Made after the first full run had started and before any of its data was
kept; see* Runs.

Until this amendment the runtime assembled **every skill of the checklist**
into every session, so that "all descriptions compete". That was a deliberate
design, inherited from the harness's first milestone — and it is the wrong
default for a question about modular skills. It offered the model redundant
copies of instructions: exp-02's monolith was offered `classify-panels` while
carrying the same text inline, and a check calling one shared skill was offered
another it had no use for. No checklist maintained for modularity would ship
that, so it tests nothing this line of experiments is about. It also blurred the
arrangements: exp-02's stray calls — **11/570** `classify-panels` in `A ← B|C`,
**40/570** `identify-panels` in `A|B ← C`, none in the monolith — were possible
only because the unnamed skill was there to be found.

So **a session now holds the call-graph closure of its entry point**: the entry
skill and every skill its pinned prose reaches, transitively, following
`requires` on the pinned version. This is the harness default from this date
(`assembly="closure"`), and `run.py` names it explicitly.

| condition | session holds |
|---|---|
| `A\|B\|C_i` | the check (v1) |
| `A\|B ← C_i` | the check (v3), `classify-panels` |
| `A\|B\|C_i ← D` | D, the three checks (v1) |
| `A\|B ← C_i ← D` | D, the three checks (v3), `classify-panels` |

Two consequences. The per-check controls no longer see the other two checks,
so a control is now a check genuinely dispatched **alone**. And the fan-out
differs from its control in the skill pool by exactly what the fan-out
*requires*: D and the two other checks — no idle skill on either side.

exp-01 and exp-02 were run under the old assembly, and their results stand as
results about it; the harness keeps `assembly="all"` so that they can be
reproduced.

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
- **the skill pool** — D and the two other checks, which the fan-out needs and
  the control, assembled as its own closure, does not hold;
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

*Run under the old whole-checklist assembly, before the amendment above; the
closure smoke test follows.*

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

### The closure smoke test, 2026-09-28: the same picture, with nothing idle

The same 24 sessions under closure assembly, $1.27, all completed, none failed.
Every session held exactly its closure — 1, 2, 4 and 5 skills for the four
conditions, recorded in each `skill_set.json` — so no skill was available that
a condition does not name.

**D dispatched to all three checks in 6/6 sessions**, in the listed order every
time, as before.

**Nested delegation is as reluctant without the idle skills as with them.**

| condition | check invocations that reached `classify-panels` |
|---|---|
| `A\|B ← C_i`, per check | **8/9** — `individual-data-points` 2/3, the others 3/3 |
| `A\|B ← C_i ← D`, fan-out | **2/9** — both `error-bars-defined`; `micrograph-scale-bar` 0/3 again |

So the reluctance is not a side effect of the whole-checklist pool: it survives
a pool holding only what the arrangement needs.

**Cost** per figure, fan-out ÷ per-check, mean of 3 examples: **0.82** for
`A|B|C_i ← D` and **0.67** for `A|B ← C_i ← D`, close to the first smoke test's
0.83 and 0.60.

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|
| 2026-09-27 | smoke, whole-checklist assembly | `run.py --smoke` | $1.33 | superseded by the closure smoke test |
| 2026-09-28 | all four, whole-checklist assembly | `run.py` | ≈ $15 | **stopped** after 153 `A\|B\|C_i ← D` sessions; moved to `experiments/runs/exp-03-superseded/` (not committed), not experiment data — see *Amendment* |
| 2026-09-28 | smoke, closure assembly | `run.py --smoke` | $1.27 | `experiments/runs/exp-03-checklist-entry/smoke/` |
| | all four, closure assembly | `python experiments/exp-03-checklist-entry/run.py` | est. $90–110 | `experiments/runs/exp-03-checklist-entry/` |

1,520 sessions. exp-02 averaged about $0.04 per session over 2,280, which puts
the 1,140 control sessions near $45 and the per-check cost of a figure near
$0.12. The fan-out is estimated at about that per figure — whether it costs
less is what the cost endpoint measures — so 380 sessions near $45–60.

## Findings

Run 2026-09-28/29 under closure assembly: 1,520 sessions, **none failed**,
all 38 examples × 5 replicates in every condition. Analysis in
`notebooks/experiments/exp-03-checklist-entry.ipynb`; runs committed in
`dd902c828`.

### Numbers

**Endpoint 0 — dispatch.**

| | `A\|B\|C_i ← D` | `A\|B ← C_i ← D` |
|---|---|---|
| all three checks invoked | 189/190 | 189/190 |
| order | the listed one, 189/189 | the listed one, 189/189 |
| `classify-panels` reached, per check | — | `error-bars-defined` 37%, `individual-data-points` 0%, `micrograph-scale-bar` 0% |
| `classify-panels` calls per session | 0 in 190 | 0 in 118, **1** in 72, never more |

Per check, `A|B ← C_i` reached `classify-panels` in 95%, 86% and 99% of sessions
(`error-bars-defined`, `individual-data-points`, `micrograph-scale-bar`). No
skill was invoked that a condition did not name, on either side. The one session
per fan-out arm that did not dispatch invoked D and then answered all three
checks **without invoking any check skill** — the failure mode named in advance.

**Non-response.** One empty answer in 1,520: `micrograph-scale-bar`, per-check
`A|B ← C_i`, one session.

**Gate 1 — layer S**, fan-out − control, δ_S = 0.0125:

| check | `A\|B\|C_i ← D` | `A\|B ← C_i ← D` |
|---|---|---|
| `micrograph-scale-bar` | −0.0059 [−0.0132, 0.0000] **inconclusive** | −0.0020 [−0.0137, 0.0129] **inconclusive** *(pre-declared uninformative)* |
| `individual-data-points` | −0.0050 [−0.0112, 0.0000] **non-inferior** | −0.0010 [−0.0086, 0.0061] **non-inferior** |
| `error-bars-defined` | −0.0050 [−0.0112, 0.0000] **non-inferior** | −0.0055 [−0.0131, 0.0000] **inconclusive** |

Row outcomes behind it, summed over examples and replicates (1,490 gold rows per
check and condition):

| check | `A\|B\|C_i` | `A\|B\|C_i ← D` | `A\|B ← C_i` | `A\|B ← C_i ← D` |
|---|---|---|---|---|
| `micrograph-scale-bar` | 0 missing, 15 spurious | 8, **28** | 9, 10 | 8, **21** |
| `individual-data-points` | 0, 3 | 7, **25** | 6, 10 | 6, **15** |
| `error-bars-defined` | 0, 3 | 7, **25** | 0, 0 | 6, **15** |

**Gate 2 — layer 1**, δ₁ = 0.02:

| check | `A\|B\|C_i ← D` | `A\|B ← C_i ← D` |
|---|---|---|
| `micrograph-scale-bar` | −0.0025 [−0.0067, 0.0005] non-inferior | −0.0036 [−0.0105, 0.0025] non-inferior |
| `individual-data-points` | −0.0022 [−0.0092, 0.0039] non-inferior | +0.0008 [−0.0057, 0.0074] non-inferior |
| `error-bars-defined` | **−0.0620 [−0.0782, −0.0459] degraded** | **−0.0473 [−0.0624, −0.0326] degraded** |

**Gate 3 — layer 2**, δ₂ = 0.02. No property degraded. Of the properties per
check and condition, all were non-inferior except:

| condition | property | difference [95% CI] | half-width |
|---|---|---|---|
| both | `micrograph-scale-bar · from_the_image` | −0.014 / −0.038 | 0.039 / 0.040 — **uninformative** (10 examples) |
| both | `micrograph-scale-bar · scale_bar_defined_in_image` | −0.007 [−0.021, 0.007] | 0.014 — inconclusive |
| `A\|B ← C_i ← D` | `individual-data-points · explanation` | −0.013 [−0.025, −0.001] | 0.012 — inconclusive |
| `A\|B\|C_i ← D` | `error-bars-defined · from_the_caption` | −0.015 [−0.026, −0.005] | 0.011 — inconclusive |
| `A\|B ← C_i ← D` | `error-bars-defined · from_the_caption` | −0.020 [−0.032, −0.009] | 0.011 — inconclusive |

**Through the fixed sequence**, each comparison stops at its first gate that
does not return non-inferior:

| check | `A\|B\|C_i ← D` | `A\|B ← C_i ← D` |
|---|---|---|
| `micrograph-scale-bar` | stops at layer S (inconclusive) | stops at layer S (pre-declared uninformative) |
| `individual-data-points` | **non-inferior at all three gates** | S and 1 non-inferior; layer 2 inconclusive on one property |
| `error-bars-defined` | S non-inferior; **degraded at layer 1** | stops at layer S (inconclusive); layer 1 degraded |

Later gates past a stop are reported above as description, not as claims.

**Secondary — difference-in-differences** of the delegation contrast, fan-out
against per check: every interval includes 0 (layer S −0.001 to +0.004; layer 1
−0.001 to +0.015, the largest `error-bars-defined` at +0.0147 [−0.0005, 0.0308]).

**Cost and time** per figure, fan-out ÷ per-check, mean of 38 per-figure ratios:

| | cost | input tokens | output tokens | turns | time vs sum | time vs max |
|---|---|---|---|---|---|---|
| `A\|B\|C_i ← D` | **0.77** [0.74, 0.79] | 0.65 | 1.07 | 0.83 | 0.93 | 2.18 |
| `A\|B ← C_i ← D` | **0.66** [0.63, 0.69] | 0.45 | 1.10 | 0.61 | 0.90 | 2.38 |

About $0.086 against $0.113 per figure for `A|B|C_i`, and $0.075 against $0.114
for `A|B ← C_i`. The predicted direction — cost and input tokens below 1 —
holds in both arms.

**Observed against planned half-widths.** Layer S intervals came out wider than
P2 planned: 0.0056–0.0073 where exp-02's variance predicted ≤ 0.0033, except
`micrograph-scale-bar`'s delegating arm, planned at 0.0253 and observed at
0.0133. The assumption that neither side would be noisier than exp-02's arms did
not hold at layer S; it is why three layer-S cells return inconclusive with
differences near −0.005.

### Reading

*Interpretation, separable from the numbers above.*

**D works as a dispatcher.** It reached all three checks in 99.5% of sessions,
so the fan-out conditions are the conditions they are labelled as — at the level
of the checks.

**Below the checks, delegation is optional, and the model treats the shared step
as belonging to the figure.** Under D, `classify-panels` was reached far less
than when each check ran alone, and when it was reached it was reached **once
per session, never once per check**. The layer-S row counts say the same from
the other side: under D, `individual-data-points` and `error-bars-defined` have
**identical** missing and spurious counts in both arms (7 / 25 and 6 / 15), and
`micrograph-scale-bar` is close. That reads as one panel inventory made once and
copied into each check's list. By the preregistered interpretation, the
delegating fan-out arm is **safe but optional** for the checks where it holds:
the arrangement labelled `A|B ← C_i ← D` mostly ran without its B skill.

**The fan-out costs `error-bars-defined` its applicability judgement**, in both
arms, by more than twice the margin. That is the one clear degradation, and it
is not explained by the skipped classification: it appears as strongly in
`A|B|C_i ← D`, where every check carries A and B inline and nothing is skipped.
It is consistent with interference — a check that runs last, after two others
have already read the figure, deciding applicability from their reading rather
than its own. Order was never varied (189/189 in the listed order), so position
and identity are confounded, as the threats anticipated: this cannot say whether
`error-bars-defined` degrades because it is that check or because it runs third.

**The spurious rows are small in rate and large in ratio.** Layer S moves by
about 0.005 at most, but spurious rows rise from 3 to 25 for two checks. They
matter less for layer S, which counts gold rows found, than as evidence of how
the model builds its answer under D.

**The saving is real and partly work not done.** The fan-out is 23% cheaper in
the monolith arm, where nothing is skipped — the cleaner estimate of what
sending the figure once saves — and 34% cheaper in the delegating arm, where part
of the saving is `classify-panels` not being called. Against per-check sessions
run in parallel, the fan-out is 2.2–2.4× slower.

**What it settles**: a single entry point dispatches reliably and is cheaper,
and it holds accuracy for `individual-data-points`. **What it does not**: it
does not hold for `error-bars-defined` at layer 1, and `micrograph-scale-bar`'s
layer S is too noisy to call. The pattern — a shared step done once per figure,
restated per check in the contract — motivates
[exp-04](exp-04-panel-major.md), which makes the contract share it too.

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
- **Descriptions still compete, within a closure.** Closure assembly removes
  every skill a session has no route to, which is what drew exp-02's stray
  calls. It cannot remove competition among skills that *are* reached: the
  fan-out puts all three checks' descriptions in front of a session working on
  all of them, so a check can be reached by discovery as well as by D.
- **The assembly changed after the run began.** The first full run was stopped
  after 153 `A|B|C_i ← D` sessions, made under the old whole-checklist
  assembly, when that assembly was judged to test the wrong thing. Those
  sessions were moved out of the run root and are not experiment data. The
  change was made on design grounds before any of them was scored, and the
  amendment is committed before the rerun — but it was a change made with a
  run in progress, and it is recorded as one.
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

## Gold this was scored against

**`gold-v1`** — the gold as of `cfbaa91c5`, 2026-09-28. The contract cleanup migrated `individual-data-points`' gold to `not_applicable` / `not_required` on 2026-10-02, after it. Its notebook pins the scorer to this tag (`soda_mmqc/gold.py`), so re-running it reproduces these numbers; re-scoring under the current gold is exploratory and recorded separately. Verified 2026-10-02: re-scoring a committed leaf against `gold-v1` reproduces its original analysis instance for instance.

**Changed since, 2026-10-04: gold, prose and contracts.** After exp-03, the contract cleanup (`thinking/plans/2026-09-30-contract-cleanup.md`) changed the `schema.json`, `eval-manifest.json`, `SKILL.md` prose and gold of seven `fig-checklist` checks: `individual-data-points`, `error-bars-defined`, `plot-axis-units`, `plot-gap-labeling`, `stat-significance-level`, `stat-test` and `replication-reporting`. A panel that is not a plot is now `not_applicable`, a plot with nothing to check is `PASS` with `not_required`, explanations are unscored and free text is scored semantically; damaged gold text was repaired. The result is tagged `gold-v2`. The numbers here are not re-scored under it (decided 2026-10-03): the sessions answered the prose and contracts of their time, so a re-score would measure the change of vocabulary rather than the models. The cleanup's effect is measured from exp-04 on.

## Status and next

Done. Preregistered, amended on 2026-09-28 to closure assembly before any kept
data, run in full, and read in *Findings*. The preregistration and its amendment
were committed before the runs, so

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

## Addendum 2026-09-30 — `error-bars-defined`'s layer 1: a format failure, not a judgement failure *(post-hoc)*

**This is exploratory with respect to the preregistration above.** It was done
after the findings were read, to see which panels drove the one clear
degradation. The preregistered verdict — `error-bars-defined` **degraded** at
layer 1 in both fan-out arms — stands as scored and is not revised here. What
changes is what that verdict means.

### What drives it

Every layer-1 instance of `error-bars-defined`, in all four conditions, traced
back to its figure, panel and field (5 replicates, 38 figures):

| | `A\|B\|C_i` | `A\|B\|C_i ← D` | `A\|B ← C_i` | `A\|B ← C_i ← D` |
|---|---|---|---|---|
| spurious "applicable", `Decision_and_explanation` | 239 | **630** | 199 | **508** |
| … of which the answer begins "not needed" | 234 | 624 | 195 | 504 |
| spurious "applicable", all other fields together | 5 | 6 | 6 | 4 |
| withheld "applicable", all fields | 16 | 41 | 18 | 34 |

The degradation sits almost entirely in **one field**. On a panel without error
bars, the skill asks three times for `Decision_and_explanation` to be exactly
`"not needed"`, and the schema description says so again. Under D the model
writes instead `not needed - micrograph panel with no error bars.` The manifest
treats a field as not applicable only on an exact `na_values` match (`""`,
`"not needed"`), so an annotated "not needed" is scored as an applicable answer
— a spurious applicability call — although the judgement it expresses is right.

Counting an answer that begins "not needed" as not applicable — which the
manifest does not do, and which is not a preregistered rule — the pooled layer-1
correct rate becomes:

| | `A\|B\|C_i` | `A\|B\|C_i ← D` | `A\|B ← C_i` | `A\|B ← C_i ← D` |
|---|---|---|---|---|
| as scored | 0.9651 | 0.9091 | 0.9701 | 0.9267 |
| "not needed …" read as not applicable | 0.9965 | 0.9929 | 0.9962 | 0.9944 |

About 94% of the gap disappears: from −0.056 to −0.004, inside δ₁ = 0.02
(pooled over instances, not the gate's per-figure mean). The field that decides
applicability, `error_bar_on_figure`, is essentially unchanged; its handful of
withheld instances come from missing rows, not wrong answers.

### Where

It is spread, not concentrated: 162 panels in 35 of 38 figures. Some figures flip
completely — in `s41592-023-01987/content/4` all seven micrograph panels are
annotated in 5 of 5 fan-out replicates and in 0 of 5 per check. By panel type
(from the other checks' gold), annotated answers rise under `A|B|C_i ← D` from 76
to 252 on micrograph panels, 72 to 173 on plots, 91 to 205 on other panels. The
annotation often names the panel's type — "micrograph panel", "schematic
panel" — which is what `micrograph-scale-bar`, always dispatched first, has just
established.

The per-panel table is committed as
`experiments/exp-03-checklist-entry/error-bars-defined-layer1-by-panel.csv`: one
row per figure, panel, field and error type, with counts per condition and an
example prediction.

### Reading

The fan-out does not break `error-bars-defined`'s applicability judgement. It
**erodes compliance with a fixed token inside a free-text field**, and the model
fills the space with what an earlier check in the same context decided. That is
interference, as the findings suggested — but in the *format* of the answer, not
in the decision.

It is also not specific to exp-03. The same field, in every committed run:

| experiment | arm | "not needed" written with an annotation |
|---|---|---|
| exp-01 | `pinned` (detailed) | 22% |
| exp-01 | `error-bars-defined@v2` (minimal) | **100%** |
| exp-02 | `pinned` | 18% |
| exp-02 | `error-bars-defined@v2` | 50% |
| exp-02 | `error-bars-defined@v3` | 27% |
| exp-02 | `classify-panels@v2-error-bars-defined@v3` | 35% |
| exp-03 | per check, `pinned` / `@v3` | 27% / 22% |
| exp-03 | fan-out, `pinned` / `all@v3` | **72% / 58%** |

So this artifact contributes to every `error-bars-defined` layer-1 comparison
made so far — including exp-01's 0.094 detailed-versus-minimal movement, which
exp-02 cited when sizing its margins, and in which the minimal arm annotated
every "not needed" it wrote.

### What follows

- **The contract is the defect**: a field scored for applicability against a
  fixed token should be an enum, not free text. A verdict and its explanation
  in one string invite exactly this. The fix — a separate enum field for the
  decision, with the explanation as its own free-text field — changes the
  contract, so it belongs to the next experiment ([exp-04](exp-04-panel-major.md)),
  not to a re-scoring of this one.
- **A contract audit across every check** — schema against manifest — is being
  done alongside, since the same omission may exist elsewhere.
