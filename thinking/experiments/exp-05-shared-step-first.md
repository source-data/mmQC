---
title: exp-05 — the shared step first, by design
date: 2026-10-06
status: draft          # draft | planned | running | done | abandoned
kind: experiment
extends: exp-04
tags: [experiment, skills, dag, entry-point, shared-step, tokens]
---

# exp-05 — the shared step first, by design

*A draft plan, not a preregistration. Open decisions carry a recommendation;
the note becomes a preregistration once they are settled and the prep steps
have passed.*

## Question

Should the entry skill run the shared step itself — panel identification and
classification, once — and only then dispatch the checks, which take the panel
list as given?

exp-03 and exp-04 chained the skills from the bottom: D names the checks, and
each check either does the shared step inline (`A|B|C_i ← D`) or calls it
(`A|B ← C_i ← D`, `A ← B ← C_i ← D`). The model kept undoing that order. Under
D, `classify-panels` was reached once per session and never once per check
(exp-03); and under the panel-major contract, which asks D for the panel
classes directly, D took the shared step on itself and in 20 sessions then
answered without invoking any check (exp-04). exp-05 makes the order the model
reaches for the designed one:

```
[A|B, {C_i}] ← D        D invokes classify-panels (A|B) once, then each check
```

## Why, from exp-04

From [exp-04's findings](exp-04-panel-major.md#findings):

- `A|B ← C_i ← D` under the check-major contract was the most accurate of the
  six conditions at layer S counting both errors (0.997);
- the panel-major contract pulled the shared step up to D: `classify-panels`
  reached in 95–97% of PM sessions against 68–76% under CM, and 33 PM sessions
  answered without invoking a check;
- PM wrote 31–44% more output tokens than CM, unaccounted for by the answer or
  by resubmissions; one untested explanation is that a panel-major answer must
  be transposed from check-by-check work.

## Hypotheses (draft)

Both contract shapes, each against the **same shape** under exp-04's
`A|B ← C_i ← D` — exp-04's CM-2 and PM-2:

1. **Non-inferior.** `[A|B, {C_i}] ← D` is no worse, per check, at layers S, 1
   and 2, under exp-04's statistics and margins.
2. **Fewer output tokens under PM.** PM under `[A|B, {C_i}] ← D` writes fewer
   output tokens per figure than exp-04's PM `A|B ← C_i ← D`: the per-figure
   ratio's 95% interval lies below 1. If the shared step is settled once, up
   front, by the skill that owns the panel rows, less is written to assemble
   them. CM's output tokens, cost and input tokens are reported beside it,
   without a direction.

What would count as being wrong: a check degrading under the new arrangement,
which would say the checks need to make or fetch the inventory themselves; or
PM's output tokens unchanged, which would say its extra writing is not about
where the shared step sits.

**Dispatch is read first, and carries a named risk**: having classified the
panels itself, D may answer every check without invoking one — exp-04's PM
failure mode, which this arrangement could make easier rather than harder.

## Design (draft)

### Conditions

| condition | entry | arrangement | source |
|---|---|---|---|
| **CM-5** | `do-fig-checklist-cm` v2 | `[A\|B, {C_i}] ← D` | new, 190 sessions |
| **PM-5** | `do-fig-checklist-pm` v2 | `[A\|B, {C_i}] ← D` | new, 190 sessions |
| CM-2 | `do-fig-checklist-cm` v1 | `A\|B ← C_i ← D` | **exp-04's run, reused** |
| PM-2 | `do-fig-checklist-pm` v1 | `A\|B ← C_i ← D` | **exp-04's run, reused** |
| PM-2, sanity rerun | `do-fig-checklist-pm` v1 | `A\|B ← C_i ← D` | rerun, 38 figures × 1 replicate |

Model, provider, closure assembly, the 38 figures, 5 replicates, the contracts
and `gold-v4` are exp-04's. **About 418 sessions, ≈ $40.**

**exp-04's references are reused** (decided 2026-10-06): exp-04 ran on
2026-10-05/06, with the same model pinned by name, and nothing on this side has
changed. As a **sanity check**, not a gate, exp-04's PM-2 — the reference
hypothesis 2 reads — is rerun once on every figure, and its output tokens and
layer-S and layer-1 rates are reported beside exp-04's. No decision rule rests
on it: one replicate against five is a look, not a test.

### The skills

A new checklist, `fig-checklist-exp05`, starts as a copy of
`fig-checklist-exp04` as it stands — which stays frozen — and adds new versions:

- **`do-fig-checklist-cm` and `-pm` v2**: invoke `classify-panels` first, then
  each check. Identical but for the name, as at v1.
- **the three checks at v4**: v3 without the call to `classify-panels`; they
  take the panel list and classes established earlier in the session. Their
  `requires` is empty.
- **`classify-panels` v1** as A|B: it identifies and classifies, and calls
  nothing. `identify-panels` is reached by no arrangement, and closure assembly
  leaves it out.

The entry skills keep their names, so their contracts and `gold-v4`'s merged
gold apply unchanged. Written as exp-04's were: one skill at a time, proposed
by Claude from the v1/v3 wording, edited by the author, checked.

### Endpoints

exp-04's, unchanged — dispatch (endpoint 0), layers S, 1 and 2 with layer S
also reported with spurious rows, spurious and missing panels per figure,
replicate variance — with two changes:

- **Hypothesis 2** is the PM output-token ratio, one-sided: the mean of
  per-figure ratios, exp-05 ÷ exp-04, replicates averaged per figure first,
  percentile bootstrap over the 38 figures; **fewer** if the 95% interval lies
  below 1. Cost, input tokens, turns and time reported beside it, both shapes.
- **Endpoint 0** adds whether `classify-panels` was invoked **by D, before
  any check** — the designed order — and how many sessions answered without
  invoking any check.

## Decisions to settle

| # | decision | recommendation |
|---|---|---|
| 1 | reuse exp-04's CM-2 and PM-2 as references | **settled 2026-10-06**: yes, with one sanity rerun of PM-2, reported, not gated |
| 2 | does a check at v4 say where its panel list comes from | **settled**: yes — "established earlier in this session, by the skill that invoked you" |
| 3 | the order in D v2 | **settled**: `classify-panels`, then exp-04's check order |

## Prep work (draft)

| # | step |
|---|---|
| P1 | Copy `fig-checklist-exp04` to `fig-checklist-exp05` |
| P2 | Write D v2 and the checks at v4, one at a time, reviewed |
| P3 | Check the closures: D v2 reaches `classify-panels` and the three checks at v4, nothing else |
| P4 | The contracts are exp-04's, byte for byte; `build_contract.py`'s checks rerun on the new checklist |
| P5 | A runner for the two new conditions and the drift check |
| P6 | Smoke test |
| P7 | The notebook: exp-04's, reading exp-05's runs against exp-04's references |

## Threats (draft)

- **References from another run**, a day earlier; the sanity rerun looks at
  one of them on one replicate.
- **Wording moves with the arrangement.** D v2 says more than D v1, and the
  checks at v4 say less than at v3; the comparison is of arrangements as
  written, not of call order alone.
- **The same named risk as exp-04**: a D that classifies may answer without
  dispatching.
- **Order is fixed**, as in exp-03 and exp-04.

## Status and next

Draft, decisions settled. Next: P1–P2.
