<!-- This file is generated. Never hand-edit it: run `python -m soda_mmqc.cli graph fig-checklist-exp06 --write` instead. `graph fig-checklist-exp06` fails when it and the skills disagree. -->

# `fig-checklist-exp06`

0 check(s) and 14 shared skill(s), pinned by [`version-manifest.yaml`](version-manifest.yaml).

- **SkillSet digest:** `355fae4c42f94c1bca5697a3b1936f0c0606d98c4456701a75a81c2b1d59eac6`

A check is a skill that owns the evaluation contracts (schema.json, benchmark.json). Nothing else distinguishes a check from a shared skill: the hierarchy below is carried entirely by what each skill's own prose asks for, never by where its directory sits.

## Skills

| skill | version | kind | description |
| --- | --- | --- | --- |
| `classify-panels` | v1 | shared | Classify panels by labelling them with the kind of content it shows (micrograph, plot, blot, molecular or protein structure, sequence, schematic, photograph, table). Use when a check applies to only some kinds of panel. |
| `do-fig-checklist-cm` | v1 | shared | Run the whole figure checklist on a figure. |
| `error-bars-defined` | v3 | shared | Check that error bars, and box or violin plot elements, are explained in the caption. |
| `identify-panels` | v1 | shared | Find every labelled panel in a figure. Use before any per-panel check. |
| `image-annotation-defined` | v1 | shared | Check that graphical annotations drawn on imaging panels — arrows, arrowheads, circles, boxes, dashed lines — are explained in the caption. |
| `individual-data-points` | v3 | shared | Check that a plot showing averages also shows the individual data points behind them. |
| `micrograph-scale-bar` | v3 | shared | Check that every micrograph panel carries a scale bar, and that its length is stated on the image or in the caption. |
| `panel-image-matches-caption` | v1 | shared | Judge whether what a panel's image shows contradicts what its caption says is shown. |
| `plot-axis-units` | v1 | shared | Check that the axes of quantitative plots state the units of what they measure. |
| `plot-gap-labeling` | v1 | shared | Check that any discontinuity in a quantitative plot's axis is marked with a visual break indicator. |
| `replication-reporting` | v1 | shared | Check that panels showing replicated data report the number of replicates and what they represent. |
| `single-channel-for-overlay` | v1 | shared | Check that each channel of a multicoloured overlay micrograph is also shown as a single-channel image. |
| `stat-significance-level` | v1 | shared | Check that significance symbols shown on plots, such as asterisks, are defined in the caption. |
| `stat-test` | v1 | shared | Check that a panel claiming statistical significance names the statistical test behind the claim. |

## Call graph

Each entry is one check and the skills its prose asks for, transitively.


### Called by no check

These are pinned, but no check's prose reaches them today. Under closure assembly -- the default since exp-03 -- a session holds its entry point and what that prose reaches, so none holds these. Runs made with `assembly="all"`, as exp-01 and exp-02 were, had them in every session.

- `classify-panels`
- `do-fig-checklist-cm`
- `error-bars-defined`
- `identify-panels`
- `image-annotation-defined`
- `individual-data-points`
- `micrograph-scale-bar`
- `panel-image-matches-caption`
- `plot-axis-units`
- `plot-gap-labeling`
- `replication-reporting`
- `single-channel-for-overlay`
- `stat-significance-level`
- `stat-test`
