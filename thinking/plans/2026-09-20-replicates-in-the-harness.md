---
title: Replicates belong to the harness, and every axis is a directory
date: 2026-09-20
status: proposed, awaiting review
---

# Replicates belong to the harness, and every axis is a directory

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let one `run` command produce N replicates of the same
configuration, and give every run the same output shape, so that measuring a
non-deterministic system needs no second runner and no conditional path
logic anywhere downstream.

**Architecture:** A replicate is the third axis of a tuple whose other two
axes the harness already loops over — examples, and skill sets from
`--unpin`. It becomes `--replicates N`. Every run, however scoped, writes
`<root>/<arm>/rep-NN/<example>/prediction.json`, and every prediction's
sidecar records which arm and which replicate produced it.

**Tech Stack:** Python, `pytest`, the existing `soda_mmqc/agentic/` harness.

**Spec:** this document.

---

## Why

### Now

`run_check_live` loops examples, and `--unpin` expands to one skill set per
arm. Both axes are the harness's: it owns the loop, the directory level and
the sidecar recording which skill set produced a prediction.

Replicates are not. Running the same configuration five times means five
invocations and a directory convention invented by the caller.

`tl_dev_agentic` solved that with `experiments/expNN.py` scripts that owned
the arm and replicate levels while the harness owned the example level. Its
layout principle was right — *"every axis a directory, because an arm is not
a replicate"* — but splitting ownership of one tree across two components is
what made the second runner necessary, and then load-bearing.

**The baseline arm is also special-cased.** It writes to `<root>/<example>/`
while every other arm writes to `<root>/<arm>/<example>/` — not "flatten when
there is one arm", but "the baseline is flat", even in a two-arm comparison.
So a single run's output has two shapes at once.

That matters because of a coupling: `_load_predictions_from_dir` derives each
example's key from `prediction_file.parent.relative_to(root)`. **The
directory layout is the scoring key.** Point `score --predictions` at a
two-arm run root today and `rglob` finds both arms, but the variant's keys
come out as `<arm>/<example>`, matching no benchmark example. The result is a
plausible-looking score for the baseline alone, with a warning that reads as
though some stray files were ignored.

### Proposed

**Every axis is a directory, always.**

```
<root>/<arm>/rep-NN/<example>/prediction.json
```

- `<arm>` is the skill set's label — `pinned` when nothing has moved off the
  manifest pins, otherwise what moved (`micrograph-scale-bar@v2`). The
  baseline stops being special.
- `rep-NN` is present even for a single replicate, as `rep-00`.
- The sidecar beside every prediction records the arm label and the replicate
  index, alongside the skill-set digest already there.

`--replicates N` defaults to 1, which produces exactly one `rep-00`.

### Why no exceptions, including for the degenerate cases

Three reasons, in increasing order of weight.

**Adding an axis later must not move what exists.** Run once, then decide the
result needs five replicates: with a flattened single run, the first one is
in the wrong place and has to be relocated before the second can be written.

**One shape means one reader.** Anything walking the tree — a notebook
aggregating arms × replicates, a script collecting runs — handles one case.
Every conditional avoided here is a conditional avoided in every consumer.

**A wrong `--predictions` path should fail, not half-succeed.** Under the
uniform layout, pointing `score` at a run root matches *nothing*, so the
existing hard error fires: *"None of the predictions match an example in the
benchmark."* Today it silently scores one arm. Removing the special case
removes the failure mode rather than annotating it.

### Why the sidecar carries arm and replicate

`skill_set.json` exists beside every prediction because **a directory name is
not evidence** — the reason recorded when it was added. The same argument
applies to which arm and which sample a prediction came from: a notebook
should read what produced it, not infer it from a path someone could move.

### A replicate is a resample, not a reproduction

There is no seed to fix. Two replicates of one configuration differ because
the model is non-deterministic, which is exactly what makes them worth
running — but "replicate" must never be read as "should be identical". The
CLI help and the experiments README say so.

### What stays out

