---
title: exp-02 — does splitting a skill into a DAG degrade it?
date: 2026-09-23
status: planned        # planned | running | done | abandoned
kind: experiment
extends:
tags: [experiment, skills, dag, delegation, non-inferiority]
---

# exp-02 — does splitting a skill into a DAG degrade it?

## Question

When one self-contained check skill is split into a chain of shared skills —
panel identification, then panel classification, then the check itself — does
the result get **worse**?

## Paper claim

That skills can be decomposed into a shared, hierarchical DAG **without paying
for it in accuracy**. This is the precondition for every claim about structure:
if factoring common work out of three checks into one shared skill degrades all
three, then the DAG is a cost centre and its maintainability argument has to
carry the whole burden alone.

Note what this is *not*. It is deliberately **not** a claim that the DAG
outperforms the monolith. At this stage that hypothesis would be premature —
nothing yet suggests a direction, and predicting one to look ambitious is how a
result gets written to fit. Non-inferiority is the honest question: we want to
know whether decomposition is *safe*, because it is the structure everything
later depends on.

[exp-01](exp-01-skill-verbosity.md) tested how a skill is *written*, and named
this gap in its own threats to validity: *"Leaf-only. No shared skills exist in
this checklist, so nothing here transfers to a chained DAG."* This is that.

## Hypothesis

**Depth 2 and depth 3 are each non-inferior to depth 1** on layer S, on layer 1
and on layer 2 — and each delegates as instructed, which is a precondition for
those three meaning anything.

| | chain | skills |
|---|---|---|
| **depth 1** | check, everything inline | 1 |
| **depth 2** | check → `identify-panels` | 2 |
| **depth 3** | check → `classify-panels` → `identify-panels` | 3 |

No improvement is predicted. An arm that scores *better* is reported as
observed, but it is not what this experiment tests and it may not be relabelled
afterwards as though it were.

What would count as being wrong: either deeper arm degrading by more than the
margin below at any gate. That is a live possibility, and there are two distinct
mechanisms for it. Delegation can lose information at the boundary — the leaf
works from what the shared skill reported rather than from the figure. And the
shared skill necessarily serves three callers, so it carries the union of what
they need, which is more than any one of them asked for.

## Decision criteria

Written before the run, so the threshold cannot drift to meet the data.

### Endpoints, and why they are tested in this order

Four endpoints, tested in a **fixed sequence**. The order is not a ranking; it
is the conditional structure of the layers themselves, which exp-01's notebook
already warns about — an arm that withholds more has fewer instances left for
layer 2, so a layer-2 mean compared across arms whose layer 1 differs is a
comparison between two different populations. Each gate must hold for the next
to mean anything.

| # | endpoint | statistic | what it catches |
|---|---|---|---|
| **0** | **skill invocation** | fraction of sessions whose `skill_trace.json` shows the expected chain | an arm that silently did not delegate is not the arm it claims to be |
| **1** | **layer S** | `correct_row` as a fraction of gold rows, per check per `list_key` | panel enumeration moving out into `identify-panels` |
| **2** | **layer 1** | `correct_applicable` + `correct_NA` as a fraction of all profiled instances, per check | classification moving out into `classify-panels` |
| **3** | **layer 2** | `mean_score` per property, on applicable instances, paired by example | the check-specific prose that stayed in the leaf |

Layers S and 1 are the primary endpoints, and that is an empirical choice rather
than a stylistic one. On exp-01's data **for these same three checks**, layer 1
moved by **0.094** on `error-bars-defined` between the detailed and minimal
arms, against a largest layer-2 property difference of 0.074 across those three.
Layer S moved by 0.011 on `micrograph-scale-bar`. Both aggregate hundreds to
thousands of rows per replicate, so they are also the best-measured things
available. They are where prose acts, and — being the two stages that move out
of the leaf — they are where delegation should act.

The restriction to these three checks matters and is not a rhetorical hedge.
Across all eleven of exp-01's checks, layer 2 moved far more than this: up to
**0.261** on `replication-reporting · involves_replicates`. Layer 2 is capable
of large swings; it is simply the noisiest per property, and the three checks
chosen here are not the ones where it swung hardest.

A fixed-sequence procedure also settles multiplicity without arbitrary choices:
each gate is tested at α = 0.05 in a preregistered order and testing stops at
the first failure, which controls the family-wise error rate with no correction.

### Margins, one per layer

