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
skills carrying the cleaned wording and contracts, scored against `gold-v4`. It
is not compared with exp-01 to exp-03, which answered other prose and other
contracts (see their notes, "Gold this was scored against"). Its conditions
become the baseline for what follows.*

## Where this sits in the series

1. **exp-04 — the baseline, and the schema question.** Three DAG
   arrangements × two contract shapes, cleaned prose and contracts, `gold-v4`,
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
to run; the contract reaches the session as the leaf's `schema.json`. D is two
leaves in one checklist, `do-fig-checklist-cm` and `do-fig-checklist-pm`, each
owning one contract, with prose identical but for the name (decided 2026-10-05);
closure assembly gives a session the one it starts from and never the other. So
within an arm, CM and PM run the same checks and shared skills byte for byte,
and an entry skill differing in its name alone. D's prose says nothing on how
rows are assembled; the smoke test (P9) shows whether it needs to.

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
exp-03 merged it per check for CM, merged per panel for PM, into
`checks/do-fig-checklist-cm/` and `checks/do-fig-checklist-pm/`. `gold-v4`
tags `gold-v3` with those two merged golds added, and is what exp-04 is scored
against.

### Endpoints (draft)

Every check is scored per check in all six conditions — a PM answer is read as
three per-check lists, each panel row counting for every check — so the two
shapes are compared on the same footing:

- **Dispatch**: every check invoked; whether the shared step was done, and how
  often (trace and answer).
- **Layer S, per check**: correct, missing and spurious rows (the evaluator's
  three outcomes). Two statistics, decided 2026-10-05:
  - **for the comparison**, the gate statistic of exp-02 and exp-03,
    `correct / (correct + missing)` -- the share of gold rows found, tested for
    non-inferiority. It leaves spurious rows out, so it measures missing panels
    alone;
  - **for reporting**, `correct / (correct + missing + spurious)`, per check
    and condition, beside the gate: the one number that charges both errors.
    exp-02 and exp-03 reported the gate statistic only, with spurious rows
    visible in the stacked layer-S plots but in no rate.
- **Spurious panels per figure** (directional): a panel no check's gold has,
  counted once however many check lists carry it — the measure of an inventory
  restated and drifting. Missing panels per figure are reported beside it,
  without a direction: layer S's gate already tests them per check, and exp-03
  gives no mechanism by which PM would lose fewer.
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
| P7 | Pin the scorer to `gold-v4` | as exp-01 to exp-03 are pinned to theirs |
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

**P4 done, 2026-10-05.** `fig-checklist-exp04` carries the cleanup's wording
in all three checks at v1 and v3 (`1199f44d1`, `6ac3db034`, `33abc0a2e`), each
v3 identical to its v1 after its call to `classify-panels`. The shared skills
are aligned with the checks (`8b1350ee8`, `d276f5374`): panel identification
and classification are worded the same wherever they are written out, apart
from what depends on having a caller, so the arms differ in arrangement
only. `do-fig-checklist` is unchanged, pending P5.

**P1, P3, P5, P6 done; P7 ready, 2026-10-05.**

- *P1*: the scorer read a field in an object nested in a row as absent on
  both sides; fixed (`892393a14`), with a test that the nested and flat shapes
  score identically. No earlier contract has such a field.
- *P5*: two entry points, `do-fig-checklist-cm` and `-pm`, identical but for
  the name (`0d2feb23e`).
- *P6*: both contracts derived by `experiments/exp-04-panel-major/
  build_contract.py`, which refuses unless each scores every check exactly as
  its own contract does, on answers made from the gold (1,137 comparisons under
  CM, 795 under PM); both audit with no finding.
- *P3*: the merged gold, 38 files per shape (`27b8c4208`), reviewed.
- *P7*: `gold-v4` tagged; the runner and notebook pin to it when written.

- *Runner* (`10e30f9a6`): six conditions, closures checked -- neither entry
  point reaches the other; `identify-panels` only in the third arrangement.
