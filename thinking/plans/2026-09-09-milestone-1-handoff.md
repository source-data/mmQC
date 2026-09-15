# Milestone 1 Handoff — Separate `run` from `evaluate`

**Status:** complete. Both gates pass on the real examples dataset.
**Branch:** `agentic` (changes are uncommitted in the working tree).
**Plan:** [`2026-09-02-agentic-checklist-skills.md`](2026-09-02-agentic-checklist-skills.md) — Milestone 1.
**Next:** Milestone 2 (pilot the hierarchy on `micrograph-scale-bar`).

Milestone 1's deliverable was: *running a check and scoring a check are separate
operations; existing behavior is unchanged.* Both halves are done — a new
`score` command scores stored predictions through the untouched `FlatEvaluator`
wiring, and check enumeration now follows from the evaluation contracts so a
shared skill sitting beside the checks cannot become a phantom check.

---

## Files changed

| File | Status | What |
|---|---|---|
| `soda_mmqc/cli.py` | **new** (362 lines) | Agentic CLI; `score` subcommand |
| `soda_mmqc/scripts/run.py` | modified | `owns_evaluation_contracts()`, rewritten `list_checks()`, tightened `--check` resolution |
| `tests/test_agentic_cli.py` | **new** (1036 lines, 49 tests) | Enumeration + scoring tests, synthetic and against the real examples dataset |
| `tests/test_run_analyze_results.py` | modified | Skip instead of erroring at import when the examples dataset is absent |

Nothing else was touched. No dependencies were added. `pyproject.toml` is
unchanged — no console-script entry point was added for `cli.py`, since the
plan puts CLI-boundary delegation in Milestone 5; invoke it as
`python -m soda_mmqc.cli` for now.

---

## 1. `soda_mmqc/cli.py` (new)

The module that will own runtime assembly, per-example agent sessions,
prediction writing, DAG validation, and SkillSet resolution. Milestone 1
delivers only the scoring half.

### Public surface

```python
PREDICTION_FILENAME = "prediction.json"   # one example's final leaf JSON
DEFAULT_RUN_LABEL   = "agentic"           # top-level key in analysis.json

resolve_check_dir(checklist, check) -> Path
load_predictions(predictions_path) -> dict[str, dict]
score_check(checklist, check, predictions_path, *, model, run_label,
            sentence_transformer_model, embedder, save) -> dict
main(argv=None) -> int
```

### The command

```bash
python -m soda_mmqc.cli score fig-checklist \
    --check micrograph-scale-bar \
    --predictions PATH \
    [--model MODEL] [--run-label LABEL] \
    [--sentence-transformer-model NAME] [--no-save]
```

`argparse` uses a subparser (`score`), so `run` and `graph` slot in later
without reshaping the CLI.

### Prediction layouts accepted by `--predictions`

**A directory** — the layout the Milestone 4 runner will write. One
subdirectory per example, mirroring the example's relative source path, each
holding a `prediction.json` containing exactly that example's final leaf JSON:

```
predictions/
  10.1038_s44318-026-00715-1/content/1/prediction.json
  10.1038_s44318-026-00715-1/content/1/intermediates/skill_trace.json   # ignored
  10.1038_s44318-026-00715-1/content/2/prediction.json
```

Discovery is `rglob("prediction.json")`, so debug sidecars (intermediate
artifacts, skill traces) can sit alongside and are ignored — **only leaf JSON is
scored**, per the plan's constraint. A `prediction.json` at the root of the
directory is an error, since there is no example path to key it by.

**A JSON file** — an object mapping example relative source path to that
example's leaf JSON. Convenient for hand-assembled runs and tests.

### How `score_check` works

1. `resolve_check_dir` — resolves `CHECKLIST_DIR / checklist / check` and
   refuses a directory that is not a check (see §2).
