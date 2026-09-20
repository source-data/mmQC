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

One check, one arm, seven replicates.

| | |
|---|---|
| Checklist | `fig-checklist-exp01` |
| Check | `micrograph-scale-bar` |
| Arm | `pinned` — every skill at its manifest pin, i.e. the detailed `v1` |
| Replicates | 7 |
| Examples | all 38 in the check's benchmark |
| Model | `claude-sonnet-5`, pinned by exact name |
| Provider | `claude-sdk` |
| Sessions | 266 |

Nothing varies between the replicates. There is no seed to fix, so they
differ only because the model is non-deterministic, and that difference is
the measurement.

```bash
python experiments/exploration-replicate-variability/run.py
```

Seven rather than five so that the estimate of the spread is not itself made
from the number under question, and odd so a median is unambiguous.

`micrograph-scale-bar` was chosen because it is the check with the most prior
evidence behind it: it is the one run live during the refactor, scoring
15/15 rows and `mean_score` 1.0 on the informative example. A check that is
already working is the right place to measure noise — a check that is
failing would confound run-to-run variance with its own unreliability.

**That choice is also this probe's main limitation**, recorded here rather
than in the findings: one check is not eleven, and a check that scores near
1.0 has less room to vary than one scoring in the middle. The spread measured
here is likely a *floor* on the spread across the whole checklist.

## What happened

*Not yet run.*

To fill in: per-replicate check mean, the standard deviation across the
seven, the implied standard error at n = 1, 3, 5, and the observed cost per
session.

## What it does and does not establish

*Not yet run.* When it is, this section says plainly what the number supports.

Stated in advance, because it bears on how the result may be used:

- It measures the spread of **one arm**, not of the **difference between
  arms**. exp-01's statistic is a paired difference, whose variance is not
  this one — pairing by example cancels some noise and the two arms may be
  unequally noisy. This bounds the problem; it does not size it exactly.
- It is one check of eleven, chosen for being reliable. See the limitation
  above.
- It cannot support a paper claim. It is a design input for exp-01, and
  exp-01's note will say which replicate count it chose and cite this.

## Open questions

- Does the paired difference between arms vary less than a single arm does,
  as pairing would predict? Answering that needs both arms, which is exp-01
  itself — so the honest order may be to run exp-01 at a chosen n and report
  the observed spread alongside the result.
- Is variance comparable across checks, or do the harder checks move much
  more? Eleven checks × 7 replicates would answer it and cost about 2,900
  sessions, which is most of exp-01 itself and not obviously worth it.

## Cost

266 sessions. At the $0.035 observed for one `micrograph-scale-bar` session
during the refactor, roughly **$9**.

Spending that to choose between a 2,616-session run and a 4,360-session one
is the trade this probe exists to make: the difference between three and five
replicates is about 1,700 sessions, so the probe pays for itself if it moves
the decision at all.

Actual cost to be filled in from the runs — every session now records
`total_cost_usd` in its `tool_audit.json`.