- **Scoring stays "one predictions directory → one analysis".** That is what
  keeps `FlatEvaluator` general. The caller points it at one `rep-NN`.
- **Aggregation across replicates belongs to reporting.** `RunSummaries`
  already exposes `models` and `prompts` as comparison dimensions; a
  replicate is a third of the same kind. Not scheduled here.
- **How many replicates, and how they are compared, belongs to an
  experiment** — its note, its builder, its notebook.

### Migration cost

**Nothing committed depends on the current layout.** No `prediction.json` is
tracked in git, `experiments/runs/` holds only its README, `data/predictions/`
and `data/evaluation/` are gitignored, and exp-01 has not run. The change is
a one-time break of habit and of two tests, not of any result.

---

## Global Constraints

- **One shape, no exceptions.** Every path a run writes is
  `<root>/<arm>/rep-NN/<example>/`, including `--mock`, including a run with
  one arm and one replicate. A conditional on "is this axis real" is the
  thing this plan removes; do not reintroduce one.
- **The harness produces; it does not aggregate.** No task computes a mean, a
  variance or a comparison across replicates.
- **No new agent capability**, and no change to what a session sees: a
  replicate is the same runtime assembled again.
- **Run after every task:** `pytest tests/test_agentic_cli.py tests/test_agentic_integration.py -q`
  (baseline: 326 before this plan).

---

## File Structure

| File | Responsibility after this plan |
|---|---|
| `soda_mmqc/agentic/runner.py` | `run_check_live` gains `replicates` and writes `<arm>/rep-NN/`; `run_check_mock` writes the same shape; `_write_prediction` records arm and replicate. |
| `soda_mmqc/cli.py` | `--replicates` flag; the live-run branch announces the session count. |
| `soda_mmqc/cli.py` (`score_check`) | When nothing matches, the error says the directory looks like a run root and names the leaves it found. |
| `thinking/experiments/README.md` | What a replicate is, and the run layout, beside the standing rules. |
| `tests/test_agentic_cli.py` | Two layout tests replaced; new tests for the uniform shape, the sidecar, and the run-root error. |

---

## Task 1: One shape for every run

**Files:**
- Modify: `soda_mmqc/agentic/runner.py` — `run_check_live`, `run_check_mock`,
  `_write_prediction`
- Modify: `tests/test_agentic_cli.py` — replace the two tests that pin the
  old layout (`test_the_pinned_run_keeps_the_flat_layout` at ~4316, and the
  flat assertion inside `test_a_single_variant_gets_its_own_directory` at
  ~4303)

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `run_check_live(..., replicates: int = 1)`
  - `_write_prediction(..., arm: str, replicate: int)` — both required, both
    written into the sidecar.
  - `RUN_LAYOUT = "<root>/<arm>/rep-NN/<example>/"` as a module docstring
    statement, not a constant to interpolate.

**The two tests being replaced** asserted the old shape deliberately, so they
are not deleted silently: each is replaced by one asserting the new shape,
and the reason is in the commit message.

- [ ] **Step 1: Write the failing test**

