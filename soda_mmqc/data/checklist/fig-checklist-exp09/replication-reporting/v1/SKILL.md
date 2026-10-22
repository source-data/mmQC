---
name: replication-reporting
description: Check that panels showing replicated data report the number of replicates and what they represent.
requires:
  - classify-panels
produces:
  - replication-reporting
needs: []
---

# replication-reporting

## Summary
Replicates allow researchers to estimate the sources of variability in measurements and observations. For panels derived from replicated observations, the figure caption should state the number of replicates — `n = 3`, `five animals` — and what they represent: biological replicates, technical replicates, animals, cells.

Proceed step-by-step and establish a systematical strategy to be very accurate and avoid mistakes.

## List and classify all figure panels

To be systematic, start from a complete and accurate list of all the figure's panels. Before you do anything else, invoke the `classify-panels` skill to list every panel and classify it by content type.

## Applicability of the check to panels involving replicates

Set `involves_replicates` to:

- "yes" — the panel shows replicated quantitative data: bar charts with error bars, box plots, violin plots, scatter plots with statistics, survival curves, dose-response curves, quantified microscopy data, or **any panel carrying p-values or statistical tests**. Most panels whose classification includes `plot` are in this case, but not all, and a quantified micrograph can be.
- "no" — the panel shows non-replicated content: schematics, workflows, representative images without quantification, model diagrams, representative blots.
- "unclear" — you genuinely cannot tell. Do not force it either way.

When `involves_replicates` is "no" or "unclear", the check does not apply: set `n_reported`, `replicate_type_reported`, `n_value_min` and `decision` to "not_applicable", leave `replicate_statements` empty and `replicate_type` an empty string, and skip the next section.

## Extract the replicate information

When `involves_replicates` is "yes", search **both the figure image and the caption** for:

- an n-number — `n = 3`, `five animals`, `n = 3-5`;
- a replicate type — `biological replicates`, `independent experiments`, `cells`, `animals`.

**Extract verbatim and minimally. Do not paraphrase.** Put each statement you find into `replicate_statements`.

- If a range is reported (`n = 3-5`), set `n_value_min` to the lower bound.
- If several conditions report different n, list them all in `replicate_statements` and set `n_value_min` to the lowest.
- Set `n_reported` and `replicate_type_reported` to "yes" or "no", and put the type itself in `replicate_type`. If no n-number is reported, set `n_value_min` to "not_reported"; if no type is reported, leave `replicate_type` an empty string.

## Decision and explanation

Put "PASS", "FAIL" or "not_applicable" in `decision`, with a brief reason in `explanation`.

- A panel involving replicates that reports **both** the n-number and the replicate type is a "PASS". Whether n is large enough is not this check's question.
- A panel involving replicates that is missing either is a "FAIL" — say which.
- A panel not involving replicates, or where you cannot tell, is "not_applicable": the check does not apply to it, so it neither passes nor fails.

## Please note:
- Report every panel of the figure, including panels that involve no replicates, which take "not_applicable" as above.