- *P2*: `experiments/exp-04-panel-major/panels.py`, tested. A spurious panel is
  a label the answer states -- in any check's list, for CM -- that the gold
  does not have, counted once per figure; also missing and (CM only) partly
  missing panels. **Reference, exp-03's CM fan-out** against `gold-v4`'s labels:
  28 spurious panels in 190 sessions (`A|B|C_i <- D`) and 21 (`A|B <- C_i <-
  D`), from only 4 and 5 of the 38 figures.

- *P9, smoke test, 2026-10-05*: six conditions x 3 figures (`s44318-026-00715-1`
  content/1-3), one replicate, 18 sessions, none failed, $1.84.
  - **Dispatch**: all three checks in 18/18, always in D's listed order. No
    skill outside a condition's closure.
  - **Reach**: `A|B <- C_i <- D` reached `classify-panels` in 2/3 sessions (CM)
    and 3/3 (PM), once each; `A <- B <- C_i <- D` reached both shared skills
    in 6/6, `classify-panels` twice in one CM session.
  - **Shape**: every answer validates against its contract. PM rows all carry
    `panel_classes`, none empty, composite panels with several classes
    (`micrograph, plot`). **D needs no sentence on assembling rows**: the
    schema is enough (P5 closed).
  - **Panels**: the one figure with spurious panels (content/3: 2 spurious, 1
    missing, as if one panel were split) shows them in both shapes.
  - **Cost** per condition, CM against PM: $0.32 / $0.35, $0.24 / $0.31,
    $0.25 / $0.37 -- PM dearer in all three, on three figures.
  - **For the notebook**: a CM check's `panel_label` instances sit under its
    name, a PM row's once under `outputs[]`; per-check rates must count PM's
    shared label towards every check, as `build_contract.py`'s verification
    does, or the shapes are compared on different instance sets.

Left: the preregistration, the notebook.

#### P8, margins (settled 2026-10-05)

exp-04's comparisons -- PM against CM within an arrangement -- pair two fan-out
conditions of five replicates each, the structure of exp-03's fan-out against
per-check comparisons. exp-03's **observed** half-widths are therefore the
closest estimate of exp-04's, with one caveat each way: both exp-04 sides are
fan-outs, a little noisier than exp-03's per-check controls; and the cleaned
vocabulary changes what layers 1 and 2 count. The third arrangement has no
prior data and is assumed as noisy as the second.

| gate | δ (exp-03's) | exp-03 observed half-width | expected to clear |
|---|---|---|---|
| layer S | 0.0125 | 0.0056-0.0073; `micrograph-scale-bar` delegating 0.0133 | all but `micrograph-scale-bar` in the two delegating arrangements |
| layer 1 | 0.02 | 0.0036-0.0066; `error-bars-defined` 0.015-0.016 | all |
| layer 2 | 0.02 | <= 0.014, but `micrograph-scale-bar · from_the_image` 0.039 (10 examples) | all but `from_the_image` |

**Settled 2026-10-05**: **keep δ_S = 0.0125, δ₁ = 0.02, δ₂ = 0.02**, and pre-declare as
expected to be uninformative `micrograph-scale-bar` at layer S in the two
delegating arrangements, and `micrograph-scale-bar · from_the_image` at layer
2 -- reported, not counted, if their intervals are wider than δ, as exp-03 did.

**Spurious panels** need no margin: the hypothesis is directional. Statistic:
per figure, spurious panels averaged over replicates; PM minus CM, paired by
figure; percentile bootstrap over the 38 figures, 10,000 resamples; **fewer**
if the 95% interval lies below 0. Power is limited and stated in advance: in
exp-03 the spurious panels came from 4-5 figures, so the interval excludes 0
only if PM removes most of them; a reduction confined to one or two figures
will read as inconclusive, and the counts are reported either way.


Draft. The contract cleanup it depended on is closed (`gold-v3`, 2026-10-05); exp-04 is scored against `gold-v4`.
Next: settle the decisions, run P1–P3, port the skills one check at a time for
review (P4–P5), derive and audit the contracts (P6–P7), size margins (P8),
smoke-test (P9), then preregister in exp-03's format — on the `exp-04` branch
once the plan is ready.
