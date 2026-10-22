---
name: plot-gap-labeling
description: Check that any discontinuity in a quantitative plot's axis is marked with a visual break indicator.
requires: []
produces:
  - plot-gap-labeling
needs: []
---

# plot-gap-labeling

## Summary
Check whether any axis discontinuities in quantitative plots are properly marked with visual indicators. An unmarked axis break can seriously mislead readers about the relationship between data points — a y-axis that jumps from 30 to 500 with no break marker creates a false impression of the data distribution.

Proceed step-by-step and establish a systematical strategy to be very accurate and avoid mistakes.

## List and classify all figure panels

To be systematic, start from a complete and accurate list of all the figure's panels. Before you do anything else, list every panel and classify it by content type, as follows. Proceed step-by-step and be accurate.

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
- When the image alone leaves the panel structure or sequence unclear, use the
  caption: it usually names the panels in order and says which images belong
  to which panel.

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

Report **every** panel from step 1, in label order, including panels
whose content looks irrelevant to whatever this check is about. This
check decides what is relevant; dropping a panel here silently removes
it from that decision. A panel you cannot classify at all gets `other`, never an empty list.

### 5. How to report it

State the classification in your own reply, as a comma-separated list with one
entry per panel, in label order. Each entry carries two things:

- the panel's label, exactly as you recorded it in step 1;
- every content type you found, from the vocabulary above, as a list.

## Applicability of the check to plots with axes only

Set `is_a_plot_with_axes` to "yes" for a panel whose classification includes `plot` and which is a quantitative plot with labeled axes — bar charts, line plots, scatter plots, box plots and similar visualizations. Set it to "no" otherwise.

For a panel where `is_a_plot_with_axes` is "no", the check does not apply: set `tick_sequence_anomaly`, `gap_visually_marked` and `decision` to "not_applicable", leave `explanation` empty, and skip the next two sections.

## Look for an anomalous jump in the tick labels

For each axis of a quantitative plot, read its tick labels as printed. A consistent sequence is evenly spaced, follows a logarithmic scale, or is otherwise numerically regular. Look specifically for anomalous jumps or skips — labels reading `0, 10, 20, 30, 500`, where the final value is disproportionately large relative to the preceding intervals.

**Categorical axes never count.** An axis whose tick labels are category names — treatment groups, sample names, discrete time points — has no numerical sequence and must never be flagged.

If every axis is consistent, or categorical, set `tick_sequence_anomaly` to "no" and `gap_visually_marked` to "not_required" — there is no gap to mark — and skip the next section.

## Is the gap marked?

Where you found an anomalous jump, set `tick_sequence_anomaly` to "yes" and look at the image for a break indicator at that point — a pair of slanted parallel lines, a zigzag, or a visible gap drawn through the axis or the bars. Set `gap_visually_marked` to "yes" or "no" accordingly.

## Decision and explanation

Put "PASS", "FAIL" or "not_applicable" in `decision`:

- "PASS" — no anomaly, or an anomaly that is visually marked.
- "FAIL" — an anomalous jump with no break indicator. Describe the unmarked gap briefly in `explanation`.
- "not_applicable" — `is_a_plot_with_axes` is "no": the check does not apply to it, so it neither passes nor fails.

Leave `explanation` empty unless `decision` is "FAIL".

## Please note:
- Report every panel of the figure, including panels that are not quantitative plots, which take `is_a_plot_with_axes` "no" and "not_applicable" in `tick_sequence_anomaly`, `gap_visually_marked` and `decision`.
