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

*C1, C2, C4 and C5, and the gold-migration approach, were decided at G1 on
2026-10-01, and C3's scoring of the explanation on 2026-10-01. See the
decisions record.*

### C1 — One token for "not applicable", always NA

**`not_applicable`**, snake case, used for every field and every check where the
check does not apply to the panel — **in the schema, the manifest, the skill
prose and the gold alike** — and **always** listed in the manifest's
`na_values`, so applicability is judged at layer 1 everywhere.

- `not needed`, `not_needed`, `N/A` and `not a plot` are retired.
- `not_applicable` over `not needed` because it names the concept — "needed"
  suggests an obligation, not applicability — and because four checks already use
  it.
- `N/A` in the three `decision` enums (`plot-axis-units`, `plot-gap-labeling`,
  `stat-significance-level`) means not applicable; its absence from their
  manifests' `na_values` was an oversight, not a design. It becomes
  `not_applicable` **and moves to layer 1**. That changes what those checks'
  layer 2 measures, which is the point: a verdict on a panel the check does not
  apply to is not a verdict.

### C2 — "Not applicable" and "not reported" stay distinct

`not_reported` (the check applies; the figure or caption does not say) and
`unclear` are **real answers**, scored at layer 2, never NA. The convention
states it so that `not_reported` is not normalised away with the rest.

### C3 — A fixed token never lives in free text

Every field scored against a fixed token is an **enum**. A field that combines a
verdict and its reason is split into an enum field and a free-text field. For
`error-bars-defined`, whose skill lumped the two together:
`decision: PASS | FAIL | not_applicable` and `explanation: <free text>`.

**The split's gold is mechanical, and verified.** In the 38 benchmark figures all
298 `Decision_and_explanation` values parse, and agree exactly with
`error_bar_on_figure`: 174 bare `not needed` (every one with
`error_bar_on_figure: no`), 113 `PASS: <reason>` and 11 `FAIL: <reason>` (every
one `yes`). So `decision` is the leading token and `explanation` the text after
it — empty when not applicable. The migration script checks that every row
parses, that the decision agrees with `error_bar_on_figure`, and that the two
fields rejoin into the original string.

**Not adopted: widening `na_values`** to catch annotated variants. It is an
exact-match list, and the annotations are open-ended (`not needed - micrograph
panel …`, `not needed: …`), so a list would chase the model's wording and still
miss. A single **prefix rule** — the NA token, a separator, then anything —
recovers 99% of the annotated cases in exp-03, and is kept for one purpose only:
**exploratory re-scores of exp-01 to exp-03**, labelled as such. It is never a
way to keep a lumped field in a new contract.

