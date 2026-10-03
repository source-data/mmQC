---
title: exp-04 — a panel-major schema for a skill DAG
date: 2026-09-29
status: draft          # draft | planned | running | done | abandoned
kind: experiment
extends: exp-03
tags: [experiment, skills, dag, schema, panel-major]
---

# exp-04 — a panel-major schema for a skill DAG

*A draft plan, not a preregistration. Each open decision below carries a
recommendation; the note becomes a preregistration once they are settled, the
margins are sized and the verification steps have passed.*

## Question

When checks share an upstream step — panel identification and classification
— should the output contract share it too? Does a **panel-major** contract,
with one row per panel carrying the shared step once and each check's fields
beside it, do better than exp-03's **check-major** contract, where every check
restates its own panel list?

## Paper claim

That the schema should **mirror the skill DAG**: what a shared skill produces is
a shared field, what a check produces is that check's field. exp-03 showed that a
single entry point dispatches reliably and saves cost, and that below it the
model already treats the shared step as belonging to the figure rather than to
each check. The claim here is that a contract built to that shape removes the
cost exp-03 paid for restating it.

## Why, from exp-03

From [exp-03's findings](exp-03-checklist-entry.md#findings) (closure assembly,
5 replicates, 38 figures, 1,520 sessions):

- **D dispatches**: all three checks invoked in 189/190 sessions per arm.
- **The shared step is done once per figure, or not at all.** Under D,
  `classify-panels` was reached in 72 of 190 sessions — **once each time, never
  once per check** — against 86–99% of sessions per check when each ran alone.
- **Under D, the checks' row lists look like one inventory copied three times.**
  `individual-data-points` and `error-bars-defined` have *identical* missing and
  spurious counts under the fan-out (7 missing / 25 spurious in `A|B|C_i ← D`,
  6 / 15 in `A|B ← C_i ← D`), and `micrograph-scale-bar` is close (8 / 28, 8 / 21).
  Per check, spurious rows were 3, 3 and 15 in `A|B|C_i`.
- **`error-bars-defined` loses its applicability judgement under D**: layer 1
  degraded by −0.062 and −0.047, against δ₁ = 0.02, in both arms — including
  the one where every check carries A and B inline and nothing is skipped.
- **The fan-out is cheaper**: 0.77 and 0.66 of the per-check cost per figure.

The model does the shared step once; the check-major contract then makes it
restate that step in three lists, and the restatement is where rows are added
and, for one check, where applicability goes wrong. A contract that asks for the
shared step once, where the DAG puts it, matches what the model already does.

## Hypothesis (draft)

**A panel-major contract reduces spurious rows and restores
`error-bars-defined`'s layer 1, relative to exp-03's check-major fan-out, and is
non-inferior to the per-check controls on every gate.**

This is the series' first **directional** prediction, and it is recommended as
such: exp-03 supplies the direction and a mechanism, which exp-02 and exp-03 did
not have when they chose non-inferiority. The alternative — non-inferiority
throughout, with any improvement reported as observed — remains open.

What would count as being wrong: spurious rows no lower than exp-03's fan-out,
or `error-bars-defined`'s layer 1 still degraded. The latter would say the
degradation is interference between checks sharing a context — order, attention
— rather than a consequence of restating the inventory, and that no contract
change reaches it.

## Design (draft)

### The contract

One list, one row per panel:

```json
{
  "outputs": [
    {
      "panel_label": "A",
      "panel_classes": ["micrograph"],
      "micrograph-scale-bar":   { "micrograph": "yes", "scale_bar_on_image": "yes", "…": "…" },
      "individual-data-points": { "plot": "no", "…": "…" },
      "error-bars-defined":     { "error_bar_on_figure": "no", "…": "…" }
    }
  ]
}
```

- `panel_label` is aligned once, so **layer S is one row set per figure**.
- Each check's fields sit in a nested object inside the row, unchanged in name
  and matching profile. Layer 1 and layer 2 stay per check and pair with exp-03
  after a prefix rewrite, as exp-03 paired with its controls.
- `panel_classes` is the shared B field — see *Decisions*.

Derived, not authored, from the three per-check contracts, as exp-03's was, with
the same refuse-unless-identical verification on committed predictions.

### Conditions

| condition | contract | skills | source |
|---|---|---|---|
| **check-major fan-out** | `{<check>: [rows]}` | D + checks v1 | **exp-03's `A\|B\|C_i ← D` runs, reused** |
| **panel-major, same skills** | one row per panel | D + checks v1 | new |
| **panel-major, restructured** | one row per panel | D doing A\|B once; checks C-only (v4) | new |
| per-check controls | per-check | each check v1 alone | **exp-03's `A\|B\|C_i` runs, reused** |

**Recommended: all three fan-out conditions**, on the monolith arrangement.

- *Panel-major, same skills* changes **only the contract**: the skills are
  exp-03's, byte for byte. It is the condition that answers the question as
  asked.
- *Panel-major, restructured* adds the skill change the contract invites — the
  shared step moved to D and out of the checks, which also removes exp-03's
  unreliable nested call rather than trying to make it reliable. Against the
  previous condition it isolates the skill change; against the check-major
  fan-out it measures both together.
- The monolith arrangement, not `A|B ← C_i`, because it is exp-03's cleaner
  arm: nothing is skipped, so a difference is not confounded with a delegation
  that did not happen.

**Reusing exp-03's runs** as the check-major and per-check references is
recommended on the same grounds as borrowing was first considered for exp-03,
now without its flaw: same model, same closure assembly, same skills byte for
byte, a day apart. The time gap is a stated threat.

