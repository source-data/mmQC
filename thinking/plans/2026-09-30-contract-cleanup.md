# Contract cleanup: make every schema agree with its manifest

**Goal:** every check's output schema and eval manifest agree on what each field
may hold and how it is scored, one vocabulary for "not applicable" is used
everywhere, and a check proves it on every commit. **exp-04 does not start until
this is done.**

**Why now:** exp-03's addendum (2026-09-30) found that `error-bars-defined`'s
layer-1 "degradation" was a contract defect, not a judgement failure: a
not-applicable token inside free text, scored by exact match. The same artifact
runs through exp-01 and exp-02 at 18–100% by arm. An audit of every contract then
found more — including a field that has **never been scored at all**. Contracts
are the one thing every experiment holds fixed; if they are wrong, every
comparison inherits it.

**Scope:** every checklist with contracts, run or not. A contract that has never
been run is still a contract, and the consistency between its halves must hold
before it is.

---

## What the audit found

`python -m soda_mmqc.scripts.audit_contracts --runs`, and three inventories run
alongside it. All facts below are verified against the files and the committed
runs.

### 1. A field the scorer never sees — `replication-reporting · n_value_min`

The schema types it only through `anyOf` (an integer, or the enum
`not_reported` / `not_applicable`), with no top-level `type`. The scorer's schema
discovery reads the `type` key and **silently skips** a node without one, so the
field is not a scored leaf: exp-01's analyses of `replication-reporting` contain
no `n_value_min` instances at all.

**Why it has no manifest entry.** Not an outdated prompt: the field was in the
schema when the manifests were created (commit `d9309796b`, 2026-07-03, "Generated
evaluation manifests"), with the same `anyOf` shape it has now. The manifests
were generated, and the generator — not committed — evidently walked the same
typed nodes the scorer does, so it never saw the field either. **Two tools with
one blind spot, both silent.** The earlier audit message, that it "inherits the
default polarity", was wrong: it is not scored by any rule.

### 2. Not-applicable tokens inside free text

| field | runs |
|---|---|
| `error-bars-defined · Decision_and_explanation` | **2,900 annotated "not needed"** of 13,713 per-check values — the exp-03 case |
| `error-bars-defined · from_the_caption` | 7,696 exact, 0 annotated |
| `replication-reporting · replicate_type` | 544 exact, 0 annotated |
| `stat-significance-level · symbol_definition` | no runs |

Only the first has done harm, but all four have the shape that caused it.

### 3. The not-applicable vocabulary

Across the nine figure checks that use one, **four spellings of one idea**, and
three neighbours with different meanings:

| token | where | meaning |
|---|---|---|
| `not needed` | `error-bars-defined`, `individual-data-points`, `stat-test`, `plot-axis-units` (some fields) | not applicable |
| `not_needed` | `stat-significance-level` manifest only | not applicable — **used by neither its schema nor its gold** |
| `not_applicable` | `panel-image-matches-caption`, `plot-gap-labeling`, `replication-reporting`, `single-channel-for-overlay` | not applicable |
| `N/A` | `decision` of `plot-axis-units`, `plot-gap-labeling`, `stat-significance-level` | not applicable — **but scored as an ordinary class**, at layer 2 |
| `not_reported` | `replication-reporting` | applicable, information absent — a real answer |
| `unclear` | `replication-reporting · involves_replicates` | a real answer |
| `none` | skill prose of three checks | varies |
| `not a plot` | schema descriptions and prose | a reason, written where a token is expected |

So "not applicable" is judged at **layer 1** in some checks and at **layer 2** in
others, a manifest lists a token nothing produces, and the same concept is
spelled four ways — each a place for a session to write the "wrong" one.

### 4. Free text and its metric

Free text — quotes from the figure or caption, explanations — should be free
text, scored by **semantic similarity**. Where it is not:

| field | scored | nature |
|---|---|---|
| `doc-checklist · author-contribution-in-ms · statement_type` | multiclass | a closed set written as free text — should be an **enum** |
| `stat-significance-level · significance_level_symbols_on_image` | exact | symbols (`*`, `**`, `ns`) — an identifier |
| `doc-checklist` URLs, identifiers, section names (10 fields) | exact | identifiers |

Identifiers are the one principled exception: `**` and `***` are different
answers, and so are two URLs that differ by a character. They are not
explanations.

### 5. Missing contracts

`data-checklist`'s three checks (`SD-mapping`, `panel-data-replication-validation`,
`western-blot-matching-SD`) have schemas and no manifest.

---

## Conventions to adopt

*Decisions — each is a human gate below. Recommendations are marked.*

### C1 — One token for "not applicable", always NA

**Recommended: `not_applicable`**, snake case, used for every field and every
check where the check does not apply to the panel, and **always** listed in the
manifest's `na_values`, so applicability is judged at layer 1 everywhere.

- `not needed`, `not_needed`, `N/A` and `not a plot` are retired.
- `not_applicable` over `not needed` because it names the concept — "needed"
  suggests an obligation, not applicability — and because four checks already use
  it.
- `N/A` in the three `decision` enums becomes `not_applicable` **and moves to
  layer 1**. That changes what those checks' layer 2 measures, which is the point:
  a verdict on a panel the check does not apply to is not a verdict.