2. Reads the check's own `schema.json` and `benchmark.json`. `check_name` comes
   from `benchmark["name"]`, `example_class` from `benchmark["example_class"]`.
3. Loads the predictions.
4. **Scores only the examples that have a prediction.** Benchmark examples
   without one are logged and skipped; predictions for examples outside the
   benchmark are logged and ignored. Zero overlap raises. This makes a partial
   run over a handful of examples scoreable, which Milestone 4's human gate
   explicitly needs ("scope this to a handful of examples — never the full
   checklist").
5. Builds each example via `EXAMPLE_FACTORY.create(rel_path, example_class)` and
   reads gold with `example.get_expected_output(check_name)`, so `doc_id` and
   `example_type` are derived exactly as the legacy path derives them.
6. Builds `ModelResult` objects whose metadata is
   `{"doc_id", "source", "example_type"}` — byte-for-byte the same dict the
   legacy `--mock` path in `process_check` builds.
7. Calls `analyze_results(...)` and `save_analysis(...)` **imported verbatim
   from `run.py`**. No evaluator semantics, thresholds, or output shape were
   changed or reimplemented.

### Output shape

```json
{ "<run_label>": { "flat": [ {doc_id, expected_output, model_output, metadata, analysis}, ... ] } }
```

Identical to the legacy shape. The legacy path keys the top level by prompt
name; the agentic path has no prompt, so the key is `--run-label`
(default `agentic`).

> **Known wrinkle for later:** `soda_mmqc/reporting/load.py::normalize_prompt_name`
> expects keys shaped like `prompt.N` and logs a warning for anything else.
> `agentic` will trip that warning. Harmless for Milestone 1 — reporting
> integration is Milestone 5's job — but it is the thing to decide there:
> either teach the normalizer about non-prompt run labels, or pick a run-label
> convention that satisfies it.

### Error handling

`main()` catches `FileNotFoundError` and `ValueError`, logs the message, and
returns exit code 1. Everything else propagates.

---

## 2. `soda_mmqc/scripts/run.py` (modified)

Three edits, all serving the plan's "Two Different Discoveries" section: the
runner-side *check enumeration* fix that has to land before any shared skill is
added to a checklist directory.

### `EVALUATION_CONTRACT_FILES` — [run.py:53](../../soda_mmqc/scripts/run.py#L53)

```python
EVALUATION_CONTRACT_FILES = ("schema.json", "benchmark.json")
```

### `owns_evaluation_contracts()` — [run.py:1149](../../soda_mmqc/scripts/run.py#L1149)

A directory is a check when it owns the evaluation contracts. Not a name
convention, not a marker file, not a `kind` discriminator in frontmatter — one
discriminator, and it is the thing that already has to be true.

### `list_checks()` — [run.py:1171](../../soda_mmqc/scripts/run.py#L1171)

Was: every subdirectory of the checklist directory. Now: only directories that
own the evaluation contracts. Also sorted, so processing order is deterministic
(previously raw `iterdir()` order).

### `--check` resolution in `main()` — [run.py:1487](../../soda_mmqc/scripts/run.py#L1487)

Was `if check_dir.exists()`, which bypassed `list_checks` entirely and would
happily try to run `evaluate fig-checklist --check identify-panels` once that
shared skill exists. Now gated on `owns_evaluation_contracts`, with a distinct
error message for "directory exists but is not a check" versus "no such
directory".

### ⚠️ Design decision to be aware of: which files are "the contracts"

The plan describes a leaf as carrying **three** files — `schema.json`,
`eval-manifest.json`, and `benchmark.json`. **I used only `schema.json` +
`benchmark.json` as the enumeration test**, and the reason is load-bearing:

| Checklist | All checks have `schema.json` + `benchmark.json`? | All have `eval-manifest.json`? |
|---|---|---|
| `fig-checklist` (11 checks) | yes | yes |
| `doc-checklist` (11 checks) | yes | yes |
| `data-checklist` (3 checks) | yes | **no — none of them** |
| `Retired-checklist` (6 checks) | yes | **no — only 1 of 6** |

Requiring `eval-manifest.json` would have silently dropped `data-checklist`
entirely and five of six `Retired-checklist` checks from enumeration — a real
behavior break, against the milestone's own "do not break existing scoring,
reporting, or curation" constraint.

Two files are still a sufficient discriminator for Milestone 2's purpose: a
shared skill like `identify-panels` carries a runtime `schema.json` and **no**
`benchmark.json`, so it is correctly excluded. `eval-manifest.json` remains
required by `analyze_results` at *scoring* time — it is just not part of the
*enumeration* test. This is documented in the function's docstring.

If you disagree with this call, the change is one tuple at
[run.py:53](../../soda_mmqc/scripts/run.py#L53) — but you would need to decide
what happens to `data-checklist` and `Retired-checklist` first.

---

## 3. `tests/test_agentic_cli.py` (new — 49 tests, 9 classes)

### 3a. Synthetic tests (28)

| Class | Covers |
|---|---|
| `TestOwnsEvaluationContracts` | contracts present → check; shared skill with runtime schema only → not a check; bare directory → not; a file → not |
| `TestListChecks` | fig-checklist still enumerates exactly its 11 checks; the three legacy checklists still enumerate *every* subdirectory; a shared-skill sibling is not enumerated |
| `TestLoadPredictions` | directory layout; sidecars ignored; JSON-file mapping; missing path; empty directory; prediction at root; non-object prediction |
| `TestResolveCheckDir` | resolves a check; unknown checklist; unknown check; shared skill is not scoreable |
| `TestScoreCheck` | **parity with `analyze_results`**; flat records carry gold + prediction; partial runs; out-of-benchmark predictions ignored; no overlap raises; `analysis.json` lands where the legacy path puts it |
| `TestCli` | `main()` end to end incl. `--run-label`; bad check → exit 1 |

**These tests do not need the examples dataset.** The `pilot` fixture builds a
self-contained checklist and example tree in `tmp_path` from the *real*
`micrograph-scale-bar` `schema.json` and `eval-manifest.json`, with a synthetic
`benchmark.json` and two synthetic figure examples (caption + a 1×1 PNG +
gold). It monkeypatches `soda_mmqc.cli.CHECKLIST_DIR` and
`soda_mmqc.core.examples.EXAMPLES_DIR`. Semantic string fields use a mock
embedder, so no SentenceTransformer model is ever loaded.

The key test is `test_matches_the_legacy_analyze_results_output`: the same
predictions are scored through `score_check` and, separately, through a
hand-built `ModelResult` list handed straight to `analyze_results`, and the
`flat` payloads must be equal. One example is deliberately given a wrong
prediction so the comparison is not a trivial run of perfect scores.

**Verified failing-first:** with the pre-change `list_checks` restored,
`test_shared_skill_sibling_is_not_enumerated` reports
`['identify-panels', 'micrograph-scale-bar']` and fails. The new enumeration is
genuinely what makes it pass.

### 3b. Real-dataset tests (21) — added after the dataset landed

The 28 tests above were written before `soda_mmqc/data/examples/` was
available, so nothing exercised `score_check` against a real example. Three
classes at the bottom of the file close that gap using
**`D4R_10.1038_s44318-026-00693-4`** — a five-figure EMBO J submission with
real captions, real JPEGs, `source_data/` siblings and real gold for
`panelisation-and-classification` and `panel-label-detection`. All 21 are
guarded by `requires_real_example`, so they skip when the dataset is absent.

| Class | Covers |
|---|---|
| `TestRealExampleWiring` (6) | the five figures exist with caption + image; the real benchmarks list exactly those five and gold is non-empty; `EXAMPLE_FACTORY` derives `doc_id`/`source`/`example_type` from the real tree; `get_expected_output` equals the JSON on disk; `load_predictions` keys by a three-segment real path with a `skill_trace.json` sidecar alongside |
| `TestScoreCheckOnRealExamples` (8) | scoring real gold against itself is perfect across all 27 panels; flat records carry real gold + metadata; **parity with `analyze_results` on real data**; a misclassified panel scores `0.0`/`FN`; a missed panel is a `missing_row` with `withheld_applicable` instances; partial run over two figures; predictions from another document ignored; `main()` writes `analysis.json` for all five figures |
| `TestRealChecksWithoutAnEvalManifest` (7) | the enumeration/scoring asymmetry from §2, pinned on real checks |

The `real_pilot` fixture synthesizes **only the checklist** — the check's real
`schema.json`, a benchmark narrowed to this one document, and the
`eval-manifest.json` the check lacks. `EXAMPLES_DIR` is *not* monkeypatched, so
examples, content and gold are the ones on disk. The manifest has no semantic
fields, so no SentenceTransformer model is loaded and the full file still runs
in **~3 seconds**.

`TestRealChecksWithoutAnEvalManifest` is the test the §2 design decision was
missing. `Retired-checklist/panelisation-and-classification`,
`Retired-checklist/panel-label-detection` and
`data-checklist/panel-data-replication-validation` all benchmark this document,
all pass `owns_evaluation_contracts`, all resolve through `resolve_check_dir` —
and none ship an `eval-manifest.json`. The tests assert that scoring them fails
with `Missing eval manifest`, that the CLI turns that into exit 1, and that
`panel-data-replication-validation` (benchmarked for this document but with no
`expected_output.json` anywhere in it) raises `No expected outputs found`
rather than scoring predictions against empty gold.

**Verified failing-first**, by mutating the code under test and confirming the
failures land on the intended tests:

| Mutation | New tests that fail |
|---|---|
| add `eval-manifest.json` to `EVALUATION_CONTRACT_FILES` | 6 of the 7 `TestRealChecksWithoutAnEvalManifest` tests (plus the 2 pre-existing legacy-enumeration tests) |
| `metadata["source"] = str(example.source_path)` | 6 of `TestScoreCheckOnRealExamples` (plus 4 synthetic) |
| drop the "no expected output → skip" guard in `score_check` | `test_benchmark_examples_without_gold_are_skipped` |

### Suite impact

`pytest tests/ -q` (minus the five stale modules below) with the file removed
versus present: the `FAILED`/`ERROR` line sets are **character-identical**
(58 lines, 0-line diff). The only delta is the added passing tests.

---

## 4. `tests/test_run_analyze_results.py` (modified)

The module read the gold expected output at **import** time, so on any machine
without the untracked examples dataset it raised `FileNotFoundError` during
collection — which aborts the whole `pytest tests/` run, not just that module.
Now it checks for the file and calls `pytest.skip(..., allow_module_level=True)`
with a clear reason. No behavior change when the dataset is present.

---

## Gate results

Both gates were run **twice**: once against a synthetic examples tree, then
again against the real `soda_mmqc/data/examples` dataset once it became
available. The results below are from the **real dataset**.

### Automatic gate — `pytest tests/ -v`

Compared against a `git worktree` at `HEAD` (`60f73b22`), same interpreter, same
dataset:

| | baseline (HEAD) | after |
|---|---|---|
| passed | 313 | **341** |
| failed | 35 | 35 |
| skipped | 16 | 16 |
| errors | 23 | 23 |

The `FAILED`/`ERROR` line sets are **character-identical** (59 lines diffed
clean). The only delta is **+28 passing tests** — exactly the new file.

### Human gate

| Check | Result |
|---|---|
| `evaluate fig-checklist --check micrograph-scale-bar --mock` (38 examples), HEAD vs. after | `analysis.json` **byte-identical** |
| `export-fig-report` on that output, HEAD vs. after | **identical** once random plotly div UUIDs and timestamps are normalized (0-line diff) |
| Extra: feed the same real gold to `python -m soda_mmqc.cli score` | reproduces the legacy `--mock` `flat` records **exactly, all 38** |

Both legacy runs redirected only `EVALUATION_DIR` to a temp path, so the repo's
own `soda_mmqc/data/evaluation` was never written to.

---

## Environment notes (read before you run anything)

- **There is no working environment in the repo.** `.venv/` is empty (a Python
  3.14 venv with zero packages) and system Python is 3.9, below the project's
  `requires-python = ">=3.12"`. I built a throwaway 3.12 venv in the session
  scratchpad with `uv`; it is *not* persisted and you will need your own.
- **`soda_mmqc/data/examples/` is untracked and not in `.gitignore`,** so it
  shows up as a 2868-file untracked directory in `git status`. Consider
  ignoring it.
- The `all-MiniLM-L6-v2` SentenceTransformer model must be in the HF cache (or
  the network reachable) for any test touching `string_compare: semantic`.
  Eleven `tests/test_leaves.py` tests error without it.

### Pre-existing breakage, not caused by this milestone

Five modules fail at **collection**, which aborts a plain `pytest tests/` run
entirely. They import a `JSONEvaluator` that no longer exists in
`soda_mmqc/core/evaluation.py`:

```
tests/test_compare_lists.py  tests/test_compare_objects.py  tests/test_compare_strings.py
tests/test_evaluate.py       tests/test_fuzzy_matching.py
```

To run the suite at all you must exclude them:

```bash
pytest tests/ -q \
  --ignore=tests/test_compare_lists.py --ignore=tests/test_compare_objects.py \
  --ignore=tests/test_compare_strings.py --ignore=tests/test_evaluate.py \
  --ignore=tests/test_fuzzy_matching.py
```

They are stale and should be deleted or ported — **worth doing before Milestone
2**, so that milestone's gate can be a clean `pytest tests/ -v` rather than a
command with five exclusions.

The remaining 35 failures / 23 errors are also pre-existing and identical on
`HEAD`. By module:

| Module | failed | errored |
|---|---|---|
| `test_reporting_context.py` | 3 | 11 |
| `test_reporting_plots.py` | 4 | 6 |
| `test_reporting_phase1.py` | 5 | 5 |
| `test_reporting_compare.py` | 5 | — |
| `test_model_api.py` | 5 | — |
| `test_reporting_display.py` | 4 | — |
| `test_reporting_streamlit.py` | 2 | 1 |
| `test_project_architecture.py` | 2 (`test_config_paths`, `test_data_structure`) | — |
| `test_image_compression.py` | 2 | — |
| `test_real_image_compression.py`, `test_evaluation_collated.py`, `test_collation.py` | 1 each | — |

---

## Where this leaves Milestone 2

Milestone 2 creates `identify-panels` as a flat sibling of the checks, with a
runtime `schema.json` and **no** eval assets. The enumeration work above is what
makes that safe, and it is already tested from the shared-skill side:
`TestOwnsEvaluationContracts::test_shared_skill_with_runtime_schema_only_is_not_a_check`
builds exactly that shape.

Carried forward into Milestone 2:

- `tests/test_agentic_cli.py` gains the skill-loading and consistency tests
  (frontmatter parses; `requires` names an existing skill; graph is acyclic;
  `requires` and prose agree in both directions; the resolved graph survives a
  rename or move). Nothing in Milestone 1 anticipates those — no YAML/frontmatter
  parsing exists in `cli.py` yet.
- The "no version directory contains a copy of `schema.json` /
  `eval-manifest.json` / `benchmark.json`" assertion (Milestone 2 Step 3) is not
  written yet.
- Milestone 2's gate is
  `pytest tests/test_agentic_cli.py tests/test_micrograph_scale_bar_manifest.py -v`;
  both currently pass (28 + 3).
