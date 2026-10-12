---
name: plot-axis-units
description: Check that the axes of quantitative plots state the units of what they measure.
requires:
  - classify-panels
produces:
  - plot-axis-units
needs: []
---

# plot-axis-units

## Summary
Check that the axes of quantitative plots state the units of what they measure, so a reader can tell what the numbers mean.

Proceed step-by-step and establish a systematical strategy to be very accurate and avoid mistakes.

## List and classify all figure panels

To be systematic, start from a complete and accurate list of all the figure's panels. Before you do anything else, invoke the `classify-panels` skill to list every panel and classify it by content type.

## Applicability of the check to plots with axes only

Set `is_a_plot_with_axes` to "yes" for a panel whose classification includes `plot` and which is a plot of quantitative data with drawn axes — XY or XYZ.

Set it to "no" otherwise, including for pie charts, heat maps and sequence alignment plots, and for any plot with no drawn axes.

For a panel where `is_a_plot_with_axes` is "no", the check does not apply: set `decision` to "not_applicable", leave the three axis lists empty, and skip the next section.

## Check each axis for units

For each axis of a quantitative plot, read its title and its tick labels as printed:

- A unit is present when the title names one, whether in brackets or not — `Time (h)`, `Concentration [µM]`, `Intensity (a.u.)`.
- A quantity that is genuinely dimensionless — a ratio, a percentage, a count, a fold change — needs no unit and counts as satisfied. Say so in the explanation.
- A **categorical** axis — its tick labels are category names such as treatment groups or sample names, not numbers — has no units to give, and never fails this check.

**`units_provided`, `unit_definition_as_provided` and `explanation` each hold a list of objects, one per axis** — not single values for the panel, and not lists of bare strings. Every entry names the axis it describes, as `x`, `y` or `z`:

- `units_provided` — `{"axis": "y", "answer": "yes"}`, where `answer` is "yes", "no", or "not_required" for an axis that needs no unit (a categorical axis, or a dimensionless quantity such as a ratio, percentage, count or fold change).
- `unit_definition_as_provided` — `{"axis": "y", "definition": "%"}`, the unit exactly as printed. Transcribe rather than normalise; use an empty string where there is none.
- `explanation` — `{"axis": "y", "explanation": "percentage is dimensionless"}`, a brief per-axis reason.

Cover the same axes in all three lists.

## Decision and explanation

`decision` is a single value for the panel, not a list. Put "PASS", "FAIL" or "not_applicable" in it:

- "PASS" — every axis that needs a unit has one.
- "FAIL" — any numeric axis measuring a dimensional quantity has no unit.
- "not_applicable" — `is_a_plot_with_axes` is "no": the check does not apply to it, so it neither passes nor fails.

## Please note:
- Report every panel of the figure, including panels that are not quantitative plots with axes, which take `is_a_plot_with_axes` "no", `decision` "not_applicable" and empty axis lists.
