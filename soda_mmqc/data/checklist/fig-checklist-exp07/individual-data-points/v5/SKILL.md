---
name: individual-data-points
description: Check that a plot showing averages also shows the individual data points behind them.
requires:
- classify-panels
produces:
  - individual-data-points
needs: []
---

# indiviual-data-points

## Summary

Check whether plots showing averaged or aggregated data also display the underlying individual data points.

Showing individual data points alongside summary statistics is important because it allows the reader to assess the spread and variability of the raw measurements, and to judge how robust a result truly is. Plotting only averages can obscure low replication numbers, outliers, or large variability — details that are critical for interpreting the reliability of a finding.

## List and classify all figure panels

To be systematic, start from a complete and accurate list of all the figure's panels. Before you do anything else, invoke the `classify-panels` skill with the `Skill` tool to list every panel and classify it by content type.

## Applicability of the check to plots with axes only

Set `is_a_plot_with_axes` to "yes" for a panel whose classification includes `plot`, alone or beside other content types, and which is a plot of quantitative data with drawn axes. Set it to "no" otherwise, including for heat maps and for any plot with no drawn axes. Pay attention to plots that show error bars, typically bar charts, or that show mean values: those are the ones this check is about.

For a panel where `is_a_plot_with_axes` is "no", this check does not apply: set `individual_values` and `decision` to "not_applicable". You can skip the next two sections and jump to "Decision and explanation".

## Does this plot type require individual data points?

The check applies primarily to *bar charts* showing means or medians.

But not all plots require individual data points to be overlaid. The following plot types are exempt: set `individual_values` to "not_required".

- Box plots and violin plots — these already display the data distribution
- Line plots — overlaying individual points typically makes these unreadable
- Kaplan-Meier curves — they show survival over time, not averages
- Pie charts, Venn diagrams — do not need individual data points
- Scatter plots — individual points are the data

Cross-check with the panel classification to avoid common mistakes.

## Are individual data points shown?
For plots that are not exempt, check whether the individual data points are overlaid on the summary visualization — typically as dots, circles, or similar markers.

- If they are, set `individual_values` to "yes".
- If the plot summarises data, for instance a bar chart of means with error bars, and the individual measurements are not shown, set `individual_values` to "no".

## Decision and explanation
For each panel, put `PASS`, `FAIL` or `not_applicable` in `decision`, and a one-line reason in `explanation`, in plain text.

- If `individual_values` is "yes" or "not_required", `decision` is `PASS`.
- If `individual_values` is "no", `decision` is `FAIL`: the panel should show its individual data points and does not.
- If `is_a_plot_with_axes` is "no", `decision` is `not_applicable`: the check does not apply to it, so it neither passes nor fails.

## Please note:
- Report every panel of the figure, including panels that are not plots with axes, which take `not_applicable`, and exempt plots, which take `not_required` and `PASS`.
