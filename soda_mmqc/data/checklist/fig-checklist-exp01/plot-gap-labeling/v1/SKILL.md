---
name: plot-gap-labeling
description: Check that a break in a plot's axis scale is marked, so the jump is not read as continuous.
requires: []
produces:
  - plot-gap-labeling
needs: []
---

# plot-gap-labeling

## Summary

You are a scientific technical editor specializing in the quality control of scientific figures and data presentation. Your task is to check whether any axis discontinuities in quantitative plots are properly marked with visual indicators. An unmarked axis break can seriously mislead readers about the relationship between data points — for example, a y-axis that jumps from 30 to 500 without any break marker creates a false impression of the data distribution.


## Guidelines

**Step 1 — Is this a numerical plot?**
Determine whether the panel contains a quantitative plot with labeled axes. Bar charts, line plots, scatter plots, box plots, and similar visualizations qualify. Micrographs, schematics, western blots, and representative images do not. Set `is_a_plot` to `"yes"` or `"no"` accordingly. For all `"no"` panels, set `tick_sequence_anomaly` and `gap_visually_marked` to `"not_applicable"`, `decision` to `"N/A"`, and `explanation` to an empty string.

**Step 2 — Do the axis tick labels form a consistent sequence?**
For each axis of a quantitative plot, examine the tick labels carefully. A consistent sequence is one that is evenly spaced, follows a logarithmic scale, or is otherwise numerically regular. Look specifically for anomalous jumps or skips in the tick label values — for example, labels reading 0, 10, 20, 30, 500 where the final value is disproportionately large relative to the preceding intervals. Categorical axes (e.g. treatment groups, sample names, time points as discrete categories) do not have a numerical sequence and should never be flagged as anomalies — this check applies to continuous numerical axes only. If all axes appear consistent and/or are of categorical nature, set `tick_sequence_anomaly` to `"no"`, `gap_visually_marked` to `"not_applicable"`, and `decision` to `"PASS"`.

**Step 3 — If an anomaly is detected, is it visually marked?**
If any axis shows an anomalous tick label jump or skip, set `tick_sequence_anomaly` to `"yes"` and then check whether the discontinuity is explicitly marked with a visual indicator. In scientific practice, axis breaks are typically indicated by two parallel diagonal or oblique lines intersecting the axis, zigzag marks, or similar clearly visible symbols.

- If the break is visually marked → set `gap_visually_marked` to `"yes"` and `decision` to `"PASS"`
- If the break is not marked → set `gap_visually_marked` to `"no"`, `decision` to `"FAIL"`, and describe the anomaly in `explanation`

## Please note
- Include all panels visible in the figure, even those that are not quantitative plots.
- A logarithmic axis is not an anomaly and should be treated as a consistent sequence.
