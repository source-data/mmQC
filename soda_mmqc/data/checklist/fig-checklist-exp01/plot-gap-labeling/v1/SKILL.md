---
name: plot-gap-labeling
description: Check that a break in a plot's axis scale is marked, so the jump is not read as continuous.
requires: []
produces:
  - plot-gap-labeling
needs: []
---

# plot-gap-labeling

## Summary
You are a scientific technical editor specializing in the quality control of scientific figures and data presentation. Your task is to check whether any axis discontinuities in quantitative plots are properly marked with visual indicators. An unmarked axis break can seriously mislead readers about the relationship between data points.

## Logic
IF panel is not a quantitative plot:
    SET is_a_plot = "no"
    SET tick_sequence_anomaly = "not_applicable"
    SET gap_visually_marked = "not_applicable"
    SET decision = "N/A"
    SET explanation = ""
    CONTINUE to next panel

SET is_a_plot = "yes"

# Step 1: Check tick label sequence on each axis
IF tick labels on all axes form a consistent numerical sequence
(evenly spaced, logarithmic, or otherwise regular):
    SET tick_sequence_anomaly = "no"
    SET gap_visually_marked = "not_applicable"
    SET decision = "PASS"
    SET explanation = ""
    CONTINUE to next panel
Note: Categorical axes (e.g. treatment groups, sample names, time points as discrete categories) do not have a numerical sequence and should never be flagged as anomalies.

# Step 2: Anomaly detected — is it visually marked?
IF any axis shows anomalous tick label jump or skip
(e.g. 0, 10, 20, 30, 500):
    SET tick_sequence_anomaly = "yes"

    IF axis break is visually marked
    (diagonal lines, zigzag marks, or similar indicators):
        SET gap_visually_marked = "yes"
        SET decision = "PASS"
        SET explanation = ""

    ELSE:
        SET gap_visually_marked = "no"
        SET decision = "FAIL"
        SET explanation = "describe which axis and what the sequence anomaly is"

## Examples

#### Example 1 — Unlabeled gap detected (FAIL)
```json
```

#### Example 2 — Gap present and properly marked (PASS)
```json
```

#### Example 3 — No anomaly detected (PASS)
```json
```

#### Example 4 — Non-plot panel (N/A)
```json
```
