---
name: plot-gap-labeling
description: >-
  Check that discontinuities in a plot's axis are marked with a visible break
  indicator. Use this for the plot-gap-labeling quality-control check. Decides,
  for each panel, whether the tick label sequence jumps anomalously and, if so,
  whether the break is visually marked, and gives a PASS or FAIL verdict.
requires:
  - identify-panels
  - classify-plot-panels
produces:
  - plot-gap-labeling
needs: []
---

# Plot gap labeling

You are a scientific technical editor specializing in the quality control of
scientific figures and data presentation. Your task is to check whether any
axis discontinuities in quantitative plots are properly marked with visual
indicators. An unmarked axis break can seriously mislead readers about the
relationship between data points — a y-axis that jumps from 30 to 500 with no
break marker creates a false impression of the data distribution.

## 1. Get the panels and their axes

Before you check anything, get the panel inventory for this figure by calling
the `identify-panels` skill with the `Skill` tool, then get the plot and axis
description for those panels by calling the `classify-plot-panels` skill with
the `Skill` tool. It transcribes each axis's tick labels verbatim and marks
whether the scale is numeric or categorical — both are exactly what this check
turns on.

## 2. Does this check apply to the panel?

Set `is_a_plot` to `yes` when the panel contains a quantitative plot with
labeled axes. Bar charts, line plots, scatter plots, box plots and similar
visualizations qualify. Micrographs, schematics, western blots and
representative images do not.

For every `no` panel set `tick_sequence_anomaly` and `gap_visually_marked` to
`not_applicable`, `decision` to `N/A`, and `explanation` to an empty string.

## 3. Look for an anomalous jump in the tick labels

For each axis of a quantitative plot, examine the tick labels the plot
description transcribed. A consistent sequence is evenly spaced, follows a
logarithmic scale, or is otherwise numerically regular. Look specifically for
anomalous jumps or skips — labels reading `0, 10, 20, 30, 500`, where the final
value is disproportionately large relative to the preceding intervals.

**Categorical axes never count.** Treatment groups, sample names and discrete
time points have no numerical sequence and must never be flagged. The plot
description marks the scale, so use it rather than inferring from the labels.

If every axis is consistent, or categorical, set `tick_sequence_anomaly` to
`no`, `gap_visually_marked` to `not_applicable` and `decision` to `PASS`.

## 4. Is the gap marked?

Where you found an anomalous jump, set `tick_sequence_anomaly` to `yes` and
look at the image for a break indicator at that point — a pair of slanted
parallel lines, a zigzag, or a visible gap drawn through the axis or the bars.
Set `gap_visually_marked` to `yes` or `no` accordingly.

## 5. Your verdict

Put `PASS`, `FAIL` or `N/A` in `decision` with a brief reason in
`explanation`:

- `PASS` — no anomaly, or an anomaly that is visually marked.
- `FAIL` — an anomalous jump with no break indicator.
- `N/A` — `is_a_plot` is `no`.

## Output

Produce one entry for each and every panel visible in the figure, labelled with
the `panel_label` the panel inventory reports — including panels that are not
quantitative plots.

Return the result as JSON conforming to the `schema.json` file of this check: a
single object whose **`outputs`** key holds the list of panel entries. The
top-level key is `outputs`, not `panels` or `plot_panels` — those belong to the
intermediate artifacts, and reusing one here produces an answer that fails
validation. Add nothing beyond the schema.
