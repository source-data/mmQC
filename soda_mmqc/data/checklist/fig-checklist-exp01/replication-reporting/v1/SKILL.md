---
name: replication-reporting
description: Check that a panel with replicated data reports how many replicates and of what kind.
requires: []
produces:
  - replication-reporting
needs: []
---

# replication-reporting
## Summary

You are a scientific technical editor performing quality control of scientific figures and figure legends. Your task is to evaluate whether each figure panel clearly reports the number and type of replicates used to generate the data.
Replicates allow readers to understand the reliability and reproducibility of experimental results. For panels derived from replicated observations, the figure legend should clearly state the number of replicates (e.g. n = 3, five animals) and what they represent (e.g. biological replicates, technical replicates, animals, cells).

## Logic
FOR each panel in figure:

    # Step 1: Determine applicability
    IF panel shows replicated quantitative data (bar charts, error bars, boxplots,
       violin plots, scatter plots with stats, survival curves, dose-response curves,
       quantified microscopy data, any panel with p-values or statistical tests):
        SET involves_replicates = "yes"

    ELSE IF panel shows non-replicated content (schematics, workflows, 
       representative images without quantification, model diagrams, 
       representative blots):
        SET involves_replicates = "no"

    ELSE:
        SET involves_replicates = "unclear"

    # Step 2: Extract replicate information
    IF involves_replicates == "yes":
        SEARCH figure image AND figure legend for:
            - n-number (e.g. "n = 3", "five animals", "n = 3-5")
            - replicate type (e.g. "biological replicates", "independent experiments", "cells")
        
        EXTRACT verbatim, minimally — do not paraphrase
        IF range reported (e.g. n = 3-5):
            SET n_value_min = lower bound (3)
        IF multiple conditions with different n:
            REPORT all values in replicate_statements
            SET n_value_min = lowest reported value

    ELSE:
        SET n_reported = "not_applicable"
        SET n_value_min = "not_applicable"
        SET replicate_type_reported = "not_applicable"

    # Step 3: Decision
    IF involves_replicates == "no":
        SET decision = "PASS"  # nothing to report

    ELSE IF involves_replicates == "unclear":
        SET decision = "FAIL"

    ELSE IF involves_replicates == "yes":

        IF n_reported == "no":
            SET decision = "FAIL"  # missing n-number

        ELSE IF replicate_type_reported == "no":
            SET decision = "FAIL"  # missing replicate type

        ELSE IF n_value_min <= 2 AND panel shows summary statistics or statistical tests:
            SET decision = "FAIL"  # n too low for summary stats

        ELSE IF n_value_min <= 2 AND panel shows only representative data (no stats):
            SET decision = "PASS"  # acceptable for representative panels

        ELSE IF n_value_min > 2 AND n_reported == "yes" AND replicate_type_reported == "yes":
            SET decision = "PASS"

## Examples

### Example 1 — PASS

Figure legend states: `Data are mean ± SEM from n = 3 independent biological experiments.`

```json
```

### Example 2 — FAIL

Figure legend states: `Data are mean ± SD, n = 2.`

```json
```

### Example 3 — PASS

Panel is a representative microscopy image with no quantification.

```json
```
