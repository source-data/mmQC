---
name: do-fig-checklist-cm
description: Run the whole figure checklist on a figure.
requires:
- micrograph-scale-bar
- individual-data-points
- error-bars-defined
produces:
  - do-fig-checklist-cm
needs: []
---

# Do-fig-checklist

## Summary
Run the quality-control checks on a scientific figure and report the result of every check on every figure.

## Run each check

Run the following figure checks on every figure:

- `micrograph-scale-bar`
- `individual-data-points`
- `error-bars-defined`