```python
@requires_subpanel_figure
class TestEveryAxisIsADirectory:
    """One shape for every run: <root>/<arm>/rep-NN/<example>/.

    The baseline arm used to write flat while variants wrote into their own
    directory, so one run's output had two shapes and pointing `score` at
    the root scored the baseline alone -- plausibly, and silently.
    """

    def test_a_plain_run_still_has_both_levels(self, tmp_path: Path, stub_session):
        out = tmp_path / "preds"
        cli.run_check_live(
            "fig-checklist", PILOT_LEAF, output=out, examples=[SUBPANEL_FIGURE],
        )
        assert (
            out / "pinned" / "rep-00" / SUBPANEL_FIGURE / cli.PREDICTION_FILENAME
        ).is_file()
        assert not (out / SUBPANEL_FIGURE).exists(), (
            "the baseline arm must not write flat: that is the special case "
            "this layout removes"
        )

    def test_replicates_sit_under_the_arm(self, tmp_path: Path, stub_session):
        """An arm is not a replicate: arm outermost, samples within it."""
        out = tmp_path / "preds"
        cli.run_check_live(
            "fig-checklist", PILOT_LEAF, output=out,
            examples=[SUBPANEL_FIGURE], replicates=3,
        )
        for i in range(3):
            assert (
                out / "pinned" / f"rep-{i:02d}" / SUBPANEL_FIGURE
                / cli.PREDICTION_FILENAME
            ).is_file()

    def test_a_variant_gets_its_own_arm_directory(self, tmp_path: Path, stub_session):
        out = tmp_path / "preds"
        cli.run_check_live(
            "fig-checklist", PILOT_LEAF, output=out,
            examples=[SUBPANEL_FIGURE], unpin={PILOT_LEAF: ["v1"]},
        )
        assert (
            out / "pinned" / "rep-00" / SUBPANEL_FIGURE / cli.PREDICTION_FILENAME
        ).is_file()

    def test_the_sidecar_records_arm_and_replicate(
        self, tmp_path: Path, stub_session
    ):
        """A directory name is not evidence -- the reason skill_set.json exists.

        A notebook reads this rather than parsing paths, so moving a tree
        cannot change what a prediction claims about itself.
        """
        out = tmp_path / "preds"
        cli.run_check_live(
            "fig-checklist", PILOT_LEAF, output=out,
            examples=[SUBPANEL_FIGURE], replicates=2,
        )
        for i in range(2):
            sidecar = json.loads(
                (
                    out / "pinned" / f"rep-{i:02d}" / SUBPANEL_FIGURE
                    / cli.INTERMEDIATES_DIRNAME / cli.SKILL_SET_FILENAME
                ).read_text(encoding="utf-8")
            )
            assert sidecar["arm"] == "pinned"
            assert sidecar["replicate"] == i
            assert sidecar["digest"]

    def test_mock_writes_the_same_shape(self, tmp_path: Path):
        """No exceptions: a mock run is scored by the same command."""
        out = tmp_path / "preds"
        cli.run_check_mock(
            "fig-checklist", PILOT_LEAF, output=out, examples=[SUBPANEL_FIGURE],
        )
        assert (
            out / "pinned" / "rep-00" / SUBPANEL_FIGURE / cli.PREDICTION_FILENAME
        ).is_file()

    def test_zero_replicates_is_refused(self, tmp_path: Path):
        with pytest.raises(ValueError, match="at least one"):
            cli.run_check_live(
                "fig-checklist", PILOT_LEAF, output=tmp_path / "p",
                examples=[SUBPANEL_FIGURE], replicates=0,
            )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_agentic_cli.py -q -k TestEveryAxisIsADirectory`
Expected: FAIL — `run_check_live() got an unexpected keyword argument 'replicates'`

- [ ] **Step 3: Record arm and replicate in the sidecar**

In `soda_mmqc/agentic/runner.py`:

```python
def _write_prediction(
    predictions_dir: Path,
    example: str,
    prediction: Dict[str, Any],
    trace: List[Dict[str, Any]],
    skill_set: Optional[SkillSet] = None,
    arm: str = "pinned",
    replicate: int = 0,
) -> Path:
```

and where the skill-set sidecar is built:

```python
    if skill_set is not None:
        (intermediates / SKILL_SET_FILENAME).write_text(
            json.dumps(
                {
                    "digest": skill_set.digest,
                    # Which configuration and which sample, recorded rather
                    # than inferred: the path says the same thing, but a path
                    # can be moved and a sidecar travels with the prediction.
                    "arm": arm,
                    "replicate": replicate,
                    "skills": [
                        dataclasses.asdict(e)
                        for e in sorted(
                            skill_set.entries, key=lambda e: e.name
                        )
                    ],
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
```

- [ ] **Step 4: Write the uniform layout in `run_check_live`**

Add the parameter and validate it beside the other argument checks:

```python
    replicates: int = 1,
```

```python
    if replicates < 1:
        raise ValueError(f"replicates must be at least one, got {replicates}")
```