A single margin across three layers would be a category error: the layers sit on
different scales and are measured to different precision. Each margin is set
between two bounds, and the principle is stated here so the numbers can be
checked against it rather than taken on trust:

> **Lower bound:** the margin must exceed the measurement's 95% half-width, or
> the claim cannot be made whatever the data say.
> **Upper bound:** the margin must be smaller than the effects the endpoint is
> known to show, or non-inferiority is satisfied trivially and means nothing.

All half-widths below are **at five replicates**, which is what the replicate
count was chosen to deliver — see *Why five replicates* under Design.

| gate | endpoint | δ | half-widths on the three checks | largest effect the endpoint shows |
|---|---|---|---|---|
| 1 | layer S | **0.0125** | 0.0099, 0.0094, 0.000 | 0.094 |
| 2 | layer 1 | **0.02** | 0.0094, 0.0086, 0.0026 | 0.199 |
| 3 | layer 2 | **0.02** | 0.000–0.0195, all 17 properties | 0.261 |

Gate 0 is a rate with a floor, not a difference with a margin, and is specified
separately below.

δ_S is 0.0125 rather than 0.01 because 0.01 leaves almost nothing in hand: the
half-widths of 0.0099 and 0.0094 clear it by 0.0001 and 0.0006, so any noise
above what exp-01 showed would send the gate inconclusive. 0.0125 keeps real
slack and is still far below the layer-S movements prose caused in exp-01 —
0.094 on `single-channel-for-overlay` and 0.023 on `stat-significance-level`.

### How these half-widths were estimated, and one way to get it wrong

**The relevant variance is measurement noise, not the spread of exp-01's
effect.** This is worth stating explicitly because the first version of this
note got it wrong, and the error was not conservative.

The statistic at every gate is, per example,
`d_e = rate(depth k) − rate(depth 1)`. Its variance across examples has two
components: the noise in measuring each arm, and the genuine heterogeneity of
the effect between examples. Under this experiment's hypothesis the effect is
zero, so only the first component survives, and it is estimable **from one arm
alone**:

```
Var(d_e) = 2σ²_e / n          σ²_e = between-replicate variance for example e
SE       = sqrt( (2/n) · mean(σ²_e) / 38 )      n = replicates per arm
```

`σ²_e` is a property of the measurement, not of the replicate count: it is
estimated from exp-01's three replicates and then projected to the five exp-02
will run. The factor of two is the two arms, whose session noise is
independent — they are separate sessions, and whatever makes an example hard has
already cancelled in the pairing.

Estimating it instead from exp-01's `minimal − detailed` contrast — which is
what the first draft of this note did — folds in the heterogeneity of the
*verbosity* effect, which has nothing to do with delegation. That is not merely
an inflated estimate, it is a different quantity, and it moves in both
directions: `error-bars-defined`'s layer S looked precise at 0.007 by that route
and is actually 0.012, while `individual-data-points · decision` looked hopeless
at 0.041 and is actually 0.007.

So every half-width in this note comes from exp-01's **detailed arm only**,
three replicates over 38 examples per check — the arm whose prose exp-02
inherits — and is quoted at the five replicates exp-02 will run.
The comparison between exp-01's arms is the answer to exp-01's question and is
immaterial to this one.

**The assumption this rests on**, stated so it can be checked against the
result: that depth 2 and depth 3 are no noisier than depth 1. A longer chain has
more places to vary, so if delegation raises the per-example variance the real
intervals will be wider than planned here, and a gate may return inconclusive
where this sizing said it would not. exp-02 reports its own observed
half-widths beside these, so the assumption is visible rather than buried.

### Verdicts

All confidence intervals are paired by example and bootstrapped **over the 38
examples**, which is the clustering unit: rows within one figure share a
figure, a caption and a curator, and are not independent draws. The bootstrap is
a seeded percentile bootstrap, 10,000 resamples — seeded because an interval a
reader cannot recompute is not one an experiment can preregister, and percentile
rather than normal because layer S sits above 0.97, where the sampling
distribution is skewed and a symmetric interval would be centred on a point it
should not be centred on.

The statistic for gates 1 and 2 is the **mean of per-example rate differences**,
which weighs every example alike. That is deliberately not the ratio of sums a
stacked count plot shows, where a twelve-panel figure counts twelve times a
one-panel figure. Only the per-example form has an example-level interval, and
only it matches what `arm_contrast` does at gate 3.

- **Non-inferior** if the lower bound of the 95% CI on (depth *k* − depth 1)
  lies above **−δ** for that gate's δ.
