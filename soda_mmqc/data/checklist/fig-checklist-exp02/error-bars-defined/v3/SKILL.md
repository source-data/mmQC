---
name: error-bars-defined
description: Check that error bars, and box or violin plot elements, are explained in the caption.
requires:
  - classify-panels
produces:
  - error-bars-defined
needs: []
---

# error-bars-defined

## Summary 
Analyze a scientific figure and its caption to check for the presence of error bars and whether they are properly defined.

Proceed step-by-step and establish a systematical structured strategy to be very accurate and avoid mistakes.

## Classify figure panels

To decide when the check is applicable or not, invoke the `classify-panels` skill to classify panels based on content type before you do anything else.

## Determine if the panel contains error bars or box-plot elements to define
Your job is to pay attention to any plots that have error bars (typically bar charts, line plots). This is easy when the plot is itself an individual panel image. Pay attention also to more difficult cases when a plot is only part of a composite panel image. 

Cross-check with the panel classification to avoid common mistakes. 

For each panel in the figure:
- Determine if the plot contains error bars (lines extending from data points indicating variability). These are typically on bar charts, line charts, and sometimes scatter plots.
- *Box plots* and *violin plots*: whiskers and median/mean lines are not classical error bars, but lines, box and whisker elements still require a caption definition (e.g., IQR, percentiles, confidence intervals). For box plots and violin plots, set `error_bar_on_figure` to "yes" and check whether the caption defines the lines,  boxes and whiskers. If undefined, use FAIL.

## Check figure caption for explanation
- If error bars or box-plot elements are present in the panel, check whether the caption explains what they represent (e.g., standard deviation, standard error, confidence interval, IQR, whisker definition).
- If no error bars or box-plot elements apply to the panel, set `error_bar_defined_in_caption`, `from_the_caption`, and `Decision_and_explanation` to "not needed".

*IMPORTANT*: When extracting definitions from the caption, ONLY include the specific text that describes what the error bars or box elements represent (e.g., "standard error of the mean", "standard deviation", "95% confidence interval"). Do NOT include general descriptions of the figure or panel content. It is fine to extract only fragments of a sentence and omit further information about statistical tests. Use plain text only — write `mean +/- SD` not `mean ± SD`.

## Decision and explanation
For each panel, provide `Decision_and_explanation` as a single short string with verdict PASS or FAIL and a concise explanation of whether error bars or box-plot elements are properly defined in the caption.

- Use `"not needed"` for `Decision_and_explanation` when `error_bar_on_figure` is "no".
- Use FAIL when error bars or box-plot whiskers are present but not adequately defined in the caption.

## Please note: 
- If the caption defines error bars for multiple panels, include the same definition for each relevant panel.

- For panels without error bars or box-plot elements to define, set `error_bar_defined_in_caption`,`from_the_caption`, and `Decision_and_explanation` to "not needed".

- Be thorough and precise in your analysis. Include all panels visible in the figure, even if they don't contain error bars.
