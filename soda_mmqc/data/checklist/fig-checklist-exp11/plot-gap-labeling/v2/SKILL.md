---
name: plot-gap-labeling
description: Check that any discontinuity in a quantitative plot's axis is marked with a visual break indicator.
requires:
  - classify-panels
produces:
  - plot-gap-labeling
needs: []
---

# plot-gap-labeling

## Summary
Check whether any axis discontinuities in quantitative plots are properly marked with visual indicators. An unmarked axis break can seriously mislead readers about the relationship between data points — a y-axis that jumps from 30 to 500 with no break marker creates a false impression of the data distribution.

Proceed step-by-step and establish a systematical strategy to be very accurate and avoid mistakes.

## List and classify all figure panels

To be systematic, start from a complete and accurate list of all the figure's panels. Before you do anything else, invoke the `classify-panels` skill with the `Skill` tool to list every panel and classify it by content type.

## Applicability of the check to plots with axes only

Set `is_a_plot_with_axes` to "yes" for a panel whose classification includes `plot` and which is a quantitative plot with labeled axes — bar charts, line plots, scatter plots, box plots and similar visualizations. Set it to "no" otherwise.

For a panel where `is_a_plot_with_axes` is "no", the check does not apply: set `tick_sequence_anomaly`, `gap_visually_marked` and `decision` to "not_applicable", leave `explanation` empty, and skip the next two sections.

## Look for an anomalous jump in the tick labels

For each axis of a quantitative plot, read its tick labels as printed. A consistent sequence is evenly spaced, follows a logarithmic scale, or is otherwise numerically regular. Look specifically for anomalous jumps or skips — labels reading `0, 10, 20, 30, 500`, where the final value is disproportionately large relative to the preceding intervals.

**Categorical axes never count.** An axis whose tick labels are category names — treatment groups, sample names, discrete time points — has no numerical sequence and must never be flagged.

If every axis is consistent, or categorical, set `tick_sequence_anomaly` to "no" and `gap_visually_marked` to "not_required" — there is no gap to mark — and skip the next section.

## Is the gap marked?

Where you found an anomalous jump, set `tick_sequence_anomaly` to "yes" and look at the image for a break indicator at that point — a pair of slanted parallel lines, a zigzag, or a visible gap drawn through the axis or the bars. Set `gap_visually_marked` to "yes" or "no" accordingly.

## Decision and explanation

Put "PASS", "FAIL" or "not_applicable" in `decision`:

- "PASS" — no anomaly, or an anomaly that is visually marked.
- "FAIL" — an anomalous jump with no break indicator. Describe the unmarked gap briefly in `explanation`.
- "not_applicable" — `is_a_plot_with_axes` is "no": the check does not apply to it, so it neither passes nor fails.

Leave `explanation` empty unless `decision` is "FAIL".

## Please note:
- Report every panel of the figure, including panels that are not quantitative plots, which take `is_a_plot_with_axes` "no" and "not_applicable" in `tick_sequence_anomaly`, `gap_visually_marked` and `decision`.
