<!-- This file is generated. Never hand-edit it: run `python -m soda_mmqc.cli graph fig-checklist --write` instead. `graph fig-checklist` fails when it and the skills disagree. -->

# `fig-checklist`

11 check(s) and 2 shared skill(s), pinned by [`version-manifest.yaml`](version-manifest.yaml).

- **SkillSet digest:** `c975706bbc94a3dfcfe07c9f0a8d432ef5275032444b52481d18bdf21f6018c0`

A check is a skill that owns the evaluation contracts (schema.json, benchmark.json). Nothing else distinguishes a check from a shared skill: the hierarchy below is carried entirely by what each skill's own prose asks for, never by where its directory sits.

## Skills

| skill | version | kind | description |
| --- | --- | --- | --- |
| `classify-plot-panels` | v1 | shared | Describe what kind of plot each figure panel contains and what its axes are: the plot types observed, whether drawn axes are present, and for each axis its numeric or categorical scale, its tick labels verbatim, and its title. Use this whenever a task needs to know what a panel plots or how its axes are laid out. Reports observations only — it does not decide whether a panel counts as a quantitative plot for any particular check, because different checks answer that differently. |
| `error-bars-defined` | v1 | check | Check that error bars and box-plot elements shown in a figure are defined in its caption. Use this for the error-bars-defined quality-control check. Decides, for each panel, whether error bars or box/whisker elements are present, whether the caption says what they represent, extracts that definition, and gives a PASS or FAIL verdict. |
| `identify-panels` | v1 | shared | Identify every labeled panel of a scientific figure and map each panel to the caption text that describes it. Use this first, whenever a task needs the list of panels, their labels, where each panel sits in the figure image, what each panel shows, or which caption sentence applies to which panel. Produces the shared panels artifact. Makes no quality-control judgement about what a panel contains. |
| `image-annotation-defined` | v1 | check | Check that graphical annotations drawn on imaging panels — arrows, arrowheads, circles, boxes, dashed lines — are explained in the figure caption. Use this for the image-annotation-defined quality-control check. Decides, for each panel, whether it holds imaging data, lists each unique annotation by shape and colour, and extracts the caption text defining each one. Scale bars are excluded entirely. |
| `individual-data-points` | v1 | check | Check that plots which should show individual data points actually do. Use this for the individual-data-points quality-control check. Decides, for each panel, whether it is a plot, whether individual values are displayed or are not required for that plot type, and gives a PASS or FAIL verdict with an explanation. |
| `micrograph-scale-bar` | v1 | check | Check that every micrograph panel of a scientific figure carries a scale bar, and that the scale bar length is defined either on the image itself or in the figure caption. Use this for the micrograph-scale-bar quality-control check. Decides, for each panel, whether the panel is a micrograph, whether a scale bar is present on it, whether its length is written on the image or in the caption, and extracts that definition. |
| `panel-image-matches-caption` | v1 | check | Judge whether what a panel's image actually shows contradicts what its caption claims is shown. Use this for the panel-image-matches-caption quality-control check. Returns a yes/no/not_applicable verdict per panel plus a description of any substantive discrepancy — wrong plot type, missing conditions, contradictory labels, or elements present in one and absent from the other. It does not identify panels and does not map caption text to panels; it compares content that has already been identified. |
| `plot-axis-units` | v1 | check | Check that the axes of quantitative plots carry the units of the quantity they measure. Use this for the plot-axis-units quality-control check. Decides, for each panel, whether it is a quantitative plot with axes, whether units are provided on each axis, extracts the unit definitions as printed, and gives a PASS or FAIL verdict. |
| `plot-gap-labeling` | v1 | check | Check that discontinuities in a plot's axis are marked with a visible break indicator. Use this for the plot-gap-labeling quality-control check. Decides, for each panel, whether the tick label sequence jumps anomalously and, if so, whether the break is visually marked, and gives a PASS or FAIL verdict. |
| `replication-reporting` | v1 | check | Check that panels showing replicated quantitative data report how many replicates were used and what they represent. Use this for the replication-reporting quality-control check. Decides, for each panel, whether replicates apply, extracts the n-number and replicate type verbatim from the figure and legend, and gives a PASS or FAIL verdict. |
| `single-channel-for-overlay` | v1 | check | Check that multicolour fluorescence overlay micrographs are accompanied by the corresponding single-channel images. Use this for the single-channel-for-overlay quality-control check. Decides, for each panel, whether a merged multi-channel microscopy image is present, counts the channels merged into it and the separate single-channel images shown beside it, and judges whether every channel is also shown on its own. |
| `stat-significance-level` | v1 | check | Check that significance symbols drawn on a plot — asterisks, hashes, letters — are defined in the caption with the p-value thresholds they stand for. Use this for the stat-significance-level quality-control check. Decides, for each panel, which symbols appear, whether each is defined, extracts those definitions, and gives a PASS or FAIL verdict. |
| `stat-test` | v1 | check | Check that figures claiming statistical significance say which statistical test produced it. Use this for the stat-test quality-control check. Decides, for each panel, whether it plots quantitative data, whether a significance claim makes a test mandatory, whether the caption names one, extracts that text, and gives a PASS or FAIL verdict. |

## Call graph

Each entry is one check and the skills its prose asks for, transitively.

- `error-bars-defined`
  - `classify-plot-panels`
    - `identify-panels`
  - `identify-panels`
- `image-annotation-defined`
  - `identify-panels`
- `individual-data-points`
  - `classify-plot-panels`
    - `identify-panels`
  - `identify-panels`
- `micrograph-scale-bar`
  - `identify-panels`
- `panel-image-matches-caption`
  - `identify-panels`
- `plot-axis-units`
  - `classify-plot-panels`
    - `identify-panels`
  - `identify-panels`
- `plot-gap-labeling`
  - `classify-plot-panels`
    - `identify-panels`
  - `identify-panels`
- `replication-reporting`
  - `classify-plot-panels`
    - `identify-panels`
  - `identify-panels`
- `single-channel-for-overlay`
  - `identify-panels`
- `stat-significance-level`
  - `classify-plot-panels`
    - `identify-panels`
  - `identify-panels`
- `stat-test`
  - `classify-plot-panels`
    - `identify-panels`
  - `identify-panels`
