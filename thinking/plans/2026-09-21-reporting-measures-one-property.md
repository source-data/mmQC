---
title: Reporting measures one property at a time, over two axes
date: 2026-09-21
status: planned
---

# Reporting measures one property at a time, over two axes

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `soda_mmqc/reporting/` the axes the harness actually
produces — arm and replicate — a root it can be pointed at, and statistics
that never average across leaf properties; then delete the hand-rolled
pandas in both experiment notebooks by giving them the library instead.

**Architecture:** The measured quantity is **one leaf property**. Variation
comes from two places and only two: which example was measured, and which
replicate measured it. Nothing pools `panel_label` with `micrograph`. The
library's core deliverable is a tidy long frame — one row per
`(check, arm, replicate, example, property)` — and everything else
(replicate spread, non-response, arm contrasts, every plot) derives from it.

**Tech Stack:** Python, `pandas`, `plotly`, `pytest`, Streamlit.

**Spec:** this document.

**Depends on:** `2026-09-21-the-cli-owns-the-commands.md`, which is **done**
and is this branch's parent. It moved `save_analysis` into the run leaf and
gave every root the same shape.

## What the companion plan already built

Checked against the tree rather than assumed, because two of these change
what this plan should do:

| surface | where | use it, do not rebuild it |
|---|---|---|
| `ANALYSIS_FILENAME` | `core/scoring.py` | the file this plan reads |
| `score_check(...) -> {"flat": [...]}` | `core/scoring.py` | no run-label wrapper to unwrap |
| `BASELINE_ARM = "pinned"` | `core/gold_drafts.py:39` | the arm name, already named once |
| `DRAFT_REPLICATE = "rep-00"` | `core/gold_drafts.py:45` | — |
| `_draft_leaf(root, check)` | `core/gold_drafts.py:48` | **already walks `<arm>/rep-NN/`** |

`_draft_leaf` is the important one. It resolves a run root to one
`<arm>/rep-NN/` directory, including the "root holds one check or several"
case that `experiments/runs/` creates. Task 3 needs the same traversal over
*every* arm and replicate rather than one, so the two must share a module
rather than diverge: two walkers over the same layout will disagree the
first time the layout gains anything.

Task 3 therefore begins by extracting the shared piece, and the line
references into `reporting/` below are still accurate — the companion plan
never opened that package.

---

## Why

### Now

`reporting/` was built for the prompt pipeline. `FlatRun` is
`(checklist, check, model, prompt)` (`load.py:74`); `load_flat_runs` reads
`EVALUATION_DIR/<checklist>/<check>/<model>/analysis.json` and splits it by
prompt key; `RunSummaries` is keyed by `(model, prompt)`; every comparison
plot takes `compare: Literal["prompt", "model"]`.

The harness produces `(check, arm, replicate)`. Neither `arm` nor
`replicate` exists anywhere in `reporting/`, and `prompt` names something
that is being deleted. `data/evaluation/` is empty only because no
production benchmark has run yet — the substrate is right, the axes are not.

So both experiment notebooks bypass the library completely. Each hand-rolls
a `leaves()` walker, calls `score_check` per leaf, and reduces the result
with ad-hoc pandas. The same code is written twice, tested nowhere.

Worse, what they hand-rolled encodes a statistical mistake that we do not
want to keep. Both compute an **instance-weighted mean across properties**,
with this comment:

> `mean_score` is the layer-2 rollup over instances that are applicable and
> correctly so — and it is **0.0 when a property has no eligible instances
> at all**, which means "nothing to score", not "scored zero".

The weighting was a workaround for that zero. But the cross-property average
it produces is not a quantity we want at all: `panel_label` and `micrograph`
measure different things, and a number that mixes them hides the case where
an arm improves one and degrades the other. It was tolerable in an
exploration sizing replicate counts. It is not what a benchmark reports.

### Proposed

Three layers, each a strictly per-property quantity.

```
instance            one leaf property, one example, one replicate
  |                 pooled within a leaf, per property
PropertyRollup      mean_score: float | None, eligible: int
  |                 pooled across replicates of one arm, per property
ReplicateSpread     mean, sd, n_replicates, eligible_total
  |                 two arms, paired by example, per property
ArmContrast         difference, se, n_examples
```

Nothing in that column ever crosses a property boundary.

The primitive underneath is a tidy frame, because it is what both notebooks
built by hand and what every plot needs:

```
scores_frame(runs) -> DataFrame[
    check, arm, replicate, example, property,
    mean_score, eligible, layer1_*, layer2_*
]
```

### Why `mean_score` must be allowed to be `None`

`property_mean_score` (`core/property_rollup.py:22`) returns `0.0` when no
instance is eligible. `0.0` is a score a model can earn; "no eligible
instance" is not a score at all. Conflating them is wrong on every axis:

- **Across replicates** — a property with no eligible instance in `rep-03`
  contributes a spurious `0.0`, pulling the arm's mean down and inflating
  its SD. This is the same defect the notebooks worked around, now on the
  axis this plan introduces. Fixing it at the source is why Task 1 comes
  first.
- **Across examples** — the same, per example.
- **In a plot** — a bar at zero and a bar for "not applicable here" must not
  look alike.

So `PropertyRollup.mean_score` becomes `float | None` and gains
`eligible: int`. Every consumer must then decide explicitly what to do with
`None`, which is the point.

### Why a layer-2 number is never shown without its denominator

The policy for `mean_score` is unchanged and deliberate: **the mean is taken
over instances the model judged applicable and judged so correctly**
(`layer1 == correct_applicable`). Layer 2 asks "when the model correctly saw
that this property applied, how well did it match?" Whether the model gets
applicability right is layer 1's question, and mixing the two would make
neither answerable.

Excluding an ineligible replicate follows from the same policy rather than
extending it. A replicate that judged the property not-applicable has
nothing to say about matching quality, so it contributes nothing to the
layer-2 mean — and the variation in *that* judgement is a layer-1 result,
analysed there.

The cost is a conditioning confound, and it must be stated rather than
designed away. Each arm's layer-2 mean is computed over **its own** eligible
set. If `pinned` finds a property applicable in 5 of 5 replicates and
`<check>@v2` in 1 of 5, the two means describe different populations, and
`@v2`'s is over a subset it selected — plausibly the easy cases.

exp-01 is exactly where this bites. A minimal skill that returns
`outputs: []` produces non-response at layer S *and* an empty eligible set
at layer 2, so **the failing arm can show the better layer-2 mean by
answering less.** Layer 2 read alone would call the minimal skill fine.

Hence two rules, enforced by Tasks 5, 6 and 7:

1. **Every layer-2 figure carries its denominator.** `mean` never appears
   without `n_replicates` and `eligible_total` beside it, in a table or in
   hover text. A bare layer-2 mean is not a reportable number.
2. **A contrast says how much of the benchmark it used.**
   `arm_contrast` pairs on examples both arms scored, and reports
   `n_baseline_only`, `n_variant_only` and `eligibility_agreement` so a
   difference computed on a shrunken set announces it.

Neither rule tries to correct the confound — there is no honest way to
impute a score for an instance the model never judged applicable. They make
it visible, and pair it with `non_response_counts` (Task 6), which is the
layer-S half of the same story.

### Why the library stops at `ArmContrast`

`ArmContrast` pairs by example within a property and reports a mean
difference with its standard error. That much is general: it is what "did
this arm move this property" means, and exp-01 needs it.

What the library does **not** do is decide whether a contrast is
significant, combine contrasts across properties into a verdict, or correct
for multiplicity. Those are the experiment's claims and belong in the
experiment's note, where a reader can see the reasoning.

### Why a root parameter, not a new directory convention

`load_flat_runs(checklist, check)` resolves `EVALUATION_DIR` internally, so
an experiment's results are unreachable. After the companion plan every root
has the same shape — *a root is a directory whose children are arms* — so
one walker serves both:

