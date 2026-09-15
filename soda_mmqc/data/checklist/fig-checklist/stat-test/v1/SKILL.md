---
name: stat-test
description: >-
  Check that figures claiming statistical significance say which statistical
  test produced it. Use this for the stat-test quality-control check. Decides,
  for each panel, whether it plots quantitative data, whether a significance
  claim makes a test mandatory, whether the caption names one, extracts that
  text, and gives a PASS or FAIL verdict.
requires:
  - identify-panels
  - classify-plot-panels
produces:
  - stat-test
needs: []
---

# Statistical test mentioned

You are a scientific technical editor specialized in the quality control of
scientific figures and data presentation. Where a figure asserts statistical
significance, it must say which test produced that assertion; otherwise the
claim cannot be evaluated.

## 1. Get the panels and what they plot

Before you check anything, get the panel inventory for this figure by calling
the `identify-panels` skill with the `Skill` tool, then get the plot
description for those panels by calling the `classify-plot-panels` skill with
the `Skill` tool. Work from what they return rather than deriving your own
list, so that this check and every other check of this figure agree on what the
panels are and what they show.

## 2. Does the panel plot quantitative data?

Set `is_a_plot` to `yes` for a plot of quantitative data. **This check reads
that broadly**: plots with XY or XYZ axes, bar charts, line charts, any scatter
plots including FACS analyses, histograms, **pie charts**, box plots,
**heatmaps**, area charts, bubble charts, violin plots, radar charts, treemaps,
waterfall charts, funnel charts, dot plots, Sankey diagrams, contour plots,
density plots, polar charts and similar all count. Note this is deliberately
wider than some other checks — a pie chart is in scope here even where another
check excludes it.

**A plot included inside a schematic or workflow diagram for illustration is
not quantitative data** — it is an illustration. The plot description says when
that is the case; take it into account before analysing the panel.

If `is_a_plot` is `no`, set `statistical_test_needed` to `no`,
`statistical_test_mentioned` to `not needed`, `from_the_caption` to an empty
string, `decision` to `PASS` and `explanation` to an empty string.

## 3. Is a test mandatory for this panel?

A test must be named **only** where there is a statement of statistical
significance — p-values, significance stars, a claim of a significant
difference. Set `statistical_test_needed` accordingly.

**The mere presence of error bars does NOT imply statistical analysis and does
NOT require a statistical test.** If the panel plots quantitative data but
makes no significance claim, use the same values as for a non-plot panel.

## 4. Is the test named?

Where a test is needed, check the caption for its name — t-test, ANOVA,
Mann-Whitney, and so on. Put `yes`, `no` or `not needed` in
`statistical_test_mentioned`, and the exact caption text naming it in
`from_the_caption`. Use the caption text the panel inventory already mapped to
this panel.

## 5. Your verdict

Put `PASS` or `FAIL` in `decision` with a brief reason in `explanation`. A
panel that claims significance without naming a test is a FAIL; everything else
is a PASS.

## Output

Produce one entry for each and every panel of the figure, labelled with the
`panel_label` the panel inventory reports — including panels that plot no
quantitative data.

Return the result as JSON conforming to the `schema.json` file of this check: a
single object whose **`outputs`** key holds the list of panel entries. The
top-level key is `outputs`, not `panels` or `plot_panels` — those belong to the
intermediate artifacts, and reusing one here produces an answer that fails
validation. Add nothing beyond the schema.
