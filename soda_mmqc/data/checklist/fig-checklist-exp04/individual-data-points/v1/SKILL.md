---
name: individual-data-points
description: Check that a plot showing averages also shows the individual data points behind them.
requires: []
produces:
  - individual-data-points
needs: []
---

# indiviual-data-points

## Summary
Check whether plots showing averaged or aggregated data also display the underlying individual data points.

Showing individual data points alongside summary statistics is important because it allows the reader to assess the spread and variability of the raw measurements, and to judge how robust a result truly is. Plotting only averages can obscure low replication numbers, outliers, or large variability — details that are critical for interpreting the reliability of a finding.

## Classify figure panels

To decide when the check is applicable or not, classify panels based on content type before you do anything else. Proceed step-by-step and be accurate.

### 1. Get all the panels

Understand the figure image and see where there are figure sub-parts or
"panels". Each panel depicts an experiment either with a plot, a micrograph,
some other kinds of images, a scheme.

- Panels are typically labeled with consecutive letters (for example: A, B, C,
  ... or (a), (b), (c)).
- There are sometimes subpanels. For example "a)", "a')", "a'')" or "Ai)", "Aii)", "Aiii)" or "B top", "B bottom" or "C left", "C right". Consider them as individual panels.
- The first panel is usually on the top left. The last panel tends to be on the
  bottom right. Sometimes the layout is however a bit messy.
- Record the label without its brackets, so that `(a)` is reported as `a`.
  Report the labels the figure actually carries: do not invent, reorder or
  renumber them.
- Sometimes one panel can include several images. For example, a panel can include both a microscopy image and a plot that typically displays a
quantification of some features shown on the image.

You must analyze each labeled panel independently, even if panels are related.

### 2. Name every content type in the panel

Classify each panel using the following types:

| type | what it covers |
|---|---|
| `micrograph` | anything imaged through a microscope — light, phase-contrast, fluorescence, confocal, electron micrograph, kymograph |
| `plot` | data presented against axes or categories - bar, line, scatter, box,
violin, histogram, pie, donut charts, heatmaps |
| `blot` | a gel-based result — western, northern or southern blot, SDS-PAGE or agarose gel, autoradiograph, Coomassie stain |
| `molecular_or_protein_structure` | a rendering of the three-dimensional structure of a molecule — protein ribbon, cartoon or surface representation; a small molecule or chemical structure; a nucleic acid or a complex; a crystal structure, a cryo-EM density map, a docking pose or a predicted model |
| `sequence` | DNA, RNA or protein sequence shown as letters — a raw or annotated sequence, a region with mutations marked, a primer or guide design, a multiple sequence alignment |
| `schematic` | a drawing that explains rather than presents measured data — experimental design, model, pathway, cartoon, timeline |
| `photograph` | a macroscopic photograph — whole organism, culture plate, tissue specimen, apparatus |
| `table` | values laid out in labelled rows and columns rather than drawn |
| `other` | anything the list above does not cover.|


Note of caution: **A plot drawn inside a schematic, for illustration rather than to
  present data, is not a plot.** An idealised curve in a model diagram, a sketched bar
  chart in an experimental-design cartoon: report `schematic` alone.

### 3. A panel can hold several things

**Report every type present, not the single most prominent one.** A micrograph
beside the bar chart quantifying it is "micrograph, plot". A blot above
the densitometry of its own bands is "blot, plot". A structure shown next
to the binding curve that supports it is
"molecular_or_protein_structure, plot".

Dropping the second type silently removes that panel from whichever check cares
about it.

### 4. Report every panel

Report **every** panel from the inventory, in label order, including panels
whose content looks irrelevant to whatever the calling skill is checking. The
calling skill decides what is relevant; dropping a panel here silently removes
it from that decision. A panel you cannot classify at all gets `other`, never an empty list.


### 5. How to report it

State the classification in your own reply, as a comma-separated list with one
entry per panel, in label order. Each entry carries two things:

- the panel's label, exactly as the inventory gave it;
- every content type you found, from the vocabulary above, as a list.

## Applicability of the check to plots only

Set `plot` to "yes" for a panel whose classification includes `plot`, alone or beside other content types, and to "no" otherwise. Pay attention to plots that show error bars, typically bar charts, or that show mean values: those are the ones this check is about.

For a panel that is not a plot, this check does not apply: set `individual_values` and `decision` to "not_applicable". You can skip the next two sections and jump to "Decision and explanation".

## Does this plot type require individual data points?

The check applies primarily to *bar charts* showing means or medians.

But not all plots require individual data points to be overlaid. The following plot types are exempt: set `individual_values` to "not_required".

- Box plots and violin plots — these already display the data distribution
- Heatmaps — individual points are not meaningful in this context
- Line plots — overlaying individual points typically makes these unreadable
- Kaplan-Meier curves — they show survival over time, not averages
- Pie charts, Venn diagrams — do not need individual data points
- Scatter plots — individual points are the data

Cross-check with the panel classification to avoid common mistakes.

## Are individual data points shown?
For plots that are not exempt, check whether the individual data points are overlaid on the summary visualization — typically as dots, circles, or similar markers.

- If they are, set `individual_values` to "yes".
- If the plot summarises data, for instance a bar chart of means with error bars, and the individual measurements are not shown, set `individual_values` to "no".

## Decision and explanation
For each panel, put `PASS`, `FAIL` or `not_applicable` in `decision`, and a one-line reason in `explanation`, in plain text.

- If `individual_values` is "yes" or "not_required", `decision` is `PASS`.
- If `individual_values` is "no", `decision` is `FAIL`: the panel should show its individual data points and does not.
- If the panel is not a plot, `decision` is `not_applicable`: the check does not apply to it, so it neither passes nor fails.

## Please note:
- Report every panel of the figure, including panels that are not plots, which take `not_applicable`, and exempt plots, which take `not_required` and `PASS`.
