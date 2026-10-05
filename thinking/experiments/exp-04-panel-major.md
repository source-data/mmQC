---
title: exp-04 — panel-major or check-major, on the cleaned contracts
date: 2026-10-05
status: planned        # planned | running | done | abandoned
kind: experiment
extends: exp-03
tags: [experiment, skills, dag, schema, panel-major, baseline]
---

# exp-04 — panel-major or check-major, on the cleaned contracts

*Preregistration, written before the full run. The draft it grew from (first
dated 2026-09-29, reframed 2026-10-04) is in this file's history; the
decisions it settled are recorded under* Preparation.

## Where this sits in the series

1. **exp-04 — the baseline, and the schema question.** Three DAG arrangements
   × two contract shapes, on exp-03's skills carrying the contract cleanup's
   wording, scored against `gold-v4`, one model, three checks.
2. **Orchestration experiments.** Each varies one thing against exp-04's best
   condition — subagents for the checks, parallel dispatch, other arrangements
   of the DAG — and asks whether it is faster, cheaper or more accurate.
3. **Model comparison**, on the arrangement that comes out best.

Extending to the rest of `fig-checklist` comes once the DAG works on three
checks. exp-04 runs **all its conditions itself** and is not compared with
exp-01 to exp-03, which answered other prose and other contracts (see their
notes, "Gold this was scored against").

## Question

Should the shape of the answer follow the shape of the skill DAG?

In a **panel-major** (PM) contract, what the shared skills produce — the panel
label and the panel's classes, from panel identification and classification
(A|B) — is stated once per panel, and only what each check produces is that
check's. That makes the contract **depend on the DAG**: which fields are common
and which check-specific is decided by which skills are shared. This was not
planned; it appeared when drafting exp-04. With deeper or more branched DAGs,
the contract would have to be re-derived from the DAG each time, and a field
shared by some checks but not others has no obvious place.

The **check-major** (CM) contract of exp-03 — one list per check, each
restating its own panels — is independent of the DAG: a check's contract is
the same whether it runs alone, under an entry skill, or anywhere else. It is
simpler, and exp-03 suggests it costs something. exp-04 measures whether the
dependency is worth taking on.

## Paper claim

That **the schema should mirror the skill DAG** — what a shared skill produces
is a shared field, what a check produces is that check's — when checks share an
upstream step. exp-03 showed that under one entry skill the model does the
shared step once per figure, and that a contract asking for it once per check
gets copies that drift: invented panels, appearing in every check's list. The
claim is that a contract built to the DAG's shape removes them at no cost to the
checks.