| root | what the path carries |
|---|---|
| `data/evaluation/<checklist>/<check>/<model>/` | checklist, check, model |
| `experiments/runs/<exp>/<check>/` | check only |

The difference is which facts the path supplies and which the caller must.
`load_run_root(root, *, checklist, check, model="")` takes them as
arguments; `load_evaluation_dir(checklist, check, models=None)` is the
convenience that resolves the production tree and calls it per model.

### What stays out

- **Any cross-property aggregate.** Not as a default, not as an option, not
  as a convenience for a notebook. See Global Constraints.
- **Significance testing and multiplicity correction.** See above.
- **`reporting/context.py`, `navigate.py`, `display.py`** except where a
  renamed field forces an edit. They inspect individual records and are
  indifferent to these axes.
- **Re-running anything.** Every task reads committed predictions under
  `experiments/runs/`.

---

## Test fixtures used throughout

Every task's test code assumes these, defined once in
`tests/test_reporting_statistics.py` and imported by the others. Write them
in Task 4, the first task that needs them.

| helper | what it makes |
|---|---|
| `CHECKLIST`, `CHECK`, `MODEL` | `"fig-checklist-exp01"`, `"replication-reporting"`, `"claude-sonnet-5"` |
| `_record(example, scores)` | a `FlatRecord` whose `metadata["source"]` is `example` and whose `analysis["instances"]` holds one instance per `{property: score}` entry, `layer1="correct_applicable"` when the score is not `None` and `"correct_not_applicable"` when it is |
| `_record_with_rows(example, correct, missing, spurious)` | a `FlatRecord` whose `analysis["by_list"]["outputs"]["row_counts"]` holds those three counts |
| `_run(arm, replicate, records)` | a `FlatRun` with a `RunRef` for `CHECKLIST`/`CHECK`/`MODEL` and a stub manifest that profiles every property |
| `_frame(rows)` | a `scores_frame`-shaped DataFrame from tuples `(arm, replicate, example, property, mean_score, eligible)`, with `check=CHECK` |
| `_write_analysis(leaf, record)` | writes `{"flat": [record]}` to `leaf / "analysis.json"`, creating parents |
| `_one_flat_record()` | one minimal serialisable flat record for the loader tests |
| `_two_arm_summaries(replicates=1)`, `_summaries_with_ineligible_property()`, `_runs_for(summaries)`, `_REF`, `_INELIGIBLE_INDEX` | the plot fixtures in Task 7; `_REF` is the `RunRef` of the first summary and `_INELIGIBLE_INDEX` the x-axis position of the property with `eligible == 0` |

---

## Global Constraints

- **Never average across leaf properties.** No function in
  `soda_mmqc/reporting/` or `soda_mmqc/core/` may return a number pooling
  two distinct `leaf_property` values. This is the constraint the plan
  exists to enforce; a helper that "just makes the notebook shorter" by
  doing it is a failure, not a convenience. Task 8 asserts it.
- **Two variance axes: examples and replicates.** Any spread reported must
  say which one it is over. A bare SD with no axis named is a bug.
- **`mean_score is None` means "nothing eligible to score".** It is never
  coerced to `0.0`, never filled, never dropped silently. A consumer that
  skips `None` rows says so in a comment.
- **Layer 2 is conditional on layer 1, on every axis.** The mean is over
  instances with `layer1 == correct_applicable`; a replicate with none is
  excluded, not zeroed. Variation in applicability is a **layer-1** result
  and is reported there, never allowed to move a layer-2 mean.
- **No layer-2 number is presented without its denominator.** `mean`
  travels with `n_replicates` and `eligible_total`; a contrast travels with
  `eligibility_agreement`. An arm can earn a better layer-2 mean by
  answering less, so a bare one is not a reportable number.
- **A replicate is a resample, not a reproduction.** Replicates of one arm
  may be pooled. Arms may never be pooled with each other.
- **Reporting reads; it does not run.** No task calls `run_check_live`.
  Scoring a leaf via `core.scoring.score_check` is allowed and cached.
- **One walker over the run layout.** `<arm>/rep-NN/` is traversed by code
  in one module. `core/gold_drafts.py` already has one; Task 3 extracts it
  rather than writing a second.
- **Run after every task:** `pytest -q`. Measured baseline on this branch's
  parent: **726 passed, 7 skipped, 10 deselected, 0 failed.** Every task
  must keep passed >= 726 and add no failure.

---

## File Structure

| File | Responsibility after this plan |
|---|---|
| `soda_mmqc/core/property_rollup.py` | `property_mean_score` returns `float \| None`; new `eligible_instance_count`. |
| `soda_mmqc/reporting/load.py` | `RunRef`, `FlatRun` with `arm`/`replicate`; `load_run_root`, `load_evaluation_dir`. `prompt` and `normalize_prompt_name` removed. |
| `soda_mmqc/reporting/aggregate.py` | `PropertyRollup` gains `eligible`; `RunSummaries` keyed by `(model, arm, replicate)`; new `scores_frame`, `replicate_spread`, `non_response_counts`, `arm_contrast`. |
| `soda_mmqc/reporting/plots.py` | `compare="arm"`; error bars from `ReplicateSpread`; `None` rendered as a gap, never a zero bar. |
| `soda_mmqc/reporting/compare.py`, `export_report.py`, `streamlit_app.py` | Follow the renamed axes. |
| `notebooks/experiments/exp-01-skill-verbosity.ipynb` | Uses the library; the hand-rolled walker and weighted mean go. |
| `notebooks/experiments/exploration-replicate-variability.ipynb` | Same, with a note that its cross-property average was an exploration shortcut. |
| `notebooks/comparative-reporting.ipynb` | Prompt contrasts become arm contrasts. |
| `tests/test_property_rollup.py` | The `None` contract. |
| `tests/test_reporting_load.py` | **New.** Root walking, both layouts. |
| `tests/test_reporting_statistics.py` | **New.** The three-layer hierarchy and the no-cross-property rule. |

---

## Task 1: `mean_score` tells the truth when nothing was eligible

> **Done, and it grew.** Two questions from review turned this from a
> one-field change into the measure/aggregate split the rest of the plan
> now assumes. Recorded here because the tasks below were written against
> the smaller version.
>
> - **`eligible` was deleted again.** It duplicated
>   `layer1_counts["correct_applicable"]` exactly for profiled properties
>   -- 10 of 10 across the snapshots, and structurally, since
>   `LeafInstanceResult.score` is never `None`. The denominator is
>   `PropertyRollup.n_scored`, derived from the layer-1 count. There is no
>   second word for an outcome layer 1 already names: use
>   `Layer1Label.CORRECT_APPLICABLE`, not "eligible".
> - **`by_property` left the serialization.** It was computed at scoring
>   time and stored, while `reporting/aggregate.py` recomputed its own
>   from `instances` and `reporting/tables.py` read the stored copy --
>   two live paths to one number. Manifest thresholds are tunable, so a
>   stored rollup is a cache nothing invalidates. `analysis.json` now
>   holds `instances` and `by_list` only, and
>   `core/property_rollup.py::rollup_by_property` is the single
>   instances-to-statistics step, run when a report is built.
>
> **Consequence for Task 4:** `scores_frame` has one source. Group a
> record's `instances`, call `rollup_by_property` per example with the
> manifest. Do not look for a stored `by_property`; there isn't one.
>
> **Consequence for Task 7:** `PropertyRollup` gained `n_scored` and
> `n_instances`, so "never show a layer-2 mean without its denominator"
> has something concrete to show.


**Files:**
- Modify: `soda_mmqc/core/property_rollup.py:22-37`
- Modify: `soda_mmqc/reporting/aggregate.py:16-23, 99-137`
- Modify: `tests/test_property_rollup.py`
- Modify: every consumer of `PropertyRollup.mean_score` — find with
  `grep -rn "mean_score" soda_mmqc/ tests/`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `property_mean_score(instances, *, profiled) -> float | None`
  - `eligible_instance_count(instances, *, profiled) -> int`
  - `PropertyRollup(mean_score: float | None, eligible: int, layer1_counts: dict[str, int], layer2_counts: dict[str, int])`

