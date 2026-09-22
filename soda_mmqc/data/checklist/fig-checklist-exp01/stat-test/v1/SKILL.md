---
name: stat-test
description: Check that a plot claiming statistical significance names the test used.
requires: []
produces:
  - stat-test
needs: []
---

# stat-test
## Summary
You are a scientific technical editor specializing in the quality control of scientific figures and data presentation. Your task is to check whether figure panels that report statistical significance also state which statistical test was used. Reporting significance indicators without naming the test is incomplete and does not allow the reader to evaluate the validity of the analysis.

## Guidelines
### Step 1 — Is this a numerical plot?
Determine whether the panel contains a plot of quantitative data. Bar charts, line plots, scatter plots, box plots, and similar visualizations qualify. Micrographs, schematics, western blots, and representative images do not. Set `is_a_plot` to `"yes"` or `"no"` accordingly. For all `"no"` panels, set `statistical_test_needed` to `"no"`, `statistical_test_mentioned` to `"not needed"`, `from_the_caption` to `""`, `decision` to `"PASS"`, and `explanation` to `""`.

### Step 2 — Is a statistical test needed?
A statistical test is needed when the panel contains any indicator of statistical significance — asterisks (*, **, ***), ns, exact p-values (p = 0.003), or similar annotations. If none of these are present, set `statistical_test_needed` to `"no"`, `statistical_test_mentioned` to `"not needed"`, `from_the_caption` to `""`, `decision` to `"PASS"`, and `explanation` to `""`.

### Step 3 — Is the statistical test mentioned in the caption?
If a test is needed, check whether the caption names the statistical test used (e.g. Student's t-test, Mann-Whitney U, ANOVA). Extract only the minimal phrase naming the test — do not include surrounding context or general panel descriptions. Use plain ASCII text only.

- If mentioned → `statistical_test_mentioned` = `"yes"`, fill `from_the_caption`, `decision` = `"PASS"`, `explanation` = `""`
- If not mentioned → `statistical_test_mentioned` = `"no"`, `from_the_caption` = `""`, `decision` = `"FAIL"`, and provide a brief rationale in `explanation`

### Examples  

*Example 1 — Test needed and mentioned (PASS)*  

*Example 2 — Test needed but not mentioned (FAIL)*  

*Example 3 — No test needed (PASS)*  

*Example 4 — Non-plot panel (PASS)*
