# Benchmarking and evaluation

This document describes how mmQC compares model predictions to curated gold labels during benchmarking. The implementation lives in `soda_mmqc.core.evaluation` (`FlatEvaluator`) and related modules.

Slide deck: [mmQC-benchmarking-slides.pptx](mmQC-benchmarking-slides.pptx).

## The flat leaf model

Each check asks the model to return structured JSON defined by `schema.json`. During benchmarking, each **benchmark example** is one model call: the runner compares one prediction to one gold `expected_output.json`. Both documents match the check schema at the root (for example `{ "outputs": [...] }`).

Each such comparison becomes one record in the `flat` array of `analysis.json`. There is no scoring hierarchy above that — aggregation across examples happens only when you summarize many `flat` records (for example in reporting notebooks).

Rather than scoring whole objects or nested structures as units, the evaluator works on **leaf properties** — the lowest-level fields in the output. Every compared value is either:

- a single **primitive** (`string`, `number`, `integer`, `boolean`), or
- an **array of primitives** (for example `tags: string[]`).

Intermediate objects are containers only. Their fields are flattened to dotted paths such as `outputs[].panel_label` or `item.meta.author`.

This “flat leaf” approach keeps scoring transparent: each field is judged on its own, and summaries roll up **within one leaf property at a time** — never across unrelated fields.

Two files define the contract:

| File | Role |
|------|------|
| `schema.json` | What the model **must** return (types, required fields, enums). The structured output the agent session is constrained to. |
| `eval-manifest.json` | How predictions are **scored and reported** (alignment, applicability, match rules). Applied at evaluation time only. |

Changing `eval-manifest.json` does not change what the model is asked to produce; it changes how strictly predictions are judged.

---

## Leaf properties and instances

A **leaf property** is a path pattern from the output root, for example `outputs[].micrograph` or `tags`.

A **leaf instance** is one concrete occurrence of that pattern in a given comparison, for example `outputs[0].micrograph` or `outputs[1].micrograph`.

A single figure may produce many instances of the same property (one per panel row). Aggregates such as `mean_score` are computed **per leaf property**, not mixed across properties.

### Scalar primitives

Strings, numbers, integers, and booleans are compared directly at their path.

| Type | Comparison |
|------|------------|
| `number`, `integer`, `boolean` | Exact equality → score `1.0` or `0.0` |
| `string` with schema `enum` | Exact literal match → `1.0` or `0.0`. A prediction outside the enum scores `0`. |
| Free `string` (no `enum`) | Comparison method set in the manifest (`exact`, `fuzzy`, or `semantic`) |

**Missing values:** an absent key or `null` where a value is expected scores `0`. An empty string `""` is a real string value — it is not treated as “missing” unless the manifest marks it as not applicable (see Layer 1 below).

### Arrays of primitives