**Open for C3:** how the free-text companion is scored on a panel where the
decision is `not_applicable`. If it is scored on its own value, a session that
explains itself there is again a spurious applicable answer. Options: (a) the
explanation is **not scored**; (b) its applicability **follows the decision
field**, which the scorer cannot express today (layer 1 is judged per field, from
that field's own value) and would need a manifest feature such as
`applicable_when`. **Decided: (a), the explanation is not scored**; (b) remains a
possible scorer feature if explanations turn out to be worth scoring.

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
| W1 | Extend `audit_contracts` with the rules still missing: manifest token absent from schema and gold (`not_needed`); free text scored non-semantically without an identifier declaration; missing manifest; vocabulary outside C1; gold outside its own enum | `soda_mmqc/scripts/audit_contracts.py` | **done** 2026-10-01, `6164c51ff`, `0c32ce7a0`; 19 rule tests |
| W2 | Scorer: type `anyOf` / union nodes, and **refuse** a schema leaf it cannot type (C5) | `soda_mmqc/core/schema_discovery.py` | **done** 2026-10-01, `2b4983b4b` |
| W2b | Manifest: a field can be **declared unscored** (`"scored": false`) — today an unlisted field inherits the default polarity, so C3's unscored explanation is impossible | `soda_mmqc/core/eval_manifest.py`, evaluation | tests; after G2 |
| W3 | Decide C1–C5 | this plan | **human gate G1** |
| W4 | Field-by-field fix list for every check: new enum, token, metric, gold rewrite rule, skill-prose change | this plan, appendix | **drafted** 2026-10-01 — **human gate G2** |
| W5a | Tag `gold-v1`; add the `SODA_MMQC_EXAMPLES_DIR` override; pin the exp-01–03 notebooks to `gold-v1` and record it in their notes | `config.py`, notebooks, `thinking/experiments/` | tests; each frozen notebook reproduces its committed findings against `gold-v1` |
| W5 | Migrate gold to the new vocabulary with a script: token rewrites, and the `error-bars-defined` split — verified that every row parses, decisions agree with `error_bar_on_figure`, split fields rejoin to the original, nothing else changes, and every rewritten gold validates against its new schema | `soda_mmqc/scripts/` | **human gate G3** — the diff is reviewed before commit; **W5a first** |
| W6 | Update schemas and manifests of the production checklist | `…/fig-checklist/`, `…/doc-checklist/` | audit clean |
| W7 | Update skill prose to the new tokens and split fields — **one skill at a time, reviewed** | `…/SKILL.md` | **human gate G4**, per skill |
| W8 | Manifests for `data-checklist`, or declare it out of scope | `…/data-checklist/` | G2 |
| W9 | Make the audit a test: every contract of the production checklist passes with no finding | `tests/` | CI |
| W10 | Addenda to exp-01 and exp-02: the `error-bars-defined` artifact, `n_value_min` unscored, and — as **exploratory** re-scores, kept apart from the preregistered numbers — what their layer-1 numbers become under the prefix rule and under the new gold | `thinking/experiments/` | — |

### Where the rewritten gold lives, and how the frozen experiments stay reproducible

*Decided at G1.*

**Gold is rewritten in place**, in `soda_mmqc/data/examples/`, and committed on
this branch. It is not copied to a parallel folder: the scorer, the runner's
staging and the curation UI all resolve gold at
`examples/<figure>/checks/<check>/expected_output.json`, by check name, and a
second tree would need a switch in every reader — and would drift, since a
curator's fix would land in one of the two. Git already versions all 1,586 gold
files.

**The hazard it creates.** Experiment analyses are not committed; they are
recomputed from predictions and gold. After the rewrite, re-running the exp-01–03
notebooks at head would score their predictions (`not needed`, `N/A`) against
the new gold (`not_applicable`) and change their numbers without saying so —
the exp-03 notebook would even trigger it, since it re-scores whenever gold is
newer than an analysis.

**So, before the rewrite:**

1. **Tag the last commit before it** — `gold-v1` — and write into each
   experiment note which gold it was scored against.
2. **Make the gold location overridable** — a `SODA_MMQC_EXAMPLES_DIR`
   environment variable read by `config.py`, whose comment already promises a
   data-directory override that nothing implements. A frozen experiment's
   notebook then scores against a `git worktree` of `gold-v1`, while its code and
   runs stay at head.
3. **Point each frozen experiment's notebook at `gold-v1`**, and make it refuse
   to score against any other gold unless told to.

**Re-scores under the new gold are exploratory**, and kept separate from the
preregistered numbers: recorded as addenda, never as revisions. The experiment
checklists (`fig-checklist-exp01` … `-exp03`) are not edited.

### Order

1. W1, W2 — tooling first, so the audit can be trusted and the scorer sees
   every field.
2. G1 — conventions, including the historical-runs option.
3. W4 → G2 — the fix list.
4. W5a, then W5 → G3, W6, W7 → G4 — protect the frozen experiments, then gold,
   contracts, prose.
5. W8, W9 — coverage and the standing test.
6. W10 — what it changes for the experiments already run.
7. Then exp-04, on clean contracts, and exp-02-closure.

## Decisions record

*Filled in at each gate: date, who, decision, conditions.*

| gate | decision | date | by |
|---|---|---|---|
| G1 | C1 `not_applicable` everywhere, gold included; `N/A` treated as not applicable; C2; C3 split of `error-bars-defined`'s field, no widened `na_values`, prefix rule for exploratory re-scores only; C4; C5. Gold rewritten in place, after tagging `gold-v1` and adding a gold-location override; new-gold re-scores exploratory and separate. C3: the explanation is **not scored** | 2026-10-01 | Thomas Lemberger |
| G2 | | | |
| G3 | | | |
| G4 | | | |


---

## Appendix — W4, the field-by-field fix list *(for gate G2)*

Drafted 2026-10-01 from `audit_contracts --checklist fig-checklist
--checklist doc-checklist` (39 findings) and the gold. **Mechanical** gold
rewrites follow a rule a script applies and verifies; **curation** needs a
person's judgement and goes to the curation UI, not a script. Counts are over
every gold file of the check, benchmark or not. Skill prose: line numbers in
the pinned `v1/SKILL.md`, changed one skill at a time at G4.

### `error-bars-defined` — prose lines 70, 72, 77, 84

| field | change | manifest | gold |
|---|---|---|---|
| `Decision_and_explanation` | **split** into `decision: PASS \| FAIL \| not_applicable` and `explanation: string` (C3) | `decision`: multiclass, `na_values [not_applicable]`; `explanation`: **unscored** (needs W2b) | mechanical, verified: `not needed` → `decision not_applicable`, `explanation ""` (178); `PASS: …` / `FAIL: …` → token + reason (124 in the benchmark) |
| `error_bar_defined_in_caption` | enum `not needed` → `not_applicable` | `na_values [not_applicable]` | mechanical: 254 |
| `from_the_caption` | free text keeps no token: not applicable is `""` — applicability is carried by `error_bar_defined_in_caption` (C3) | `na_values [""]`, semantic | mechanical: `not needed` → `""` (174). `""` already means "no definition found" (88), and both stay NA, as today |

### `individual-data-points` — prose lines 52, 54, 57, 63, 66

| field | change | manifest | gold |
|---|---|---|---|
| `individual_values` | enum `not needed` → `not_applicable` | `na_values [not_applicable]` | mechanical: 379 |
| `decision` | enum gains `not_applicable` | multiclass, `na_values [not_applicable]` | **mixed**. Mechanical: `plot: no` → `not_applicable` (223 now `PASS`, 53 now `""`). **Curation**: 50 plots with a blank decision; 30 plots with `individual_values: no` marked `PASS`, beside 31 marked `FAIL` — the rule is not the gold's |

The blank gold matters already: under a `PASS \| FAIL` enum no session can
answer `""`, so all 103 blanks have been forced layer-2 mismatches, in every
experiment, equally in every arm.

### `plot-axis-units` — prose lines 62, 78, 82, 89

| field | change | manifest | gold |
|---|---|---|---|
| `decision` | enum `N/A` → `not_applicable` | multiclass, `na_values [not_applicable]` — **moves to layer 1** | mechanical: 283 |
| `units_provided[].answer` | enum `not needed` → `not_applicable` | `na_values [not_applicable]` | mechanical: 409 |

### `plot-gap-labeling` — prose lines 42, 57, 68, 73

| field | change | manifest | gold |
|---|---|---|---|
| `decision` | enum `N/A` → `not_applicable` | multiclass, `na_values [not_applicable]` — **moves to layer 1** | mechanical: 274 |

Its other fields already use `not_applicable`.

### `replication-reporting` — prose line 67

| field | change | manifest | gold |
|---|---|---|---|
| `n_value_min` | none — the union is now typed (W2) | **new entry**: multiclass (an integer matches exactly), `na_values [not_applicable]`; `not_reported` stays a class (C2) | none |
| `replicate_type` | free text keeps no token: `""` when nothing to extract — applicability and "not reported" are carried by `replicate_type_reported` (C3) | `na_values [""]`, semantic | mechanical: `not_applicable` → `""` (137), `not_reported` → `""` (31) |
| `n_reported`, `replicate_type_reported`, `decision` | — | — | **curation**: one row blank in all three |

### `stat-significance-level` — prose lines 65, 70, 77

| field | change | manifest | gold |
|---|---|---|---|
| `decision` | enum `N/A` → `not_applicable` | multiclass, `na_values [not_applicable]` — **moves to layer 1** | mechanical: 418 |
| `symbol_definition` | — | `na_values` drops the orphan `not_needed`, keeps `""` | none |
| `significance_level_symbols_on_image` | — | stays exact: **declared an identifier** (`*`, `**`, `ns` are different answers) | none |
| `is_a_plot` | — | — | **curation**: 4 blank |

### `stat-test` — prose lines 49, 65

| field | change | manifest | gold |
|---|---|---|---|
| `statistical_test_mentioned` | enum `not needed` → `not_applicable` | `na_values [not_applicable]` | mechanical: 405 |

### `doc-checklist`

| field | change | manifest | gold |
|---|---|---|---|
| `author-contribution-in-ms · statement_type` | free text scored as multiclass → **enum** `free_text \| CRediT \| contribution_roles \| not_applicable` (from its description; gold uses `not_applicable` 14, `free_text` 2) | multiclass, `na_values [not_applicable]` | none |
| URLs in `external-data-url-validation` and `-agentic` (2 fields) | — | stay exact: **declared identifiers** | none |
| section names in `section-order` and `section-order-alt` (8 fields) | — | stay exact: **declared identifiers** | none |

### `data-checklist`

`SD-mapping` (25 gold files), `panel-data-replication-validation` (5) and
`western-blot-matching-SD` (36) have schemas, benchmarks and gold, and **no
manifest**. *Proposed:* in scope — W8 drafts their manifests under C1–C5 after
G2, for review then.

### Totals

| | |
|---|---|
| mechanical gold rewrites | about 3,700 values across 7 checks |
| curation | `individual-data-points · decision` (80 rows), `replication-reporting` (1 row), `stat-significance-level · is_a_plot` (4) |
| new scorer feature | W2b, an unscored declaration |
| skills to edit at G4 | 7 |
| identifiers to declare | 11 fields |
