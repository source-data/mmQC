---
title: How many replicates does a check need?
date: 2026-09-20
status: done
kind: exploration
tags: [exploration, skills, replicates, cost]
---

# How many replicates does a check need?

Exploration: work done to understand, tweak, optimize or de-risk. No
hypothesis was committed in advance, so nothing here is confirmatory — which
is a description, not a caveat.

## Question

**How much does one check's score move between identical runs, and how many
replicates does it take to see past that?**

exp-01 was sketched at five replicates, which is 4,360 sessions. Three would
be 2,616. Neither number came from anything: they were chosen before anyone
had measured how noisy a single configuration is.

The number that decides it is the standard deviation of a check's mean score
across replicates of the *same* configuration. If that is small relative to
the difference exp-01 is looking for, three replicates suffice; if it is
comparable, five will not save the experiment either and the design needs
rethinking rather than more sampling.

## What was done

One check, one arm, ten replicates over ten examples.

| | |
|---|---|
| Checklist | `fig-checklist-exp01` |
| Check | `replication-reporting` |
| Arm | `pinned` — every skill at its manifest pin, i.e. the detailed `v1` |
| Replicates | 10 |
| Examples | 10, one per document, from 10 distinct documents |
| Model | `claude-sonnet-5`, pinned by exact name |
| Provider | `claude-sdk` |
| Sessions | 100 |

Nothing varies between the replicates. There is no seed to fix, so they
differ only because the model is non-deterministic, and that difference is
the measurement.

```bash
python experiments/exploration-replicate-variability/run.py
```

### Why this check

**Run-to-run variation is the model choosing different words for the same
judgement.** A `binary_polarity` field absorbs that completely — yes is yes.
A field scored by `semantic` string comparison does not: it goes through
sentence-transformer similarity against a 0.8 threshold, so a rephrasing
lands anywhere on a continuum. Variance should therefore concentrate in
checks with semantic fields, which is a structural prediction rather than an
inference from any run.

`replication-reporting` has **three** semantic fields —
`replicate_statements`, `replicate_type`, `explanation` — more than any other
check. On the single figure scored during the refactor its
`replicate_statements` came out at 0.71, the lowest property of any check.

The obvious alternatives are worse for this purpose. `micrograph-scale-bar`
and `stat-test` scored highest of the eleven (~0.99 and ~0.98 on that
figure), so a probe on either measures a **floor** — there is little room to
move. `single-channel-for-overlay` has no semantic fields at all and would be
the floor by construction.

So this probe is biased towards the **noisy** end, and the number it produces
should be read as closer to an upper bound on per-check variance than a
typical value. That is the safer direction for sizing an experiment.

### Why ten examples rather than all thirty-eight

Cost, and because the example count can be taken out of the answer.

The statistic exp-01 needs is the spread of a check mean computed over **38**
examples. A check mean over 10 is intrinsically noisier — by about
√(38/10) ≈ 2× — so the spread measured here must **not** be reported as the
spread exp-01 will see.

What ten examples × ten replicates gives is ten independent estimates of the
*per-example* between-replicate variance. The check-level spread for any
example count follows from that, and the analysis reports it that way. Ten
replicates also estimates a per-example variance more precisely than seven.

The notebook checks the assumption this rests on — that examples are
independent — by comparing the derived spread at N=10 against the spread
actually observed at N=10. If those disagree, the extrapolation to 38 is
wrong and the note says so.

### Which ten

One figure per document, taking the first document-figure in benchmark order
where the check applies, for ten distinct documents. 51 of the panels in
those ten figures are ones where replicates apply.

Taking the first ten examples in benchmark order would have been simpler and
worse: seven of them come from a single paper, and figures from one paper
share authorship and conventions, so their scores are not independent draws.

## What happened

100 sessions, all completed, none failed, none returned an empty answer.

### Per-replicate check mean

Nine examples, ten identical runs:

```
rep-00  0.9049      rep-05  0.9039
rep-01  0.9116      rep-06  0.9132
rep-02  0.9128      rep-07  0.9179
rep-03  0.9142      rep-08  0.9194
rep-04  0.9143      rep-09  0.9223
```

Range 0.018 across ten runs of the identical configuration.

### The decomposition

| | |
|---|---|
| Mean per-example variance | 0.000643 |
| Per-example SD across replicates | **0.0254** |
| SD of a check mean over 38 examples | **0.0041** |

| replicates | SE, one arm | SE, paired difference (upper bound) |
|---|---|---|
| 1 | 0.0041 | 0.0058 |
| **3** | **0.0024** | **0.0034** |
| 5 | 0.0018 | 0.0026 |

Per-example SD ranged from 0.0038 to 0.0478 — an order of magnitude between
the steadiest example and the least steady. For comparison, the *between
example* spread of means is 0.889 to 0.980, far larger than any example's
run-to-run movement.

