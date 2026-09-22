---
title: The CLI owns the commands, and scoring is not a script
date: 2026-09-21
status: planned
---

# The CLI owns the commands, and scoring is not a script

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the transition to agentic: delete the prompt-scanning
pipeline, give the run-level evaluator a home of its own in `core/`, and
make `soda_mmqc.cli` the one place a command is declared — so that "where
does this run from" and "where is this implemented" have one answer each.

**Architecture:** `scripts/run.py` is two unrelated programs sharing a file.
The prompt pipeline is dead and goes. The four symbols that are not dead
move: the evaluator wiring to a new `core/scoring.py`, `list_checks` to
`config.py` beside the predicate it wraps. `cli.py` sheds its domain logic
and its re-export surface and becomes a parser. `scripts/` keeps only
launchers, and nothing imports from it.

**Tech Stack:** Python, `pytest`, `argparse`, the existing
`soda_mmqc/agentic/` harness.

**Spec:** this document.

**Companion plan:** `2026-09-21-reporting-measures-one-property.md` depends
on the run layout and `core.scoring` established here. Do not start it first.

---

## Why

### Now

`soda_mmqc/scripts/run.py` is 1612 lines. Four things in it are live:

| symbol | used by |
|---|---|
| `analyze_results`, `save_analysis`, `ModelResult` | `cli.score_check` |
| `list_checks` | `agentic/runner.py`, `initialize` |

Everything else — Langfuse prompt fetching, `run_model`,
`prepare_check_data`, `load_prompt_config_for_check`, `process_check`,
`process_checklist`, `main`, `initialize_main`, and the
`is_agentic_check`/`_dispatch_check` bridge — serves the prompt pipeline,
reachable only through the `evaluate` and `init` console scripts.

Two further symbols are imported *from* `run.py` by three modules and are
not run.py's at all: `EVALUATION_CONTRACT_FILES` and
`owns_evaluation_contracts` are defined at `config.py:94` and `config.py:97`
and merely re-exported. That accident is why `agentic/skills.py`,
`agentic/views.py` and `cli.py` all depend on the legacy module.

Meanwhile `cli.py` (846 lines) holds the scoring half of the workflow
(`load_predictions`, `score_check`) alongside the parser, re-exports about
forty symbols from `agentic/` under `# noqa: F401 (compatibility surface)`,
and **redefines five constants it has already imported** — so
`PREDICTION_FILENAME`, `DEFAULT_RUN_LABEL`, `INTERMEDIATES_DIRNAME`,
`TOOL_AUDIT_FILENAME` and `SKILL_TRACE_FILENAME` each have two definitions
that nothing keeps in agreement.

And three modules under `scripts/` have no importers at all:
`visualize.py` (955 lines, superseded by `reporting/plots.py`),
`check_data.py` (146), `analysis_json_to_html.py` (269, superseded by
`reporting/export_report.py`). Only `test_project_architecture.py` mentions
them, to assert they import.

### Proposed

```
soda_mmqc/
  cli.py            parser + dispatch, no domain logic, no re-exports
  config.py         paths, contracts, list_checks
  core/scoring.py   load_predictions, score_check, analyze_results,
                    save_analysis, ModelResult
  core/evaluation.py            FlatEvaluator (unchanged)
  agentic/          the harness (unchanged)
  scripts/          launchers only: curate.py, report.py,
                    export_fig_checklist_report.py
```

`scripts/run.py`, `scripts/visualize.py`, `scripts/check_data.py` and
`scripts/analysis_json_to_html.py` are deleted.

### Why `core/scoring.py` and not `core/evaluation.py`

`core/evaluation.py` is 803 lines and owns `FlatEvaluator`, which evaluates
*one record* against *one gold*. `scoring` is a run's worth of that: resolve
the check, read `benchmark.json`, load gold, pair predictions to examples,
persist. Different altitude. Keeping them apart is what lets `scoring`
depend on `evaluation` and never the reverse.

### Why not a `scripts/evaluate.py`

An earlier draft put the scoring entry point in `scripts/` beside
`report.py` and `curate.py`. That contradicts itself: if `scripts/` is
"things you invoke", then `cli.py` is a second, parallel thing you invoke,
and a reader has two places to look for a command. One CLI. `scripts/`
keeps `curate.py` and `report.py` because they are genuinely launchers —
they set environment variables and exec `streamlit run` — and the `curate`
and `report` subcommands call them.

### Why the analysis lives in the run leaf

`save_analysis` currently writes
`EVALUATION_DIR/<checklist>/<check>/<model>/analysis.json`. A run writes
`<root>/<arm>/rep-NN/<example>/`, so one analysis path serves every arm and
every replicate: the second one scored overwrites the first, silently and
plausibly.

The fix is to put the analysis where the predictions it describes are:

```
<root>/<arm>/rep-NN/
    analysis.json          <- scored result for this leaf
    <example>/prediction.json
```

A run is then one directory holding both what the agent produced and what
the evaluator made of it. It is also the unit `score_check` already takes
and the unit the notebooks already iterate. `.gitignore` already describes
this intent — *"`cli run` writes predictions here by default and `cli score`
writes analysis beside them"* — so this makes the code match the comment.

Consequently `save_analysis` takes a **root** rather than
`(checklist, check, model)`, and reporting gains one meaning for "point me
at the results" that works for `data/evaluation/` and
`experiments/runs/<exp>/<check>/` alike.

### Why the `predictions/` path segment goes

`default_predictions_dir` returns
`EVALUATION_DIR/<checklist>/<check>/<model>/predictions`, and the harness
appends `<arm>/rep-NN/<example>/`. Once the analysis sits in the leaf, a
segment named `predictions` holds analyses too. Dropping it gives

    EVALUATION_DIR/<checklist>/<check>/<model>/<arm>/rep-NN/

which has the same shape as `experiments/runs/<exp>/<check>/<arm>/rep-NN/`.
**A root is a directory whose children are arms** — one sentence, one
walker, no special case for the production tree.

### Why `analysis.json` loses its outer key

`score_check` returns `{run_label: {"flat": [...]}}` and `save_analysis`
writes that verbatim. The outer key existed to hold one entry per prompt.
With prompts gone it is always the literal `"agentic"`, and each leaf's
analysis now has its own file anyway. It becomes `{"flat": [...]}`.

No migration is needed: `soda_mmqc/data/evaluation/` does not exist in the
tree and no `analysis.json` is committed anywhere. This is free now and
expensive once a production benchmark has run.

### Why `init` survives the pipeline that implemented it

`init` writes a first-draft `expected_output.json` for every benchmark
example, so curation becomes correction rather than filling in most of the
fields by hand. That is worth keeping, and only its *producer* was legacy:
`initialize` at `run.py:1175` is a loop that gets one output per example and
calls `example.save_expected_output(...)`. `run_check_live` already produces
exactly that output. `init` is a change of sink, not new machinery.

It gains a second source. A run that already exists can seed the drafts
without spending anything, which matters because runs are expensive and we
now keep them. With replicates there are N candidates per example and
`init --from-run` takes `rep-00`, not a consensus: a curator correcting one
draft is not helped by an average that hides where the replicates disagreed.

### What stays out

**Langfuse.** It remains the route by which skills are exposed to the
production application and will be redesigned on its own. `lib/api.py`,
`core/curation.py`, `.github/workflows/build-prompts-langfuse.yml` and
`.github/scripts/build_langfuse_checklist.py` are untouched. Note that
`scripts/check_data.py` is deleted, but it is a *consumer* of Langfuse with
no importers, not part of the integration.

