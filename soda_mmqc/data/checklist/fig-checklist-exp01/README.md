<!-- This file is generated. Never hand-edit it: run `python -m soda_mmqc.cli graph fig-checklist-exp01 --write` instead. `graph fig-checklist-exp01` fails when it and the skills disagree. -->

# `fig-checklist-exp01`

11 check(s) and 0 shared skill(s), pinned by [`version-manifest.yaml`](version-manifest.yaml).

- **SkillSet digest:** `e28a03cbc6ddcc3d08d98005af1186c625248331aac3aa7401cdef598b7167dd`

A check is a skill that owns the evaluation contracts (schema.json, benchmark.json). Nothing else distinguishes a check from a shared skill: the hierarchy below is carried entirely by what each skill's own prose asks for, never by where its directory sits.

## Skills

| skill | version | kind | description |
| --- | --- | --- | --- |
| `error-bars-defined` | v1 | check | Check that error bars, and box or violin plot elements, are explained in the caption. |
| `image-annotation-defined` | v1 | check | Check that arrows, arrowheads and other markings drawn on image panels are explained in the caption. |
| `individual-data-points` | v1 | check | Check that a plot showing averages also shows the individual data points behind them. |
| `micrograph-scale-bar` | v1 | check | Check that every micrograph panel carries a scale bar, and that its length is stated on the image or in the caption. |
| `panel-image-matches-caption` | v1 | check | Check that each panel shows what its caption says it shows. |
| `plot-axis-units` | v1 | check | Check that each plot axis states its units, or does not need them. |
| `plot-gap-labeling` | v1 | check | Check that a break in a plot's axis scale is marked, so the jump is not read as continuous. |
| `replication-reporting` | v1 | check | Check that a panel with replicated data reports how many replicates and of what kind. |
| `single-channel-for-overlay` | v1 | check | Check that a multicolour overlay micrograph also shows each of its channels separately. |
| `stat-significance-level` | v1 | check | Check that significance symbols on a plot are defined, on the image or in the caption. |
| `stat-test` | v1 | check | Check that a plot claiming statistical significance names the test used. |

## Call graph

- `error-bars-defined`
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
