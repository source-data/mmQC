---
name: stat-test
description: Check that a panel claiming statistical significance names the statistical test behind the claim.
requires:
  - classify-panels
produces:
  - stat-test
needs: []
---

# stat-test

## Summary
Where a figure asserts statistical significance, it must say which test produced that assertion; otherwise the claim cannot be evaluated.

Proceed step-by-step and establish a systematical strategy to be very accurate and avoid mistakes.

## List and classify all figure panels

To be systematic, start from a complete and accurate list of all the figure's panels. Before you do anything else, invoke the `classify-panels` skill with the `Skill` tool to list every panel and classify it by content type.

## Applicability of the check to plots only

Set `is_a_plot` to "yes" for a panel whose classification includes `plot`, alone or beside other content types, and to "no" otherwise.

For a panel that is not a plot, the check does not apply: set `statistical_significance_claim`, `statistical_test_mentioned` and `decision` to "not_applicable", leave `from_the_caption` and `explanation` empty, and skip the next two sections.

## Does the panel claim statistical significance?

Set `statistical_significance_claim` to "yes" if the panel, or the caption text about it, marks or states statistical significance — p-values, significance stars or other significance symbols, `ns`, a claim of a significant difference — and to "no" otherwise. This asks only what the figure shows, not whether its data would call for a statistical analysis. **Error bars alone are not a significance claim.**

If the panel makes no claim, no test needs to be named: set `statistical_test_mentioned` to "not_required", leave `from_the_caption` empty, and skip the next section.

## Is the test named?

Where the panel claims significance, check the caption for the name of the test — t-test, ANOVA, Mann-Whitney, and so on. Put "yes" or "no" in `statistical_test_mentioned`, and the exact caption text naming it in `from_the_caption`. Remember that one caption sentence can cover several panels.

## Decision and explanation

Put "PASS", "FAIL" or "not_applicable" in `decision`, with a brief reason in `explanation`.

- If the panel claims significance and the caption names the test, `decision` is "PASS".
- If it claims significance without naming a test, `decision` is "FAIL".
- If the panel is a plot that makes no significance claim, no test is needed, so `decision` is "PASS".
- If the panel is not a plot, `decision` is "not_applicable": the check does not apply to it, so it neither passes nor fails.

## Please note:
- Report every panel of the figure, including panels that are not plots, which take "not_applicable" as above.