**Sessions**: two new conditions × 38 figures × 5 replicates = **380**, at
exp-03's fan-out cost of about $0.086 per figure, **≈ $35**.

### Endpoints (draft)

As exp-03 — dispatch reported, layers S, 1, 2 in a fixed sequence — with two
changes forced by the contract:

- **Layer S becomes one row set per figure.** "Correct rows" compares directly;
  **spurious rows** is promoted to an endpoint, since it is where the hypothesis
  predicts a difference, and needs a definition that compares one list with
  three — recommended: per figure, a spurious panel counts once, however many
  check lists in exp-03 repeated it.
- **Endpoint 0 adds whether D did A\|B itself** in the restructured condition,
  read from the trace and the answer.

## Decisions to settle

| # | decision | recommendation |
|---|---|---|
| 1 | directional hypothesis, or non-inferiority | directional, as drafted |
| 2 | which conditions | all three fan-out conditions, monolith arm |
| 3 | reuse exp-03's runs as references | yes |
| 4 | `panel_classes`: scored, derived, or left out | **left out of scoring** for exp-04 — see below |
| 5 | vary D's check order | not here; see below |
| 6 | how an explanation field is scored beside an enum decision | settled in the contract cleanup (C3) |

**On `panel_classes`.** There is no gold for it: the per-check golds carry
yes/no flags (`micrograph`, `plot`, …), not a content-type label. Curating it is
the only way to score the shared step directly, and it is new curation work. For
exp-04 the recommendation is to include the field in the schema — so the model
states the shared step once, where it belongs — but not to score it, and to curate
it as a separate piece of work if exp-04 holds. Whether the scorer tolerates an
unprofiled schema field has to be checked; if not, the field is omitted.

**On order.** exp-03 could not tell whether `error-bars-defined` degrades
because it is that check or because it always ran third. Counterbalancing D's
order would answer that, but it varies D's prose, and it is a question about
exp-03's degradation rather than about the contract. It fits better as its own
small follow-up — or as a fourth condition, if the panel-major contract does not
restore layer 1 and position becomes the leading explanation.

## Depends on the contract cleanup

exp-03's addendum traced `error-bars-defined`'s layer-1 degradation to a
contract defect, and an audit of every contract found more. That work is
separate from exp-04 and comes first:
[`plans/2026-09-30-contract-cleanup.md`](../plans/2026-09-30-contract-cleanup.md).
**exp-04 does not start until it is done.**

**Status, 2026-10-03:** the production `fig-checklist` is clean. What exp-04
still needs from it is a **port**: exp-04 builds on exp-03's hierarchical skills
(`fig-checklist-exp03`: the three checks at v1 and v3, `classify-panels`, D),
which predate the cleanup and use its legacy vocabulary. Their wording,
contracts and gold conventions have to be brought in line with the cleaned
`fig-checklist` — `individual-data-points`' `not_required` / `not_applicable`,
`error-bars-defined`'s `is_a_plot`, split `decision` and `explanation`, and the
"a plot is checked" model — one skill at a time and reviewed, since the exp-03
skills split the same instructions across blocks differently from the
production skills. `micrograph-scale-bar` had no findings and needs no port.
exp-04 is then also the first experiment scored against the cleaned gold.

What exp-04 takes from it: one `not_applicable` token, always scored as NA;
no fixed token inside free text, so each check's verdict is an enum and any
explanation a separate field; free text scored semantically; and a clean audit
as a precondition for every contract exp-04 builds.

## Prep work (draft)

| # | step | why |
|---|---|---|
| P1 | Show the scorer handles a check's object nested inside a list row (`outputs[].<check>.x`) exactly as the flat field | exp-03 found the scorer reads lists only at the root or in a row; nesting objects in rows is untested |
| P2 | Define and implement the one-list spurious-row count, and compute it on exp-03's runs | the reference value for the hypothesis |
| P3 | Merge the gold per panel — labels agree across the three checks on all 38 figures since the `emboj.2009.340` fix | mechanical, verified like exp-03's |
| P4 | Size the margins from exp-03's observed variance, which came out wider than exp-02's at layer S | exp-03's planned half-widths were too tight |
| P5 | Write the checks' v4 (C-only) and D's v2 (A\|B once, then dispatch) — **drafted one at a time and reviewed**, since the blocks encode domain judgement | skills need human review |
| P6 | Every contract passes `audit_contracts` with no finding | the audit of 2026-09-30 |
| P7 | Smoke test on every new condition | as for exp-03 |

## Threats (draft)

- **Contract and skills move together** in the restructured condition; the
  same-skills condition is what separates them.
- **References from another run.** exp-03's runs are a day old; nothing
  re-measures them alongside the new conditions.
- **The spurious-row definition is new**, and a comparison between one list and
  three depends on it. It is fixed before the run, not after.
- **`panel_classes` unscored** means the shared step is present but unmeasured;
  a contract that improves layer S through it cannot show so directly.
- **Order stays fixed**, so `error-bars-defined`'s position is still confounded
  with its identity.
- **exp-02-closure is pending.** exp-02 is to be re-run under closure assembly;
  exp-04 does not depend on it, but both bear on how the monolith is read.

## Status and next

Draft, **blocked on the contract cleanup**. Then: settle the decisions, run P1–P4, draft the skills one at a
time for review (P5), pass the contract audit (P6), smoke-test (P7), then
preregister in exp-03's format.
