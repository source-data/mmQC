---
title: exp-01 — detailed skill instructions against minimal ones
date: 2026-09-20
status: planned
kind: experiment
extends:
tags: [experiment, skills, verbosity]
---

# exp-01 — detailed skill instructions against minimal ones

## Question

Does a skill that spells out its procedure produce better answers than one
that states only what it is for?

## Paper claim

That how a skill is *written* — not only how skills are decomposed or chained
— measurably changes what the agent produces. This is the simplest form of
that claim: one skill, one entry point, no DAG, nothing varying but the prose
below the frontmatter.

It is the baseline the decomposition and chaining results are read against.
If instruction detail turns out not to matter at this scale, a later claim
that *structure* matters has to explain why.

## Hypothesis

**The detailed version scores better on all three evaluation layers.**

| layer | what improves, if the hypothesis holds |
|---|---|
| **S** — structural | more `correct_row`, fewer `missing_row` and `spurious_row`: the detailed skill enumerates panels more reliably |
| **1** — applicability | more instances correctly classified applicable or N/A: the detailed skill says when a field does not apply |
| **2** — matching | higher `mean_score`: the detailed skill extracts and phrases the answer closer to gold |

The direction is predicted for all three, and predicted **before** the runs
exist. A result on two of three is not this hypothesis confirmed — see the
decision criteria.

What would count as being wrong: the minimal version scoring equal or better
on any layer by the threshold below. That is a live possibility. The minimal
skill keeps the full frontmatter `description`, which already states the
check's purpose, and a shorter prompt leaves the model less to contradict
itself with.

## Decision criteria

Written before the run, so the threshold cannot drift to meet the data.

### Endpoints

Per check, per arm, averaged over the three replicates:

| layer | statistic |
|---|---|
| **2 (primary)** | `mean_score`, instance-weighted across properties |
| **S** | `correct_row` as a fraction of gold rows |
| **1** | instances labelled `correct_applicable` or `correct_NA`, as a fraction of all profiled instances |

Instance-weighted, not a mean of property means: `mean_score` is `0.0` when a
property has no eligible instances, which means *nothing to score*, and
averaging those zeros both depresses the score and injects variance when
applicability moves between replicates.

Comparison is **paired by check** across the eleven. Never pooled across
checks: they have different schemas and different difficulty.

### Threshold

**0.01 absolute difference, and agreement in ≥ 8 of 11 checks.**

0.01 is about three times the per-check standard error the replicate probe
measured at n=3 (0.0034, on the noisiest check, so an upper bound), and about
ten times the standard error of the mean across eleven paired checks. It is
comfortably detectable and small enough not to require a large effect to
register. See
[`exploration-replicate-variability.md`](exploration-replicate-variability.md).

- **Supports the hypothesis if** the detailed arm is ahead by ≥ 0.01 on the
  mean paired difference **on all three layers**, with ≥ 8/11 checks agreeing
  in direction on the primary endpoint.
- **Refutes it if** the minimal arm is ahead by ≥ 0.01 on any layer with
  ≥ 8/11 agreeing, **or** all three layers land within ±0.01 of zero.
- **Partial, and reported as partial, if** some layers clear the threshold and
  others do not. This is the likeliest outcome and it is **not** support: the
  hypothesis named all three. A partial result may be preregistered as its own
  experiment and tested again; it may not be relabelled as confirmation of a
  weaker claim it was not written to test.
- **Inconclusive if** direction is split below 8/11 on the primary endpoint
  while no layer clears the threshold. A reportable result, not a failure.

### Non-response is scored, not excluded

A session that answers `outputs: []` scores as a **fully missing row set** —
`correct_row: 0`, `missing_row: N` — rather than being dropped. A skill so
thin the model returns nothing is worse, and excluding those examples would
make the failing arm look better.

Sessions that *fail* write no prediction and so leave the mean. **Failures are
therefore counted and reported per arm**, and a difference of more than 5% in
failure rate between arms is itself a finding about the arms, reported
whatever the scores say.

## Design

| | |
|---|---|
| Checklist | `fig-checklist-exp01` @ `3f75bc9a` |
| Arms | `pinned` (every skill at its manifest pin, the detailed `v1`) and `<check>@v2` (that check at the minimal `v2`) |
| What varies | the prose below the frontmatter of one skill, and nothing else |
| Held fixed | contracts (`schema.json`, `eval-manifest.json`, `benchmark.json`), gold, examples, model, frontmatter — **identical between arms**, including `description` |
| Decomposition | none. Every check is a leaf; no shared skills exist in this checklist |
| Model | `claude-sonnet-5`, pinned by exact name, not the `sonnet` alias |
| Provider | `claude-sdk` |
| Replicates | 3, from [`exploration-replicate-variability.md`](exploration-replicate-variability.md) |
| Examples | 436 example-checks over 11 checks |
| Sessions | 2,616 |
| Runner | `experiments/exp-01-skill-verbosity/run.py` |