**Curation.** Still used. `core/curation.py` and `scripts/curate.py` change
only insofar as `curate` becomes a subcommand.

**Everything in the companion plan.** No task here changes
`soda_mmqc/reporting/`, any plot, or any notebook, beyond what a moved
import requires.

---

## Test fixtures used throughout

Defined in `tests/conftest.py` in Task 5, the first task that needs them,
and used by Tasks 5 and 8.

| helper | what it makes |
|---|---|
| `CHECKLIST`, `CHECK` | `"fig-checklist-exp01"`, `"replication-reporting"` — a check with committed examples and a real `eval-manifest.json` |
| `EXAMPLE`, `EXAMPLE_A`, `EXAMPLE_B` | relative source paths taken from that check's `benchmark.json`, so the gold exists |
| `stub_embedder` | fixture returning the deterministic embedder already used in `tests/test_agentic_cli.py` around line 495; move it to `conftest.py` rather than duplicating it |
| `_write_one_prediction(leaf, example, payload)` | creates `leaf / example` with `parents=True` and writes `payload` as `prediction.json` |
| `_capture_saved_expected_outputs(monkeypatch)` | patches `Example.save_expected_output` and returns a dict keyed by `(relative_source_path, check_name)`. **Patch, never let it write** — real gold files live under `soda_mmqc/data/` and a test writing them corrupts the curated corpus |

---

## Global Constraints

- **`cli.py` declares commands and dispatches. Nothing else.** It defines no
  domain function and re-exports no symbol for a test's convenience. A test
  that needs `_write_prediction` imports it from `agentic.runner`.
- **One definition per constant.** After Task 4 no name is defined in two
  modules. `agentic/session.py` and `agentic/runner.py` own the run-artifact
  filenames.
- **Nothing imports from `soda_mmqc.scripts`.** It is a leaf package of
  launchers. A `grep -rn "from soda_mmqc.scripts" soda_mmqc/ tests/` that
  returns anything other than `cli.py`'s two launcher calls is a failure.
- **One tree per run.** `<root>/<arm>/rep-NN/` holds `analysis.json` and the
  `<example>/` directories it describes. No parallel analysis tree.
- **Never average across leaf properties.** No task here computes such a
  mean; the companion plan forbids it too. `panel_label` and `micrograph`
  measure different things.
- **Langfuse is untouched.** See "What stays out".
- **Run after every task:** `pytest -q`
  (baseline: `2 failed, 720 passed, 7 skipped, 10 deselected`. The two
  failures are `test_config_paths` and `test_data_structure`, both asserting
  `EVALUATION_DIR.exists()`; Task 10 fixes them. Every other task must keep
  passed >= 720 and add no new failure.)

---

## File Structure

| File | Responsibility after this plan |
|---|---|
| `soda_mmqc/cli.py` | Subcommands `run`, `score`, `assemble`, `graph`, `init`, `curate`, `report`. Parser and dispatch only; ~300 lines. |
| `soda_mmqc/core/scoring.py` | **New.** `load_predictions`, `score_check`, `analyze_results`, `save_analysis`, `ModelResult`. The run-level evaluator. |
| `soda_mmqc/core/gold_drafts.py` | **New.** `init_expected_outputs` — run or promote predictions into `expected_output.json`. |
| `soda_mmqc/config.py` | Gains `list_checks`, beside `owns_evaluation_contracts`. |
| `soda_mmqc/agentic/runner.py` | `default_predictions_dir` drops the `predictions/` segment. Otherwise unchanged. |
| `soda_mmqc/scripts/run.py` | **Deleted.** |
| `soda_mmqc/scripts/visualize.py` | **Deleted.** Superseded by `reporting/plots.py`. |
| `soda_mmqc/scripts/check_data.py` | **Deleted.** No importers. |
| `soda_mmqc/scripts/analysis_json_to_html.py` | **Deleted.** Superseded by `reporting/export_report.py`. |
| `soda_mmqc/scripts/curate.py`, `report.py` | Unchanged launchers, now called by subcommands. |
| `pyproject.toml` | `[project.scripts]` collapses to `mmqc` plus kept aliases. |
| `tests/test_scoring.py` | **New.** Moved from `test_run_analyze_results.py`, plus root-layout tests. |
| `tests/test_gold_drafts.py` | **New.** `init` from a live run and from an existing run root. |
| `tests/test_agentic_cli.py` | Imports repointed from `cli` to the owning modules. |
| `tests/test_project_architecture.py` | Asserts the new layout; the two `EVALUATION_DIR` tests made honest. |
| `tests/test_model_api.py` | `ModelInput` import removed or the file retired — see Task 7. |

---

## Task 1: Stop importing config through the legacy module

**Files:**
- Modify: `soda_mmqc/agentic/skills.py:25-29`
- Modify: `soda_mmqc/agentic/views.py:18-21`
- Modify: `soda_mmqc/cli.py:161-168`
- Modify: `soda_mmqc/config.py` — add `list_checks`
- Modify: `soda_mmqc/agentic/runner.py:62`
- Test: `tests/test_project_architecture.py`

**Interfaces:**
- Consumes: `config.owns_evaluation_contracts(candidate_dir: Path) -> bool`
  and `config.EVALUATION_CONTRACT_FILES: tuple[str, ...]`, both already
  present.
- Produces: `config.list_checks(checklist_dir: Path) -> Dict[str, Path]`.