### Independence

The extrapolation from 10 examples to 38 assumes examples vary independently.
Observed SD of the check mean at N=9 was **0.0058** against a derived
**0.0085** — a ratio of 0.68, just outside the 0.7–1.4 band the notebook
treats as agreement.

The direction is the safe one: the check mean moves *less* than independence
predicts, so the figures above **overstate** the noise rather than
understating it. With nine examples and ten replicates both quantities are
themselves noisily estimated, and a ratio of 0.68 is within sampling error of
1. Treat the SE column as conservative.

### One non-response of a different kind

One cell of the hundred — `10.1038_emboj.2009.312`, one replicate — scored
nothing at all: no property had a single applicable instance, where the other
nine runs of that example all did. The model classified every panel as not
involving replicates in that one run.

That is not an empty answer (there were none) and it is not a scoring
failure. It is the applicability judgement itself moving between runs, which
no amount of averaging scores will reveal. It is also exactly the case that
made the first version of this analysis wrong: `mean_score` is `0.0` when a
property has nothing to score, and averaging those zeros treated "not
applicable" as "scored zero".

## What it does and does not establish

**Three replicates.** At n=3 the paired-difference standard error is bounded
above by 0.0034, so a difference of 0.01 in mean score between detailed and
minimal skills sits about three standard errors clear, and 0.02 sits six.
Going to five moves that bound from 0.0034 to 0.0026 — a change of 0.0008,
against roughly 1,700 more sessions and another 16 hours. That is not a
purchase this evidence supports.

Even **one** replicate would resolve an effect of 0.02. Three is chosen over
one because it costs little, and because a single run cannot show that an
arm's own spread is what this probe measured it to be.

What it does not establish:

- It measures **one arm**, not a difference. exp-01's statistic is paired,
  and pairing cancels whatever noise the two arms share. The paired column
  above is an upper bound assuming they vary independently, which they do
  not; the true SE is lower, by an unknown amount.
- It is **one check**, deliberately the noisiest — three semantic fields,
  more than any other, and 47% of its output tokens are reasoning. A check
  whose fields are all binary should move less. This bounds per-check
  variance from above; it says nothing about the spread *between* checks.
- It says nothing about **applicability** stability, beyond the one flip
  observed. That is a separate axis, and layer 1 is where it would be
  measured.
- It cannot support a paper claim. It is a design input, and exp-01's note
  records three replicates and cites this.

## Open questions

- Does the paired difference between arms vary less than a single arm does,
  as pairing would predict? Answering that needs both arms, which is exp-01
  itself — so the honest order may be to run exp-01 at a chosen n and report
  the observed spread alongside the result.
- Is variance comparable across checks? This probe deliberately picked the
  check where it should be highest, so it cannot say. Repeating it on
  `single-channel-for-overlay`, which has no semantic fields, would bracket
  the range for about $3 — but with n=3 already justified by the noisy end,
  the answer would not change the decision.
- **How stable is the applicability judgement?** One example flipped to
  "nothing applicable" in one run of ten. Layer 1 measures that directly and
  this analysis never looked at it; a check whose panel classification moves
  between runs is unreliable in a way no mean score shows.

## Cost

**Actual, from the 100 sessions.**

| | |
|---|---|
| Total | **$6.28** |
| Per session | $0.063 mean, $0.055 median, $0.021–$0.134 |
| Turns | 4 median, 4–9 |
| Duration | 33 s median, **1.1 h** total |
| Output tokens | 3,468 median, **47% of them reasoning** |
| Cache | 7,504 created, 11,273 read (median) |

The pre-run estimate of $3.50 was low and the corrected one of $9.50 was
high; the smoke test's two sessions happened to be the slowest of the
hundred. Median session cost $0.055 against `micrograph-scale-bar`'s $0.035,
so this check is about 1.6× the cheap one rather than the 2.7× two sessions
suggested.

### What this implies for exp-01

Per-session cost still spans roughly 2× across checks, so the total depends
on the mix. Taking $0.05 as a middle:

| replicates | sessions | cost | serial time |
|---|---|---|---|
| **3** | **2,616** | **~$130** | **~24 h** |
| 5 | 4,360 | ~$218 | ~40 h |

Choosing three over five saves about $88 and 16 hours, for a standard error
that moves from 0.0034 to 0.0026 — a difference no plausible effect size
would notice. The probe cost $6.28 to establish that, which it repaid many
times over.

The wall clock remains the uncomfortable number. 24 hours serial is still an
overnight-plus job, and replicates are independent by construction, so
parallelism — left out of scope in
[`plans/2026-09-20-replicates-in-the-harness.md`](../plans/2026-09-20-replicates-in-the-harness.md)
— is the obvious next lever if exp-01 needs to be repeated.
