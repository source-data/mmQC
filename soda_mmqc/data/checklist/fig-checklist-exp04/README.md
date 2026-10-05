<!-- This file is generated. Never hand-edit it: run `python -m soda_mmqc.cli graph fig-checklist-exp04 --write` instead. `graph fig-checklist-exp04` fails when it and the skills disagree. -->

# `fig-checklist-exp04`

2 check(s) and 5 shared skill(s), pinned by [`version-manifest.yaml`](version-manifest.yaml).

- **SkillSet digest:** `d527afdb25ee5d2d1d8bd077980a58fdd5f08f8a64684868dad8cc4b481426da`

A check is a skill that owns the evaluation contracts (schema.json, benchmark.json). Nothing else distinguishes a check from a shared skill: the hierarchy below is carried entirely by what each skill's own prose asks for, never by where its directory sits.

## Skills

| skill | version | kind | description |
| --- | --- | --- | --- |
| `classify-panels` | v1 | shared | Classify panels by labelling them with the kind of content it shows (micrograph, plot, blot, molecular or protein structure, sequence, schematic, photograph, table). Use when a check applies to only some kinds of panel. |
| `do-fig-checklist-cm` | v1 | check | Run the whole figure checklist on a figure. |
| `do-fig-checklist-pm` | v1 | check | Run the whole figure checklist on a figure. |
| `error-bars-defined` | v1 | shared | Check that error bars, and box or violin plot elements, are explained in the caption. |
| `identify-panels` | v1 | shared | Find every labelled panel in a figure. Use before any per-panel check. |
| `individual-data-points` | v1 | shared | Check that a plot showing averages also shows the individual data points behind them. |
| `micrograph-scale-bar` | v1 | shared | Check that every micrograph panel carries a scale bar, and that its length is stated on the image or in the caption. |

## Call graph

Each entry is one check and the skills its prose asks for, transitively.

- `do-fig-checklist-cm`
  - `error-bars-defined`
  - `individual-data-points`
  - `micrograph-scale-bar`
- `do-fig-checklist-pm`
  - `error-bars-defined`
  - `individual-data-points`
  - `micrograph-scale-bar`

### Called by no check

These are pinned, but no check's prose reaches them today. Under closure assembly -- the default since exp-03 -- a session holds its entry point and what that prose reaches, so none holds these. Runs made with `assembly="all"`, as exp-01 and exp-02 were, had them in every session.

- `classify-panels`
- `identify-panels`