- **Degraded** if a CI lies entirely below −δ.
- **Inconclusive** if a CI straddles −δ — including the case where the interval
  is simply wider than the margin. A reportable result, not a failure.

Two comparisons, **depth 2 vs depth 1** and **depth 3 vs depth 1**, each runs
the sequence independently. They are two separate claims, not a family from
which the better one is chosen, so nothing is corrected across them.

At gate 0 the margin is not used: an arm whose expected chain is invoked in
fewer than **95%** of its sessions is reported as not having been run as
specified, and its scores are reported but carry that caveat. Invocation is an
endpoint in its own right and not merely a precondition, because whether a model
reliably calls a skill it was told to call is the mechanism every deeper
topology depends on.

### Every property clears the noise floor, at five replicates

At gate 3, a property can only support a 0.02 claim if its 95% half-width is
smaller than 0.02 — otherwise even an observed difference of exactly zero leaves
an interval whose lower end falls below −0.02, and the claim cannot be made
whatever the data say.

At three replicates one property failed that test. At five, **all 17 clear it**:

| property | half-width, n=3 | half-width, n=5 |
|---|---|---|
| `individual-data-points · plot` | 0.0252 ✗ | **0.0195** ✓ |
| `micrograph-scale-bar · from_the_image` | 0.0090 | 0.0070 |
| `error-bars-defined · Decision_and_explanation` | 0.0077 | 0.0059 |
| `individual-data-points · decision` | 0.0069 | 0.0053 |
| `individual-data-points · explanation` | 0.0068 | 0.0052 |
| `error-bars-defined · from_the_caption` | 0.0063 | 0.0049 |
| `micrograph-scale-bar · micrograph` | 0.0030 | 0.0024 |
| ten further properties | 0.000 | 0.000 |

So no property is set aside in advance, and the awkward case that shaped earlier
drafts of this note — `individual-data-points` entering with almost nothing
measurable — does not arise. That check contributes all five of its properties.

`plot` clears by 0.0005, which is thin. It is the property where the model
decides whether a panel is a plot at all, and its per-example spread is genuine
run-to-run disagreement. If exp-02's observed half-width there exceeds 0.02 it is
reported as uninformative on the same terms a preregistered exclusion would
have been, rather than being counted on a margin the measurement did not reach.

Observed half-widths are reported for all 17 properties, so a reader can see
where this prediction held.

### Non-response is scored, not excluded

As in exp-01. A session answering `outputs: []` scores as a **fully missing row
set** — `correct_row: 0`, `missing_row: N` — rather than being dropped, so an
arm that says nothing is penalised rather than flattered. Sessions that *fail*
write no prediction and leave the mean, so **failures are counted and reported
per arm**, and a difference of more than 5% in failure rate between arms is
itself a finding, reported whatever the scores say.

## Design

| | |
|---|---|
| Starting point | `fig-checklist-exp01`'s detailed (`v1`) prose, edited to compose — not preserved verbatim |
| Checklist | `fig-checklist-exp02`, built by `experiments/exp-02-delegation-depth/build_checklist.py` |
| Checks | `micrograph-scale-bar`, `individual-data-points`, `error-bars-defined` |
| Arms | `pinned` (v1, depth 1), `<check>@v2` (depth 2), `<check>@v3` (depth 3) |
| Held fixed | contracts (`schema.json`, `benchmark.json`, `eval-manifest.json`), gold, examples, model, provider |
| Model | `claude-sonnet-5`, pinned by exact name, not the `sonnet` alias |
| Provider | `claude-sdk` |
| Replicates | 5 — see below |
| Examples | 38 per check, 114 example-checks per arm |
| Sessions | 1,710 |
| Runner | `experiments/exp-02-delegation-depth/run.py` |

The independent variable in one sentence: **how many skills the same
instructions are spread across.**

**Why five replicates**, where exp-01 used three and the replicate exploration
argued against five. The difference is what the variance turned out to be made
of. Replicates reduce *measurement noise* as `1/n` and do nothing about
example-to-example heterogeneity of an effect. exp-01's paired contrast is
dominated by the latter, so more replicates could not help it; exp-02's
endpoints, planned under a null, are pure measurement noise, so they can.

Against exp-01's detailed arm, what the extra 684 sessions buy is specific:

