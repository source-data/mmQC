<!-- This file is generated. Never hand-edit it: run `python -m soda_mmqc.cli graph fig-checklist-exp02 --write` instead. `graph fig-checklist-exp02` fails when it and the skills disagree. -->

# `fig-checklist-exp02`

3 check(s) and 2 shared skill(s), pinned by [`version-manifest.yaml`](version-manifest.yaml).

- **SkillSet digest:** `08066e7c41b2b098875d13b2b84631c66866ec1290b47f2e26003a955ae06879`

A check is a skill that owns the evaluation contracts (schema.json, benchmark.json). Nothing else distinguishes a check from a shared skill: the hierarchy below is carried entirely by what each skill's own prose asks for, never by where its directory sits.

## Skills

| skill | version | kind | description |
| --- | --- | --- | --- |
| `classify-panels` | v1 | shared | Classify panels by labelling them with the kind of content it shows (micrograph, plot, blot, molecular or protein structure, sequence, schematic, photograph, table). Use when a check applies to only some kinds of panel. |
| `error-bars-defined` | v1 | check | Check that error bars, and box or violin plot elements, are explained in the caption. |
| `identify-panels` | v1 | shared | Find every labelled panel in a figure and the caption text that describes it. Use before any per-panel check. |
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
