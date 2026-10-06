---
name: error-bars-defined
description: Check that error bars, and box or violin plot elements, are explained in the caption.
requires: []
produces:
  - error-bars-defined
needs: []
---

# error-bars-defined

## Summary
Analyze a scientific figure and its caption to check for the presence of error bars and whether they are properly defined.

Proceed step-by-step and establish a systematical structured strategy to be very accurate and avoid mistakes.

## Applicability of the check to plots only

Set `is_a_plot` to "yes" for panels whose classification includes `plot`, alone or beside other content types, and to "no" otherwise.

For a panel that is not a plot, this check does not apply: set
`error_bar_on_figure`, `error_bar_defined_in_caption` and `decision` to "not_applicable", and leave `from_the_caption` empty. You can skip the next two sections and jump to "Decision and explanation".

## Determine if panels contain error bars or box-plot elements to define
Your job is to pay attention to any plots that have error bars (typically bar charts, line plots). This is easy when the plot is itself an individual panel image. Pay attention also to more difficult cases when a plot is only part of a composite panel image.

Cross-check with the panel classification to avoid common mistakes.

For each plot in the figure:
- Determine if the plot contains error bars (lines extending from data points indicating variability). These are typically on bar charts, line charts, and sometimes scatter plots.
- *Box plots* and *violin plots*: whiskers and median/mean lines are not classical error bars, but lines, box and whisker elements still require a caption definition (e.g., IQR, percentiles, confidence intervals). For box plots and violin plots, set `error_bar_on_figure` to "yes" and check whether the caption defines the lines,  boxes and whiskers. If undefined, use FAIL.

## Check figure caption for explanation
- If error bars or box-plot elements are present in the panel, check whether the caption explains what they represent (e.g., standard deviation, standard error, confidence interval, IQR, whisker definition). Put "yes" or "no" in `error_bar_defined_in_caption`.
- If a plot has no error bars or box-plot elements, there is nothing to define: set `error_bar_on_figure` to "no", `error_bar_defined_in_caption` to "not_required", and leave `from_the_caption` empty.
- If error bars are absent from the figure but mentioned in the caption, note that mismatch in the explanation.


*IMPORTANT*: When extracting definitions from the caption, ONLY include in `from_the_caption` the specific text that describes what the error bars or box elements represent (e.g., "standard error of the mean", "standard deviation", "95% confidence interval"). Do NOT include general descriptions of the figure or panel content. It is fine to extract only fragments of a sentence and omit further information about statistical tests. Use plain text only — write `mean +/- SD` not `mean ± SD`.

## Decision and explanation
For each panel, put `PASS`, `FAIL` or `not_applicable` in `decision`, and a one-line reason in `explanation`, in plain text.

- If error bars or box-plot elements are present and the caption defines them, `decision` is `PASS`.
- If they are present and the caption does not define them, `decision` is `FAIL`.
- If the panel is a plot with no error bars or box-plot elements, there is nothing to define, so `decision` is `PASS`.
- If the panel is not a plot, `decision` is `not_applicable`: the check does not apply to it, so it neither passes nor fails.


## Please note:
- If the caption defines error bars for multiple panels, include the same definition for each relevant panel.
- Report every panel of the figure, including panels that are not plots, which take `not_applicable`, and plots without error bars, which take `not_required` and `PASS`.
