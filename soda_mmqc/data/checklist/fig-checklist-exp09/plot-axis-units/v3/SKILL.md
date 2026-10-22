---
name: plot-axis-units
description: Check that the axes of quantitative plots state the units of what they measure.
requires: []
produces:
  - plot-axis-units
needs: []
---

# plot-axis-units

## Summary
Check that the axes of quantitative plots state the units of what they measure, so a reader can tell what the numbers mean.

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

Set `is_a_plot_with_axes` to "yes" for a panel whose classification includes `plot` and which is a plot of quantitative data with drawn axes — XY or XYZ.

Set it to "no" otherwise, including for pie charts, heat maps and sequence alignment plots, and for any plot with no drawn axes.

For a panel where `is_a_plot_with_axes` is "no", the check does not apply: set `decision` to "not_applicable", leave the three axis lists empty, and skip the next section.

## Check each axis for units

For each axis of a quantitative plot, read its title and its tick labels as printed:

- A unit is present when the title names one, whether in brackets or not — `Time (h)`, `Concentration [µM]`, `Intensity (a.u.)`.
- A quantity that is genuinely dimensionless — a ratio, a percentage, a count, a fold change — needs no unit and counts as satisfied. Say so in the explanation.
- A **categorical** axis — its tick labels are category names such as treatment groups or sample names, not numbers — has no units to give, and never fails this check.

**`units_provided`, `unit_definition_as_provided` and `explanation` each hold a list of objects, one per axis** — not single values for the panel, and not lists of bare strings. Every entry names the axis it describes, as `x`, `y` or `z`:

- `units_provided` — `{"axis": "y", "answer": "yes"}`, where `answer` is "yes", "no", or "not_required" for an axis that needs no unit (a categorical axis, or a dimensionless quantity such as a ratio, percentage, count or fold change).
- `unit_definition_as_provided` — `{"axis": "y", "definition": "%"}`, the unit exactly as printed. Transcribe rather than normalise; use an empty string where there is none.
- `explanation` — `{"axis": "y", "explanation": "percentage is dimensionless"}`, a brief per-axis reason.

Cover the same axes in all three lists.

## Decision and explanation

`decision` is a single value for the panel, not a list. Put "PASS", "FAIL" or "not_applicable" in it:

- "PASS" — every axis that needs a unit has one.
- "FAIL" — any numeric axis measuring a dimensional quantity has no unit.
- "not_applicable" — `is_a_plot_with_axes` is "no": the check does not apply to it, so it neither passes nor fails.

## Please note:
- Report every panel of the figure, including panels that are not quantitative plots with axes, which take `is_a_plot_with_axes` "no", `decision` "not_applicable" and empty axis lists.
