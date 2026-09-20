---
title: How many replicates does a check need?
date: 2026-09-20
status: planned
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

*Not yet run.*

To fill in: the per-example between-replicate variance, the check-level
spread it implies at 38 examples, the standard error that gives at n = 1, 3
and 5 replicates, whether the independence assumption held, and the observed
cost per session.

## What it does and does not establish

*Not yet run.* When it is, this section says plainly what the number supports.

Stated in advance, because it bears on how the result may be used:

- It measures the spread of **one arm**, not of the **difference between
  arms**. exp-01's statistic is a paired difference, whose variance is not
  this one — pairing by example cancels some noise and the two arms may be
  unequally noisy. This bounds the problem; it does not size it exactly.
- It is one check of eleven, chosen for being the noisiest by construction.
  It therefore suggests an upper bound on per-check variance, and says
  nothing about whether variance differs much between checks — which is what
  would decide whether any single number generalises.
- Ten examples, extrapolated to thirty-eight. The extrapolation assumes
  examples are independent draws; the notebook tests that assumption and the
  finding is only as good as it holds.
- It cannot support a paper claim. It is a design input for exp-01, and
  exp-01's note will say which replicate count it chose and cite this.

## Open questions

- Does the paired difference between arms vary less than a single arm does,
  as pairing would predict? Answering that needs both arms, which is exp-01
  itself — so the honest order may be to run exp-01 at a chosen n and report
  the observed spread alongside the result.
- Is variance comparable across checks? This probe deliberately picked the
  check where it should be highest, so it cannot say. Repeating it on
  `single-channel-for-overlay`, which has no semantic fields, would bracket
  the range for another ~$3.50 — cheap, and the obvious follow-up if the
  number here is uncomfortably large.

## Cost

100 sessions. At the $0.035 observed for one session during the refactor,
roughly **$3.50**.

exp-01 is about $153 at five replicates and $92 at three, so the decision
this probe informs is worth roughly $61. It pays for itself many times over
if it moves that decision at all.

Actual cost to be filled in from the runs — every session now records
`total_cost_usd` in its `tool_audit.json`.
