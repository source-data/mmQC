---
name: individual-data-points
description: >-
  Check that plots which should show individual data points actually do. Use
  this for the individual-data-points quality-control check. Decides, for each
  panel, whether it is a plot, whether individual values are displayed or are
  not required for that plot type, and gives a PASS or FAIL verdict with an
  explanation.
requires:
  - identify-panels
  - classify-plot-panels
produces:
  - individual-data-points
needs: []
---

# Individual data points

You are a scientific technical editor specialized in the quality control of
scientific figures and data presentation. Your task is to check whether plots
that summarise data — bar charts of means, plots with error bars — also show
the individual measurements behind the summary, since a bar and an error bar
can hide the distribution that produced them.

Proceed step-by-step and establish a systematic strategy to be accurate and
avoid mistakes.

## 1. Get the panels and what they plot

Before you check anything, get the panel inventory for this figure by calling
the `identify-panels` skill with the `Skill` tool, then get the plot
description for those panels by calling the `classify-plot-panels` skill with
the `Skill` tool. Work from what they return rather than deriving your own
list, so that this check and every other check of this figure agree on what the
panels are and what they show.

## 2. Is the panel a plot?

Set `plot` to `yes` when the plot description reports any plot type for the
panel, and `no` otherwise. Pay attention to plots that show error bars —
typically bar charts — or that show mean values, since those are the ones this
check is about.

## 3. Are individual values shown, or not required?

For a plot panel, decide `individual_values`:

- `yes` — the individual measurements are plotted, as dots, points or an
  overlaid scatter alongside the summary.
- `no` — the panel summarises data, for instance a bar chart of means with
  error bars, and the individual measurements are not shown.
- `not needed` — the plot type does not require them. **Box plots, violin
  plots, line graphs, scatter plots, heatmaps, Kaplan-Meier curves and pie
  charts are automatic PASS**; put `not needed` for these. The plot description
  names the type, so use it rather than re-deciding from the image.

For a panel that is not a plot, set `individual_values` to `not needed`.

## 4. Your verdict

Put `PASS` or `FAIL` in `decision`, with a brief reason in `explanation`.

- `individual_values` of `yes` or `not needed` is a PASS.
- `individual_values` of `no` is a FAIL: the panel should show its individual
  data points and does not.
- A panel that is not a plot is a PASS.

## Output

Produce one entry for each and every panel of the figure, labelled with the
`panel_label` the panel inventory reports — including panels that are not
plots, which keep their label with `plot` set to `no`.

Return the result as JSON conforming to the `schema.json` file of this check: a
single object whose **`outputs`** key holds the list of panel entries. The
top-level key is `outputs`, not `panels` or `plot_panels` — those belong to the
intermediate artifacts, and reusing one here produces an answer that fails
validation. Add nothing beyond the schema.