Pure subtraction: three modules stop depending on `scripts.run` for symbols
it does not own, and the one symbol it does own that they need moves to sit
beside its own predicate. No behaviour changes.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_project_architecture.py`:

```python
class TestNoLegacyDependency(unittest.TestCase):
    """The agentic package must not reach through scripts.run for config.

    `EVALUATION_CONTRACT_FILES` and `owns_evaluation_contracts` are defined
    in config.py; scripts.run only re-exported them. Importing them from
    there made three live modules depend on a module we are deleting.
    """

    def test_list_checks_lives_in_config(self):
        from soda_mmqc.config import list_checks, CHECKLIST_DIR
        checks = list_checks(CHECKLIST_DIR / "fig-checklist")
        self.assertIn("micrograph-scale-bar", checks)
        self.assertTrue(checks["micrograph-scale-bar"].is_dir())

    def test_a_shared_skill_is_not_a_check(self):
        """owns_evaluation_contracts is the discriminator; list_checks must
        use it, or a shared skill beside the checks becomes a phantom."""
        from soda_mmqc.config import list_checks, CHECKLIST_DIR
        root = CHECKLIST_DIR / "fig-checklist"
        for name in list_checks(root):
            self.assertTrue(
                (root / name / "schema.json").is_file(),
                f"{name} was listed as a check but owns no schema.json",
            )

    def test_agentic_does_not_import_scripts_run(self):
        import pathlib
        pkg = pathlib.Path(__file__).resolve().parents[1] / "soda_mmqc"
        offenders = [
            path.name
            for path in (pkg / "agentic").glob("*.py")
            if "scripts.run" in path.read_text(encoding="utf-8")
        ]
        self.assertEqual(offenders, [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_project_architecture.py::TestNoLegacyDependency -v`
Expected: FAIL — `ImportError: cannot import name 'list_checks' from 'soda_mmqc.config'`, and the third test lists `skills.py`, `views.py`, `runner.py`.

- [ ] **Step 3: Add `list_checks` to config.py**

Append directly after `owns_evaluation_contracts` (around `config.py:120`):

```python
def list_checks(checklist_dir: Path) -> Dict[str, Path]:
    """Every check in a checklist, keyed by directory name.

    Only directories owning the evaluation contracts are returned, so a
    shared skill sitting beside the checks cannot become a phantom check.
    """
    return {
        check_dir.name: check_dir
        for check_dir in sorted(checklist_dir.iterdir())
        if owns_evaluation_contracts(check_dir)
    }
```

Add `from typing import Dict` to the imports if it is not already there.

- [ ] **Step 4: Repoint the four importers**

In `soda_mmqc/agentic/skills.py`, replace the `from soda_mmqc.scripts.run import (...)` block with:

```python
from soda_mmqc.config import (
    EVALUATION_CONTRACT_FILES,
    list_checks,
    owns_evaluation_contracts,
)
```

In `soda_mmqc/agentic/views.py`:

```python
from soda_mmqc.config import (
    EVALUATION_CONTRACT_FILES,
    owns_evaluation_contracts,
)
```

In `soda_mmqc/agentic/runner.py:62`, replace `from soda_mmqc.scripts.run import list_checks` with `from soda_mmqc.config import list_checks`.

In `soda_mmqc/cli.py:161-168`, narrow the import to only what `run.py` still owns:

```python
from soda_mmqc.scripts.run import (
    ModelResult,
    analyze_results,
    save_analysis,
)
from soda_mmqc.config import (
    EVALUATION_CONTRACT_FILES,
    list_checks,
    owns_evaluation_contracts,
)
```

Leave `list_checks` defined in `scripts/run.py` for now — it is deleted with
the file in Task 7, and removing it here would break `initialize`, which is
still alive until then.

- [ ] **Step 5: Run the tests**

Run: `pytest tests/test_project_architecture.py tests/test_agentic_cli.py -q`
Expected: the three new tests PASS; no new failures.

- [ ] **Step 6: Commit**

```bash
git add soda_mmqc/config.py soda_mmqc/agentic/skills.py soda_mmqc/agentic/views.py soda_mmqc/agentic/runner.py soda_mmqc/cli.py tests/test_project_architecture.py
git commit -m "list_checks belongs beside the predicate it wraps"
```

---

## Task 2: Delete the three scripts nothing imports

**Files:**
- Delete: `soda_mmqc/scripts/visualize.py` (955 lines)
- Delete: `soda_mmqc/scripts/check_data.py` (146 lines)
- Delete: `soda_mmqc/scripts/analysis_json_to_html.py` (269 lines)
- Modify: `tests/test_project_architecture.py:71-80` — `test_scripts_imports`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing. This task only removes.

`visualize.py` is superseded by `reporting/plots.py`;
`analysis_json_to_html.py` by `reporting/export_report.py`; `check_data.py`
fetched prompts and has no caller. The only reference to any of them is
`test_scripts_imports`, which asserts they import — a test that keeps dead
code alive.

- [ ] **Step 1: Confirm there are no importers**

Run:

```bash
grep -rn "visualize\|check_data\|analysis_json_to_html" \
  --include="*.py" --include="*.ipynb" --include="*.toml" --include="*.yml" \
  soda_mmqc/ tests/ notebooks/ experiments/ pyproject.toml .github/
```

Expected: matches only inside the three files themselves and in
`tests/test_project_architecture.py:74`. **If anything else appears, stop
and report it** — this task's premise is that nothing imports them.

- [ ] **Step 2: Rewrite the test first**

Replace `test_scripts_imports` in `tests/test_project_architecture.py`:

```python
    def test_scripts_are_launchers_only(self):
        """scripts/ launches things; it holds no library code.

        The rule that makes this checkable: nothing imports from
        soda_mmqc.scripts except cli.py, which calls the two Streamlit
        launchers. Library code that grew here (visualize.py) was dead and
        duplicated soda_mmqc/reporting/.
        """
        from soda_mmqc.scripts import curate, report
        self.assertTrue(callable(curate.main))
        self.assertTrue(callable(report.main))

        scripts_dir = PACKAGE_ROOT / "scripts"
        for retired in ("visualize.py", "check_data.py",
                        "analysis_json_to_html.py"):
            self.assertFalse(
                (scripts_dir / retired).exists(),
                f"{retired} was deleted as dead code; do not restore it "
                "without a caller",
            )
```

- [ ] **Step 3: Run it to verify it fails**

Run: `pytest tests/test_project_architecture.py -k scripts_are_launchers -v`
Expected: FAIL — `AssertionError: visualize.py was deleted as dead code...`

- [ ] **Step 4: Delete the files**

```bash
git rm soda_mmqc/scripts/visualize.py soda_mmqc/scripts/check_data.py soda_mmqc/scripts/analysis_json_to_html.py
```

- [ ] **Step 5: Run the suite**

Run: `pytest -q`
Expected: PASS for the new test; still exactly the two pre-existing `EVALUATION_DIR` failures.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "Delete three scripts nothing imports

visualize.py is superseded by reporting/plots.py and
analysis_json_to_html.py by reporting/export_report.py; check_data.py
fetched prompts for a pipeline that is going. The only reference to any of
them was a test asserting they import."
```

---

## Task 3: Give the run-level evaluator a home

**Files:**
- Create: `soda_mmqc/core/scoring.py`
- Modify: `soda_mmqc/scripts/run.py` — remove `ModelResult`,
  `analyze_results` (311-373), `save_analysis` (374-410), import them back
  for the legacy pipeline's own use
- Modify: `soda_mmqc/cli.py` — move `load_predictions` (238-307) and
  `score_check` (309-450) out; import from `core.scoring`
- Create: `tests/test_scoring.py`
- Delete: `tests/test_run_analyze_results.py` (moved into the above)

**Interfaces:**
- Consumes: `config.list_checks`, `core.eval_manifest.load_eval_manifest`,
  `core.evaluation.FlatEvaluator`, `core.examples.EXAMPLE_FACTORY`,
  `agentic.skills.resolve_check_dir`.
- Produces:
  - `ModelResult(doc_id: str | None, model_output: dict, metadata: dict)`
  - `analyze_results(results, schema, expected_outputs, *, check_dir, match_threshold=1.0, sentence_transformer_model=..., embedder=None) -> dict[str, list[dict]]`
  - `save_analysis(analyzed_results, checklist_name, check_name, model) -> None` *(signature changes in Task 5, not here)*
  - `load_predictions(predictions_path: Path) -> dict[str, dict]`
  - `score_check(checklist, check, predictions_path, *, model, run_label, sentence_transformer_model, embedder, save) -> dict`

A pure move. **No behaviour changes in this task** — signatures, defaults
and return shapes are byte-identical, so that Task 5's change to
`save_analysis` is reviewable on its own.

Beware the circular import: `core/scoring.py` must not import `cli`, and
`agentic/runner.py` must not import `core.scoring`. `score_check` needs
`resolve_check_dir` from `agentic.skills`, which is fine —
`core.scoring -> agentic.skills` has no cycle. Confirm with the test in
Step 5.

- [ ] **Step 1: Write the failing test**

Create `tests/test_scoring.py`. Start by moving both tests from
`tests/test_run_analyze_results.py` verbatim, changing only the import
(`from soda_mmqc.core.scoring import ModelResult, analyze_results`), then
add:

```python
def test_scoring_does_not_import_the_cli():
    """core/ is below cli: the CLI calls scoring, never the reverse.

    A cycle here would be invisible until someone imports core.scoring in a
    notebook and pulls argparse and the whole agentic surface with it.
    """
    import pathlib
    source = (
        pathlib.Path(__file__).resolve().parents[1]
        / "soda_mmqc" / "core" / "scoring.py"
    ).read_text(encoding="utf-8")
    assert "from soda_mmqc.cli" not in source
    assert "import soda_mmqc.cli" not in source


def test_scoring_does_not_import_the_legacy_runner():
    import pathlib
    source = (
        pathlib.Path(__file__).resolve().parents[1]
        / "soda_mmqc" / "core" / "scoring.py"
    ).read_text(encoding="utf-8")
    assert "scripts.run" not in source
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_scoring.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'soda_mmqc.core.scoring'`

- [ ] **Step 3: Create `core/scoring.py`**

Move, without editing their bodies:

- from `scripts/run.py`: the `ModelResult` dataclass (102-113),
  `_model_schema` (304-309), `analyze_results` (311-372),
  `save_analysis` (374-410), and the module-level `_default_semantic_embedder`
  helper `analyze_results` calls.
- from `cli.py`: `load_predictions` (238-263),
  `_load_predictions_from_dir` (265-282), `_load_predictions_from_file`
  (284-297), `_read_prediction` (299-307), `score_check` (309-450), and the
  `_read_json` helper they share.

Import `PREDICTION_FILENAME` and `DEFAULT_RUN_LABEL` from
`soda_mmqc.agentic.runner` — do not redefine them. Give the module this
docstring:

```python
"""Score a run's predictions against the gold outputs of its benchmark.

This is a *run's* worth of evaluation: resolve the check, read its
``benchmark.json``, pair each stored prediction with the expected output of
the same example, and hand the pairs to ``FlatEvaluator``. Evaluating one
record against one gold is ``core.evaluation``'s job, and this module never
reaches inside it.

The unit of scoring is one run leaf -- ``<root>/<arm>/rep-NN/`` -- because a
replicate is a resample and an arm is a different configuration. Pooling
them is reporting's job, never this module's.
"""
```

- [ ] **Step 4: Repoint the importers**

In `cli.py`, delete the moved functions and import instead:

```python
from soda_mmqc.core.scoring import (
    ModelResult,
    analyze_results,
    load_predictions,
    save_analysis,
    score_check,
)
```

In `scripts/run.py`, the legacy pipeline still calls `analyze_results`,
`save_analysis` and `ModelResult`. Add at the top:

```python
from soda_mmqc.core.scoring import (
    ModelResult, analyze_results, save_analysis,
)
```

and delete their definitions. `ModelInput` and `CheckData` stay in `run.py`
— they belong to the pipeline and die with it in Task 7.

- [ ] **Step 5: Run the suite**

Run: `pytest -q`
Expected: the new tests PASS; no new failures. If an `ImportError` about a
circular import appears, it means `agentic.skills` imports something that
imports `core.scoring` — break it by importing `resolve_check_dir` inside
`score_check`'s body rather than at module level, and note why in a comment.

- [ ] **Step 6: Commit**

```bash
git rm tests/test_run_analyze_results.py
git add soda_mmqc/core/scoring.py soda_mmqc/cli.py soda_mmqc/scripts/run.py tests/test_scoring.py
git commit -m "Scoring a run is core work, not a script and not the CLI

Pure move: analyze_results, save_analysis and ModelResult out of
scripts/run.py, load_predictions and score_check out of cli.py, into
core/scoring.py. No signature or behaviour change -- save_analysis's
new layout is the next commit, reviewable on its own."
```

---

## Task 4: `cli.py` stops re-exporting and stops shadowing

**Files:**
- Modify: `soda_mmqc/cli.py` — delete the `# noqa: F401 (compatibility
  surface)` import blocks (120-160), the duplicate constant definitions
  (230, 234, 456-470) and `__all__`
- Modify: `tests/test_agentic_cli.py` — repoint imports to the owning modules

**Interfaces:**
- Consumes: the real definitions in `agentic/session.py` (`PREDICTION_FILENAME`,
  `INTERMEDIATES_DIRNAME`, `TOOL_AUDIT_FILENAME`, `SKILL_TRACE_FILENAME`,
  `SKILL_SET_FILENAME`) and `agentic/runner.py` (`DEFAULT_RUN_LABEL`).
- Produces: `cli.main`, `cli._build_parser`. Nothing else is public.

`cli.py` imports five constants from `agentic/` and then redefines all five,
shadowing what it imported. Two definitions of `PREDICTION_FILENAME =
"prediction.json"` exist and nothing keeps them equal. The re-export surface
exists only so `tests/test_agentic_cli.py` can write `cli.anything`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_agentic_cli.py`:

```python
class TestTheCliIsAParser:
    """cli.py declares commands. It is not a re-export surface.

    It used to import five constants from agentic/ and then redefine all
    five, so each had two definitions and nothing kept them in agreement.
    Tests reached through `cli.X` for symbols owned elsewhere, which is what
    made the surface load-bearing.
    """

    def test_no_constant_is_defined_twice(self):
        from soda_mmqc import cli
        from soda_mmqc.agentic import runner, session
        assert "PREDICTION_FILENAME" not in vars(cli), (
            "PREDICTION_FILENAME is owned by agentic.session; cli must not "
            "define or re-export it"
        )
        assert session.PREDICTION_FILENAME == "prediction.json"
        assert runner.DEFAULT_RUN_LABEL == "agentic"

    def test_cli_defines_no_domain_logic(self):
        """Every def in cli.py is parser or dispatch."""
        import ast, pathlib
        source = (
            pathlib.Path(__file__).resolve().parents[1]
            / "soda_mmqc" / "cli.py"
        ).read_text(encoding="utf-8")
        names = {
            node.name
            for node in ast.parse(source).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert names <= {"main", "_build_parser"}, (
            "cli.py grew domain logic: "
            f"{sorted(names - {'main', '_build_parser'})}"
        )
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_agentic_cli.py::TestTheCliIsAParser -v`
Expected: FAIL on both — `PREDICTION_FILENAME` is in `vars(cli)`, and `cli.py` still defines whatever Task 3 left behind.

- [ ] **Step 3: Repoint the test file's imports**

`tests/test_agentic_cli.py` uses `cli.<symbol>` throughout. Repoint by
source module rather than deleting:

```bash
grep -o "cli\.[a-zA-Z_][a-zA-Z_0-9]*" tests/test_agentic_cli.py | sort -u
```

For each symbol, add an explicit import at the top of the test file from its
owner (`soda_mmqc.agentic.runner`, `.session`, `.runtime`, `.skills`,
`.pinning`, or `soda_mmqc.core.scoring`) and replace `cli.X` with `X`. Keep
`cli.main` as `cli.main` — that one genuinely belongs to `cli`.

The `mock.patch` targets also move: `"soda_mmqc.cli.run_check_live"` becomes
`"soda_mmqc.agentic.runner.run_check_live"`. Patch where the function is
*defined*, not where `cli` happened to re-export it.

- [ ] **Step 4: Strip cli.py**

Delete the two `# noqa: F401 (compatibility surface)` import blocks, the
five duplicate constant definitions, and `__all__`. Keep only the imports
`_build_parser` and `main` actually reference.

- [ ] **Step 5: Run the suite**

Run: `pytest -q`
Expected: the two new tests PASS; no new failures. `pytest tests/test_agentic_cli.py -q` should report the same count as before this task.

- [ ] **Step 6: Commit**

```bash
git add soda_mmqc/cli.py tests/test_agentic_cli.py
git commit -m "cli.py is a parser, not a re-export surface

It imported five constants from agentic/ and redefined all five. The
compatibility surface existed so tests could write cli.X for symbols owned
elsewhere; they now import from the owner, and mock.patch targets point at
the definition rather than the re-export."
```

---

## Task 5: The analysis lands in the run leaf

**Files:**
- Modify: `soda_mmqc/core/scoring.py` — `save_analysis`, `score_check`
- Modify: `soda_mmqc/cli.py` — the `score` subparser: `--run-label` and
  `--model` go
- Modify: `tests/test_scoring.py`
- Modify: `tests/test_agentic_cli.py` — the `EVALUATION_DIR` monkeypatches
  at 458, 492, 935
- Modify: `tests/conftest.py` — host the shared embedder fixture

**Interfaces:**
- Consumes: `load_predictions` from Task 3.
- Produces:
  - `ANALYSIS_FILENAME = "analysis.json"`
  - `save_analysis(analyzed_results: dict[str, list[dict]], root: Path) -> Path`
    — writes `root / ANALYSIS_FILENAME`, returns the path.
  - `score_check(checklist, check, predictions_path, *, sentence_transformer_model=..., embedder=None, save=True) -> dict[str, list[dict]]`
    — returns `{"flat": [...]}`; `model` and `run_label` parameters are gone.

Two changes, together because one forces the other: the analysis is written
beside the predictions it describes, and the `{run_label: ...}` wrapper goes.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_scoring.py`:

```python
def test_the_analysis_lands_beside_the_predictions(tmp_path, stub_embedder):
    """A run leaf holds its own score.

    save_analysis used to write EVALUATION_DIR/<checklist>/<check>/<model>/
    analysis.json -- one path for every arm and every replicate, so the
    second leaf scored overwrote the first, silently.
    """
    leaf = tmp_path / "pinned" / "rep-00"
    _write_one_prediction(leaf, EXAMPLE, {"outputs": []})

    result = score_check(
        CHECKLIST, CHECK, leaf, embedder=stub_embedder, save=True,
    )

    assert (leaf / "analysis.json").is_file()
    assert set(result) == {"flat"}, (
        "the run_label wrapper existed to hold one entry per prompt; with "
        "prompts gone it was always the literal 'agentic'"
    )
    on_disk = json.loads((leaf / "analysis.json").read_text())
    assert set(on_disk) == {"flat"}
    assert on_disk == result


def test_two_replicates_do_not_overwrite_each_other(tmp_path, stub_embedder):
    """The defect that motivated the layout, asserted directly."""
    written = []
    for rep in ("rep-00", "rep-01"):
        leaf = tmp_path / "pinned" / rep
        _write_one_prediction(leaf, EXAMPLE, {"outputs": []})
        score_check(CHECKLIST, CHECK, leaf, embedder=stub_embedder, save=True)
        written.append(leaf / "analysis.json")

    assert all(path.is_file() for path in written)
    assert written[0] != written[1]


def test_scoring_without_saving_writes_nothing(tmp_path, stub_embedder):
    leaf = tmp_path / "pinned" / "rep-00"
    _write_one_prediction(leaf, EXAMPLE, {"outputs": []})
    score_check(CHECKLIST, CHECK, leaf, embedder=stub_embedder, save=False)
    assert not (leaf / "analysis.json").exists()
```

Define `_write_one_prediction(leaf, example, payload)` as a helper in the
test module: it creates `leaf / example`, `mkdir(parents=True)`, and writes
`prediction.json`. `stub_embedder` is a fixture returning the deterministic
embedder already used in `tests/test_agentic_cli.py` around line 495 — move
it to `tests/conftest.py` so both files share it.

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_scoring.py -k "beside or overwrite" -v`
Expected: FAIL — `analysis.json` is written under `EVALUATION_DIR`, not in the leaf; and `set(result)` is `{"agentic"}`.

- [ ] **Step 3: Rewrite `save_analysis`**

```python
def save_analysis(
    analyzed_results: Dict[str, List[Dict[str, Any]]],
    root: Path,
) -> Path:
    """Write one run leaf's analysis beside the predictions it describes.

    ``root`` is a run leaf -- ``<root>/<arm>/rep-NN/`` -- so each arm and
    each replicate keeps its own score. The previous signature took
    ``(checklist, check, model)`` and resolved one path per model, which
    every arm and replicate then shared and overwrote in turn.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    analysis_file = root / ANALYSIS_FILENAME
    analysis_file.write_text(
        json.dumps(analyzed_results, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Saved analysis to %s", analysis_file)
    return analysis_file
```

Add `ANALYSIS_FILENAME = "analysis.json"` beside it. Note the error handling
changes deliberately: the old body caught, logged and re-raised, which added
nothing. Let it raise.

- [ ] **Step 4: Update `score_check`**

Drop the `model` and `run_label` parameters. Return `analyzed_results`
directly instead of `{run_label: analyzed_results}`, and call
`save_analysis(analyzed_results, Path(predictions_path))`.

Keep the run-root guidance error (currently `cli.py:385-399`, now in
`core/scoring.py`) — it is still correct and now points at a directory that
will also hold an `analysis.json`.

- [ ] **Step 5: Update the CLI**

Remove `--run-label` and `--model` from the `score` subparser and their use
in `main`. `--model` existed only to choose the output directory. Say so in
the subparser help:

```python
score.add_argument(
    "--predictions",
    type=Path,
    required=True,
    help=(
        "One run leaf -- <root>/<arm>/rep-NN/ -- or a JSON file mapping "
        "example path to leaf output. The analysis is written beside it."
    ),
)
```

- [ ] **Step 6: Run the suite**

Run: `pytest -q`
Expected: new tests PASS. Several `test_agentic_cli.py` tests that monkeypatch `EVALUATION_DIR` (458, 492, 935) will fail — they assert the old path. Update each to assert the leaf path; do not delete them.

- [ ] **Step 7: Commit**

```bash
git add soda_mmqc/core/scoring.py soda_mmqc/cli.py tests/test_scoring.py tests/test_agentic_cli.py tests/conftest.py
git commit -m "A run leaf holds its own analysis

save_analysis wrote one path per model, which every arm and every replicate
shared -- the second scored overwrote the first, silently and plausibly. It
now takes the leaf it scored. The {run_label: ...} wrapper goes with it: it
held one entry per prompt, and with prompts gone it was always 'agentic'.
Nothing to migrate; no analysis.json is committed anywhere."
```

---

## Task 6: A root is a directory whose children are arms

**Files:**
- Modify: `soda_mmqc/agentic/runner.py:78-81` — `default_predictions_dir`
- Modify: `.gitignore` — the stale `soda_mmqc/data/predictions/` rule
- Modify: `tests/test_agentic_cli.py` — tests asserting the default path

**Interfaces:**
- Consumes: `config.EVALUATION_DIR`.
- Produces: `default_predictions_dir(checklist: str, check: str, model: str) -> Path`
  returning `EVALUATION_DIR / checklist / check / model` — one segment shorter.

With the analysis in the leaf, a directory named `predictions` holds
analyses too. Dropping it also makes the production root the same shape as
an experiment root.

- [ ] **Step 1: Write the failing test**

```python
def test_a_run_root_has_the_same_shape_everywhere():
    """Production and experiment roots differ only in prefix.

    A root is a directory whose children are arms. One walker serves
    data/evaluation/<checklist>/<check>/<model>/ and
    experiments/runs/<exp>/<check>/ alike -- which is what lets reporting
    take a single `root` argument.
    """
    from soda_mmqc.agentic.runner import default_predictions_dir
    from soda_mmqc.config import EVALUATION_DIR

    root = default_predictions_dir(
        "fig-checklist", "micrograph-scale-bar", "gpt-5"
    )
    assert root == (
        EVALUATION_DIR / "fig-checklist" / "micrograph-scale-bar" / "gpt-5"
    )
    assert root.name != "predictions", (
        "the segment named 'predictions' now holds analyses too"
    )
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_agentic_cli.py -k same_shape -v`
Expected: FAIL — the path ends in `/predictions`.

- [ ] **Step 3: Change the function**

```python
def default_predictions_dir(checklist: str, check: str, model: str) -> Path:
    """The root a run writes under, when no --output is given.

    A root is a directory whose children are arms: the harness appends
    ``<arm>/rep-NN/<example>/`` beneath this. There is no ``predictions``
    segment because the leaf holds its ``analysis.json`` too.
    """
    return EVALUATION_DIR / checklist / check / model
```

- [ ] **Step 4: Fix the stale .gitignore rule**

`.gitignore` ignores `soda_mmqc/data/predictions/`, a path the code has
never written — `default_predictions_dir` has always resolved under
`data/evaluation/`. Delete that line and correct the comment above it:

```
# Run output, regenerable and per-machine: `mmqc run` writes predictions
# under data/evaluation/<checklist>/<check>/<model>/<arm>/rep-NN/ and
# `mmqc score` writes analysis.json in the same leaf. Committed runs that a
# paper figure depends on live under `experiments/runs/`, which stays
# tracked on purpose -- see experiments/runs/README.md.
soda_mmqc/data/evaluation/
```

(Task 10 changes this last line again, to keep the directory.)

- [ ] **Step 5: Run the suite**

Run: `pytest -q`
Expected: PASS. Update any `test_agentic_cli.py` test asserting the old default path.

- [ ] **Step 6: Commit**

```bash
git add soda_mmqc/agentic/runner.py .gitignore tests/test_agentic_cli.py
git commit -m "Drop the predictions/ segment: a root's children are arms

The leaf now holds its analysis, so a segment named 'predictions' is wrong,
and without it the production root has the same shape as an experiment
root. Also drops a .gitignore rule for data/predictions/, a path the code
has never written."
```

---

## Task 7: Delete the prompt pipeline

**Files:**
- Delete: `soda_mmqc/scripts/run.py`
- Modify: `pyproject.toml` — `evaluate` and `init` entries (Task 9 rebuilds them)
- Modify: `tests/test_project_architecture.py:125-140` — `test_cli_entry_points`
- Modify: `tests/test_model_api.py:16` — the `ModelInput` import
- Modify: `tests/test_agentic_cli.py:3293-3506` — the `is_agentic_check` tests

**Interfaces:**
- Consumes: nothing. Everything still needed left in Tasks 1 and 3.
- Produces: nothing.

What goes: `CheckData`, `ModelInput`, `load_model_config`,
`_log_model_config_summary`, `run_model`, `_load_local_config`,
`_load_local_prompts`, `load_prompt_config_for_check`, `prepare_check_data`,
`process_check`, `process_checklist`, `initialize`, `list_checks` (the copy
left behind in Task 1), `is_agentic_check`, `_agentic_main`, `_agentic_argv`,
`_dispatch_check`, `main`, `initialize_main`, and the module-level Langfuse
client.

`is_agentic_check` goes with it: it routed a legacy invocation to the
agentic runner during the conversion. With no legacy invocation there is
nothing to route, and every check is agentic.

`init` is unavailable between this task and Task 9. That is deliberate — the
deletion and the rebuild are separately reviewable — but **do not ship the
branch with Task 7 done and Task 9 not.**

- [ ] **Step 1: Confirm the four live symbols have moved**

```bash
grep -rn "from soda_mmqc.scripts.run import\|from soda_mmqc.scripts import run\|scripts\.run" \
  soda_mmqc/ tests/ notebooks/ experiments/ .github/
```

Expected: only `tests/test_model_api.py` (`ModelInput`),
`tests/test_project_architecture.py`, and the `is_agentic_check` tests in
`tests/test_agentic_cli.py`. **Anything under `soda_mmqc/` means Task 1 or
Task 3 is incomplete — stop and finish it.**

- [ ] **Step 2: Write the failing test**

Replace `test_cli_entry_points` in `tests/test_project_architecture.py`:

```python
    def test_one_cli_declares_every_command(self):
        """Commands are declared in cli.py and nowhere else.

        `evaluate` and `init` used to be separate console scripts pointing
        into scripts/run.py, so a reader looking for a command had two
        places to look and the prompt pipeline stayed alive to host them.
        """
        from soda_mmqc.cli import _build_parser
        parser = _build_parser()
        actions = [
            a for a in parser._actions
            if isinstance(a, argparse._SubParsersAction)
        ]
        self.assertEqual(len(actions), 1)
        self.assertEqual(
            set(actions[0].choices),
            {"run", "score", "assemble", "graph", "init", "curate", "report"},
        )

    def test_the_prompt_pipeline_is_gone(self):
        self.assertFalse(
            (PACKAGE_ROOT / "scripts" / "run.py").exists(),
            "scripts/run.py held the prompt-scanning pipeline; its four live "
            "symbols moved to core/scoring.py and config.py",
        )
```

Import `argparse` at the top of the test module.

- [ ] **Step 3: Run to verify it fails**

Run: `pytest tests/test_project_architecture.py -k "one_cli or prompt_pipeline" -v`
Expected: FAIL — `scripts/run.py` exists, and the parser has no `init`, `curate` or `report` yet.

- [ ] **Step 4: Handle `tests/test_model_api.py`**

It imports `ModelInput`, which belongs to the pipeline. Read the file and
decide per test class:

- Tests exercising `soda_mmqc/lib/api.py::generate_response` directly are
  worth keeping — rewrite them to construct the arguments `generate_response`
  actually takes, dropping `ModelInput`.
- Tests exercising `run_model` or prompt assembly go with the pipeline.

**Do not delete the file wholesale without reading it** — `lib/api.py` is
live and this is its main test. Record in the commit message which classes
were kept and which were dropped.

- [ ] **Step 5: Delete the `is_agentic_check` tests**

`tests/test_agentic_cli.py:3293-3506` tests per-check routing between the
prompt path and the agentic path. Delete them, with the reason in the
commit message: routing existed because a checklist had both kinds of
check, and now it has one kind.

- [ ] **Step 6: Delete the module**

```bash
git rm soda_mmqc/scripts/run.py
```

Remove the `evaluate` and `init` lines from `[project.scripts]`. Task 9
restores both as subcommands.

- [ ] **Step 7: Run the suite**

Run: `pytest -q`
Expected: `test_the_prompt_pipeline_is_gone` PASSES; `test_one_cli_declares_every_command` still FAILS (Task 9 finishes it); no other new failures.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "Delete the prompt-scanning pipeline

1450 of run.py's 1612 lines served prompts: Langfuse fetching, run_model,
prepare_check_data, process_check, process_checklist, initialize, and the
is_agentic_check bridge that routed between the two paths during the
conversion. With one kind of check there is nothing to route.

The four live symbols left earlier: analyze_results, save_analysis and
ModelResult to core/scoring.py, list_checks to config.py.

init is restored in the next commit and the branch must not ship without it."
```

---

## Task 8: `init` drafts gold, from a run or from scratch

**Files:**
- Create: `soda_mmqc/core/gold_drafts.py`
- Create: `tests/test_gold_drafts.py`
- Modify: `soda_mmqc/cli.py` — the `init` subparser and its dispatch

**Interfaces:**
- Consumes: `agentic.runner.run_check_live`, `core.scoring.load_predictions`,
  `core.examples.EXAMPLE_FACTORY`, `config.list_checks`.
- Produces:
  - `init_expected_outputs(checklist: str, checks: Sequence[str], *, from_run: Path | None = None, model: str | None = None, overwrite: bool = True, examples: Sequence[str] | None = None, limit: int | None = None) -> dict[str, list[str]]`
    returning `{check_name: [relative_source_path, ...]}` for what was written.
  - `DRAFT_REPLICATE = "rep-00"`

`initialize` at the old `run.py:1175` was: for each check, produce one output
per example, then `example.save_expected_output(output, check_name, True)`.
Only the producer was legacy.

- [ ] **Step 1: Write the failing test**

Create `tests/test_gold_drafts.py`:

```python
class TestInitFromAnExistingRun:
    """A run already paid for can seed the drafts.

    Runs are expensive and we keep them, so re-running a check only to write
    expected_output.json spends money for predictions we already have.
    """

    def test_it_writes_one_draft_per_example(self, tmp_path, monkeypatch):
        leaf = tmp_path / "pinned" / "rep-00"
        _write_one_prediction(leaf, EXAMPLE_A, {"outputs": [{"panel_label": "A"}]})
        _write_one_prediction(leaf, EXAMPLE_B, {"outputs": [{"panel_label": "B"}]})
        saved = _capture_saved_expected_outputs(monkeypatch)

        written = init_expected_outputs(CHECKLIST, [CHECK], from_run=tmp_path)

        assert sorted(written[CHECK]) == sorted([EXAMPLE_A, EXAMPLE_B])
        assert saved[(EXAMPLE_A, CHECK)] == {"outputs": [{"panel_label": "A"}]}

    def test_it_takes_rep_00_not_a_consensus(self, tmp_path, monkeypatch):
        """A curator corrects one draft; an average hides disagreement."""
        for rep, label in (("rep-00", "A"), ("rep-01", "Z")):
            _write_one_prediction(
                tmp_path / "pinned" / rep, EXAMPLE_A,
                {"outputs": [{"panel_label": label}]},
            )
        saved = _capture_saved_expected_outputs(monkeypatch)

        init_expected_outputs(CHECKLIST, [CHECK], from_run=tmp_path)

        assert saved[(EXAMPLE_A, CHECK)] == {"outputs": [{"panel_label": "A"}]}

    def test_it_refuses_a_root_with_no_rep_00(self, tmp_path):
        _write_one_prediction(
            tmp_path / "pinned" / "rep-03", EXAMPLE_A, {"outputs": []},
        )
        with pytest.raises(ValueError, match="rep-00"):
            init_expected_outputs(CHECKLIST, [CHECK], from_run=tmp_path)


class TestInitByRunning:
    def test_it_runs_the_check_when_given_no_run(self, tmp_path, monkeypatch):
        """Default (a): produce the predictions, then write them as drafts."""
        calls = []

        def fake_run_check_live(checklist, check, **kwargs):
            calls.append((checklist, check))
            leaf = kwargs["output"] / "pinned" / "rep-00"
            _write_one_prediction(leaf, EXAMPLE_A, {"outputs": []})
            return kwargs["output"], []

        monkeypatch.setattr(
            "soda_mmqc.core.gold_drafts.run_check_live", fake_run_check_live
        )
        saved = _capture_saved_expected_outputs(monkeypatch)

        written = init_expected_outputs(CHECKLIST, [CHECK], limit=1)

        assert calls == [(CHECKLIST, CHECK)]
        assert written[CHECK] == [EXAMPLE_A]
        assert (EXAMPLE_A, CHECK) in saved
```

`_capture_saved_expected_outputs(monkeypatch)` patches
`Example.save_expected_output` and returns a dict keyed by
`(relative_source_path, check_name)`. **Patch it rather than letting it
write** — writing real gold files from a test would corrupt the curated
corpus under `soda_mmqc/data/`.

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_gold_drafts.py -v`
Expected: FAIL — `No module named 'soda_mmqc.core.gold_drafts'`

- [ ] **Step 3: Implement**

```python
"""Draft ``expected_output.json`` so curation is correction, not typing.

A check's gold starts as a model's answer and is corrected by a curator.
Producing that first draft by hand means filling in most fields from
scratch; producing it from a run means reading and fixing.

Two sources. By default the check is run. With ``from_run`` the drafts come
from a run that already exists, which costs nothing -- and since a run may
hold several replicates, the draft is ``rep-00``, never a consensus: the
curator is correcting one answer, and an average across replicates would
hide exactly the cases where the model was unsure.
"""

DRAFT_REPLICATE = "rep-00"
```

`init_expected_outputs` resolves the checks with `config.list_checks`, gets a
run root per check (either `from_run / check` if that exists else `from_run`,
or by calling `run_check_live` into a temporary directory), reads
`<root>/pinned/<DRAFT_REPLICATE>/` with `load_predictions`, and calls
`example.save_expected_output(prediction, check_name, overwrite)` per example.

Raise `ValueError` naming `rep-00` when the root has no such directory, and
`ValueError` when `from_run` holds no arm named `pinned`.

- [ ] **Step 4: Add the subcommand**

```python
init = subparsers.add_parser(
    "init",
    help=(
        "Draft expected_output.json for a check's benchmark examples, so "
        "curation is correction rather than typing"
    ),
)
init.add_argument("checklist", type=str, help="Name of the checklist")
init.add_argument(
    "--check", type=str, action="append",
    help="Check to initialize; repeatable. Default: every check.",
)
init.add_argument(
    "--from-run", type=Path, default=None,
    help=(
        "Take drafts from an existing run root instead of running the "
        "check. Uses rep-00 -- a curator corrects one answer, not an "
        "average. Costs nothing."
    ),
)
init.add_argument(
    "--limit", type=int, default=None,
    help="Run at most this many examples (ignored with --from-run)",
)
init.add_argument(
    "--no-overwrite", action="store_true",
    help="Keep any expected_output.json that already exists",
)
```

Dispatch in `main` with the same `except (FileNotFoundError, ValueError)` →
`return 1` shape the other commands use. Guard a live `init` the way `run`
is guarded at `cli.py:757`: without `--from-run` and without `--limit`,
refuse and say a live run costs money.

- [ ] **Step 5: Run the suite**

Run: `pytest tests/test_gold_drafts.py -q && pytest -q`
Expected: all new tests PASS.

- [ ] **Step 6: Commit**

```bash
git add soda_mmqc/core/gold_drafts.py soda_mmqc/cli.py tests/test_gold_drafts.py
git commit -m "init drafts gold again, from a run or from scratch

The old initialize was a loop calling save_expected_output; only its
producer was legacy. run_check_live emits the same per-example leaf JSON,
so this is a change of sink.

It gains --from-run: a run already paid for seeds the drafts for nothing.
With replicates that is rep-00, never a consensus -- a curator corrects one
answer and an average would hide where the replicates disagreed."
```

---

## Task 9: One CLI, including curate and report

**Files:**
- Modify: `soda_mmqc/cli.py` — `curate` and `report` subparsers
- Modify: `pyproject.toml` — `[project.scripts]`
- Modify: `tests/test_project_architecture.py`

**Interfaces:**
- Consumes: `scripts.curate.main`, `scripts.report.main`.
- Produces: `cli.main` handling all seven commands; console script `mmqc`.

- [ ] **Step 1: The test from Task 7 is the failing test**

Run: `pytest tests/test_project_architecture.py -k one_cli -v`
Expected: FAIL — `init` is present after Task 8 but `curate` and `report` are not.

- [ ] **Step 2: Add the two subcommands**

```python
subparsers.add_parser(
    "curate", help="Launch the curation interface (Streamlit)",
)
subparsers.add_parser(
    "report", help="Launch the evaluation reporting app (Streamlit)",
)
```

Dispatch by importing inside the branch, so `import soda_mmqc.cli` does not
pull Streamlit:

```python
    if args.command == "curate":
        # Imported here, not at module scope: `mmqc score` in a notebook
        # must not pay for Streamlit. Both launchers sys.exit internally,
        # so the `or 0` is defensive rather than load-bearing.
        from soda_mmqc.scripts.curate import main as curate_main
        return curate_main() or 0

    if args.command == "report":
        from soda_mmqc.scripts.report import main as report_main
        return report_main() or 0
```

`scripts/curate.py` parses its own arguments today; leave that, and forward
any remainder via `parse_known_args` if it needs them.

- [ ] **Step 3: Collapse the console scripts**

```toml
[project.scripts]
mmqc = "soda_mmqc.cli:main"
# Kept for muscle memory; each is also `mmqc <command>`.
curate = "soda_mmqc.scripts.curate:main"
report = "soda_mmqc.scripts.report:main"
export-fig-report = "soda_mmqc.scripts.export_fig_checklist_report:main"
```

`evaluate` and `init` are **not** restored as separate scripts: they are
`mmqc score` and `mmqc init`. `curate` and `report` stay because they are in
people's fingers and cost nothing — they point at the launcher directly, so
there is still one implementation.

- [ ] **Step 4: Add the import-isolation test**

```python
    def test_importing_the_cli_does_not_pull_streamlit(self):
        """A subcommand's dependency is imported when it runs, not on import.

        `mmqc score` in a notebook must not pay for Streamlit.
        """
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-c",
             "import soda_mmqc.cli, sys; print('streamlit' in sys.modules)"],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(result.stdout.strip(), "False")
```

- [ ] **Step 5: Run the suite**

Run: `pytest -q`
Expected: `test_one_cli_declares_every_command` PASSES; only the two `EVALUATION_DIR` failures remain.

- [ ] **Step 6: Verify by hand**

```bash
python -m soda_mmqc.cli --help
python -m soda_mmqc.cli score --help
python -m soda_mmqc.cli init --help
```

Expected: seven commands listed; `score` shows no `--run-label` and no `--model`.

- [ ] **Step 7: Commit**

```bash
git add soda_mmqc/cli.py pyproject.toml tests/test_project_architecture.py
git commit -m "One CLI: curate and report are subcommands too

Commands were declared in two places -- cli.py and [project.scripts]
pointing into scripts/ -- so a reader looking for one had two places to
look. mmqc <command> is now the single surface; curate and report keep
their console scripts for muscle memory, pointing at the same launcher.
Streamlit is imported in the branch, so mmqc score in a notebook does not
pay for it."
```

---

## Task 10: `data/evaluation/` exists on purpose

**Files:**
- Create: `soda_mmqc/data/evaluation/.gitkeep`
- Modify: `.gitignore`
- Modify: `tests/test_project_architecture.py:99, 147`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing.

`test_config_paths` and `test_data_structure` assert
`EVALUATION_DIR.exists()` against a directory that does not exist — the two
failures in the baseline. The directory is where a production benchmark
writes, so it should exist and be empty, not be conjured by whichever test
runs first.

The catch: `.gitignore` ignores `soda_mmqc/data/evaluation/`, so a
`.gitkeep` inside it is ignored too. A negation is required, and a negation
cannot rescue a file whose *parent directory* is excluded — so the rule must
ignore the directory's contents rather than the directory.

- [ ] **Step 1: Run the failing tests**

Run: `pytest tests/test_project_architecture.py -k "config_paths or data_structure" -v`
Expected: FAIL, `AssertionError: False is not true` at lines 99 and 147.

- [ ] **Step 2: Change the ignore rule**

Replace `soda_mmqc/data/evaluation/` with:

```
# Run output under data/evaluation/ is regenerable and per-machine, but the
# directory itself is part of the layout: it is where a production
# benchmark writes. Ignore the contents, keep the directory -- a negation
# cannot rescue a file whose parent directory is excluded.
soda_mmqc/data/evaluation/*
!soda_mmqc/data/evaluation/.gitkeep
```

- [ ] **Step 3: Create the file and verify git sees it**

```bash
touch soda_mmqc/data/evaluation/.gitkeep
git check-ignore -v soda_mmqc/data/evaluation/.gitkeep; echo "exit=$?"
```

Expected: `exit=1` (not ignored). Then confirm run output still *is*
ignored:

```bash
mkdir -p soda_mmqc/data/evaluation/x/y/z
touch soda_mmqc/data/evaluation/x/y/z/analysis.json
git status --short | grep evaluation
rm -rf soda_mmqc/data/evaluation/x
```

Expected: only `.gitkeep` appears.

- [ ] **Step 4: Make the assertions say why**

```python
        self.assertTrue(
            EVALUATION_DIR.exists(),
            "data/evaluation/ is where a production benchmark writes; it is "
            "kept by .gitkeep so the layout does not depend on a run having "
            "happened",
        )
```

Apply the same at line 147 for `DATA_DIR / "evaluation"`.

- [ ] **Step 5: Run the whole suite**

Run: `pytest -q`
Expected: **0 failed**. This is the first task at which the suite is fully
green.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "Keep data/evaluation/, ignore what runs write into it

Two tests asserted the directory exists and it did not, so the baseline had
two failures. The directory is part of the layout; its contents are not.
The ignore rule had to move from the directory to its contents, since a
negation cannot rescue a file whose parent is excluded."
```

---

## Verification

After Task 10:

```bash
pytest -q
```
Expected: 0 failed. Baseline was 2 failed / 720 passed; both failures were
Task 10's.

```bash
grep -rn "from soda_mmqc.scripts" soda_mmqc/ tests/ notebooks/ experiments/
```
Expected: only the two launcher imports inside `cli.py`'s `curate` and
`report` branches.

```bash
grep -rn "scripts.run\|scripts import run" . --include="*.py" --include="*.ipynb" --include="*.toml"
```
Expected: nothing outside `thinking/` and `miscdoc/`, which are historical.

```bash
python -m soda_mmqc.cli --help
```
Expected: `run`, `score`, `assemble`, `graph`, `init`, `curate`, `report`.

```bash
python -m soda_mmqc.cli score fig-checklist-exp01 \
  --check replication-reporting \
  --predictions experiments/runs/exploration-replicate-variability/pinned/rep-00
```
Expected: exit 0, and `analysis.json` written **inside** that `rep-00`
directory. This is the end-to-end check that Task 5 landed: it scores a real
committed run. Leave the file — the companion plan wants it.

Finally, confirm the running exp-01 job is unaffected: this branch is a
worktree, and `experiments/runs/` is written by the process in the main
checkout.

## Not in scope

- **`soda_mmqc/reporting/`** — axes, pooling, plots and notebooks are the
  companion plan, `2026-09-21-reporting-measures-one-property.md`.
- **Langfuse.** See "What stays out".
- **`core/curation.py`** beyond the `curate` subcommand.
- **Re-running any experiment.** No task here spends money or invalidates
  exp-01: the scoring changes where an analysis is *written*, not what the
  evaluator computes.