This is first because every later statistic inherits the defect otherwise.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_property_rollup.py`:

```python
def test_no_eligible_instance_is_not_a_score_of_zero():
    """0.0 is a score a model can earn; "nothing to score" is not.

    Conflating them injects a spurious 0.0 into every mean taken over this
    property -- across replicates, across examples, and into every bar
    chart -- which is exactly what both experiment notebooks had to work
    around by hand.
    """
    instances = [
        {"leaf_property": "outputs.micrograph", "score": 1.0,
         "layer1": "correct_not_applicable"},
    ]
    assert property_mean_score(instances, profiled=True) is None
    assert eligible_instance_count(instances, profiled=True) == 0


def test_a_genuine_zero_is_still_zero():
    instances = [
        {"leaf_property": "outputs.micrograph", "score": 0.0,
         "layer1": "correct_applicable"},
    ]
    assert property_mean_score(instances, profiled=True) == 0.0
    assert eligible_instance_count(instances, profiled=True) == 1


def test_eligible_counts_only_what_the_mean_used():
    instances = [
        {"leaf_property": "p", "score": 1.0, "layer1": "correct_applicable"},
        {"leaf_property": "p", "score": 0.0, "layer1": "correct_applicable"},
        {"leaf_property": "p", "score": 1.0, "layer1": "correct_not_applicable"},
        {"leaf_property": "p", "score": None, "layer1": "correct_applicable"},
    ]
    assert eligible_instance_count(instances, profiled=True) == 2
    assert property_mean_score(instances, profiled=True) == 0.5


def test_an_unprofiled_property_counts_every_scored_instance():
    instances = [
        {"leaf_property": "p", "score": 1.0, "layer1": None},
        {"leaf_property": "p", "score": 0.0, "layer1": None},
    ]
    assert eligible_instance_count(instances, profiled=False) == 2
    assert property_mean_score(instances, profiled=False) == 0.5
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_property_rollup.py -v`
Expected: FAIL — `property_mean_score` returns `0.0` where `None` is expected; `eligible_instance_count` does not exist.

- [ ] **Step 3: Implement**

In `core/property_rollup.py`:

```python
def _eligible_scores(
    instances: Sequence[Any],
    *,
    profiled: bool,
) -> list[float]:
    """Instance scores that contribute to this property's mean."""
    scores: list[float] = []
    for instance in instances:
        score = _instance_score(instance)
        if score is None:
            continue
        if profiled and _instance_layer1(instance) != LAYER1_MEAN_SCORE_ELIGIBLE:
            continue
        scores.append(score)
    return scores


def eligible_instance_count(
    instances: Sequence[Any],
    *,
    profiled: bool,
) -> int:
    """How many instances this property's mean was taken over.

    Carried beside the mean because a mean over zero instances is not a
    score, and a mean over one is not comparable to a mean over forty.
    """
    return len(_eligible_scores(instances, profiled=profiled))


def property_mean_score(
    instances: Sequence[Any],
    *,
    profiled: bool,
) -> float | None:
    """Mean instance score for one leaf property, or ``None``.

    ``None`` means no instance was eligible -- the property had nothing to
    score here. It is not ``0.0``: that is a score a model can earn, and
    returning it for "not applicable" injects a false zero into every mean
    taken over this property.
    """
    scores = _eligible_scores(instances, profiled=profiled)
    if not scores:
        return None
    return sum(scores) / len(scores)
```

- [ ] **Step 4: Update `PropertyRollup` and `aggregate_run`**

```python
@dataclass
class PropertyRollup:
    """Pooled summary for one leaf property across one run leaf.

    ``mean_score`` is ``None`` when ``eligible`` is 0: the property had no
    instance to score here, which is not the same as scoring zero.
    """

    mean_score: float | None
    eligible: int
    layer1_counts: dict[str, int]
    layer2_counts: dict[str, int]
```

In `aggregate_run`, pass `eligible=eligible_instance_count(instances, profiled=profiled)`.

- [ ] **Step 5: Fix every consumer**

```bash
grep -rn "mean_score" soda_mmqc/ tests/ notebooks/
```

For each site, decide explicitly and leave a comment saying which:
- a plot skips `None` and leaves a gap in the bar (Task 6 does this properly);
- a table shows an em dash;
- a mean over rollups skips `None` and weights by `eligible`.

**No site may write `mean_score or 0.0`.** That reintroduces the defect in
one character.

- [ ] **Step 6: Run the suite**

Run: `pytest -q`
Expected: 0 failed. Expect several `tests/test_reporting_plots.py` and `test_reporting_phase1.py` failures first — fix each at the site, not by coercing.

- [ ] **Step 7: Commit**

```bash
git add soda_mmqc/core/property_rollup.py soda_mmqc/reporting/aggregate.py tests/
git commit -m "mean_score is None when nothing was eligible

0.0 is a score a model can earn; 'no eligible instance' is not a score.
Conflating them put a false zero into every mean over the property, which
is what both experiment notebooks worked around by hand with an
instance-weighted average. Fixed at the source, with the eligible count
carried beside the mean so consumers can weight honestly."
```

---

## Task 2: A run is identified by its arm and its replicate

**Files:**
- Modify: `soda_mmqc/reporting/load.py:56-100` — `FlatRun`, add `RunRef`
- Modify: `soda_mmqc/reporting/aggregate.py:25-40, 138-171` — `RunSummary`,
  `RunSummaries`
- Modify: `soda_mmqc/reporting/__init__.py` — exports
- Modify: `tests/test_reporting_phase1.py`, `test_reporting_compare.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:

```python
@dataclass(frozen=True)
class RunRef:
    """What identifies one scored run leaf."""
    checklist: str
    check: str
    model: str       # "" when the root does not carry one
    arm: str         # "pinned", or "<check>@v2" for an unpinned variant
    replicate: int
```

  - `FlatRun(ref: RunRef, records: tuple[FlatRecord, ...], manifest: EvalManifest)`
    with `checklist`/`check`/`model`/`arm`/`replicate` as read-only properties
    delegating to `ref`, so existing attribute access keeps working.
  - `RunSummary` likewise carries `ref`.
  - `RunSummaries` keyed by `RunRef`, with `.arms`, `.replicates`,
    `.for_arm(arm) -> tuple[RunSummary, ...]`.

`prompt` and `normalize_prompt_name` are deleted, not renamed: an arm is not
a prompt, and a silent rename would let prompt-era assumptions survive.

- [ ] **Step 1: Write the failing test**

Create `tests/test_reporting_load.py`:

```python
def test_a_run_is_identified_by_arm_and_replicate():
    """The axes the harness produces, not the ones prompts had.

    `prompt` is deleted rather than renamed to `arm`: an arm is a different
    configuration of the same skill set, a prompt was a different wording,
    and code written for one is not correct for the other.
    """
    ref = RunRef(
        checklist="fig-checklist-exp01", check="replication-reporting",
        model="claude-sonnet-5", arm="pinned", replicate=3,
    )
    assert ref.replicate == 3
    assert not hasattr(ref, "prompt")


def test_flat_run_still_exposes_the_flat_attributes():
    """Consumers read run.check, not run.ref.check."""
    run = _make_run(arm="pinned", replicate=0)
    assert run.check == CHECK
    assert run.arm == "pinned"
    assert run.replicate == 0


def test_summaries_group_by_arm():
    summaries = summarize_runs(FlatRuns([
        _make_run(arm="pinned", replicate=0),
        _make_run(arm="pinned", replicate=1),
        _make_run(arm=f"{CHECK}@v2", replicate=0),
    ]))
    assert set(summaries.arms) == {"pinned", f"{CHECK}@v2"}
    assert len(summaries.for_arm("pinned")) == 2
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_reporting_load.py -v`
Expected: FAIL — `RunRef` does not exist.

