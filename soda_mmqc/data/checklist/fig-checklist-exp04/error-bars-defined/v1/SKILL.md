---
name: error-bars-defined
description: Check that error bars, and box or violin plot elements, are explained in the caption.
requires: []
produces:
  - error-bars-defined
needs: []
---

# error-bars-defined

## Summary
Analyze a scientific figure and its caption to check for the presence of error bars and whether they are properly defined.

Proceed step-by-step and establish a systematical structured strategy to be very accurate and avoid mistakes.

## Classify figure panels

To decide when the check is applicable or not, classify panels based on content type before you do anything else. Proceed step-by-step and be accurate.

### 1. Get the panels

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

## Is the panel a plot?

Set `is_a_plot` to "yes" for a panel whose classification includes `plot`, alone or beside other content types, and to "no" otherwise.

For a panel that is not a plot, this check does not apply: set
`error_bar_on_figure`, `error_bar_defined_in_caption` and `decision` to "not_applicable", and leave `from_the_caption` empty. You can skip the next two sections and jump to "Decision and explanation".

## Determine if the panel contains error bars or box-plot elements to define
Your job is to pay attention to any plots that have error bars (typically bar charts, line plots). This is easy when the plot is itself an individual panel image. Pay attention also to more difficult cases when a plot is only part of a composite panel image.

Cross-check with the panel classification to avoid common mistakes.

For each plot in the figure:
- Determine if the plot contains error bars (lines extending from data points indicating variability). These are typically on bar charts, line charts, and sometimes scatter plots.
- *Box plots* and *violin plots*: whiskers and median/mean lines are not classical error bars, but lines, box and whisker elements still require a caption definition (e.g., IQR, percentiles, confidence intervals). For box plots and violin plots, set `error_bar_on_figure` to "yes" and check whether the caption defines the lines,  boxes and whiskers. If undefined, use FAIL.

## Check figure caption for explanation
- If error bars or box-plot elements are present in the panel, check whether the caption explains what they represent (e.g., standard deviation, standard error, confidence interval, IQR, whisker definition). Put "yes" or "no" in `error_bar_defined_in_caption`.
- If a plot has no error bars or box-plot elements, there is nothing to define: set `error_bar_on_figure` to "no", `error_bar_defined_in_caption` to "not_required", and leave `from_the_caption` empty.
- If error bars are absent from the figure but mentioned in the caption, note that mismatch in the explanation.


*IMPORTANT*: When extracting definitions from the caption, ONLY include in `from_the_caption` the specific text that describes what the error bars or box elements represent (e.g., "standard error of the mean", "standard deviation", "95% confidence interval"). Do NOT include general descriptions of the figure or panel content. It is fine to extract only fragments of a sentence and omit further information about statistical tests. Use plain text only — write `mean +/- SD` not `mean ± SD`.

## Decision and explanation
For each panel, put `PASS`, `FAIL` or `not_applicable` in `decision`, and a one-line reason in `explanation`, in plain text.

- If error bars or box-plot elements are present and the caption defines them, `decision` is `PASS`.
- If they are present and the caption does not define them, `decision` is `FAIL`.
- If the panel is a plot with no error bars or box-plot elements, there is nothing to define, so `decision` is `PASS`.
- If the panel is not a plot, `decision` is `not_applicable`: the check does not apply to it, so it neither passes nor fails.


## Please note:
- If the caption defines error bars for multiple panels, include the same definition for each relevant panel.
- Report every panel of the figure, including panels that are not plots, which take `not_applicable`, and plots without error bars, which take `not_required` and `PASS`.