The independent variable in one sentence: **`v1` states a procedure, `v2`
states only the frontmatter and the opening paragraph.** `v2` is `v1`
truncated, not an independent draft.

The control is structural rather than asserted: the evaluation contracts sit
above the version directories, so two versions of one skill cannot be scored
by different rulers.

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|
| | both | `python experiments/exp-01-skill-verbosity/run.py` | | `experiments/runs/exp-01-skill-verbosity/` |

## Findings

*Not yet run.*

## Threats to validity

- **`v2` is `v1` truncated.** The arms are nested, not independent drafts, so
  this measures *removing* instruction rather than two ways of writing a
  skill. A minimal skill written from scratch might do better than one that
  is a beheaded long one.
- **`v2` is not zero instruction.** It keeps the frontmatter `description`
  and the opening paragraph, both of which state the check's purpose. The
  contrast is detail versus orientation, not detail versus nothing.
- **Leaf-only.** No shared skills exist in this checklist, so nothing here
  transfers to a chained DAG, where prose also has to make delegation happen.
- **Neither arm is the shipped `fig-checklist`.** Its leaves delegate to
  `identify-panels`; these were de-delegated to make the comparison leaf-only.
  A baseline number here is not a number about production.
- **The eleven checks are not independent.** They score the same figures
  against gold written by the same curators under one convention.
- **One model, one provider, one point in time.** Pinned by exact name so the
  result stays attributable, but it is one model's response to verbosity.
- **Replicate count sized from one check.** Three comes from the noisiest
  check's single-arm spread; a paired difference has its own variance, which
  that bounds rather than measures.
- **Applicability moves between runs.** The replicate probe saw one session
  in a hundred classify every panel as not applicable where nine others did
  not. That is layer 1 noise, and layer 1 is a predicted endpoint here.
- **Skills authored by one person**, who also holds the hypothesis. The prose
  was written before this note and not adjusted to it, but it was not blind.

## Status and next

Preregistered, not yet run. The note is committed before any runs, so
`git log --oneline --reverse -- thinking/experiments/exp-01-skill-verbosity.md
experiments/runs/exp-01-skill-verbosity/` shows the prediction predating the
data.

Analysis in
[`notebooks/experiments/exp-01-skill-verbosity.ipynb`](../../notebooks/experiments/exp-01-skill-verbosity.ipynb),
which reads the committed runs and never triggers one.

---

## Addendum, 2026-09-21: the sensitivity figure, re-derived per property

**The preregistered threshold above is unchanged and stands as written.**
This records that one number in its *justification* has since been
re-derived, so that a reader is not misled by it. Nothing here alters a
decision criterion; the criteria were fixed before any result was seen and
stay fixed.

The Threshold section justifies 0.01 as "about three times the per-check
standard error the replicate probe measured at n=3 (0.0034, on the noisiest
check, so an upper bound)".

**0.0034 is not an upper bound.** It came from pooling the check's eight
leaf properties into one instance-weighted mean, which the replicate probe
did deliberately and which
[`exploration-replicate-variability.md`](exploration-replicate-variability.md)
now re-derives per property in its own addendum. Per property, on the same
data:

| | SE of a paired difference, n=3 |
|---|---|
| pooled across properties *(the figure cited above)* | 0.0034 |
| `outputs[].replicate_statements` | **0.0199** |
| `outputs[].n_reported` | 0.0081 |
| six other properties | below 0.0040 |

So 0.01 is comfortably detectable on six of eight properties, marginal on
`n_reported`, and **below the noise floor on `replicate_statements`**,
where no feasible replicate count reaches it — n=10 still gives 0.0109.

### How to read the result, without moving the goalposts

The threshold and the ≥ 8/11 agreement rule apply as preregistered. The
refinement is in interpretation, and only in one direction — it makes a
*null* weaker, never a positive stronger:

- A difference at or above 0.01 on a property with SE below 0.0040 means
  what the preregistration says it means.
- A **null on `replicate_statements` is not evidence of no effect.** The
  measurement cannot resolve 0.01 there, so that property should be
  reported as uninformative rather than as a check that disagreed.
