<!-- This file is generated. Never hand-edit it: run `python -m soda_mmqc.cli graph fig-checklist-exp05 --write` instead. `graph fig-checklist-exp05` fails when it and the skills disagree. -->

# `fig-checklist-exp05`

2 check(s) and 5 shared skill(s), pinned by [`version-manifest.yaml`](version-manifest.yaml).

- **SkillSet digest:** `ae77558f9933341fd72e83de5a1a606950a96b79f7259cab7f7b9dab99b7f5a0`

A check is a skill that owns the evaluation contracts (schema.json, benchmark.json). Nothing else distinguishes a check from a shared skill: the hierarchy below is carried entirely by what each skill's own prose asks for, never by where its directory sits.

## Skills

| skill | version | kind | description |
| --- | --- | --- | --- |
| `classify-panels` | v1 | shared | Classify panels by labelling them with the kind of content it shows (micrograph, plot, blot, molecular or protein structure, sequence, schematic, photograph, table). Use when a check applies to only some kinds of panel. |
| `do-fig-checklist-cm` | v2 | check | Run the whole figure checklist on a figure. |
| `do-fig-checklist-pm` | v2 | check | Run the whole figure checklist on a figure. |
| `error-bars-defined` | v4 | shared | Check that error bars, and box or violin plot elements, are explained in the caption. |
| `identify-panels` | v1 | shared | Find every labelled panel in a figure. Use before any per-panel check. |
| `individual-data-points` | v4 | shared | Check that a plot showing averages also shows the individual data points behind them. |
| `micrograph-scale-bar` | v4 | shared | Check that every micrograph panel carries a scale bar, and that its length is stated on the image or in the caption. |

## Call graph

Each entry is one check and the skills its prose asks for, transitively.

- `do-fig-checklist-cm`
  - `classify-panels`
  - `error-bars-defined`
  - `individual-data-points`
  - `micrograph-scale-bar`
- `do-fig-checklist-pm`
  - `classify-panels`
  - `error-bars-defined`
  - `individual-data-points`
  - `micrograph-scale-bar`

### Called by no check

These are pinned, but no check's prose reaches them today. Under closure assembly -- the default since exp-03 -- a session holds its entry point and what that prose reaches, so none holds these. Runs made with `assembly="all"`, as exp-01 and exp-02 were, had them in every session.

- `identify-panels`
