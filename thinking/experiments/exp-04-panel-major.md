---
title: exp-04 — panel-major or check-major, on the cleaned contracts
date: 2026-09-29
status: draft          # draft | planned | running | done | abandoned
kind: experiment
extends: exp-03
tags: [experiment, skills, dag, schema, panel-major, baseline]
---

# exp-04 — panel-major or check-major, on the cleaned contracts

*A draft plan, not a preregistration. Each open decision below carries a
recommendation; the note becomes a preregistration once they are settled and
the prep steps have passed.*

*Reframed 2026-10-04. The first draft compared a new panel-major contract with
exp-03's runs. exp-04 now runs **all its conditions itself**, on exp-03's DAG of
skills carrying the cleaned wording and contracts, scored against `gold-v3`. It
is not compared with exp-01 to exp-03, which answered other prose and other
contracts (see their notes, "Gold this was scored against"). Its conditions
become the baseline for what follows.*

## Where this sits in the series

1. **exp-04 — the baseline, and the schema question.** Three DAG
   arrangements × two contract shapes, cleaned prose and contracts, `gold-v3`,
   one model, three checks.
2. **Orchestration experiments.** Each varies one thing against exp-04's best
   condition — subagents for the checks, parallel dispatch, other arrangements
   of the DAG — and asks whether it is faster, cheaper or more accurate.
3. **Model comparison**, on the arrangement that comes out best.

Extending to the rest of `fig-checklist` comes once the DAG works on three
checks.

## Question

Should the shape of the answer follow the shape of the skill DAG?

In a panel-major contract, what the shared skills produce — the panel label
and the panel's class, from panel identification and classification (A|B) — is
stated once per panel, and only what each check produces is that check's. That
makes the contract **depend on the DAG**: which fields are common and which are
check-specific is decided by which skills are shared. This was not planned; it
appeared when drafting exp-04. With deeper or more branched DAGs, the contract
would have to be re-derived from the DAG each time, and a field shared by some
checks but not others has no obvious place.

The check-major contract of exp-03 — one list per check, each restating its own
panels — is independent of the DAG: a check's contract is the same whether it
runs alone, under D, or anywhere else. It is simpler, and exp-03 suggests it
costs something. exp-04 measures whether the dependency is worth taking on.

## Why the question, from exp-03

