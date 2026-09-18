# Skill-design experiments

Experiments on how to **write** skills, how to **organize** them, and how to
**chain** them — the evidence behind the results section of the paper on
hierarchically nested skills structured as a DAG.

Each experiment has a number `NN` and a slug, and owns five artifacts that
share the stem `exp-NN-<slug>`:

| Artifact | Path | What it is |
|----------|------|------------|
| Note | `thinking/experiments/exp-NN-<slug>.md` | Question, hypothesis, design, findings |
| Analysis | `notebooks/experiments/exp-NN-<slug>.ipynb` | Scoring, statistics, figures |
| Builder | `experiments/build_expNN_checklist.py` | How the checklist was transformed |
| Runs | `experiments/runs/exp-NN-<slug>/` | Raw traces, predictions, scores |
| Checklist | `soda_mmqc/data/checklist/fig-checklist-expNN/` | The artifact that ran |

Start a new experiment by copying [`TEMPLATE.md`](TEMPLATE.md).

## The catalog

Add a row when an experiment is planned, and keep `status` current.
Abandoned experiments stay listed: a method section is more honest when the
dead ends are visible.

| exp | question | status | headline result | note | notebook |
|-----|----------|--------|-----------------|------|----------|
| — | *none yet* | — | — | — | — |

Status is one of `planned`, `running`, `done`, `abandoned`.

## Standing rules

**Contracts are held fixed.** A check owns three evaluation contracts —
`schema.json` (the output shape), `benchmark.json` (which examples run) and
`eval-manifest.json` (how leaves are scored). An experiment copies all three
unchanged and varies only the skills: their prose, their decomposition, and
the DAG wiring between them.

This is the control, and it is what lets a score difference be attributed to
the skill design rather than to the measurement. Change a threshold or drop
examples from the benchmark and a difference could come from the ruler
instead of the thing being measured, with no way to tell which afterwards.
It is checkable: `diff` the three files against `fig-checklist` and they must
be identical.

Gold needs no copying. It resolves as
`<example>/checks/<check_name>/expected_output.json` — keyed by check name,
not by checklist — so every arm reads the same gold as the baseline
([examples.py](../../soda_mmqc/core/examples.py)).

An experiment that genuinely needs to vary a contract (testing whether a
richer schema helps, say) is legitimate, but it must say so in its note and
explain how arms stay comparable. The rule exists so that becomes a
deliberate exception rather than a quiet drift discovered while writing up.

**The checklist copy is built by a script, never by hand.** A copied
directory arrives in git as ~88 brand-new files, so the thing that actually
changed is invisible in the diff. The builder is the only readable statement
of the independent variable, and it is what makes the experiment
re-runnable after the baseline `fig-checklist` improves — re-run the script
rather than redoing edits from memory.

**Runs are committed.** One example's agentic output is ~20 KB of JSON, so a
38-example three-arm experiment is around 2 MB. Cheap enough that every
figure in the paper can be re-derived from committed data.
