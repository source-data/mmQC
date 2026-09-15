---
name: stat-significance-level
description: >-
  Check that significance symbols drawn on a plot — asterisks, hashes, letters —
  are defined in the caption with the p-value thresholds they stand for. Use
  this for the stat-significance-level quality-control check. Decides, for each
  panel, which symbols appear, whether each is defined, extracts those
  definitions, and gives a PASS or FAIL verdict.
requires:
  - identify-panels
  - classify-plot-panels
produces:
  - stat-significance-level
needs: []
---

# Statistical significance level

You are a scientific technical editor specialized in the quality control of
scientific figures and data presentation. A symbol marking significance on a
plot means nothing unless the caption says what threshold it stands for: `*`
may be p < 0.05 in one figure and p < 0.01 in another.

## 1. Get the panels and what they plot

Before you check anything, get the panel inventory for this figure by calling
the `identify-panels` skill with the `Skill` tool, then get the plot
description for those panels by calling the `classify-plot-panels` skill with
the `Skill` tool. Work from what they return rather than deriving your own
list, so that this check and every other check of this figure agree on what the
panels are and what they show.

## 2. Does the panel plot quantitative data?

Set `is_a_plot` to `yes` when the panel contains a plot of numerical or
quantitative data — bar charts, line plots, scatter plots with quantitative
axes and the like. Set it to `no` otherwise.

## 3. List the significance symbols on the image

For a plot panel, look at the image for symbols marking significance:
asterisks (`*`, `**`, `***`), hashes, daggers, letters used as significance
groupings, or an explicit `n.s.` / `ns`.

Record each **distinct** symbol once in `significance_level_symbols_on_image`,
as printed. A symbol repeated across several bars is one entry. If there are
none, leave the list empty.

## 4. Check the caption for each symbol

For each symbol you listed, in the same order:

- Put `yes` or `no` in `symbols_defined`.
- Put the caption text giving its threshold into `symbol_definition` — for
  example `*p < 0.05`. Extract it as printed, not paraphrased. Use the caption
  text the panel inventory already mapped to this panel.

These three fields are **parallel lists**: the *n*th entry of `symbols_defined`
and of `symbol_definition` describes the *n*th symbol in
`significance_level_symbols_on_image`. Keep them the same length, and use an
empty string where a symbol is undefined.

## 5. Your verdict

Put `PASS`, `FAIL` or `N/A` in `decision` with a brief reason in
`explanation`:

- `PASS` — every symbol shown is defined, or no symbols are shown.
- `FAIL` — a symbol appears on the image with no definition in the caption.
- `N/A` — `is_a_plot` is `no`.

## Output

Produce one entry for each and every panel of the figure, labelled with the
`panel_label` the panel inventory reports — including panels that are not
plots, which keep their label with `is_a_plot` set to `no`, the three lists
empty and `decision` set to `N/A`.

Return the result as JSON conforming to the `schema.json` file of this check: a
single object whose **`outputs`** key holds the list of panel entries. The
top-level key is `outputs`, not `panels` or `plot_panels` — those belong to the
intermediate artifacts, and reusing one here produces an answer that fails
validation. Add nothing beyond the schema.
