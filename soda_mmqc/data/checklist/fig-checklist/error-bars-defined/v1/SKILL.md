---
name: error-bars-defined
description: >-
  Check that error bars and box-plot elements shown in a figure are defined in
  its caption. Use this for the error-bars-defined quality-control check.
  Decides, for each panel, whether error bars or box/whisker elements are
  present, whether the caption says what they represent, extracts that
  definition, and gives a PASS or FAIL verdict.
requires:
  - identify-panels
  - classify-plot-panels
produces:
  - error-bars-defined
needs: []
---

# Error bars defined

You are a scientific technical editor specializing in the quality control of
scientific figures and data presentation. Your task is to analyze a scientific
figure and its caption to verify that error bars are present where expected and
are properly defined.

Error bars convey the variability or uncertainty of the data and let a reader
interpret the result correctly. It matters equally that they are defined in the
caption, because the choice of metric changes the interpretation — mean +/- SD
says something different from median +/- 2x SD. These details are small,
consequential, and easy to miss during figure preparation.

## 1. Get the panels and what they plot

Before you check anything, get the panel inventory for this figure by calling
the `identify-panels` skill with the `Skill` tool, then get the plot
description for those panels by calling the `classify-plot-panels` skill with
the `Skill` tool. Work from what they return rather than deriving your own
list, so that this check and every other check of this figure agree on what the
panels are and what they show.

Work through the panels in order.

## 2. Are error bars or box-plot elements present?

Look for lines extending from data points indicating variability — common on
bar charts, line plots, and any plot showing aggregated or averaged data. The
plot description tells you which panels those are; the presence of the bars
themselves is something you must see in the image.

**Box plots and violin plots:** whiskers and median/mean lines are not classical
error bars, but the lines, box and whisker elements still require a caption
definition — IQR, percentiles, confidence intervals. For a box or violin plot
set `error_bar_on_figure` to `yes` and check whether the caption defines the
lines, boxes and whiskers. If it does not, the verdict is FAIL.

## 3. Is it defined in the caption?

If error bars or box-plot elements are present, check whether the caption says
what they represent — standard deviation, standard error, confidence interval,
IQR, whisker definition.

- Put `yes` or `no` in `error_bar_defined_in_caption`.
- Extract **only the specific defining words** into `from_the_caption`: a
  fragment is fine, and unrelated statistical-test descriptions are not part of
  it. Extract `mean +/- SD`, not the sentence around it. Use the caption text
  the panel inventory already mapped to this panel.
- **Use plain text only** — write `mean +/- SD`, never `mean ± SD`.
- If error bars are absent from the figure but mentioned in the caption, note
  that mismatch in the explanation.
- If no error bars or box-plot elements apply to the panel, set
  `error_bar_defined_in_caption`, `from_the_caption` and
  `Decision_and_explanation` to `not needed`. **`error_bar_on_figure` is not
  one of them** — it takes only `yes` or `no`, and for such a panel it is
  `no`. `not needed` is not a permitted value there and will fail validation.

## 4. Your verdict

Give a brief `PASS` or `FAIL` with a one-line explanation in
`Decision_and_explanation`, in plain text. Use `not needed` when
`error_bar_on_figure` is `no`.

## Output

Produce one entry for each and every panel of the figure, labelled with the
`panel_label` the panel inventory reports — including panels with no error
bars, which keep their label and take `not needed` in the three fields above.

Return the result as JSON conforming to the `schema.json` file of this check: a
single object whose **`outputs`** key holds the list of panel entries. The
top-level key is `outputs`, not `panels` or `plot_panels` — those belong to the
intermediate artifacts, and reusing one here produces an answer that fails
validation. Add nothing beyond the schema.