- [ ] **Step 3: Implement `RunRef` and reshape `FlatRun`**

Keep the flat properties so the change is mechanical for consumers:

```python
@dataclass(frozen=True)
class FlatRun:
    """One scored run leaf: <root>/<arm>/rep-NN/."""

    ref: RunRef
    records: tuple[FlatRecord, ...]
    manifest: EvalManifest

    @property
    def checklist(self) -> str: return self.ref.checklist

    @property
    def check(self) -> str: return self.ref.check

    @property
    def model(self) -> str: return self.ref.model

    @property
    def arm(self) -> str: return self.ref.arm

    @property
    def replicate(self) -> int: return self.ref.replicate
```

- [ ] **Step 4: Rekey `RunSummaries`**

Replace `Mapping[tuple[str, str], RunSummary]` with `Mapping[RunRef, RunSummary]`, and add:

```python
    @property
    def arms(self) -> tuple[str, ...]:
        return tuple(sorted({ref.arm for ref in self}))

    @property
    def replicates(self) -> tuple[int, ...]:
        return tuple(sorted({ref.replicate for ref in self}))

    def for_arm(self, arm: str) -> tuple[RunSummary, ...]:
        """Every replicate of one arm, in replicate order."""
        return tuple(
            self[ref] for ref in sorted(self, key=lambda r: r.replicate)
            if ref.arm == arm
        )
```

- [ ] **Step 5: Delete the prompt machinery**

Remove `normalize_prompt_name` (`load.py:18-40`), `_prompt_matches`
(`load.py:50-54`), `load_prompt_text` (`load.py:261-281`), and their
exports from `reporting/__init__.py`.

- [ ] **Step 6: Run the suite**

Run: `pytest -q`
Expected: new tests PASS; failures in `test_reporting_phase1.py`, `test_reporting_compare.py`, `test_reporting_plots.py` where fixtures build `FlatRun(prompt=...)`. Update the fixtures.

- [ ] **Step 7: Commit**

```bash
git add soda_mmqc/reporting/ tests/
git commit -m "A run is identified by its arm and its replicate

FlatRun was (checklist, check, model, prompt) -- the prompt pipeline's
axes. The harness produces arms and replicates and neither existed here.
prompt is deleted rather than renamed: an arm is a different configuration,
a prompt was a different wording, and code written for one is not correct
for the other."
```

---

## Task 3: Point reporting at a root

**Files:**
- Create: `soda_mmqc/core/run_layout.py` — the one walker
- Modify: `soda_mmqc/core/gold_drafts.py:39-80` — `_draft_leaf`,
  `BASELINE_ARM`, `DRAFT_REPLICATE` move there and are imported back
- Modify: `soda_mmqc/reporting/load.py:383-454` — `load_flat_runs`
- Modify: `soda_mmqc/reporting/load.py:320-381` — `try_load_run_summaries`,
  `discover_evaluation_checks`
- Modify: `tests/test_reporting_load.py`, `tests/test_gold_drafts.py`

**Interfaces:**
- Consumes: `core.scoring.ANALYSIS_FILENAME`.
- Produces, in `core/run_layout.py`:
  - `BASELINE_ARM = "pinned"`, `REPLICATE_PATTERN = re.compile(r"^rep-(\d+)$")`
  - `resolve_check_root(root: Path, check: str) -> Path` — the "root holds
    one check or several" step `_draft_leaf` already does
  - `iter_leaves(root: Path) -> Iterator[tuple[str, int, Path]]` — every
    `(arm, replicate, directory)` under a root, in sorted order
  - `leaf(root: Path, *, arm: str, replicate: int) -> Path` — one named
    leaf, raising if absent. `_draft_leaf` becomes a call to this.
- Produces, in `reporting/load.py`:
  - `load_run_root(root: Path, *, checklist: str, check: str, model: str = "", include_payloads: bool = False) -> FlatRuns`
  - `load_evaluation_dir(checklist: str, check: str, *, models: Sequence[str] | None = None, include_payloads: bool = False) -> FlatRuns`

`load_flat_runs` is removed; both replacements are explicit about which tree
they read.

**Extract before adding.** `core/gold_drafts.py` already walks this layout
for `init --from-run`, including the case where a root holds one check or
several. Writing a second walker in `reporting/` would mean two pieces of
code that must agree about what `rep-NN` means and nothing making them.
`core/run_layout.py` is below both — `reporting` and `gold_drafts` may
depend on it, and it depends on neither.

Do the extraction as its own commit, with `tests/test_gold_drafts.py`
unchanged and passing, before writing anything in `reporting/`: that is the
evidence the move preserved behaviour.

- [ ] **Step 0: Extract the walker, behaviour unchanged**

Move `BASELINE_ARM`, `DRAFT_REPLICATE` and the traversal inside
`_draft_leaf` into `core/run_layout.py` as `BASELINE_ARM`,
`REPLICATE_PATTERN`, `resolve_check_root`, `iter_leaves` and `leaf`.
Re-express `gold_drafts._draft_leaf` as:

```python
#: Which replicate a draft comes from. Not a consensus across replicates:
#: a curator corrects one answer, and averaging would hide precisely the
#: examples where the replicates disagreed.
DRAFT_REPLICATE_INDEX = 0

#: Kept as the directory name it has always been, for callers and tests
#: that match on it.
DRAFT_REPLICATE = f"rep-{DRAFT_REPLICATE_INDEX:02d}"


def _draft_leaf(root: Path, check: str) -> Path:
    """The ``<arm>/rep-NN/`` directory a run root's drafts come from."""
    return leaf(
        resolve_check_root(Path(root), check),
        arm=BASELINE_ARM,
        replicate=DRAFT_REPLICATE_INDEX,
    )
```

`run_layout.leaf` takes a replicate *number*, since that is what
`iter_leaves` yields and what a reader of `rep-07` means. `gold_drafts`
keeps both names: the index it passes, and `DRAFT_REPLICATE` as the string
its tests already match on. The reason drafts are one replicate rather than
a consensus stays in `gold_drafts` — that is a fact about curation, not
about the layout.

Run: `pytest tests/test_gold_drafts.py -q`
Expected: 8 passed, **with that file unedited**. If it needed editing, the
extraction changed behaviour — undo and redo it.

Commit this before Step 1.

- [ ] **Step 1: Write the failing test**

```python
def test_it_walks_arms_and_replicates_under_a_root(tmp_path):
    """A root is a directory whose children are arms.

    The same walker serves data/evaluation/<checklist>/<check>/<model>/ and
    experiments/runs/<exp>/<check>/ -- they differ only in which facts the
    path carries, which is why checklist/check/model are arguments.
    """
    for arm, rep in (("pinned", 0), ("pinned", 1), ("c@v2", 0)):
        _write_analysis(tmp_path / arm / f"rep-{rep:02d}", _one_flat_record())

    runs = load_run_root(tmp_path, checklist=CHECKLIST, check=CHECK)

    assert {(r.arm, r.replicate) for r in runs} == {
        ("pinned", 0), ("pinned", 1), ("c@v2", 0),
    }
    assert all(r.check == CHECK for r in runs)


def test_a_leaf_without_an_analysis_is_skipped_with_a_warning(tmp_path, caplog):
    """A run that has predictions but was never scored is not an error."""
    _write_analysis(tmp_path / "pinned" / "rep-00", _one_flat_record())
    (tmp_path / "pinned" / "rep-01" / "example").mkdir(parents=True)

    runs = load_run_root(tmp_path, checklist=CHECKLIST, check=CHECK)

    assert len(runs) == 1
    assert "rep-01" in caplog.text


def test_a_directory_that_is_not_rep_nn_is_not_a_replicate(tmp_path):
    """Guards against a stray directory becoming a phantom replicate."""
    _write_analysis(tmp_path / "pinned" / "rep-00", _one_flat_record())
    (tmp_path / "pinned" / "notes").mkdir(parents=True)

    runs = load_run_root(tmp_path, checklist=CHECKLIST, check=CHECK)
    assert [r.replicate for r in runs] == [0]


def test_the_experiment_root_needs_no_model(tmp_path):
    """experiments/runs/<exp>/<check>/ carries no model segment."""
    _write_analysis(tmp_path / "pinned" / "rep-00", _one_flat_record())
    runs = load_run_root(tmp_path, checklist=CHECKLIST, check=CHECK)
    assert runs[0].model == ""


def test_the_analysis_has_no_prompt_wrapper(tmp_path):
    """The companion plan flattened analysis.json to {"flat": [...]}."""
    _write_analysis(tmp_path / "pinned" / "rep-00", _one_flat_record())
    runs = load_run_root(tmp_path, checklist=CHECKLIST, check=CHECK)
    assert len(runs[0].records) == 1
```

