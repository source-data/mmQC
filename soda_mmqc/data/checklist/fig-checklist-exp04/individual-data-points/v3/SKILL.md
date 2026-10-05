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

## Classify figure panels

To decide when the check is applicable or not, invoke the `classify-panels` skill to classify panels based on content type before you do anything else.

## Applicability of the check to plots only

Set `plot` to "yes" for a panel whose classification includes `plot`, alone or beside other content types, and to "no" otherwise. Pay attention to plots that show error bars, typically bar charts, or that show mean values: those are the ones this check is about.

For a panel that is not a plot, this check does not apply: set `individual_values` and `decision` to "not_applicable". You can skip the next two sections and jump to "Decision and explanation".

## Does this plot type require individual data points?

The check applies primarily to *bar charts* showing means or medians.

But not all plots require individual data points to be overlaid. The following plot types are exempt: set `individual_values` to "not_required".

- Box plots and violin plots — these already display the data distribution
- Heatmaps — individual points are not meaningful in this context
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
- If the panel is not a plot, `decision` is `not_applicable`: the check does not apply to it, so it neither passes nor fails.

## Please note:
- Report every panel of the figure, including panels that are not plots, which take `not_applicable`, and exempt plots, which take `not_required` and `PASS`.