From [exp-03's findings](exp-03-checklist-entry.md#findings), the motivation,
not a reference to compare against:

- under the entry skill, `classify-panels` was reached in 72 of 190 sessions,
  **once each time, never once per check**;
- two checks' row lists had **identical** missing and spurious counts, and
  spurious rows rose from 3 to 25 for one check against the same check run
  alone; per figure, 28 and 21 spurious panels in 190 sessions, from only 4 and
  5 of the 38 figures (counted against `gold-v4`'s labels).

## Hypothesis

Within each arrangement, PM against CM:

1. **PM states fewer spurious panels per figure** — directional, from exp-03's
   mechanism: restating the inventory per check is where panels are invented.
2. **PM is non-inferior** for every check at layer S, layer 1 and layer 2.

**The choice it decides.** PM becomes the series' contract if, in **at least two
of the three arrangements**, it states fewer spurious panels (hypothesis 1
holds) and no check degrades at any gate. Otherwise the DAG-independent CM
contract is kept, being simpler. An arrangement where PM states *more* spurious
panels, or where a check degrades under PM, counts against PM whatever the
other two show, and is reported as such.

What would count as being wrong: spurious panels no fewer under PM, which would
say the drift comes from making the inventory rather than from restating it; or
a check degrading under PM, which would say that answering per panel —
interleaving three checks' fields in one row — costs a check its own
judgement.

**Also measured, not hypothesised** — the baseline the later experiments need:
each condition's per-check rates at every layer with intervals, their
replicate-to-replicate variance, and cost and time per figure.

## Decision criteria

Written before the run, so the threshold cannot drift to meet the data.

### Endpoints

| # | endpoint | statistic | gate? |
|---|---|---|---|
| **0** | **dispatch** | see below | reported, not a gate |
| **H1** | **spurious panels per figure** | spurious panels, averaged over replicates; PM − CM, paired by figure | directional |
| **1** | **layer S** | `correct_row / (correct_row + missing_row)` per check — the share of gold rows found | non-inferiority, δ_S |
| **2** | **layer 1** | `correct_applicable + correct_NA` over all profiled instances, per check | non-inferiority, δ₁ |
| **3** | **layer 2** | `mean_score` per property, on applicable instances, paired by example | non-inferiority, δ₂ |

**Spurious panels** are counted by `experiments/exp-04-panel-major/panels.py`:
a label the answer states — in any check's list, for CM — that the gold does not
have, **once per figure**, however many check lists repeat it. Labels compare
exactly, as layer S aligns them. Missing panels per figure (gold labels no list
carries) and, for CM, partly missing panels are reported beside it, without a
direction: layer S's gate already tests missing rows per check, and exp-03
gives no mechanism by which PM would lose fewer.

**Layer S is reported two ways.** The gate statistic above leaves spurious rows
out, as exp-02's and exp-03's did, and measures missing rows alone; beside it,
for reporting, `correct / (correct + missing + spurious)` per check and
condition — the one rate that charges both errors (decided 2026-10-05).

**Both shapes are scored per check, on the same instances.** A PM answer is
read as three per-check lists, each panel row counting for every check. In CM a
check's `panel_label` instances sit under that check's name; in PM they sit
once under `outputs[]`, and **are counted towards every check**, as
`build_contract.py`'s verification does. Otherwise the shapes would be compared
on different instance sets.

### Statistics and verdicts

exp-03's, unchanged. Per-example rate differences, PM − CM; seeded percentile
bootstrap over the 38 examples, 10,000 resamples.

- **Non-inferiority gates**: **non-inferior** if the 95% CI's lower bound is
  above −δ, **degraded** if the CI lies entirely below −δ, **inconclusive** if
  it straddles −δ. Fixed sequence within each comparison, S → 1 → 2: a later
  gate is a claim only if the earlier ones are non-inferior. Nine comparisons —
  three checks × three arrangements — each its own claim, nothing corrected
  across them.
- **Spurious panels**: **fewer** if the 95% CI of the paired difference lies
  below 0, **more** if it lies above 0, **inconclusive** otherwise. Three tests,
  one per arrangement.

### Margins

**δ_S = 0.0125, δ₁ = 0.02, δ₂ = 0.02**, exp-03's (settled 2026-10-05, P8).
exp-04's comparisons pair two fan-out conditions of five replicates each — the
structure of exp-03's fan-out against per-check comparisons — so exp-03's
**observed** half-widths are the closest estimate of exp-04's. Caveats both
ways: both exp-04 sides are fan-outs, a little noisier than exp-03's per-check
controls, and the cleaned vocabulary changes what layers 1 and 2 count. The
third arrangement has no prior data and is assumed as noisy as the second.

| gate | δ | exp-03 observed half-width | expected to clear |
|---|---|---|---|
| layer S | 0.0125 | 0.0056–0.0073; `micrograph-scale-bar`, delegating, 0.0133 | all but `micrograph-scale-bar` in the two delegating arrangements |
| layer 1 | 0.02 | 0.0036–0.0066; `error-bars-defined` 0.015–0.016 | all |
| layer 2 | 0.02 | ≤ 0.014; `micrograph-scale-bar · from_the_image` 0.039 (10 examples) | all but `from_the_image` |

**Pre-declared as expected to be uninformative**: `micrograph-scale-bar` at
layer S in `A|B ← C_i ← D` and `A ← B ← C_i ← D`, and `micrograph-scale-bar ·
from_the_image` at layer 2. If an interval there is wider than δ it is reported
as uninformative, not counted; if it clears, it is read like any other. For the
choice rule, an uninformative cell neither counts as a degradation nor as
evidence of non-inferiority.

**Power for spurious panels is limited, and stated in advance.** In exp-03 the
spurious panels came from 4–5 figures, so the interval excludes 0 only if PM
removes most of them; a reduction confined to one or two figures will read as
inconclusive. The counts are reported either way.

### Endpoint 0: dispatch

Read from `skill_trace.json`, per session, as exp-03:

- **dispatch** — all three check skills invoked;
- **reach** — `classify-panels` invoked, in `A|B ← C_i ← D` and
  `A ← B ← C_i ← D`; `identify-panels` invoked, in `A ← B ← C_i ← D`; how many
  times per session;
- **order** — the order in which the checks were first invoked;
- **spontaneous** — any skill invoked outside the condition's closure;
- **`panel_classes`** (PM only) — rows with an empty list; it is unscored, so
  this is the only check that the shared field is filled.

A check that is non-inferior with partial dispatch is **safe but optional**, as
in exp-03, and a session that fills a check's fields without invoking its skill
is not the condition it claims to be; dispatch is what detects it.

### Non-response and failures

An empty answer scores as a fully missing row set, for every check. **Under PM
an empty `outputs` loses all three checks at once**, as a failed session does in
both shapes. Failures and empty answers are reported per session and per
condition; a difference of more than 5% between PM and CM in an arrangement is a
finding in its own right.

### Secondary, reported, not gated

- **Arrangement contrasts** within each shape — `A|B ← C_i ← D` and
  `A ← B ← C_i ← D` each against `A|B|C_i ← D` — per check, layers S and 1:
  the baseline for the orchestration experiments.
- **Cost and time per figure**, PM ÷ CM within each arrangement, mean of
  per-figure ratios with a percentile bootstrap: cost, input and output tokens,
  turns, duration, from `tool_audit.json`. **No direction predicted.** The
  smoke test had PM dearer in all three arrangements, on three figures; a PM
  that wins on accuracy and costs more is reported as both.
- **Replicate variance** per condition, check and layer, for sizing later
  margins.

## Design

| | |
|---|---|
| Checklist | `fig-checklist-exp04` |
| Entry skills | `do-fig-checklist-cm`, `do-fig-checklist-pm` — identical prose but for the name; each owns one contract |
| Checks | `micrograph-scale-bar`, `individual-data-points`, `error-bars-defined`, at v1 and v3 |
| Shared skills | `classify-panels` v1 and v2, `identify-panels` v1 |
| Conditions | the six below |
| Held fixed | skills, gold, examples, model, provider, replicate count, assembly |
| Model | `claude-sonnet-5`, pinned by exact name |
| Provider | `claude-sdk` |
| Assembly | closure: a session holds its entry skill and what its pinned prose reaches |
| Replicates | 5 |
| Examples | exp-03's 38 figures |
| Sessions | 1,140 |
| Gold | `gold-v4` |
| Contract builder | `experiments/exp-04-panel-major/build_contract.py` |
| Runner | `experiments/exp-04-panel-major/run.py` |
| Panel counts | `experiments/exp-04-panel-major/panels.py` |

### Six conditions

| arrangement | pins | check-major | panel-major |
|---|---|---|---|
| **`A\|B\|C_i ← D`** | checks at v1, A and B inline | CM-1 | PM-1 |
| **`A\|B ← C_i ← D`** | checks at v3, calling `classify-panels` v1 | CM-2 | PM-2 |
| **`A ← B ← C_i ← D`** | checks at v3, `classify-panels` v2 calling `identify-panels` | CM-3 | PM-3 |

Closures, checked before the run: each condition reaches its entry skill and
the three checks, plus `classify-panels` in the second arrangement and both
shared skills in the third. Neither entry skill reaches the other, and
`identify-panels` — kept out of exp-03 because its description alone drew calls
— is offered only in the arrangement whose prose reaches it.

**The contract is the only difference along the schema factor.** The checks'
prose says nothing about the shape of the answer, and D's says only which checks
to run; the contract reaches the session as the entry skill's `schema.json`.
Within an arrangement, CM and PM run the same checks and shared skills byte for
byte, and an entry skill differing in its name alone. The smoke test showed D
needs no sentence on assembling rows: every PM answer validated, with
`panel_classes` filled.

### The skills: exp-03's DAG, with the cleanup's wording

`fig-checklist-exp04` started as a copy of exp-03's skills as they stood, plus
exp-02's `classify-panels` v2 and `identify-panels` v1; exp-02's and exp-03's
checklists stay frozen. The contract cleanup's wording was then ported **one
skill at a time** — proposed by Claude from the cleaned `fig-checklist` skill,
edited by the author, checked against the contract and between a check's v1 and
v3:

- **`individual-data-points`**: a non-plot is `not_applicable`; an exempt plot
  type is `PASS` with `not_required`; a verdict section setting `decision` and
  `explanation`.
- **`error-bars-defined`**: `is_a_plot`; a non-plot is `not_applicable` in
  `error_bar_on_figure`, `error_bar_defined_in_caption` and `decision`; a plot
  without error bars is `PASS` with `not_required`; `Decision_and_explanation`
  split into `decision` and an unscored `explanation`.
- **`micrograph-scale-bar`**: a non-micrograph is `not_applicable` in the three
  scale-bar fields; a micrograph without a scale bar fails, its "defined"
  fields `no`; every field named.
- **Shared steps**: panel identification and classification are worded the
  same wherever they are written out — `identify-panels`, `classify-panels`,
  the v1 checks' inline steps — apart from what depends on having a caller, so
  the arrangements differ in arrangement only. Each v3 check is its v1 from the
  first check-specific section on, byte for byte.

What made the DAG work in exp-02 and exp-03 is kept: calls named in the prose
and made through the `Skill` tool, with the callee in `requires`; descriptions
saying what a skill does; closure assembly.

### The two contracts

**Check-major**, as exp-03's:

```json
{
  "micrograph-scale-bar":   [{ "panel_label": "A", "micrograph": "yes", "…": "…" }],
  "individual-data-points": [{ "panel_label": "A", "plot": "no", "…": "…" }],
  "error-bars-defined":     [{ "panel_label": "A", "is_a_plot": "no", "…": "…" }]
}
```

**Panel-major**, one row per panel:

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

`panel_classes` is a required list from the classification vocabulary, and
unscored: there is no gold for it. Each check keeps its own `micrograph`,
`plot`, `is_a_plot` field, where its gold and its layer 1 are.

Both contracts are **derived, never authored**, from the three cleaned
`fig-checklist` contracts by `build_contract.py`, which refuses to write unless
each scores every check exactly as that check's own contract does — on answers
made from the gold, with rows dropped, added and reordered, values flipped and
text altered: 1,137 comparisons under CM, 795 under PM. Both pass
`audit_contracts` with no finding.

### Gold

`gold-v3`, the gold at the close of the contract cleanup, merged per check into
`checks/do-fig-checklist-cm/` and per panel into `checks/do-fig-checklist-pm/`
for the 38 figures (`27b8c4208`, reviewed). **`gold-v4`** tags `gold-v3` with
those two merged golds added. The notebook pins the scorer to it
(`soda_mmqc/gold.py`).

## Preparation

| # | step | done |
|---|---|---|
| P1 | The scorer read a field in an object nested in a row as absent on both sides; fixed, with a test that nested and flat score identically. No earlier contract has such a field | `892393a14` |
| P2 | Spurious, missing and partly missing panels per figure, both shapes, tested | `5658e85f6` |
| P3 | `gold-v3` merged per check and per panel, refusing on any label disagreement | `27b8c4208` |
| P4 | The cleanup ported into the three checks and aligned in the shared skills, one skill at a time | `1199f44d1` … `d276f5374` |
| P5 | Two entry skills, identical but for the name; no assembly sentence needed (smoke test) | `0d2feb23e` |
| P6 | Both contracts derived, verified, audited clean | `0d2feb23e` |
| P7 | `gold-v4` tagged | `58c4d4ef7` |
| P8 | Margins from exp-03's observed half-widths | this note |
| P9 | Smoke test | below |

**Smoke test, 2026-10-05.** Six conditions × 3 figures (`s44318-026-00715-1`
content/1–3), one replicate, 18 sessions, none failed, $1.84.

- **Dispatch**: all three checks in 18/18, always in D's listed order; no skill
  outside a condition's closure.
- **Reach**: `A|B ← C_i ← D` reached `classify-panels` in 2/3 sessions (CM) and
  3/3 (PM), once each; `A ← B ← C_i ← D` reached both shared skills in 6/6,
  `classify-panels` twice in one CM session.
- **Shape**: every answer validates against its contract; PM rows all carry
  `panel_classes`, none empty, composite panels with several classes.
- **Panels**: the one figure with spurious panels (content/3: 2 spurious, 1
  missing, as if one panel were split) shows them in both shapes.
- **Cost** per condition, CM / PM: $0.32 / $0.35, $0.24 / $0.31, $0.25 / $0.37.

## Runs

| date | arm | command | cost | output |
|------|-----|---------|------|--------|
| 2026-10-05 | smoke, six conditions | `run.py --smoke` | $1.84 | `experiments/runs/exp-04-panel-major/smoke/` (not committed) |
| | all six | `python experiments/exp-04-panel-major/run.py` | est. $110–120 | `experiments/runs/exp-04-panel-major/` |

The estimate is the smoke test's cost per session — about $0.09 CM and $0.11 PM
— over 570 sessions each.

## Findings

*To be written after the run.*

## Threats to validity

- **The DAG-dependence is shown on chains only.** The third arrangement deepens
  the DAG, but every check still shares both A and B, so the PM contract's
  common fields split the same way in all three. A branched DAG — a shared skill
  used by some checks and not others — is where a PM contract has no obvious
  shape, and exp-04 does not test one.
- **The entry skills differ in their name.** The model sees `-cm` or `-pm` in
  the skill it starts from. Everything else in their prose is identical.
- **Spurious panels are rare and concentrated**, so their test has little
  power; see *Margins*.
- **The third arrangement has no prior variance**, and its margins rest on the
  second's.
- **`panel_classes` is unscored**: the shared step is present but unmeasured.
- **Order is fixed**, so a check's position is confounded with its identity, as
  in exp-03.
- **38 figures** bound the precision of every per-check estimate; properties
  that apply to few panels have wide intervals at layer 2.
- **Wording and contract both changed against exp-03.** exp-04 does not compare
  with exp-03, so this matters only for reading its numbers beside exp-03's.

## Gold this was scored against

**`gold-v4`** — `gold-v3` (the contract cleanup's gold, 2026-10-05) with the
merged gold of `do-fig-checklist-cm` and `do-fig-checklist-pm` added.

## Status and next

Planned. Next: the full run; the notebook, written while it runs, pinned to
`gold-v4`.