Replace the arm-directory rule and wrap the example loop:

```python
    for skill_set in skill_sets:
        label = skill_set.label(pins)
        versions = skill_set.pins
        for replicate in range(replicates):
            # Every axis is a directory, with no exception for the degenerate
            # case. The baseline arm used to write flat, which gave one run
            # two shapes and made `score --predictions <root>` score that arm
            # alone; and a run that later wants replicates must not have to
            # relocate the one it already has.
            predictions_dir = root_dir / label / f"rep-{replicate:02d}"
            for relative_source_path in wanted:
                ...
```

Pass `arm=label, replicate=replicate` to `_write_prediction`, and record both
on the report entry:

```python
            entry: Dict[str, Any] = {
                "example": relative_source_path,
                "skill_set": skill_set.digest,
                "label": label,
                "replicate": replicate,
            }
```

- [ ] **Step 5: Give `run_check_mock` the same shape**

In `run_check_mock`, replace the bare `predictions_dir` with the same layout.
Mock assembles no skills, so the arm is the baseline and there is one sample:

```python
    predictions_dir = (
        Path(output or default_predictions_dir(checklist, check, model))
        / "pinned" / "rep-00"
    )
```

Mock has no `SkillSet`, so its `_write_prediction` call passes no `skill_set`
and writes no sidecar — unchanged, and the arm/replicate defaults apply.

- [ ] **Step 6: Replace the two tests that pinned the old shape**

Delete `test_the_pinned_run_keeps_the_flat_layout` — its assertion is now the
inverse of `test_a_plain_run_still_has_both_levels`. In
`test_a_single_variant_gets_its_own_directory`, replace the assertion that
the baseline path does *not* exist with one that it exists under
`pinned/rep-00/`, keeping the test's actual point: a variant must never
overwrite the baseline.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `pytest tests/test_agentic_cli.py tests/test_agentic_integration.py -q`
Expected: PASS. Any failure outside the two replaced tests means something
else depended on the flat layout; fix that rather than reinstating it.

- [ ] **Step 8: Commit**

```bash
git add soda_mmqc/agentic/runner.py tests/test_agentic_cli.py
git commit -m "Every axis is a directory: <root>/<arm>/rep-NN/<example>/"
```

---

## Task 2: The flag, and the cost said out loud

**Files:**
- Modify: `soda_mmqc/cli.py` — `_build_parser`, the live branch of `main`
- Test: `tests/test_agentic_cli.py`

**Interfaces:**
- Consumes: `run_check_live(..., replicates=...)` from Task 1.
- Produces: `--replicates N` on `run`; one log line naming the product.

**Why the count is printed:** the existing guard refuses an unscoped live run
because "a live run costs money". Replicates multiply that quietly —
`--replicates 5` on a two-arm, 38-example check is 380 sessions from one
command. The product should be visible before it is spent.

- [ ] **Step 1: Write the failing test**

```python
class TestReplicatesOnTheCommandLine:
    def _capture(self, monkeypatch):
        seen = {}

        def fake_run_check_live(checklist, check, **kwargs):
            seen.update(kwargs)
            return Path("/tmp/x"), []

        monkeypatch.setattr(runner, "run_check_live", fake_run_check_live)
        return seen

    def test_the_flag_reaches_the_runner(self, monkeypatch: pytest.MonkeyPatch):
        seen = self._capture(monkeypatch)
        cli.main([
            "run", "fig-checklist", "--check", PILOT_LEAF,
            "--example", SUBPANEL_FIGURE, "--replicates", "4",
        ])
        assert seen["replicates"] == 4

    def test_the_default_is_one(self, monkeypatch: pytest.MonkeyPatch):
        seen = self._capture(monkeypatch)
        cli.main([
            "run", "fig-checklist", "--check", PILOT_LEAF,
            "--example", SUBPANEL_FIGURE,
        ])
        assert seen["replicates"] == 1

    def test_the_session_count_is_announced(
        self, monkeypatch: pytest.MonkeyPatch, caplog
    ):
        """380 sessions from one command should not be a surprise."""
        self._capture(monkeypatch)
        with caplog.at_level("INFO"):
            cli.main([
                "run", "fig-checklist", "--check", PILOT_LEAF,
                "--example", SUBPANEL_FIGURE, "--replicates", "5",
            ])
        assert "5 replicate(s)" in caplog.text

    def test_zero_replicates_is_refused_at_the_cli(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        self._capture(monkeypatch)
        assert cli.main([
            "run", "fig-checklist", "--check", PILOT_LEAF,
            "--example", SUBPANEL_FIGURE, "--replicates", "0",
        ]) == 2
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_agentic_cli.py -q -k TestReplicatesOnTheCommandLine`
Expected: FAIL — `unrecognized arguments: --replicates`

