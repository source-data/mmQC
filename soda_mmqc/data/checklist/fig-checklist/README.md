<!-- This file is generated. Never hand-edit it: run `python -m soda_mmqc.cli graph fig-checklist --write` instead. `graph fig-checklist` fails when it and the skills disagree. -->

# `fig-checklist`

12 check(s) and 3 shared skill(s), pinned by [`version-manifest.yaml`](version-manifest.yaml).

- **SkillSet digest:** `bd3b1ab371cd9c089bd0ff3b83b5996c74a000ae97bea2d9621d552b393706d3`

A check is a skill that owns the evaluation contracts (schema.json, benchmark.json). Nothing else distinguishes a check from a shared skill: the hierarchy below is carried entirely by what each skill's own prose asks for, never by where its directory sits.

## Skills

| skill | version | kind | description |
| --- | --- | --- | --- |
| `classify-panels` | v1 | shared | Classify panels by labelling them with the kind of content it shows (micrograph, plot, blot, molecular or protein structure, sequence, schematic, photograph, table). Use when a check applies to only some kinds of panel. |
| `classify-plot-panels` | v1 | shared | Describe what kind of plot each figure panel contains and what its axes are: the plot types observed, whether drawn axes are present, and for each axis its numeric or categorical scale, its tick labels verbatim, and its title. Use this whenever a task needs to know what a panel plots or how its axes are laid out. Reports observations only — it does not decide whether a panel counts as a quantitative plot for any particular check, because different checks answer that differently. |
| `do-fig-checklist-cm` | v1 | check | Run the whole figure checklist on a figure. |
| `error-bars-defined` | v2 | check | Check that error bars, and box or violin plot elements, are explained in the caption. |
| `identify-panels` | v2 | shared | Find every labelled panel in a figure. Use before any per-panel check. |
| `image-annotation-defined` | v2 | check | Check that graphical annotations drawn on imaging panels — arrows, arrowheads, circles, boxes, dashed lines — are explained in the caption. |
| `individual-data-points` | v2 | check | Check that a plot showing averages also shows the individual data points behind them. |
| `micrograph-scale-bar` | v2 | check | Check that every micrograph panel carries a scale bar, and that its length is stated on the image or in the caption. |
| `panel-image-matches-caption` | v2 | check | Judge whether what a panel's image shows contradicts what its caption says is shown. |
| `plot-axis-units` | v2 | check | Check that the axes of quantitative plots state the units of what they measure. |
| `plot-gap-labeling` | v2 | check | Check that any discontinuity in a quantitative plot's axis is marked with a visual break indicator. |
| `replication-reporting` | v2 | check | Check that panels showing replicated data report the number of replicates and what they represent. |
| `single-channel-for-overlay` | v2 | check | Check that each channel of a multicoloured overlay micrograph is also shown as a single-channel image. |
| `stat-significance-level` | v2 | check | Check that significance symbols shown on plots, such as asterisks, are defined in the caption. |
| `stat-test` | v2 | check | Check that a panel claiming statistical significance names the statistical test behind the claim. |

## Call graph

Each entry is one check and the skills its prose asks for, transitively.

- `do-fig-checklist-cm`
  - `error-bars-defined`
    - `classify-panels`
  - `image-annotation-defined`
    - `classify-panels`
  - `individual-data-points`
    - `classify-panels`
  - `micrograph-scale-bar`
    - `classify-panels`
  - `panel-image-matches-caption`
    - `classify-panels`
  - `plot-axis-units`
    - `classify-panels`
  - `plot-gap-labeling`
    - `classify-panels`
  - `replication-reporting`
    - `classify-panels`
  - `single-channel-for-overlay`
    - `classify-panels`
  - `stat-significance-level`
    - `classify-panels`
  - `stat-test`
    - `classify-panels`
- `error-bars-defined`
  - `classify-panels`
- `image-annotation-defined`
  - `classify-panels`
- `individual-data-points`
  - `classify-panels`
- `micrograph-scale-bar`
  - `classify-panels`
- `panel-image-matches-caption`
  - `classify-panels`
- `plot-axis-units`
  - `classify-panels`
- `plot-gap-labeling`
  - `classify-panels`
- `replication-reporting`
  - `classify-panels`
- `single-channel-for-overlay`
  - `classify-panels`
- `stat-significance-level`
  - `classify-panels`
- `stat-test`
  - `classify-panels`

### Called by no check

These are pinned, but no check's prose reaches them today. Under closure assembly -- the default since exp-03 -- a session holds its entry point and what that prose reaches, so none holds these. Runs made with `assembly="all"`, as exp-01 and exp-02 were, had them in every session.

- `classify-plot-panels`
- `identify-panels`