### C2 — "Not applicable" and "not reported" stay distinct

`not_reported` (the check applies; the figure or caption does not say) and
`unclear` are **real answers**, scored at layer 2, never NA. The convention
states it so that `not_reported` is not normalised away with the rest.

### C3 — A fixed token never lives in free text

Every field scored against a fixed token is an **enum**. A field that combines a
verdict and its reason is split into an enum field and a free-text field. For
`error-bars-defined`: `decision: PASS | FAIL | not_applicable` and
`explanation: <free text>`.

**Open for C3:** how the free-text companion is scored on a panel where the
decision is `not_applicable`. If it is scored on its own value, a session that
explains itself there is again a spurious applicable answer. Options: (a) the
explanation is **not scored**; (b) its applicability **follows the decision
field**, which the scorer cannot express today (layer 1 is judged per field, from
that field's own value) and would need a manifest feature such as
`applicable_when`. *Recommended: (a) now, (b) as a scorer feature if explanations
turn out to be worth scoring.*

### C4 — Free text is scored semantically; identifiers exactly

- Free text — quotes, extracted definitions, explanations — is
  `graded_string` / `semantic`, with an NA token only if the field is also an
  applicability carrier (which C3 then forbids).
- An **identifier** — a symbol, URL, accession, section name — is
  `graded_string` / `exact`, and its schema description says it is verbatim.
- A **closed set** is an enum, scored `multiclass` or `binary_polarity`.

Every free-text field is classified into one of the three, explicitly, in the
field list (W4).

### C5 — Every schema field is scored, or declared unscored

No field is silently skipped. A field the scorer cannot type is an error, not a
warning; a field deliberately left unscored is listed as such in the manifest.

---

## Work

| # | item | where | gate |
|---|---|---|---|
| W1 | Extend `audit_contracts` with the rules still missing: manifest token absent from schema and gold (`not_needed`); free text scored non-semantically without an identifier declaration; missing manifest; vocabulary outside C1 | `soda_mmqc/scripts/audit_contracts.py` | tests; runs clean on the fixed contracts |
| W2 | Scorer: type `anyOf` / union nodes, and **refuse** a schema leaf it cannot type (C5) | `soda_mmqc/core/schema_discovery.py` | tests; no published number moves except fields that were invisible |
| W3 | Decide C1–C5 | this plan | **human gate G1** |
| W4 | Field-by-field fix list for every check: new enum, token, metric, gold rewrite rule, skill-prose change | this plan, appendix | **human gate G2** |
| W5 | Migrate gold to the new vocabulary with a script: token rewrites only, verified that nothing else changes and every rewritten gold validates against its new schema | `experiments/` or `soda_mmqc/scripts/` | **human gate G3** — the diff is reviewed before commit |
| W6 | Update schemas and manifests of the production checklist | `…/fig-checklist/`, `…/doc-checklist/` | audit clean |
| W7 | Update skill prose to the new tokens and split fields — **one skill at a time, reviewed** | `…/SKILL.md` | **human gate G4**, per skill |
| W8 | Manifests for `data-checklist`, or declare it out of scope | `…/data-checklist/` | G2 |
| W9 | Make the audit a test: every contract of the production checklist passes with no finding | `tests/` | CI |
| W10 | Addenda to exp-01 and exp-02: the `error-bars-defined` artifact, `n_value_min` unscored, and — as exploratory re-scores — what their layer-1 numbers become under the fixed contracts | `thinking/experiments/` | — |

### The historical-runs problem, to settle at G1

**Gold is shared across checklists**: it lives per check in the examples tree,
not per checklist. Rewriting a gold token to `not_applicable` therefore changes
how every committed run of that check re-scores, including exp-01–03, whose
predictions say `not needed`.

Options:

1. **Rewrite gold; keep legacy aliases in the scorer.** The scorer maps legacy
   tokens (`not needed`, `not_needed`, `N/A`) to `not_applicable` on both gold
   and prediction before comparing, so committed runs re-score as before for
   exact tokens. One documented alias table, retired when no committed run needs
   it. *Recommended.*
2. **Rewrite gold; freeze experiment checklists with legacy-aware manifests.**
   Each historical checklist's manifest lists the legacy tokens in `na_values`.
   More edits, and it touches files the preregistrations hold fixed.
3. **Version gold** per contract version. Most faithful, most machinery.

Whatever is chosen, the experiment checklists (`fig-checklist-exp01` … `-exp03`)
are **not edited**: they are what their runs were scored against. Re-scoring
them under the new contracts is exploratory, and recorded as addenda (W10).

### Order

1. W1, W2 — tooling first, so the audit can be trusted and the scorer sees
   every field.
2. G1 — conventions, including the historical-runs option.
3. W4 → G2 — the fix list.
4. W5 → G3, W6, W7 → G4 — gold, contracts, prose.
5. W8, W9 — coverage and the standing test.
6. W10 — what it changes for the experiments already run.
7. Then exp-04, on clean contracts, and exp-02-closure.

## Decisions record

*Filled in at each gate: date, who, decision, conditions.*

| gate | decision | date | by |
|---|---|---|---|
| G1 | | | |
| G2 | | | |
| G3 | | | |
| G4 | | | |
