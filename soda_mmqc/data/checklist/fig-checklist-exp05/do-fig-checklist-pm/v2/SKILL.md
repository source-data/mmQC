---
name: do-fig-checklist-pm
description: Run the whole figure checklist on a figure.
requires:
- classify-panels
- micrograph-scale-bar
- individual-data-points
- error-bars-defined
produces:
  - do-fig-checklist-pm
needs: []
---

# Do-fig-checklist

## Summary
Run the quality-control checks on a scientific figure and report the result of every check on every figure.

## 1. Identify and classify the panels

Before running any check, invoke the `classify-panels` skill once. It identifies every panel of the figure and the kinds of content each shows. Every check below works from that panel list.

## 2. Run each check

Then run the following figure checks, in this order:

- `micrograph-scale-bar`
- `individual-data-points`
- `error-bars-defined`