`_write_analysis(leaf, record)` writes `{"flat": [record]}` to
`leaf / "analysis.json"`, creating parents.

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_reporting_load.py -v`
Expected: FAIL — `load_run_root` does not exist.

- [ ] **Step 3: Implement `load_run_root`**

Use `run_layout.iter_leaves(root)` from Step 0 — do not walk the directory
tree here. For each `(arm, replicate, directory)` it yields, read
`ANALYSIS_FILENAME` and take its `"flat"` array. Warn and skip a leaf with
no `analysis.json`; warn and skip a malformed one. `iter_leaves` raises
`FileNotFoundError` if `root` itself is missing.

The division: `run_layout` knows what the directories mean, `load` knows
what the files inside them contain. A leaf with predictions and no analysis
is `load`'s business, not the layout's -- it is a run that was never scored,
which is a normal state and not a malformed tree.

- [ ] **Step 4: Implement `load_evaluation_dir`**

```python
def load_evaluation_dir(
    checklist: str,
    check: str,
    *,
    models: Sequence[str] | None = None,
    include_payloads: bool = False,
) -> FlatRuns:
    """Load the production tree: EVALUATION_DIR/<checklist>/<check>/<model>/.

    A thin resolver over :func:`load_run_root` -- the production path
    carries the model, an experiment root does not, and that is the only
    difference between the two.
    """
```

- [ ] **Step 5: Update the Streamlit entry points**

`try_load_run_summaries` calls `load_evaluation_dir`. Its error strings
mention `evaluate`, a command the companion plan deleted — change them to
`mmqc run` and `mmqc score`, and drop the "Legacy files that only contain
`perfect_match`" sentence, which refers to a format no longer produced.

`discover_evaluation_checks` keeps working: it looks for model directories
under `EVALUATION_DIR/<checklist>/<check>/`, which is still the shape.

- [ ] **Step 6: Run the suite**

Run: `pytest -q`
Expected: 0 failed.

- [ ] **Step 7: Verify against a real committed run**

```bash
python -c "
from pathlib import Path
from soda_mmqc.reporting.load import load_run_root
runs = load_run_root(
    Path('experiments/runs/exploration-replicate-variability'),
    checklist='fig-checklist-exp01', check='replication-reporting',
)
print(sorted((r.arm, r.replicate) for r in runs))
"
```

Expected: ten `('pinned', N)` pairs — **but only for leaves that have an
`analysis.json`.** If the exploration run was never scored, score one leaf
first with `mmqc score` and expect one pair. Record which you saw.

- [ ] **Step 8: Commit**

```bash
git add soda_mmqc/reporting/load.py tests/test_reporting_load.py
git commit -m "Point reporting at a root

load_flat_runs resolved EVALUATION_DIR internally, so an experiment's
results were unreachable. Both trees now have the same shape -- a root is a
directory whose children are arms -- so one walker serves both, and
load_evaluation_dir is a thin resolver over it."
```

---

## Task 4: One row per property per replicate per example

**Files:**
- Modify: `soda_mmqc/reporting/aggregate.py`
- Create: `tests/test_reporting_statistics.py`

**Interfaces:**
- Consumes: `FlatRuns`, `PropertyRollup.eligible`.
- Produces:

```python
def scores_frame(runs: FlatRuns) -> pd.DataFrame:
    """One row per (check, arm, replicate, example, property)."""
```

  Columns: `check`, `arm`, `replicate`, `example`, `property`,
  `mean_score` (nullable float), `eligible` (int), `layer1` (str | None),
  `layer2` (str | None).

This replaces the `leaves()` walker and the row-building loop that both
notebooks hand-roll. `example` comes from `record.metadata["source"]`, which
is the example's `relative_source_path`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_reporting_statistics.py`:

```python
def test_one_row_per_property_per_replicate_per_example():
    """The tidy frame both notebooks built by hand.

    Keeping property on the row -- never collapsed into it -- is what makes
    every downstream statistic per-property by construction.
    """
    runs = FlatRuns([
        _run(arm="pinned", replicate=0, records=[
            _record(example="doc-a", scores={"outputs.panel_label": 1.0,
                                             "outputs.micrograph": 0.5}),
        ]),
        _run(arm="pinned", replicate=1, records=[
            _record(example="doc-a", scores={"outputs.panel_label": 0.0,
                                             "outputs.micrograph": 0.5}),
        ]),
    ])

    frame = scores_frame(runs)

    assert len(frame) == 4
    assert set(frame.columns) >= {
        "check", "arm", "replicate", "example", "property",
        "mean_score", "eligible",
    }
    panel = frame[frame["property"] == "outputs.panel_label"]
    assert sorted(panel["mean_score"]) == [0.0, 1.0]


def test_an_ineligible_property_is_a_row_with_a_null_score():
    """Absent is not zero, and the row must still exist.

    Dropping the row would make the property look unmeasured; writing 0.0
    would make it look wrong. The row carries NA and eligible == 0.
    """
    runs = FlatRuns([
        _run(arm="pinned", replicate=0, records=[
            _record(example="doc-a", scores={"outputs.micrograph": None}),
        ]),
    ])
    frame = scores_frame(runs)
    row = frame.iloc[0]
    assert pd.isna(row["mean_score"])
    assert row["eligible"] == 0


def test_the_frame_never_collapses_two_properties():
    runs = FlatRuns([
        _run(arm="pinned", replicate=0, records=[
            _record(example="doc-a", scores={"p1": 1.0, "p2": 0.0}),
        ]),
    ])
    frame = scores_frame(runs)
    assert set(frame["property"]) == {"p1", "p2"}
    assert len(frame) == 2
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_reporting_statistics.py -v`
Expected: FAIL — `scores_frame` does not exist.

- [ ] **Step 3: Implement**

Iterate runs, then `aggregate_run(run).by_property`, emitting one row per
property. Do **not** call `aggregate_run` if a per-example breakdown is
needed — `aggregate_run` pools across examples within a leaf. Instead group
each run's `records` by `metadata["source"]` first, then roll up per
property within each example. Add a docstring saying so, because the
distinction is the whole point of the frame:

```python
def scores_frame(runs: FlatRuns) -> pd.DataFrame:
    """One row per (check, arm, replicate, example, property).

    Both axes of variation stay on the frame -- ``example`` and
    ``replicate`` -- and ``property`` is never collapsed into a row. Every
    statistic downstream groups this frame; none of them may group across
    ``property``.

    Note this is *not* ``aggregate_run`` per run: that pools examples within
    a leaf, which throws away the example axis this frame exists to keep.
    """
```

- [ ] **Step 4: Run the suite**

Run: `pytest -q`
Expected: 0 failed.

- [ ] **Step 5: Commit**

```bash
git add soda_mmqc/reporting/aggregate.py tests/test_reporting_statistics.py
git commit -m "A tidy frame with both variance axes on it

One row per (check, arm, replicate, example, property). Property stays on
the row, so every statistic built on this frame is per-property by
construction. This is the walker and row loop both experiment notebooks
wrote by hand."
```

