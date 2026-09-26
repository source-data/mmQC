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

## Does this plot type require individual data points?

The check applies primarily to *bar charts* showing means or medians.

But not all plots require individual data points to be overlaid. The following plot types are exempt — set "individual_values" to "not needed" and "decision" to "PASS":

- Box plots and violin plots — these already display the data distribution
- Heatmaps — individual points are not meaningful in this context
- Line plots — overlaying individual points typically makes these unreadable
- Pie charts, Venn diagramms - do not need individual data points
- Scatter plots — individual points are the data

Cross-check with the panel classification to avoid common mistakes. 

## Are individual data points shown?
For applicable plots, check whether the individual data points are overlaid on the summary visualization — typically as dots, circles, or similar markers.

If yes → "individual_values": "yes" → "decision": "PASS"
If no → "individual_values": "no" → "decision": "FAIL"