| endpoint | n=3 | n=5 |
|---|---|---|
| `individual-data-points · plot` | 0.0252 — below the floor | 0.0195 — clears |
| `micrograph-scale-bar · layer S` | 0.0128 | 0.0099 |
| `error-bars-defined · layer S` | 0.0122 | 0.0094 |

At three, layer S could only carry δ_S = 0.015 and one property had to be set
aside. At five, δ_S tightens to 0.0125 and nothing is set aside. Seven would buy
a further 0.0015 of half-width for another 684 sessions, which is where the
returns stop being worth it.

### How the three depths are built

The three depths are **compositions of the same authored blocks**, and a builder
script is what makes that true rather than aspirational. Hand-writing three
versions of eleven files and hoping the wording matches is exactly the thing
that cannot be verified afterwards; generating them from one source can be.

| block | what it is |
|---|---|
| **P** | panel identification — labels, locations, caption mapping |
| **C** | panel classification — what kind of content each panel holds |
| **L** | the check-specific remainder |

| depth | inline | delegated |
|---|---|---|
| 1 | P + C + L | — |
| 2 | C + L | P |
| 3 | L | C, then P |

The same instructions are present at every depth; what moves is **where they
live**. The evaluation contracts sit above the version directories, which makes
the control structural rather than asserted: three versions of one skill cannot
be scored by different rulers.

### The blocks are authored for exp-02, not inherited

`fig-checklist-exp02` does **not** preserve the wording of `fig-checklist` or of
`fig-checklist-exp01`, and it does not need to. The blocks start from the
baseline prose and are then edited so that they compose cleanly — so that a
sentence belonging to classification sits in `C` and not halfway into `L`.

This costs nothing because **exp-02 is not compared to exp-01**. exp-01 supplies
variance estimates for sizing the margins, and nothing else; the comparison that
answers this experiment's question is entirely internal to exp-02, between three
depths built from one source and scored by one contract. A result here is read
against the other depths, never against a number from another checklist.

Trying instead to hold the wording fixed to the baseline would force the split
to fall wherever the existing prose happened to break, which is a worse
experiment for the sake of a comparison nobody will make.

### C classifies panel content type, and every check uses it

`classify-panels` is a new shared skill with **one job**: name what kind of
content each panel holds — micrograph, plot, blot, omics visualization,
schematic, and whatever further types the figures require.

That single job is why the same text can sit in all three monoliths without
padding them. Each check genuinely consumes it: `micrograph-scale-bar` asks
whether a panel is a micrograph, `individual-data-points` and
`error-bars-defined` ask whether it is a plot. No check carries classification
prose it has no use for, so the reference arm is not weighed down — and a
non-inferiority result bought by weighing down the baseline would be worth
nothing.

It deliberately stops short of describing **axes**. Tick labels, scales and
axis titles are used by the two plot checks and never by `micrograph-scale-bar`,
so they stay in `L` where they are needed rather than becoming exactly the kind
of dead weight the paragraph above avoids. This is narrower than the shipped
`classify-plot-panels`, which is also plot-only by design — it returns an empty
`plot_types` and a free-text note for a micrograph, so it has nothing to say to
`micrograph-scale-bar` and cannot serve as `C`.

Because `C` is identical at every depth, depth 3 differs from depth 1 in exactly
one respect: the classification prose is reached through a call instead of being
read in place.

### What the split unavoidably perturbs

A skill that delegates must say so, so depths 2 and 3 carry call instructions
that depth 1 does not, and the shared skills carry their own frontmatter and a
short section saying how to state what they found. The wording of `P`, `C` and
`L` is identical across depths; the connective tissue around them cannot be.

Two things were tightened before this experiment so that the perturbation is as
small as it can be. The session now has **one tool, `Skill`** — the `Read` tool
was removed, since the example's content travels with the request and no skill
in any checklist reaches for a file, so nothing the model saw can come from
somewhere this note does not account for. And a skill owns a **schema if and
only if it is a leaf**, so delegating no longer introduces a second output
contract alongside the check's.

**So what this measures is the combined effect of splitting a skill and of
inserting the call that makes the split work.** That is not a flaw to be
engineered away — it is what adopting a DAG actually costs, since no one can
have the decomposition without the calls. It is stated here so the result is
read as what it is, rather than as a claim about decomposition in the abstract.

### Prep work — done, 2026-09-23

Two gates of this experiment could not be measured at all, and the margins for
them could not be sized, so this was a precondition rather than a convenience.
It ran entirely on exp-01's committed data and cost nothing. **All three steps
are complete, and their results are folded into the margins above.**

