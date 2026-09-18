---
title: exp-NN — <short title>
date: YYYY-MM-DD
status: planned        # planned | running | done | abandoned
tags: [experiment, skills, dag]
---

# exp-NN — <short title>

## Question

One sentence. What do we not know?

## Paper claim

Which claim in the results section this is evidence for. If no claim needs
it, say so — that is a reason to drop the experiment, not to invent a claim.

## Hypothesis

What we expect to see, and what would count as being wrong. State the
direction before running: a prediction made afterwards is not one.

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