---

## Task 5: Spread across replicates, per property

**Files:**
- Modify: `soda_mmqc/reporting/aggregate.py`
- Modify: `tests/test_reporting_statistics.py`

**Interfaces:**
- Consumes: `scores_frame`.
- Produces:

```python
def replicate_spread(frame: pd.DataFrame) -> pd.DataFrame: ...
def arm_contrast(
    frame: pd.DataFrame, *, baseline: str, variant: str
) -> pd.DataFrame: ...
```

Both return a DataFrame rather than a list of objects, because every
consumer plots or tabulates them. The row shapes are:

| `replicate_spread` column | meaning |
|---|---|
| `check`, `arm`, `property` | the group; one row per combination |
| `mean` | mean over replicates of the per-replicate mean, or NA |
| `sd` | SD over replicates, `ddof=1`; **NA when `n_replicates < 2`** |
| `n_replicates` | replicates with at least one eligible instance |
| `eligible_total` | eligible instances summed over those replicates |

| `arm_contrast` column | meaning |
|---|---|
| `check`, `property` | the group; one row per combination |
| `difference` | mean over examples of `variant - baseline` |
| `se` | `sd(differences, ddof=1) / sqrt(n_examples)`, NA when `n < 2` |
| `n_examples` | examples scored by **both** arms — the paired set |
| `n_baseline_only` | examples the baseline scored and the variant did not |
| `n_variant_only` | examples the variant scored and the baseline did not |
| `eligibility_agreement` | `n_examples / (n_examples + n_baseline_only + n_variant_only)` |

The last three exist because of the conditioning confound described under
*Why a layer-2 number is never shown without its denominator*. A contrast
computed on a shrunken paired set must announce that it was shrunk.

- [ ] **Step 1: Write the failing test**

```python
def test_spread_is_computed_within_a_property_never_across():
    frame = _frame([
        ("pinned", 0, "doc-a", "p1", 1.0, 2),
        ("pinned", 1, "doc-a", "p1", 0.0, 2),
        ("pinned", 0, "doc-a", "p2", 0.5, 2),
        ("pinned", 1, "doc-a", "p2", 0.5, 2),
    ])
    spread = replicate_spread(frame).set_index("property")

    assert spread.loc["p1", "mean"] == 0.5
    assert spread.loc["p1", "sd"] == pytest.approx(0.7071, rel=1e-3)
    assert spread.loc["p2", "sd"] == 0.0
    assert len(spread) == 2, "one row per property; never a pooled row"


def test_a_replicate_with_nothing_eligible_does_not_count_as_zero():
    """The defect from Task 1, now on the replicate axis.

    rep-01 scored nothing for this property. Treating that as 0.0 would
    halve the mean and manufacture a spread out of nothing.
    """
    frame = _frame([
        ("pinned", 0, "doc-a", "p1", 1.0, 3),
        ("pinned", 1, "doc-a", "p1", None, 0),
    ])
    spread = replicate_spread(frame).iloc[0]

    assert spread["mean"] == 1.0
    assert spread["n_replicates"] == 1
    assert pd.isna(spread["sd"]), "one replicate has no spread"


def test_sd_is_none_with_a_single_replicate():
    frame = _frame([("pinned", 0, "doc-a", "p1", 1.0, 1)])
    assert pd.isna(replicate_spread(frame).iloc[0]["sd"])


def test_arm_contrast_pairs_by_example_within_a_property():
    """Pairing cancels whatever is common to both arms on that example."""
    frame = _frame([
        ("pinned", 0, "doc-a", "p1", 1.0, 1),
        ("pinned", 0, "doc-b", "p1", 0.0, 1),
        ("v2", 0, "doc-a", "p1", 0.5, 1),
        ("v2", 0, "doc-b", "p1", 0.0, 1),
    ])
    contrast = arm_contrast(frame, baseline="pinned", variant="v2").iloc[0]

    assert contrast["property"] == "p1"
    assert contrast["difference"] == pytest.approx(-0.25)
    assert contrast["n_examples"] == 2


def test_arm_contrast_drops_an_example_only_one_arm_scored():
    """An unpaired example cannot contribute to a paired difference."""
    frame = _frame([
        ("pinned", 0, "doc-a", "p1", 1.0, 1),
        ("pinned", 0, "doc-b", "p1", 1.0, 1),
        ("v2", 0, "doc-a", "p1", 0.0, 1),
    ])
    contrast = arm_contrast(frame, baseline="pinned", variant="v2").iloc[0]
    assert contrast["n_examples"] == 1
    assert contrast["difference"] == pytest.approx(-1.0)


def test_a_shrunken_pairing_announces_itself():
    """The conditioning confound, made visible.

    Each arm's layer-2 mean is over its own eligible set. An arm that
    judges a property inapplicable more often is scored on a subset it
    selected -- plausibly the easy cases -- so a difference computed on a
    shrunken paired set must say how shrunken it is. In exp-01 a minimal
    skill returning outputs: [] can earn a *better* layer-2 mean by
    answering less.
    """
    frame = _frame([
        ("pinned", 0, "doc-a", "p1", 1.0, 1),
        ("pinned", 0, "doc-b", "p1", 1.0, 1),
        ("pinned", 0, "doc-c", "p1", 1.0, 1),
        ("v2", 0, "doc-a", "p1", 1.0, 1),
        ("v2", 0, "doc-b", "p1", None, 0),
        ("v2", 0, "doc-c", "p1", None, 0),
    ])
    contrast = arm_contrast(frame, baseline="pinned", variant="v2").iloc[0]

    assert contrast["difference"] == 0.0, (
        "on the one example both arms scored, they agree -- which is "
        "exactly the misleading reading this row must qualify"
    )
    assert contrast["n_examples"] == 1
    assert contrast["n_baseline_only"] == 2
    assert contrast["n_variant_only"] == 0
    assert contrast["eligibility_agreement"] == pytest.approx(1 / 3)


def test_spread_reports_the_denominator_it_used():
    """A layer-2 mean without its eligible count is not reportable."""
    frame = _frame([
        ("pinned", 0, "doc-a", "p1", 1.0, 4),
        ("pinned", 1, "doc-a", "p1", 1.0, 2),
        ("pinned", 2, "doc-a", "p1", None, 0),
    ])
    row = replicate_spread(frame).iloc[0]
    assert row["n_replicates"] == 2
    assert row["eligible_total"] == 6
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_reporting_statistics.py -k "spread or contrast" -v`
Expected: FAIL — neither function exists.

- [ ] **Step 3: Implement `replicate_spread`**

Group by `(check, arm, property)`. Within a group: first collapse examples
per replicate (mean over examples of the per-example mean, skipping NA),
then take mean and `ddof=1` SD over the replicate values. `n_replicates`
counts replicates with `eligible > 0`. `sd` is NA when `n_replicates < 2`.

Docstring must state which axis the SD is over:

```python
    """Spread over **replicates**, for one arm and one property.

    The SD answers "how much would this number move if we ran it again",
    not "how much do examples differ" -- examples are collapsed first. A
    replicate that scored nothing eligible for this property is excluded
    rather than counted as zero.
    """
```

- [ ] **Step 4: Implement `arm_contrast`**

Group by `property`. Within a group, average over replicates per
`(arm, example)` skipping NA, inner-join the two arms on `example`, take
`variant - baseline` per example, then report `difference` as the mean of
those and `se` as `sd(differences, ddof=1) / sqrt(n)`.

Unpaired examples are dropped from the difference but **counted**:
`n_baseline_only` and `n_variant_only` are the examples one arm scored and
the other did not, and `eligibility_agreement` is the paired fraction.
Dropping silently is the dangerous version of this — an arm that judges a
property inapplicable more often gets scored on a subset it selected.

