# Skill-design experiments

Work on how skills are **written**, how they are **organized**, and how they
are **chained** — including the evidence behind the results section of the
paper on hierarchically nested skills structured as a DAG.

Not everything here is a confirmatory experiment, and the sequence is not
planned in advance. Most understanding arrives through exploration; a
confirmatory experiment is what you run once exploration has made a question
sharp enough to be wrong about.

## Two kinds of work

|  | Exploration | Experiment |
|---|---|---|
| File | `exploration-<slug>.md` | `exp-NN-<slug>.md` |
| Purpose | understand, tweak, optimize, de-risk | test a stated claim |
| Hypothesis | not required | **required, committed before running** |
| Decision criteria | not required | **required, committed before running** |
| Paper claim | usually none | names the claim it supports |
| Contracts | may vary — say what you varied | held fixed |
| Artifacts | whatever the probe needs | all five |
| Numbered | no | yes, **assigned at preregistration** |

Numbers are assigned when an experiment is preregistered, not planned ahead:
`exp-01` is simply the first one that got there. There is no sequence to
design up front, and no need to know whether a question will become an
experiment before exploring it.

Templates: [`TEMPLATE-exploration.md`](TEMPLATE-exploration.md),
[`TEMPLATE-experiment.md`](TEMPLATE-experiment.md).

**Explorations graduate.** One that produces a sharp question becomes an
experiment; the exploration doc stays and is linked as its motivation. A
methods section is stronger for showing where a hypothesis came from than
for presenting one that appears from nowhere.

An exploration is not a lesser thing. It is the honest label for work whose
result was not predicted, and most work is that.

## Preregistration is a commit order

For an experiment, commit the note stating hypothesis and decision criteria
**before** committing any runs. Git's ordering is the timestamp, and anyone
can check it:

```bash
git log --oneline --reverse -- \
  thinking/experiments/exp-NN-<slug>.md experiments/runs/exp-NN-<slug>/
```

If the hypothesis commit precedes the runs commit, the prediction
demonstrably predates the data. That is real preregistration at the cost of
one commit ordering, and a reviewer can verify it rather than taking it on
trust.

Decision criteria say what each outcome would be, decided before the run so
the threshold cannot drift to meet the data — including what counts as
inconclusive, which is a reportable result and not a failure.

## When an experiment grows

An experiment rarely ends where it was planned: another condition suggests
itself, an analysis opens a follow-up, a result only makes sense against a
control nobody thought of. Whether that is an addendum or a new experiment
cannot be settled in advance — but it can be settled the moment it arises,
and the test is not topical similarity:

> **Did you write a new hypothesis and new decision criteria before looking
> at the new data?**

- **Yes** → a new experiment with its own number, and `extends: exp-NN` in
  its frontmatter. Same theme, separate prediction, separately falsifiable.
- **No** → an addendum to the existing note, under a dated
  `## Addendum YYYY-MM-DD` heading, explicitly marked post-hoc.

The distinction is epistemic rather than organizational. A condition added
after seeing results is exploratory with respect to the original
preregistration even when it shares the question, and presenting it as
confirmatory is wrong regardless of which file it sits in. Marking it
post-hoc costs nothing and is the whole difference between a finding and a
claim.

A post-hoc finding worth keeping has one honest route into the results
section: preregister it as a new experiment and test it again. That is the
ordinary exploratory→confirmatory path, not a penalty.

Addendum runs go under the same `experiments/runs/exp-NN-<slug>/` in a dated
subdirectory, so a note and its data stay together. When it is genuinely
ambiguous, prefer the addendum: splitting a note later is easy, whereas
merging two numbered experiments after the paper cites them is not.

## Artifacts

An experiment owns five, sharing the stem `exp-NN-<slug>`. An exploration
takes only what its probe needs — often just the note.

| Artifact | Path |
|----------|------|
| Note | `thinking/experiments/exp-NN-<slug>.md` |
| Analysis | `notebooks/experiments/exp-NN-<slug>.ipynb` |
| Scripts | `experiments/exp-NN-<slug>/` |
| Runs | `experiments/runs/exp-NN-<slug>/` |
| Checklist | `soda_mmqc/data/checklist/fig-checklist-expNN/` |

Scripts group per experiment because there is more than one: at least a
`run.py`, and a builder when the checklist is derived rather than authored.
The notebook stays under `notebooks/` for the reason recorded there — a
reviewer should be able to read what an experiment claims without opening a
`.ipynb`.