From [exp-03's findings](exp-03-checklist-entry.md#findings) — the motivation,
not a reference to compare against:

- **The model does the shared step once per figure**, never once per check:
  under the entry skill, `classify-panels` was reached in 72 of 190 sessions,
  once each time.
- **The check-major contract made it restate that step** in one list per
  check, and the copies look like one inventory copied: identical missing and
  spurious row counts for two checks, and spurious rows up from 3 to 25 for one
  check against the same check run alone.

## Design (draft)

### Two factors, six conditions

| | **check-major** (exp-03's contract shape) | **panel-major** |
|---|---|---|
| **`A\|B\|C_i ← D`** (checks at v1, A and B inline) | CM-1 | PM-1 |
| **`A\|B ← C_i ← D`** (checks at v3, calling `classify-panels` v1) | CM-2 | PM-2 |
| **`A ← B ← C_i ← D`** (checks at v3, calling `classify-panels` v2, calling `identify-panels`) | CM-3 | PM-3 |

38 figures × 5 replicates × 6 conditions = **1,140 sessions**. At exp-03's
fan-out cost of $0.07–0.09 per figure, **≈ $90**, the deepest arm untested
for cost.

**The third arm** is exp-02's `A ← B ← C` under D: the skills exist —
`classify-panels` v2 calls `identify-panels` v1, and exp-03's checks are
byte-identical to exp-02's. It puts A and B at separate levels, so the PM
contract's common fields come from two different skills at two depths, a step
towards the deeper DAGs the dependency question is about. `identify-panels`,
kept out of exp-03 because its description alone drew calls, is reached only
in this arm: closure assembly leaves it out of the other two.

**The contract is the only difference along the schema factor.** The checks'
prose says nothing about the shape of the answer, and D's says only which checks
to run; the contract reaches the session as the leaf's `schema.json`. So within
an arm, CM and PM run **the same skills, byte for byte**, and differ in the
contract alone. If D needs a sentence on how rows are assembled, it goes into
both versions of D, worded for each, and is reviewed as the one deliberate
difference.

### The skills: exp-03's DAG, with the cleanup's wording

exp-04 keeps exp-03's structure — `do-fig-checklist` (D) dispatching
`micrograph-scale-bar`, `individual-data-points` and `error-bars-defined`
(C_i), at v1 with A and B inline, or at v3 calling `classify-panels` (B) — adds
exp-02's `classify-panels` v2 and `identify-panels` v1 for the third arm, and
carries into all of it what the contract cleanup changed in `fig-checklist`.

**What has to come across**, from the cleaned `fig-checklist` skills into both
the v1 and the v3 checks:

- **`individual-data-points`**: a panel that is not a plot is
  `not_applicable`; a plot exempt from the check, or with nothing to show, is
  `PASS` with `not_required` in `individual_values` — replacing `"not needed"`.
- **`error-bars-defined`**: the new `is_a_plot` field; a non-plot is
  `not_applicable` in `error_bar_on_figure`, `error_bar_defined_in_caption` and
  `decision`; a plot without error bars is `PASS` with `not_required`;
  `Decision_and_explanation` split into an enum `decision` and an unscored
  `explanation`; `from_the_caption` left empty rather than `"not needed"`.
- **`micrograph-scale-bar`**, **`classify-panels`** and **`identify-panels`**:
  no cleanup findings; reviewed all the same, since panel classes decide what
  is a plot, and carried over unchanged unless the review finds otherwise.

**What must not be lost**, from exp-02 and exp-03 — what made the DAG work:

- calls named in the prose, made through the `Skill` tool, with the callee in
  the frontmatter's `requires`;
- descriptions that say what a skill does, not when to call it, so that a
  skill is reached through the DAG rather than drawn in by its description;
- `identify-panels` kept out of the checklist: its description alone drew
  calls in 5–12% of exp-02's sessions;
- closure assembly, so that a session sees only the skills its entry skill
  reaches;
- the explicit statement of the answer's top-level key, which stopped answers
  being written under an intermediate's key.

**How the skills are written.** The exp-03 skills split the same
instructions across blocks differently from the production ones, so each change
is placed by hand:

1. `fig-checklist-exp04` starts as a copy of exp-03's skills **as they stand**,
   plus exp-02's `classify-panels` v2 and `identify-panels` v1. exp-02's and
   exp-03's checklists stay frozen.
2. For one skill at a time, Claude proposes the changes, read off the cleaned
   `fig-checklist` skill, as before/after text placed in that skill's blocks.
3. The author makes the changes by hand.
4. Claude checks the edited skill for consistency — with the `fig-checklist`
   wording, with the contract, and between a check's v1 and v3, which share
   most of their wording and are taken together — then moves to the next.

### The two contracts

**Check-major**, as exp-03's, with each check's cleaned fields:

```json
{
  "micrograph-scale-bar":   [{ "panel_label": "A", "micrograph": "yes", "…": "…" }],
  "individual-data-points": [{ "panel_label": "A", "plot": "no", "…": "…" }],
  "error-bars-defined":     [{ "panel_label": "A", "is_a_plot": "no", "…": "…" }]
}
```

**Panel-major**, one row per panel, A|B's fields once:

```json
{
  "outputs": [
    {
      "panel_label": "A",
      "panel_classes": ["micrograph"],
      "micrograph-scale-bar":   { "micrograph": "yes", "scale_bar_on_image": "yes", "…": "…" },
      "individual-data-points": { "plot": "no", "…": "…" },
      "error-bars-defined":     { "is_a_plot": "no", "…": "…" }
    }
  ]
}
```

Both are derived, not authored, from the three cleaned `fig-checklist`
contracts, with the same refuse-unless-identical verification exp-03 used.
`gold-v3` is shared by check name, so the cleaned gold applies as it is: as
exp-03 merged it per check for CM, merged per panel for PM.

### Endpoints (draft)

Every check is scored per check in all six conditions — a PM answer is read as
three per-check lists, each panel row counting for every check — so the two
shapes are compared on the same footing:

- **Dispatch**: every check invoked; whether the shared step was done, and how
  often (trace and answer).
- **Layer S, per check**: correct, missing and spurious rows.
- **Spurious panels per figure**: a panel no check's gold has, counted once
  however many check lists carry it — the measure of an inventory restated and
  drifting.
- **Layers 1 and 2**, per check and per field.
- **Cost, turns, tokens and wall-clock time per figure**, from `tool_audit.json`.
- **Replicate variance** per check and layer, for sizing later margins.

The contrast of interest is **PM against CM within each arm**; the arm contrast
is reported alongside, as exp-03 did.

## Decisions to settle

| # | decision | recommendation |
|---|---|---|
| 1 | hypothesis for PM against CM | **settled 2026-10-04**: directional on spurious panels, non-inferiority on layers 1 and 2 — see below |
| 2 | `panel_classes` in the PM contract: scored, or present and unscored | **settled 2026-10-04**: present, `"scored": false` — no gold for it |
| 3 | `panel_classes` in the CM contract too | **no**: CM stays exp-03's shape, so the schema factor is the shape and nothing else |
| 4 | which model | the model exp-03 ran, fixed here; models are compared later |
| 5 | check order in D | exp-03's, fixed and stated |

**On the hypothesis.** exp-03 gives a direction and a mechanism for spurious
rows: restating the inventory is where they appear. Settled: **directional
on spurious panels** (PM fewer than CM, in each arm), **non-inferiority on
layers 1 and 2** per check, margins sized from exp-03's variance. If PM is not
better on spurious panels and not worse elsewhere, the DAG-independent
check-major contract is kept, being simpler.

## Prep work (draft)

| # | step | why |
|---|---|---|
| P1 | Show the scorer handles a check's object nested in a list row (`outputs[].<check>.x`) exactly as the flat field | nesting objects in rows is untested |
| P2 | Read a PM answer as per-check lists, and count spurious panels per figure for both shapes | the endpoints compare the shapes on the same footing |
| P3 | Merge `gold-v3` per check (CM) and per panel (PM), refusing on any label disagreement | mechanical, verified |
| P4 | Copy exp-03's skills, and exp-02's `classify-panels` v2 and `identify-panels` v1, into `fig-checklist-exp04`; then port the cleanup **one skill at a time** — proposed, edited by the author, checked | the wording encodes domain judgement |
| P5 | D: one version per contract shape if its prose must differ — reviewed | the one deliberate difference along the schema factor |
| P6 | Derive both contracts; both pass `audit_contracts` with no finding | the cleanup's conventions |
| P7 | Pin the scorer to `gold-v3` | as exp-01 to exp-03 are pinned to theirs |
| P8 | Size the margins from exp-03's observed variance | if decision 1 is non-inferiority on layers 1 and 2 |
| P9 | Smoke test on all six conditions | as for exp-03 |

## Threats (draft)

- **The DAG-dependence is shown on chains only.** The third arm deepens the
  DAG, but every check still shares both A and B, so the PM contract's common
  fields split the same way in all three arms. A branched DAG — a shared skill
  used by some checks and not others — is where a PM contract has no obvious
  shape, and exp-04 does not test one.
- **Wording and contract change together against exp-03.** exp-04 does not
  compare with exp-03, so this matters only for reading its numbers beside
  exp-03's.
- **`panel_classes` unscored**: the shared step is present but unmeasured.
- **Order is fixed**, so a check's position is confounded with its identity.
- **38 figures** bound the precision of every per-check estimate; checks that
  apply to few panels will have wide intervals at layer 2.

## Status and next

Draft. The contract cleanup it depended on is closed (`gold-v3`, 2026-10-05).
Next: settle the decisions, run P1–P3, port the skills one check at a time for
review (P4–P5), derive and audit the contracts (P6–P7), size margins (P8),
smoke-test (P9), then preregister in exp-03's format — on the `exp-04` branch
once the plan is ready.
