---
name: do-fig-checklist-cm
description: Run the whole figure checklist on a figure.
requires:
- micrograph-scale-bar
- image-annotation-defined
- single-channel-for-overlay
- individual-data-points
- error-bars-defined
- plot-axis-units
- plot-gap-labeling
- stat-significance-level
- stat-test
- replication-reporting
- panel-image-matches-caption
produces:
  - do-fig-checklist-cm
needs: []
---

# Do-fig-checklist

## Summary
Run the quality-control checks on a scientific figure and report the result of every check on every figure.

## Run each check

Run the following figure checks on the figure, in this order. Run each one by invoking its skill with the `Skill` tool, one at a time, and report its result as the skill returns it:

- `micrograph-scale-bar`
- `image-annotation-defined`
- `single-channel-for-overlay`
- `individual-data-points`
- `error-bars-defined`
- `plot-axis-units`
- `plot-gap-labeling`
- `stat-significance-level`
- `stat-test`
- `replication-reporting`
- `panel-image-matches-caption`
