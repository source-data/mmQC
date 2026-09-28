<!-- This file is generated. Never hand-edit it: run `python -m soda_mmqc.cli graph fig-checklist-exp03-per-check --write` instead. `graph fig-checklist-exp03-per-check` fails when it and the skills disagree. -->

# `fig-checklist-exp03-per-check`

3 check(s) and 1 shared skill(s), pinned by [`version-manifest.yaml`](version-manifest.yaml).

- **SkillSet digest:** `3fee2dcd14d918e8de4ce200edbf39a99e487f1db3d441255151393e9e04f228`

A check is a skill that owns the evaluation contracts (schema.json, benchmark.json). Nothing else distinguishes a check from a shared skill: the hierarchy below is carried entirely by what each skill's own prose asks for, never by where its directory sits.

## Skills

| skill | version | kind | description |
| --- | --- | --- | --- |
| `classify-panels` | v1 | shared | Classify panels by labelling them with the kind of content it shows (micrograph, plot, blot, molecular or protein structure, sequence, schematic, photograph, table). Use when a check applies to only some kinds of panel. |
| `error-bars-defined` | v1 | check | Check that error bars, and box or violin plot elements, are explained in the caption. |
| `individual-data-points` | v1 | check | Check that a plot showing averages also shows the individual data points behind them. |
| `micrograph-scale-bar` | v1 | check | Check that every micrograph panel carries a scale bar, and that its length is stated on the image or in the caption. |

## Call graph

Each entry is one check and the skills its prose asks for, transitively.

- `error-bars-defined`
- `individual-data-points`
- `micrograph-scale-bar`

### Called by no check

These are pinned and assembled -- every skill's description competes in every session -- but no check's prose asks for them today.

- `classify-panels`