- [ ] **Step 3: Add the flag**

In `_build_parser`, beside `--limit`:

```python
    run.add_argument(
        "--replicates",
        type=int,
        default=1,
        metavar="N",
        help=(
            "Run each configuration N times (default: %(default)s). There is "
            "no seed to fix, so replicates are resamples of a "
            "non-deterministic system rather than reproductions: they are how "
            "its variance is measured, and they are not expected to agree"
        ),
    )
```

- [ ] **Step 4: Announce the cost, then pass it through**

In the live branch of `main`, after the existing scope guard:

```python
                if args.replicates < 1:
                    logger.error("--replicates must be at least one")
                    return 2
                logger.info(
                    "Live run: %d replicate(s) of %s/%s, one session per "
                    "example per replicate per skill set",
                    args.replicates, args.checklist, args.check,
                )
```

and add `replicates=args.replicates,` to the `run_check_live(...)` call.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `pytest tests/test_agentic_cli.py tests/test_agentic_integration.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add soda_mmqc/cli.py tests/test_agentic_cli.py
git commit -m "Add --replicates, and say the session count before spending it"
```

---

## Task 3: A run root is a recognisable mistake

**Files:**
- Modify: `soda_mmqc/cli.py` — `score_check`
- Test: `tests/test_agentic_cli.py`

**Interfaces:**
- Consumes: nothing new. No signature change.

**What changed, and what is left.** Under the uniform layout, pointing
`score --predictions` at a run root no longer half-succeeds: every key comes
out as `<arm>/rep-NN/<example>`, nothing matches, and the existing
`ValueError` fires. That is already the right outcome — the silent partial
score is gone. What remains is that the message says only *"None of the
predictions match"*, when the cause is almost always one specific, fixable
mistake: the caller pointed at a root instead of a leaf.

This task makes the error name the mistake. It is not a new guard.

- [ ] **Step 1: Write the failing test**

```python
class TestPointingAtARunRoot:
    def test_the_error_names_the_leaves_it_found(self, tmp_path: Path):
        """Scoring a run root is the one mistake worth diagnosing."""
        root = tmp_path / "preds"
        example = REAL_EXAMPLES[0]
        for arm in ("pinned", f"{PILOT_LEAF}@v2"):
            d = root / arm / "rep-00" / example
            d.mkdir(parents=True)
            (d / cli.PREDICTION_FILENAME).write_text(
                json.dumps(_valid_prediction()), encoding="utf-8"
            )

        with pytest.raises(ValueError) as exc:
            cli.score_check(
                "fig-checklist", PILOT_LEAF, root, model="sonnet", save=False,
            )
        message = str(exc.value)
        assert "pinned/rep-00" in message
        assert f"{PILOT_LEAF}@v2/rep-00" in message
        assert "--predictions" in message

    def test_a_genuinely_unrelated_directory_says_so_plainly(self, tmp_path: Path):
        """Not every mismatch is a run root; do not claim it is."""
        root = tmp_path / "preds"
        d = root / "not" / "an" / "example"
        d.mkdir(parents=True)
        (d / cli.PREDICTION_FILENAME).write_text(
            json.dumps(_valid_prediction()), encoding="utf-8"
        )
        with pytest.raises(ValueError, match="match an example"):
            cli.score_check(
                "fig-checklist", PILOT_LEAF, root, model="sonnet", save=False,
            )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_agentic_cli.py -q -k TestPointingAtARunRoot`