**The run is a script; the notebook is the analysis.** A full experiment is
thousands of sessions and hours long, so a notebook that triggers one is a
notebook nobody can re-execute. The script writes runs; the notebook reads
them and can be rerun by anyone, for nothing.

## The catalog

Add a row when work starts, and keep `status` current. Abandoned entries
stay listed: a method section is more honest when the dead ends are visible.

| id | kind | question | status | headline result | note | notebook |
|----|------|----------|--------|-----------------|------|----------|
| — | exploration | How much does a check's score move between identical runs, and how many replicates does it take to see past that? | done | **3 replicates.** Per-example SD 0.025 on the noisiest check; SE of a paired difference bounded at 0.0034 for n=3 against 0.0026 for n=5 — 1,700 extra sessions for nothing. | [note](exploration-replicate-variability.md) | [nb](../../notebooks/experiments/exploration-replicate-variability.ipynb) |
| exp-01 | experiment | Do detailed skill instructions outperform minimal ones? | planned | — | *unwritten* | [nb](../../notebooks/experiments/exp-01-skill-verbosity.ipynb) |

`kind` is `exploration` or `experiment`; `status` is `planned`, `running`,
`done` or `abandoned`.

## Standing rules

**Contracts are held fixed — for experiments.** A check owns three
evaluation contracts: `schema.json` (the output shape), `benchmark.json`
(which examples run) and `eval-manifest.json` (how leaves are scored). An
experiment copies all three unchanged and varies only the skills — their
prose, their decomposition, the DAG wiring between them.

This is the control, and it is what licenses attributing a score difference
to the skill design rather than to the measurement. Change a threshold or
drop examples and the difference could come from the ruler instead of the
thing measured, with no way to tell afterwards. It is checkable: `diff` the
three files against `fig-checklist` and they must be identical.

An exploration may vary anything, including contracts — it just has to say
what it varied, and it cannot then be cited as evidence for a paper claim.
An experiment that genuinely needs to vary a contract (testing whether a
richer schema helps, say) must say so in its note and explain how arms stay
comparable, so it is a deliberate exception rather than a drift discovered
while writing up.

Gold needs no copying. It resolves as
`<example>/checks/<check_name>/expected_output.json` — keyed by check name,
not by checklist — so every arm reads the same gold as the baseline
([examples.py](../../soda_mmqc/core/examples.py)).

**A replicate is a resample, not a reproduction.** There is no seed to fix:
two replicates of one configuration differ because the model is
non-deterministic, and that variance is the thing they exist to measure. A
replicate that disagrees with its siblings is data, not a defect.

The harness produces them. Every run writes

```
<predictions root>/<arm>/rep-NN/<example>/prediction.json
```

with no exception for a single arm or a single replicate, and each
prediction's sidecar records its arm and index — so a notebook reads what
produced a prediction rather than parsing the path it happens to sit in.
`--replicates N` chooses how many; `--unpin` chooses the arms. Scoring is
pointed at one leaf at a time; pointing it at a run root is refused with a
message naming the leaves.

How many replicates an experiment needs, and how they are combined, is the
experiment's to decide and to preregister. Note that a non-response scores as
a fully missing row set rather than being excluded, so an arm that fails more
often is correctly penalised — state that in the note rather than leaving a
reader to infer it from layer S.

**However the checklist is produced, the note says what varies.** A copied
directory arrives in git as ~88 brand-new files, so the thing that actually
changed is invisible in the diff, and something has to state it.

A builder script is the best statement when the checklist is *derived* —
skills generated, concatenated or transformed from a baseline — because it is
then the only readable account of the transformation and the only way to redo
it. When the skills are *authored*, as in exp-01 where two versions of each
check were written by hand, they are the statement: committing them directly
is clearer than a script that copies files from somewhere else.

What must not be assumed is that an experiment's contracts stay identical to
`fig-checklist`. That baseline will change, and pinning an experiment to it
would make every experiment break when it does. **The control is that the
arms of one experiment are scored identically to each other**, which for a
version comparison is structural: contracts sit above the version
directories, so two versions of one skill cannot be scored differently.

**Runs are committed.** One example's agentic output is ~20 KB of JSON, so a
38-example three-arm experiment is around 2 MB. Cheap enough that every
figure in the paper re-derives from committed data.