```python
    """Paired difference between two arms, for one property.

    Pairing is by example: the arms differ in one thing, so the comparison
    is within an example, and whatever makes an example hard cancels.
    Replicates are averaged per (arm, example) first -- they are resamples
    of the same measurement, so they reduce its noise rather than adding
    rows to the pairing.

    Returns one row per property. It never pools properties, and it does
    not test significance: what counts as a real difference is the
    experiment's claim, not this function's.

    ``difference`` is conditional on both arms having judged the property
    applicable on the same example, so it is computed on the paired set
    alone. ``eligibility_agreement`` says how much of the benchmark that
    was. Read it first: an arm that answers less is scored on fewer, easier
    cases, and a difference of zero over one of forty examples is not the
    same finding as a difference of zero over forty.
    """
```

- [ ] **Step 5: Run the suite**

Run: `pytest -q`
Expected: 0 failed.

- [ ] **Step 6: Commit**

```bash
git add soda_mmqc/reporting/aggregate.py tests/test_reporting_statistics.py
git commit -m "Replicate spread and paired arm contrast, per property

Both group by property and neither ever pools across it. A replicate that
scored nothing eligible is excluded rather than counted as zero -- the
Task 1 defect on the replicate axis. arm_contrast pairs by example and
stops at a difference with its SE; significance is the experiment's claim."
```

---

## Task 6: Non-response is a first-class count

**Files:**
- Modify: `soda_mmqc/reporting/aggregate.py`
- Modify: `tests/test_reporting_statistics.py`

**Interfaces:**
- Consumes: `FlatRuns`, `analysis["by_list"][<list>]["row_counts"]`.
- Produces:
  `non_response_counts(runs: FlatRuns) -> pd.DataFrame` with columns
  `check`, `arm`, `replicate`, `example`, `list_key`, `empty` (bool),
  `correct_row`, `missing_row`, `spurious_row`.

A session answering `outputs: []` scores as a fully missing row set, not as
an exclusion. Both notebooks count these by hand before reading any mean,
because a difference in non-response *is* part of the result.

- [ ] **Step 1: Write the failing test**

```python
def test_an_empty_answer_is_counted_not_excluded():
    """A skill so thin the model returns nothing is a result, not a gap.

    Dropping these would make the failing arm look better.
    """
    runs = FlatRuns([
        _run(arm="v2", replicate=0, records=[
            _record_with_rows("doc-a", correct=0, missing=4, spurious=0),
            _record_with_rows("doc-b", correct=3, missing=1, spurious=0),
        ]),
    ])
    counts = non_response_counts(runs)

    assert counts["empty"].sum() == 1
    assert counts.loc[counts["example"] == "doc-a", "empty"].item() is True


def test_non_response_is_reported_per_arm_and_replicate():
    runs = FlatRuns([
        _run(arm="pinned", replicate=0,
             records=[_record_with_rows("doc-a", 4, 0, 0)]),
        _run(arm="v2", replicate=0,
             records=[_record_with_rows("doc-a", 0, 4, 0)]),
    ])
    counts = non_response_counts(runs)
    by_arm = counts.groupby("arm")["empty"].sum()
    assert by_arm["pinned"] == 0
    assert by_arm["v2"] == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_reporting_statistics.py -k non_response -v`
Expected: FAIL — `non_response_counts` does not exist.

- [ ] **Step 3: Implement**

`empty` is `correct_row == 0 and missing_row > 0` — a row set where nothing
matched and something was expected. Docstring:

```python
    """Per example, whether the session returned an empty answer.

    An empty ``outputs`` scores as a fully missing row set rather than
    being excluded: a skill so thin that the model returns nothing is a
    worse result, not an absent one, and dropping those examples would
    flatter the arm that produced them. Count these before reading any
    mean -- a difference in non-response is part of the result.
    """
```

- [ ] **Step 4: Run the suite and commit**

Run: `pytest -q` — expected 0 failed.

```bash
git add soda_mmqc/reporting/aggregate.py tests/test_reporting_statistics.py
git commit -m "Non-response is a count, not a notebook one-liner

An empty answer scores as a fully missing row set. Both notebooks counted
these by hand before reading any mean, because a difference in
non-response is part of the result."
```

---

## Task 7: Plots compare arms and show the spread

**Files:**
- Modify: `soda_mmqc/reporting/plots.py` — every `compare="prompt"` site
- Modify: `soda_mmqc/reporting/compare.py`, `export_report.py`,
  `streamlit_app.py`, `styles.py`
- Modify: `tests/test_reporting_plots.py`, `test_reporting_compare.py`,
  `test_export_fig_checklist_report.py`, `test_reporting_streamlit.py`

**Interfaces:**
- Consumes: `replicate_spread`, `RunSummaries.arms`.
- Produces: `compare: Literal["arm", "model"]` throughout;
  `plot_mean_score_bars` and the comparison plots accept
  `spread: pd.DataFrame | None = None` and draw error bars from it.
- `export_report.PromptScoreRow` becomes `ArmScoreRow`; `macro_mean` is
  **deleted** — see below.

**`macro_mean` must go.** It averages `mean_score` across properties, which
is precisely the forbidden operation. `scores_table` and `winner_lines`
currently rank arms by it. Replace with a per-property table: one row per
property, one column per arm, and no summary column. If a single headline
number is wanted, that is a judgement for the experiment note, not a
library default.

- [ ] **Step 1: Write the failing test**

```python
def test_no_plot_helper_averages_across_properties():
    """The constraint, asserted against the module.

    macro_mean averaged mean_score over properties and scores_table ranked
    arms by it. panel_label and micrograph measure different things; a
    number mixing them hides an arm that improves one and degrades the
    other.
    """
    from soda_mmqc.reporting import export_report
    assert not hasattr(export_report, "macro_mean")


def test_a_bar_with_no_eligible_instance_is_a_gap_not_a_zero():
    summaries = _summaries_with_ineligible_property()
    fig = plot_mean_score_bars(summaries[_REF])
    values = list(fig.data[0].y)
    assert values[_INELIGIBLE_INDEX] is None, (
        "a gap says 'nothing to score here'; a zero bar says 'scored zero'"
    )


def test_comparison_plots_take_arms():
    summaries = _two_arm_summaries()
    fig = plot_comparison_layer1(summaries, compare="arm", model=MODEL)
    assert fig is not None
    with pytest.raises(ValueError, match="arm"):
        plot_comparison_layer1(summaries, compare="prompt", model=MODEL)


def test_error_bars_come_from_replicate_spread():
    summaries = _two_arm_summaries(replicates=3)
    spread = replicate_spread(scores_frame(_runs_for(summaries)))
    fig = plot_mean_score_bars(summaries[_REF], spread=spread)
    assert fig.data[0].error_y.array is not None, (
        "two arms plotted without spread, once replicates exist, is "
        "actively misleading"
    )
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_reporting_plots.py tests/test_export_fig_checklist_report.py -v`
Expected: FAIL on all four.

- [ ] **Step 3: Rename the comparison axis**

Replace `Literal["prompt", "model"]` with `Literal["arm", "model"]` in
`_comparison_summaries`, `_series_label`, `plot_comparison_*`,
`build_comparison_report`. Raise `ValueError` naming `arm` when passed
`"prompt"`, rather than failing obscurely — people will have old notebooks.

- [ ] **Step 4: Render `None` as a gap**

Plotly renders `None` in a `y` array as a gap. Ensure the frame builders
(`mean_scores_frame`, `applicable_instance_scores_frame`) propagate `None`
rather than filling. Add a legend note or hover text distinguishing
"no eligible instance" from zero.

- [ ] **Step 5: Add error bars**

Where `spread` is supplied, attach `error_y=dict(type="data", array=sd,
visible=True)` aligned to the property order already used on the x-axis.
Where `sd` is NA (one replicate), pass `None` for that point.

- [ ] **Step 6: Replace `macro_mean`**

Delete it. Rewrite `scores_table` to return one row per property with one
column per arm, and `winner_lines` to report per property — or delete
`winner_lines` if a per-property winner list reads worse than the table.
Record which you chose and why in the commit message.