**P1 — per-example layer S and layer 1 counts. ✅**
`layer_s_counts` and `layer1_counts` sum examples within a leaf, by design:
*"Examples are summed within a leaf — layer S is a count over row sets."* That
is the right default for a report and the wrong one for a paired interval, which
needs the example on the row so it can be bootstrapped over. `run.records`
already carries example identity — it is what `arm_contrast` pairs on — so this
is a grouping change, not new measurement.

It belongs in `soda_mmqc/reporting/aggregate.py` beside the functions it mirrors,
not in this experiment's scripts: every later experiment on topology needs the
same thing, and a copy living under `experiments/` would be the version that
rots. Tests come with it, in the repo's normal style.

Delivered as `layer_s_counts_by_example`, `layer1_counts_by_example` and
`rate_contrast`, the paired rate difference the two gates need. The pooling
functions are unchanged and provably so: summing either per-example frame over
`example` reproduces the existing function's output exactly, on all eleven
checks of exp-01's committed runs. No published number moves.

**P2 — measure the null-hypothesis interval for every gate. ✅** From exp-01's
**detailed arm alone**, as *How these half-widths were estimated* sets out. The
first attempt at this used exp-01's between-arm contrast instead and was wrong:
that quantity carries the heterogeneity of the verbosity effect, which is the
answer to exp-01's question and irrelevant to this one. It was not a
conservative error — it made `error-bars-defined`'s layer S look twice as
precise as it is, and four layer-2 properties look hopeless when they are fine.

**P3 — fix every margin and the replicate count, and commit them. ✅**
δ_S = 0.0125, δ₁ = 0.02, δ₂ = 0.02, at **five** replicates. The replicate count
is part of this decision rather than separate from it: because these variances
are measurement noise, they fall as `1/n`, and five is what makes δ_S = 0.0125
hold with slack and leaves no property below the gate-3 floor.

Doing P1–P3 after the run would have meant choosing a margin with the results
already visible, which is the one thing preregistration exists to prevent.

### What has to be built

| # | artefact | path | state |
|---|---|---|---|
| P1 | Per-example counts, `rate_contrast` | `soda_mmqc/reporting/aggregate.py` | **done**, 9 tests, suite green |
| P2–P3 | Margin sizing | this note, gates 1 and 2 | **done**, fixed from exp-01 data |
| A | `Read` removed; `Skill` is the only tool | `soda_mmqc/config.py`, `agentic/` | **done** |
| B | Leaf ⇔ owns `schema.json`; intermediates own nothing | `soda_mmqc/config.py` | **done** |
| 1 | Block **C**, `classify-panels` | `…/fig-checklist-exp02/classify-panels/v1/` | **drafted**, at the gate |
| 2 | Block **P**, `identify-panels` | `…/fig-checklist-exp02/identify-panels/v1/` | to author from exp-01 prose |
| 3 | Blocks **L** | `experiments/exp-02-delegation-depth/leaves/<check>.md` | to author from exp-01 prose |
| 4 | Builder | `experiments/exp-02-delegation-depth/build_checklist.py` | to write |
| 5 | Leaf versions `v1`/`v2`/`v3` + contracts | `…/fig-checklist-exp02/<check>/` | generated by the builder |
| 6 | Runner | `experiments/exp-02-delegation-depth/run.py` | to write, from exp-01's |
| 7 | Runs | `experiments/runs/exp-02-delegation-depth/` | — |
| 8 | Analysis | `notebooks/experiments/exp-02-delegation-depth.ipynb` | to write |
| — | Note | `thinking/experiments/exp-02-delegation-depth.md` | this file |

The checklist lives in `soda_mmqc/data/checklist/fig-checklist-exp02/`, beside
`fig-checklist-exp01`, because that is where a checklist belongs. The two shared
skills are **authored there directly** — they are the source of truth for `P`
and `C`, and the builder reads their bodies to inline at the shallower depths,
so each block exists once. Only the per-check `L` blocks live under
`experiments/`, as build inputs rather than checklist artefacts.

**Contracts come from `fig-checklist-exp01`**, not from `fig-checklist`. The
margins in this note were estimated from exp-01 predictions scored against
exp-01's `schema.json` and `eval-manifest.json`, so inheriting those same
contracts is what keeps the estimates applicable to what exp-02 measures.