When a leaf is an array of primitives (for example `tags: string[]`), the whole array is one leaf instance on path `tags`. Configure comparison in **`fields`** via **`primitive_list_compare`** (see [Evaluation manifest](#evaluation-manifest) → arrays of primitives). The manifest field selects how gold and prediction are compared:

| `primitive_list_compare` | When to use | Score |
|--------------------------|-------------|-------|
| `align` (default) | Set-like lists where order does not matter | Hungarian element matching; mean over `max(len(gold), len(pred))`, unmatched slots as `0` |
| `positional` | Index-bound parallel arrays (for example `yes`/`no` per slot) | Compare `gold[i]` to `pred[i]`; same mean-over-`max(len)` formula, no Hungarian |
| `join_string` | Holistic text comparison | Join elements (default separator `", "`), then apply `string_compare` once on the whole string |

For `join_string`, set `matching_metric: graded_string`, `string_compare`, and `match_threshold` on the same field. Optional `join_separator` and `sort_before_join` apply only to `join_string`.

There is no row-level structural reporting for primitive arrays — extra or missing elements are reflected in the aggregate score only.

### Lists of objects within one model output

When the schema contains a list of objects (for example `outputs[]` with one row per panel), row fields such as `outputs[].panel_label` are leaf properties. The model may return a variable number of rows, so the evaluator first pairs gold and predicted rows using Hungarian alignment.

`list_alignment` in the manifest names which row fields drive pairing. For example, with `"list_alignment": { "outputs": ["panel_label"] }`:

```text
s(i, j) = mean of leaf scores for alignment keys k
```

Each alignment key uses that field’s manifest profile (`string_compare`, `match_threshold`, etc.). The alignment score is used only for pairing — it is not rolled into `by_property` summaries.

After pairing, all row leaf fields are scored at each **gold row index**. A wrong value on a correctly paired row affects only that field’s score, not how rows were matched. Layer S reports whether each row was correctly paired, missing from the prediction, or spurious (`correct_row`, `missing_row`, `spurious_row`).

---

## Comparing leaf values

Every leaf instance comparison results in a **score** in the interval`[0, 1]`.

### Strings

**Schema enum fields** (for example `"yes"`, `"no"`, `"not needed"`) are always compared exactly. Do not set `string_compare` on these in the manifest.

**Free-text fields** use `matching_metric: graded_string` in the manifest and require `string_compare`:

| `string_compare` | How the score is computed |
|------------------|---------------------------|
| `exact` | Character-level equality → `0.0` or `1.0` |
| `fuzzy` | Edit-distance ratio (rapidfuzz) in `[0, 1]` |
| `semantic` | Cosine similarity of sentence embeddings in `[0, 1]` |

Each free-text field can use a different method. There is no global string metric.

## From score to matching labels

Benchmarking needs to answer three different questions about each field. They are kept separate so one number does not smuggle in policy choices that belong elsewhere.

| Question | What it captures | Why separate |
|----------|------------------|--------------|
| **How close?** | A **score** in `[0, 1]` — exact `0`/`1` for enums and numbers; graded for free text | Tracks *degree* of agreement (e.g. caption paraphrase at 0.85). Useful for `mean_score` and debugging, even when you would still call the answer “wrong” for strict QC. |
| **Was the field in scope?** | **Applicability** — should this field have been answered, or is it N/A? | Many checks use sentinels like `""` or `not needed`. A missing scale-bar quote on a non-micrograph panel is not the same kind of error as on a micrograph panel. |
| **Correct for benchmarking?** | A **discrete label** — match/mismatch, or TP/FP/FN/TN | Supports counting match vs mismatch events or confusion matrix-style reporting. Rules differ by field type (threshold vs exact yes/no). |

Pipeline for each leaf instance:

1. **Score** — compare gold and prediction (rules above).
2. **Applicability** — using manifest `na_values`, decide if both sides were in scope.
3. **Discrete label** — only when both sides were applicable: apply the field’s `matching_metric`.

For **free-text** fields (`graded_string`), the discrete label uses a **threshold** on the score:

```text
match     if score >= match_threshold
mismatch  otherwise
```

A semantic similarity of `0.85` with `match_threshold: 0.8` counts as a **match**, even though the strings differ. The property’s `mean_score` averages raw scores over **applicable** instances only (`layer1 = correct_applicable`), so N/A fields do not inflate the average.

For **yes/no** fields (`binary_polarity`), the discrete label is **TP**, **FP**, **FN**, or **TN** from exact class identity — not a similarity threshold.

For **multiclass** enums, the discrete label is **match** or **mismatch** on exact literal equality.

Fields without a manifest profile still get a **score**; applicability and discrete labels are omitted.

For object lists (`outputs[]`), row pairing (Layer S) runs before leaf scoring — see the next section.

---

## Three reporting layers

Reporting is organized in three layers that answer the three questions above.

![The three scoring layers on one micrograph-scale-bar prediction: Layer S pairs rows, Layer 1 judges applicability, Layer 2 matches values](scoring-layers.svg)

### Layer S — row alignment within a list

**Scope:** object lists in the model output (`outputs[]`, `panels[]`, …).

**Question:** For this benchmark example, was each gold row correctly paired with a prediction row?

| Outcome | Meaning |
|---------|---------|
| `correct_row` | Gold row paired with a pred row above the alignment threshold |
| `missing_row` | Gold row with no acceptable pred partner |
| `spurious_row` | Pred row with no acceptable gold partner |

Results appear under `by_list`, keyed by list name (for example `outputs`). List-level precision and recall can be derived from `row_counts`:

```text
recall    = correct_row / (correct_row + missing_row)
precision = correct_row / (correct_row + spurious_row)
```

A `missing_row` still produces leaf instances at the gold index with `pred_value = null` and `score = 0`. Layer S describes the **row event**; Layer 1 and 2 describe **field values within** that row.

`spurious_row` pred rows do not create gold-indexed leaf instances.

### Layer 1 — applicability

**Scope:** leaf instances with a manifest profile.

**Question:** Should this field have been answered, or is it not applicable (N/A)?

| Gold applicable? | Pred applicable? | Layer 1 outcome |
|------------------|------------------|-----------------|
| no (N/A sentinel) | no | `correct_NA` |
| no | yes | `spurious_applicable` |
| yes | no | `withheld_applicable` |
| yes | yes | `correct_applicable` → eligible for Layer 2 |

**Applicable** means the value is present and not listed in the field’s `na_values`. For many checks, `""` or `"not needed"` in the schema enum is marked as N/A in the manifest.

Instances with `correct_NA` or `withheld_applicable` are excluded from Layer 2 denominators.

### Layer 2 — matching

**Scope:** instances where Layer 1 = `correct_applicable`.

**Question:** Given both sides were applicable, did the values agree?

| `matching_metric` | Layer 2 labels |
|-------------------|----------------|
| `binary_polarity` | `TP`, `FP`, `FN`, `TN` |
| `multiclass` | `match`, `mismatch` |
| `graded_string` | `match`, `mismatch` (from `score >= match_threshold`) |

Layer 2 describes **value agreement on paired rows**. Missing or spurious **rows** are Layer S outcomes, not Layer 2 false positives in the classification sense.

---

## Evaluation manifest

Each check ships an `eval-manifest.json` next to `schema.json`, for example:

`soda_mmqc/data/checklist/fig-checklist/micrograph-scale-bar/eval-manifest.json`

The manifest has three top-level sections (`defaults`, `list_alignment`, `fields`). **Which section you use depends on the leaf type:**

| Leaf type in schema | Example path | Manifest configuration |
|---------------------|--------------|------------------------|
| Scalar primitive | `outputs[].micrograph` | `fields` only — `matching_metric`, `na_values`, … |
| **Array of primitives** | `tags`, `outputs[].symbols` | `fields` — **`primitive_list_compare`** (and optional layer 1/2 keys) |
| **List of objects** (rows) | `outputs[]` with `outputs[].panel_label`, … | Top-level **`list_alignment`** for row pairing **plus** `fields` per row leaf |

`list_alignment` and `primitive_list_compare` solve **different** problems. Do not put primitive-array paths in `list_alignment`, and do not use `primitive_list_compare` on object lists.

### `defaults`

Default profile merged into every entry in `fields` unless overridden (layer 1 / layer 2 keys only — not compare modes):

```json
{
  "matching_metric": "binary_polarity",
  "positive_value": "yes",
  "negative_value": "no",
  "na_values": []
}
```

`string_compare`, `match_threshold`, and `primitive_list_compare` are **not** defaults keys — set them per field.

### `list_alignment` — list-of-objects row pairing only

Use **`list_alignment`** when the schema has a **list of objects** whose rows must be paired before scoring row fields (for example `outputs[]` with one object per panel). The evaluator runs Hungarian matching on rows, then scores leaves such as `outputs[].panel_label` at each gold row index. Layer S (`by_list`) reports `correct_row` / `missing_row` / `spurious_row`.

```json
"list_alignment": {
  "outputs": ["panel_label"]
}
```

- **Keys** — list path **without** `[]` (for example `outputs`, or `figures.panels` when panels are nested under a collection wrapper).
- **Values** — short field names **inside each row object** used only to compute pairing similarity `s(i, j)` — not full leaf paths like `outputs[].panel_label`.
- **Required** for every **predictive** list-of-objects in the schema (model-produced row arrays).
- **Not used** for arrays of primitives (`string[]`, `number[]`, …). Those are single leaves scored via `primitive_list_compare` in `fields` (below).
- **Not used** for structural collection wrappers (for example a `figures[]` envelope around model output) — those lists are joined by position only.

### `fields` — per leaf property

Keys are leaf property patterns with `[]` for list indices (for example `outputs[].panel_label`, `tags`).

#### Scalar leaves

```json
"fields": {
  "outputs[].panel_label": {
    "matching_metric": "graded_string",
    "string_compare": "exact",
    "match_threshold": 1.0
  },
  "outputs[].micrograph": {
    "matching_metric": "binary_polarity"
  },
  "outputs[].scale_bar_on_image": {
    "na_values": [""],
    "matching_metric": "binary_polarity"
  }
}
```

#### Arrays of primitives (extended-primitive leaves)

When the schema type is `array` whose `items` is a primitive (for example `tags: string[]` or `outputs[].source_data_filenames: string[]`), the **whole array is one leaf**. Add an entry under `fields` with **`primitive_list_compare`**. Omit it to use the default **`align`** (set-like, order-free Hungarian matching).

**Set-like bag** — filenames, tags, symbol names (order should not matter):

```json
"outputs[].source_data_filenames": {}
```

Default `align` applies; no other keys required unless you want layer 1 / layer 2 reporting on the aggregate score.

**Index-bound parallel array** — slot `i` answers about item `i` (for example `yes`/`no` per symbol, parallel to another array):

```json
"outputs[].symbols_defined_in_caption": {
  "primitive_list_compare": "positional"
}
```

Use **`positional`** when permutations must score badly. Do **not** rely on default `align` for low-cardinality enums like `yes`/`no` — Hungarian matching would treat `["yes","no"]` vs `["no","yes"]` as a perfect match.

**Holistic string comparison** — join elements, then compare as one string:

```json
"outputs[].from_the_caption": {
  "primitive_list_compare": "join_string",
  "matching_metric": "graded_string",
  "na_values": [""],
  "string_compare": "semantic",
  "match_threshold": 0.8
}
```

`join_string` requires `matching_metric: graded_string` plus `string_compare` and `match_threshold`. Optional: `join_separator` (default `", "`), `sort_before_join` (default `false`).

Primitive arrays emit **one aggregate score** per path. There is no `by_list` / row structural reporting for them — extra or missing elements affect the score only.

| Manifest key | Applies to | Purpose |
|--------------|------------|---------|
| `primitive_list_compare` | Array-of-primitives leaves only | `align` (default), `positional`, or `join_string` — see [Arrays of primitives](#arrays-of-primitives) |
| `join_separator` | `join_string` only | String joiner between elements (default `", "`) |
| `sort_before_join` | `join_string` only | Sort elements before join (default `false`) |
| `na_values` | Any profiled leaf | Literals treated as not applicable (Layer 1) |
| `matching_metric` | Profiled leaves | Layer 2 reporting shape: `binary_polarity`, `multiclass`, or `graded_string` |
| `positive_value` / `negative_value` | `binary_polarity` | Typically `yes` / `no` |
| `string_compare` | `graded_string` scalars or `join_string` arrays | `exact`, `fuzzy`, or `semantic` |
| `match_threshold` | `graded_string` | Minimum score for Layer 2 `match` |

JSON Schema `enum` lists allowed literals but does not define which mean N/A or which is “positive”. Those semantics belong in the manifest.

---

## Evaluation output

`FlatEvaluator.evaluate(exp, pred)` runs on one gold/pred pair (one model call). It returns:

| Section | Contents |
|---------|----------|
| `instances` | One record per leaf instance: `path`, `leaf_property`, `exp_value`, `pred_value`, `score`, optional `layer1` / `layer2` |
| `by_property` | Per leaf property: `mean_score` (Layer 2 mean over applicable instances only), `layer1_counts`, `layer2_counts` |
| `by_list` | Per object list (e.g. `outputs`): `row_counts`, per-row alignment detail |

`mmqc score` stores one such result per benchmark example in the run leaf's `analysis.json` (`<run root>/<arm>/rep-NN/analysis.json`), under its `flat` array. See the README **Benchmarking and scoring** section for the on-disk layout.

After editing `eval-manifest.json`, re-run `mmqc score` on the existing predictions to recompute the analysis; the agent does not need to run again when only scoring rules change.

---

## Implementation modules

| Module | Responsibility |
|--------|----------------|
| `evaluation.py` | `FlatEvaluator` orchestrator |
| `eval_manifest.py` | Load and validate `eval-manifest.json` |
| `leaves.py` | Primitive and primitive-array comparison |
| `object_list_pairing.py` | Hungarian row pairing for predictive lists |
| `structural_reporting.py` | Layer S / `by_list` |
| `applicability_and_matching.py` | Layer 1 and Layer 2 labels |