- [ ] **Step 7: Run the suite**

Run: `pytest -q`
Expected: 0 failed.

- [ ] **Step 8: Commit**

```bash
git add soda_mmqc/reporting/ tests/
git commit -m "Plots compare arms, show replicate spread, and gap on NA

compare='prompt' became compare='arm', with a ValueError naming arm for
old callers. Two arms plotted without spread, once replicates exist, is
actively misleading, so the comparison plots take one.

macro_mean is deleted: it averaged mean_score across properties, which is
the one aggregate this codebase must not produce. scores_table is now one
row per property."
```

---

## Task 8: The notebooks use the library

**Files:**
- Modify: `notebooks/experiments/exp-01-skill-verbosity.ipynb`
- Modify: `notebooks/experiments/exploration-replicate-variability.ipynb`
- Modify: `notebooks/comparative-reporting.ipynb`
- Create: `tests/test_no_cross_property_aggregate.py`

**Interfaces:**
- Consumes: everything above.
- Produces: nothing importable.

- [ ] **Step 1: Write the guard test**

```python
def test_no_module_averages_across_leaf_properties():
    """The standing constraint, checkable.

    A helper that pools panel_label with micrograph is not a convenience,
    it is a wrong number. This catches the obvious reintroductions; it
    cannot catch a clever one, which is what review is for.
    """
    import pathlib
    banned = ("macro_mean", "across_properties", "pooled_score")
    roots = [
        pathlib.Path(__file__).resolve().parents[1] / "soda_mmqc" / p
        for p in ("reporting", "core")
    ]
    offenders = [
        f"{path.name}:{name}"
        for root in roots for path in root.glob("*.py")
        for name in banned
        if name in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_the_experiment_notebooks_do_not_reimplement_the_walker():
    """Both notebooks hand-rolled leaves() and a weighted mean.

    The walker is load_run_root and the statistics are in aggregate.py, so
    a notebook redefining them has drifted from the tested version.
    """
    import json, pathlib
    nb_dir = pathlib.Path(__file__).resolve().parents[1] / "notebooks"
    for nb_path in nb_dir.rglob("*.ipynb"):
        source = "\n".join(
            "".join(cell["source"])
            for cell in json.loads(nb_path.read_text())["cells"]
            if cell["cell_type"] == "code"
        )
        assert "def leaves(" not in source, nb_path
        assert "def weighted(" not in source, nb_path
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_no_cross_property_aggregate.py -v`
Expected: FAIL — both notebooks define `leaves` and `weighted`.

- [ ] **Step 3: Rewrite the exp-01 notebook**

Replace the walker cell and the scoring loop with:

```python
from pathlib import Path

from soda_mmqc.reporting import (
    arm_contrast, load_run_root, non_response_counts,
    replicate_spread, scores_frame,
)

RUNS = Path("../../experiments/runs/exp-01-skill-verbosity").resolve()
CHECKLIST = "fig-checklist-exp01"

frames = []
for check_dir in sorted(p for p in RUNS.iterdir() if p.is_dir()):
    runs = load_run_root(
        check_dir, checklist=CHECKLIST, check=check_dir.name,
    )
    frames.append(scores_frame(runs))
scores = pd.concat(frames, ignore_index=True)
```

Replace the `weighted()` cell and the per-check comparison with
`arm_contrast(scores, baseline="pinned", variant=...)` **per property**, and
add a markdown cell saying plainly what changed and why:

> The earlier version of this notebook averaged `mean_score` across
> properties. That number mixes `panel_label` with `micrograph`, so an arm
> that improves one and degrades the other looks unchanged. The comparison
> below is per property; there is no headline number, deliberately.

**Order the notebook so layer 2 cannot be read alone.** Layer 2 is
conditional on layer 1, so a minimal skill that answers less is scored on
fewer, easier cases and can show the *better* mean. The reading order is:

1. `non_response_counts` — how often each arm answered nothing.
2. Layer-1 applicability per property — how often each arm judged the
   property applicable, and how that varied across replicates. This is
   where the applicability difference between arms is a *result*, not a
   nuisance.
3. Only then `arm_contrast`, with `eligibility_agreement` displayed in the
   same table as `difference` — not in a later cell.

Add a markdown cell before step 3 stating the confound in one sentence, so
a reader who skips to the contrast table still meets it.

Note the arm naming: the harness writes `pinned` and `<check>@v2`, and the
notebook's `arm_name()` mapped those to `detailed`/`minimal`. Keep that
mapping as a display relabel applied to the frame, not as something the
library knows.

- [ ] **Step 4: Rewrite the exploration notebook**

Its question — how many replicates does a check need — is answered from
`replicate_spread` directly, per property. Its variance decomposition
(`v_bar`, `SD(mean) = sqrt(v_bar/N)`) stays: that arithmetic is the
notebook's argument, not library work.

Add a markdown cell recording that its original cross-property average was
an exploration shortcut, tolerated for sizing a replicate count and not
carried into benchmarking — so a reader comparing the two versions is not
left guessing which is right.

- [ ] **Step 5: Update `comparative-reporting.ipynb`**

Prompt contrasts become arm contrasts. Its header table lists
`Prompts: prompt.1, prompt.2, prompt.3` — replace with the arms actually
present. If no production run exists to point it at, point it at an
`experiments/runs/` root and say so in the first markdown cell.

- [ ] **Step 6: Execute all three, stripped**

```bash
jupyter nbconvert --execute --inplace --to notebook \
  notebooks/experiments/exp-01-skill-verbosity.ipynb
```

Then strip outputs before committing — the repo already does this
(`9e28eb20 Strip the executed outputs from the variability notebook`).
**Executing exp-01's notebook scores every committed leaf and is slow but
spends nothing.** If the run is incomplete, execute against the checks that
have output and note which.

- [ ] **Step 7: Run the suite**

Run: `pytest -q`
Expected: 0 failed.

- [ ] **Step 8: Commit**

```bash
git add notebooks/ tests/test_no_cross_property_aggregate.py
git commit -m "The notebooks use the library

Both experiment notebooks hand-rolled a leaves() walker, a scoring loop and
an instance-weighted mean across properties. The walker is load_run_root,
the statistics are tested in aggregate.py, and the cross-property mean is
gone: it mixes panel_label with micrograph, so an arm that improves one and
degrades the other looks unchanged.

exp-01 now reports per property with no headline number, deliberately."
```

---

## Verification

```bash
pytest -q
```
Expected: 0 failed.

```bash
grep -rn "prompt" soda_mmqc/reporting/
```
Expected: nothing outside comments explaining what was removed.

```bash
grep -rn "macro_mean\|def weighted\|def leaves" soda_mmqc/ notebooks/
```
Expected: nothing.

```bash
grep -rn "mean_score or 0\|mean_score, 0\|fillna(0" soda_mmqc/reporting/
```
Expected: nothing. Each would reintroduce the false zero.

End to end, against committed predictions:

```bash
python -c "
from pathlib import Path
import pandas as pd
from soda_mmqc.reporting import load_run_root, scores_frame, replicate_spread
root = Path('experiments/runs/exploration-replicate-variability')
runs = load_run_root(root, checklist='fig-checklist-exp01',
                     check='replication-reporting')
frame = scores_frame(runs)
print(frame.groupby('property')['mean_score'].describe())
print(replicate_spread(frame))
"
```

Expected: one row per property, each with its own SD over replicates, and
no row pooling properties. This requires the leaves to have been scored —
score them with `mmqc score` first if `load_run_root` returns nothing.

## Not in scope

- **Significance testing, multiplicity correction, or a verdict.** The
  library stops at a difference and its standard error.
- **Any cross-property summary**, including as an opt-in.
- **`reporting/context.py`, `navigate.py`, `display.py`** beyond renamed
  fields.
- **Re-running any experiment.** Every task reads committed predictions.
