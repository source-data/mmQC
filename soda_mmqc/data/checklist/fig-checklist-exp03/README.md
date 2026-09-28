<!-- This file is generated. Never hand-edit it: run `python -m soda_mmqc.cli graph fig-checklist-exp03 --write` instead. `graph fig-checklist-exp03` fails when it and the skills disagree. -->

# `fig-checklist-exp03`

1 check(s) and 4 shared skill(s), pinned by [`version-manifest.yaml`](version-manifest.yaml).

- **SkillSet digest:** `bd48e15ceb9b5e66ee3694abe4612903965511d1b2bae6a5b88a899ff4b20093`

A check is a skill that owns the evaluation contracts (schema.json, benchmark.json). Nothing else distinguishes a check from a shared skill: the hierarchy below is carried entirely by what each skill's own prose asks for, never by where its directory sits.

## Skills

| skill | version | kind | description |
| --- | --- | --- | --- |
| `classify-panels` | v1 | shared | Classify panels by labelling them with the kind of content it shows (micrograph, plot, blot, molecular or protein structure, sequence, schematic, photograph, table). Use when a check applies to only some kinds of panel. |
| `do-fig-checklist` | v1 | check | Run the whole figure checklist on a figure. |
| `error-bars-defined` | v1 | shared | Check that error bars, and box or violin plot elements, are explained in the caption. |
| `individual-data-points` | v1 | shared | Check that a plot showing averages also shows the individual data points behind them. |
| `micrograph-scale-bar` | v1 | shared | Check that every micrograph panel carries a scale bar, and that its length is stated on the image or in the caption. |

## Call graph

Each entry is one check and the skills its prose asks for, transitively.

- `do-fig-checklist`
  - `error-bars-defined`
  - `individual-data-points`
  - `micrograph-scale-bar`

### Called by no check

These are pinned and assembled -- every skill's description competes in every session -- but no check's prose asks for them today.

- `classify-panels`
