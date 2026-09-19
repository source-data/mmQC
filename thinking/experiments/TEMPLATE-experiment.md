---
title: exp-NN — <short title>
date: YYYY-MM-DD
status: planned        # planned | running | done | abandoned
kind: experiment
extends:               # exp-NN, if this is a separate prediction on the same theme
tags: [experiment, skills, dag]
---

# exp-NN — <short title>

## Question

One sentence. What do we not know?

## Paper claim

Which claim in the results section this is evidence for.

If there is no claim yet, this is probably an exploration rather than an
experiment — use `TEMPLATE-exploration.md`. Inventing a claim to justify a
run is worse than running it as exploration and seeing what turns up.

## Hypothesis

What we expect to see, and what would count as being wrong. State the
direction before running: a prediction made afterwards is not one.

## Decision criteria

Written before the run, so the threshold cannot drift to meet the data. Say
what each outcome would look like:

- **Supports the hypothesis if** …
- **Refutes it if** …
- **Inconclusive if** … — a reportable result, not a failure.

## Design

| | |
|---|---|
| Baseline | `fig-checklist` @ `<commit>` |
| Checklist | `fig-checklist-expNN`, built by `experiments/build_expNN_checklist.py` |
| Arms | what varies between them |
| Held fixed | contracts (`schema.json`, `benchmark.json`, `eval-manifest.json`), gold, examples, model |
| Model | `claude-...`, pinned |
| Examples | N from `benchmark.json` |

What varies, precisely — the independent variable. If it cannot be stated in
a sentence, the experiment is testing more than one thing.

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|
| | | | | `experiments/runs/exp-NN-<slug>/...` |

## Findings

What happened. Numbers first, reading second, and keep them apart: it should
be possible to disagree with the interpretation while accepting the result.

## Threats to validity

What could explain this result other than the hypothesis. Be specific —
sample size, example selection, model non-determinism, a contract that moved,
an arm that differs in more than one way.

## Status and next

What this settles, what it opens, and whether anything here belongs on the
backburner rather than in the paper.

## Addendum YYYY-MM-DD *(post-hoc — delete this section if unused)*

Work done after the findings above were seen: an extra condition, a
follow-up analysis, a control that only became obvious in hindsight.

**This is exploratory with respect to the preregistration above**, however
closely it follows the same question. If it deserves to be a claim, it needs
preregistering as its own experiment (`extends: exp-NN`) and testing again.

Runs go under `experiments/runs/exp-NN-<slug>/YYYY-MM-DD-<what>/`.