- The ≥ 8/11 rule counts *checks*, not properties, so this does not change
  how it is tallied. But if the tally turns on a check whose signal lives
  in `replicate_statements`, say so in the result rather than letting the
  count carry it silently.

This is a limitation of the measurement, not of the run, and more sessions
would not fix it.

---

## Addendum, 2026-09-24: two checks rebuilt and re-run

**The preregistered hypothesis and decision criteria above are unchanged and
stand as written.** This records a defect in how two of the eleven *arms* were
built, found after the run, and the correction made to it. No threshold moved,
no endpoint changed, and nothing here was decided by looking at a result.

### What was wrong

`plot-gap-labeling` and `replication-reporting` were converted from prompts
written as **pseudocode rather than narrative**:

```
IF panel is not a quantitative plot:
    SET is_a_plot = "no"
    SET tick_sequence_anomaly = "not_applicable"
    ...
    CONTINUE to next panel
```

24 such lines in `plot-gap-labeling`'s `v1`, 30 in `replication-reporting`'s,
each under a `## Logic` heading. Both files also carried example headings whose
JSON blocks were **empty** — 4 of 4 and 3 of 3 — so the skill announced worked
examples and then showed none.

This is a defect in constructing the **detailed** arm. exp-01 contrasts a skill
that spells out its procedure against one that states only what it is for. A
`v1` that is a register error is not the thing the hypothesis names, so the
contrast it produced was not the contrast this note preregistered — for these
two checks only.

It is worth being precise about what the error was **not**. Both checks were
converted from the version `production.json` pins, so this was not a
wrong-version mistake; the pinned prompts are themselves the pseudocode ones.
Nine of the eleven checks are unaffected, and a check of all eleven found no
other `v1` with empty example blocks.

### What changed

| check | was | now |
|---|---|---|
| `plot-gap-labeling` | prompt.1, pseudocode | **prompt.2, narrative** |
| `replication-reporting` | prompt.3, pseudocode | **prompt.1, narrative** |

The inline JSON block was removed from both: the schema is enforced as
structured output, so an inline example is a second and unenforced statement of
the same contract. `v2` was re-truncated from the new `v1` in each case, so the
arms stay nested — `v2` is a prefix of `v1`, as the design requires, and the
frontmatter stays identical between them.

### Choosing narrative over the pinned prompt is deliberate

Neither new source is the production pin. That is a choice, not an oversight,
and it is made with the next experiment in view.

The work that follows decomposes these prompts into a DAG of shared skills —
panel identification, panel classification, and a check-specific remainder.
**Prose can be cut at its seams.** A paragraph that explains how to find the
panels of a figure can be lifted into a skill of its own, called from where it
used to sit, and read by a model as the same instruction in a different place.

**Pseudocode cannot be cut that way.** `IF ... SET is_a_plot = "no"` binds a
control-flow step to a field assignment in one indivisible line; moving the
panel-finding half into a shared skill leaves a fragment that assigns to a
field the shared skill does not own, and a remainder that branches on a
variable nothing set. The decomposition the next experiment measures would not
be expressible, and any result would be about the mangling rather than about
the split.

So the register is not cosmetic here. Narrative prose is a precondition for the
question the next experiment asks, and these two checks are being brought to
the same footing as the other nine before that question is put.

### What was re-run

Both arms of both checks, three replicates: **456 sessions**. The other nine
checks were not re-run, and their predictions remain the ones frozen at
`7a816e5e`.

### One consequence to read beside the result

The narrative prompts name **fewer schema fields** than the pseudocode they
replace. `replication-reporting`'s new `v1` no longer names `decision`,
`n_reported` or `replicate_type_reported`, describing those judgements in words
instead ("Return `PASS` if …", "mark the number as not reported").

That follows from the register rather than from carelessness: pseudocode
assigns to fields by name, prose describes the judgement. The schema still
enforces all nine fields, so the model must fill them — but it now has to infer
which sentence governs which field. `n_reported` is the field to watch, being
the second-noisiest property the replicate exploration measured. It is recorded
here rather than corrected, because naming fields in brackets would partly undo
the register change this correction exists to make.

`plot-gap-labeling` has no such consequence: its field coverage is identical
before and after, at five of six, with `panel_label` named in neither.

### Also found, and not repaired: `stat-test`

The same audit found that `stat-test`'s `v1` was built from prompt.1 while
`production.json` pins prompt.3, and that the two are structurally different
documents rather than revisions of one another. This is **not** a register
defect — prompt.1 there is narrative — so that arm was left exactly as it ran.
It is recorded because a reader is entitled to know that the detailed arm is
not uniformly "the production prompt" across all eleven checks.
