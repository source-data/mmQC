---
name: stat-significance-level
description: Check that significance symbols shown on plots, such as asterisks, are defined in the caption.
requires:
  - classify-panels
produces:
  - stat-significance-level
needs: []
---

# stat-significance-level

## Summary
A symbol marking significance on a plot means nothing unless the caption says what threshold it stands for: `*` may be p < 0.05 in one figure and p < 0.01 in another.

Proceed step-by-step and establish a systematical strategy to be very accurate and avoid mistakes.

## List and classify all figure panels

To be systematic, start from a complete and accurate list of all the figure's panels. Before you do anything else, invoke the `classify-panels` skill with the `Skill` tool to list every panel and classify it by content type.

## Applicability of the check to plots only

Set `is_a_plot` to "yes" for a panel whose classification includes `plot`, alone or beside other content types, and to "no" otherwise.

For a panel that is not a plot, the check does not apply: leave the three symbol lists empty, set `decision` to "not_applicable", leave `explanation` empty, and skip the next two sections.

## List the significance symbols on the image

For a plot panel, look at the image for symbols marking significance: asterisks (`*`, `**`, `***`), hashes, daggers, letters used as significance groupings, or an explicit `n.s.` / `ns`.

Record each **distinct** symbol once in `significance_level_symbols_on_image`, as printed. A symbol repeated across several bars is one entry. If there are none, leave the list empty and skip the next section.

## Check the caption for each symbol

For each symbol you listed, in the same order:

- Put "yes" or "no" in `symbols_defined`.
- Put the caption text giving its threshold into `symbol_definition` — for example `*p < 0.05`. Extract it as printed, not paraphrased. Remember that one caption sentence can cover several panels.

These three fields are **parallel lists**: the *n*th entry of `symbols_defined` and of `symbol_definition` describes the *n*th symbol in `significance_level_symbols_on_image`. Keep them the same length, and use an empty string where a symbol is undefined.

## Decision and explanation

Put "PASS", "FAIL" or "not_applicable" in `decision`, with a brief reason in `explanation`:

- "PASS" — every symbol shown is defined, or the plot shows no significance symbols.
- "FAIL" — a symbol appears on the image with no definition in the caption.
- "not_applicable" — `is_a_plot` is "no": the check does not apply to it, so it neither passes nor fails.

## Please note:
- Report every panel of the figure, including panels that are not plots, which take `is_a_plot` "no", the three lists empty and `decision` "not_applicable".