Expected: FAIL — the first test; the message names neither the leaves nor
`--predictions`.

- [ ] **Step 3: Diagnose the run root**

In `soda_mmqc/cli.py`, replace the `if not scored_examples:` block:

```python
    if not scored_examples:
        known = set(benchmark_examples)
        # Every key having the form `<something>/<known example>` means this
        # directory is a run root, not a leaf: the run wrote one leaf per arm
        # per replicate, and each is scored separately. Saying so beats
        # reporting that nothing matched.
        leaves = set()
        for key in predictions:
            for example in known:
                if key.endswith("/" + example):
                    leaves.add(key[: -len(example) - 1])
                    break
        leaves = sorted(leaves)
        if leaves:
            raise ValueError(
                f"{predictions_path} looks like a run root, not a predictions "
                f"directory: it holds {len(leaves)} of them "
                f"({', '.join(leaves)}). A run writes one per arm per "
                f"replicate, and each is scored on its own -- point "
                f"--predictions at one of them."
            )
        raise ValueError(
            f"None of the predictions in {predictions_path} match an example "
            f"in the benchmark of {check_name}"
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_agentic_cli.py tests/test_agentic_integration.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add soda_mmqc/cli.py tests/test_agentic_cli.py
git commit -m "Scoring a run root says so, and names the leaves"
```

---

## Task 4: Say what a replicate is, once

**Files:**
- Modify: `thinking/experiments/README.md`

**Why:** the standing rules there are what an experiment author reads.
"Replicate" carries an implication from other fields — that repeated
measurements of the same thing should agree — which is exactly wrong here.

- [ ] **Step 1: Add the rule**

Under **Standing rules**, after the contracts rule:

```markdown
**A replicate is a resample, not a reproduction.** There is no seed to fix:
two replicates of one configuration differ because the model is
non-deterministic, and that variance is the thing they exist to measure. A
replicate that disagrees with its siblings is data, not a defect.

The harness produces them. Every run writes

    <predictions root>/<arm>/rep-NN/<example>/prediction.json

with no exception for a single arm or a single replicate, and each
prediction's sidecar records its arm and index — so a notebook reads what
produced a prediction rather than parsing the path it happens to sit in.
`--replicates N` chooses how many; `--unpin` chooses the arms.

How many replicates an experiment needs, and how they are combined, is the
experiment's to decide and to preregister. Note that a non-response scores as
a fully missing row set rather than being excluded, so an arm that fails more
often is correctly penalised — state that in the note rather than leaving a
reader to infer it from layer S.
```

- [ ] **Step 2: Commit**

```bash
git add thinking/experiments/README.md
git commit -m "Standing rule: a replicate is a resample, and the run layout"
```

---

## Verification

- `pytest tests/ -q` green.
- `run --check X --example E` writes
  `<out>/pinned/rep-00/<E>/prediction.json` and nothing at `<out>/<E>/`.
- `run --check X --example E --replicates 3` writes three `rep-NN/` under
  `pinned/`, each sidecar carrying `arm` and `replicate`.
- `run --check X --example E --mock` writes the same shape.
- `score --predictions <out>` fails with a message naming
  `pinned/rep-00`; `score --predictions <out>/pinned/rep-00` succeeds.

## Not in scope

- **Aggregating across replicates.** Reporting's job; `RunSummaries` already
  models comparison dimensions, and a replicate is another one.
- **Parallelism.** Replicates are independent and could run concurrently.
  That is a throughput change with its own failure modes, and it should not
  ride along with the axis that makes it possible.
- **Migrating old output.** Nothing committed depends on the layout: no
  `prediction.json` is tracked, `experiments/runs/` holds only its README,
  and `data/predictions/` and `data/evaluation/` are gitignored.
