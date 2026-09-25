<!-- This file is generated. Never hand-edit it: run `python -m soda_mmqc.cli graph fig-checklist-exp02 --write` instead. `graph fig-checklist-exp02` fails when it and the skills disagree. -->

# `fig-checklist-exp02`

3 check(s) and 2 shared skill(s), pinned by [`version-manifest.yaml`](version-manifest.yaml).

- **SkillSet digest:** `f3411f53b59e2fee40f2d8296ebbb384964b7f91f42d2b9251dd12b94f51a3ff`

A check is a skill that owns the evaluation contracts (schema.json, benchmark.json). Nothing else distinguishes a check from a shared skill: the hierarchy below is carried entirely by what each skill's own prose asks for, never by where its directory sits.

## Skills

| skill | version | kind | description |
| --- | --- | --- | --- |
| `classify-panels` | v1 | shared | Name what kind of content each figure panel holds: micrograph, plot, blot, molecular or protein structure, sequence, schematic, photograph, table, or something else. Use this whenever a task needs to know what sort of thing a panel is before deciding whether a check applies to it. Reports observations only — it does not decide whether a panel qualifies for any particular check, because different checks answer that differently. |
| `error-bars-defined` | v1 | check | Check that error bars, and box or violin plot elements, are explained in the caption. |
| `identify-panels` | v1 | shared | Identify every panel of a scientific figure and locate the caption text that describes each one. Use this first, whenever a task needs the list of panels, their labels, or which part of the caption applies to which panel. Makes no judgement about what a panel contains. |
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
- `identify-panels`
