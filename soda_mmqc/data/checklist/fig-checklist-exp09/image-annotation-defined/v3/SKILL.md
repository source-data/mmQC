---
name: image-annotation-defined
description: Check that graphical annotations drawn on imaging panels — arrows, arrowheads, circles, boxes, dashed lines — are explained in the caption.
requires: []
produces:
  - image-annotation-defined
needs: []
---

# image-annotation-defined

## Summary
Analyze a scientific figure to check for the presence of annotations on any kind of imaging data and make sure they are explained in the figure caption. Any annotation on an image must be explained so that the reader can understand the significance of what is shown. These are small but important details that authors tend to miss, since the annotation is clear to them.

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

## Applicability of the check to imaging data only

Set `image_data` to "yes" for a panel whose classification includes `micrograph` or `photograph`, and to "no" otherwise.

For a panel that is not imaging data, set `any_annotation_present_on_image` to "no" and leave the three annotation lists empty. You can skip the next two sections.

## List the annotations on the image

For an imaging panel, look for graphical overlays that are **not part of the sample itself**: arrows, arrowheads, carets, circles, ellipses, boxes, stars, dashed lines, solid lines, crosses, dots, triangles, and similar shapes intended to draw attention to specific features.

- Set `any_annotation_present_on_image` to "yes" or "no".
- Record each **unique** annotation in `annotation_description_on_image` by shape and colour, using standardized names such as `white arrow` or `red arrowhead`. If the same shape and colour appears many times, that is one entry, not many.
- **Never report scale bars.** They are standard microscopy elements and are excluded from this check entirely, regardless of colour or position. Do not list them and do not extract caption text about them.
- When a colour is ambiguous, use a plain descriptive term rather than guessing a precise one.

## Check the caption for each annotation

For each annotation you listed, in the same order:

- Put "yes" or "no" in `annotation_defined_in_caption`.
- Put the specific caption phrase that says what the symbol points to or highlights in `from_the_caption` — not a general description of the panel. Remember that one caption sentence can cover several panels.

These three fields are **parallel lists**: the *n*th entry of `annotation_defined_in_caption` and of `from_the_caption` describes the *n*th entry of `annotation_description_on_image`. Keep them the same length. Where an annotation is not defined, its `from_the_caption` entry is an empty string.

## Please note:
- Report every panel of the figure, including panels that are not imaging data, which take `image_data` "no", `any_annotation_present_on_image` "no" and empty annotation lists.