The runner generalises from exp-01's with one change: `unpin={check: ("v1",
"v2", "v3")}` instead of two versions.

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|
| | all three | `python experiments/exp-02-delegation-depth/run.py` | est. $100–140 | `experiments/runs/exp-02-delegation-depth/` |

1,710 sessions, estimated from exp-01's actual $130 over 2,616 sessions
(≈ $0.05 each), with headroom because delegation adds turns and re-reads
context.

## Findings

*Not yet run.*

## Threats to validity

- **Splitting and calling are measured together.** Depths 2 and 3 carry call
  instructions depth 1 does not, and the shared skills carry their own
  frontmatter and output sections. `P`, `C` and `L` are word-identical across
  depths, but the connective tissue cannot be, so the effect estimated here is
  decomposition *plus* the calls that make it work. Nothing separates them,
  because nothing can: a DAG without the calls is not a DAG.
- **`C` is one shared skill serving three callers**, which is only unproblematic
  because its single job — naming the panel's content type — is one all three
  checks consume. Had it carried axis description as well, the two plot checks
  would have used it and `micrograph-scale-bar` would have carried it for
  nothing. That judgement is a design choice and a reader may disagree with
  where the line was drawn.
- **The intermediate is prose, not a contract.** An earlier draft of this note
  recorded that delegation inserts an output contract, because shared skills
  used to carry a runtime `schema.json`. They no longer do: a skill owns a
  schema if and only if it is a leaf, so `identify-panels` and `classify-panels`
  state their answer into the session rather than against a contract. What
  remains is that the intermediate answer is *stated* at all, which a monolith
  never has to do — a step that can be skipped, or done and then ignored.
- **Three checks, and no tally across them.** Each check stands on its own
  interval; there is no ≥ 8/11 style agreement rule to lean on, and no claim
  that these three represent the eleven.
- **`micrograph-scale-bar` sits near the ceiling** — layer S 0.994, layer 1
  0.988 on exp-01. It can lose and can barely gain. Non-inferiority is the right
  test for a ceiling, but the check contributes little sensitivity.
- **Every half-width here assumes depth 2 and depth 3 are no noisier than depth
  1.** The variances are measured on exp-01's detailed arm, because that is the
  arm whose prose exp-02 inherits and because a null-hypothesis interval needs
  only one arm. But a longer chain has more places to vary: if delegation raises
  the per-example variance, the real intervals are wider than planned and a gate
  may return inconclusive where this sizing said it would not. exp-02 reports
  its observed half-widths beside the planned ones, so the assumption is
  checkable rather than buried.
- **The variances come from a different checklist.** They are measured on
  `fig-checklist-exp01`'s prose, not on the baseline prose exp-02 builds from.
  The magnitude of run-to-run disagreement should carry across, but it is an
  assumption, not a measurement of the arms actually run.
- **`individual-data-points · plot` clears the floor by 0.0005** at five
  replicates. That is thin enough that the real run could land outside it, in
  which case that property is reported as uninformative rather than counted.
- **Depth 1 is a reconstruction, not production.** The shipped `fig-checklist`
  leaves already delegate; depth 1 is built by inlining them back. A number here
  is not a number about production.
- **Bootstrapping over 38 examples** is itself noisy at that n, so interval
  coverage is approximate rather than exact.
- **Applicability moves between runs.** The replicate exploration saw one
  session in a hundred classify every panel as not applicable where nine others
  did not. Layer 1 is gate 2 here, so that noise sits on a primary endpoint.
- **One model, one provider, one point in time.** Pinned by exact name so the
  result stays attributable, but it is one model's response to being split.
- **Skills derived by one person, who holds the hypothesis.** The builder
  composes from baseline prose rather than from fresh drafts, which limits the
  freedom to write an arm into winning, but it was not blind.

## Status and next

Planned, not yet preregistered, not yet run. **P1–P3 are done**: the per-example
frames and `rate_contrast` exist and are tested, the paired intervals for layers
S and 1 have been measured on exp-01's committed data, and every margin in this
note is fixed. What remains before a run is the builder, the checklist it
generates, and the runner. Preregistration is the commit order, so after that

```bash
git log --oneline --reverse -- \
  thinking/experiments/exp-02-delegation-depth.md \
  experiments/runs/exp-02-delegation-depth/
```

shows the prediction predating the data.

What it settles if it holds: that decomposition is safe, which is the licence
for every later experiment on topology. What it opens if it does not: whether
the loss sits at the identification boundary or the classification one, which
the gate sequence localises — layer S failing points at `identify-panels`,
layer 1 failing at `classify-panels`.
