---
name: micrograph-scale-bar
description: Check that every micrograph panel carries a scale bar, and that its length is stated on the image or in the caption.
requires: []
produces:
  - micrograph-scale-bar
needs: []
---

# Micrograph-scale-bar

## Summary
Analyze a scientific figure to check for the presence of a scale bar on micrographs and make sure they are properly defined either in the image itsself or in the caption.

Proceed step-by-step and establish a systematical strategy to be very accurate and avoid mistakes.

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

Dropping the second type can silently remove that panel from this check.

### 4. Report every panel

Report **every** panel from step 1, in label order, including panels
whose content looks irrelevant to this check. The steps below decide what is
relevant; dropping a panel here silently removes it from that decision. A panel you cannot classify at all gets `other`, never an empty list.


### 5. How to report it

State the classification in your own reply, as a comma-separated list with one
entry per panel, in label order. Each entry carries two things:

- the panel's label, exactly as you recorded it in step 1;
- every content type you found, from the vocabulary above, as a list.

## Check for scale bars on microscopy images
For each panel in the figure:
- If and only if it is a micrograph or microscopic image, check whether there is a scale bar in the image. A scale bar is a visual reference element added to scientific micrographs (microscopic images) that indicates the actual size of the objects being depicted. It typically appears as a line or bar of defined length.

## Identify if scale bar is defined in the image itsself or in the figure caption
In some cases the defined length of the scale bar is written in the image itsself and displayed as label such as "10 μm" or "500 nm" or it is defined only in the figure caption. For each microscopy image identified in step 2 check:
- If the scale bar is defined in the image itsself. This would be indicated with a number and a unit next to the scale bar.
- If the scale bar is defined in the figure caption.

## Extract scale bar information
- If the scale bar is defined in the image itsself, extract the scale bar information from the image. This encompasses the number and the unit, for example "500 nm".
- If the scale bar is described in the text, extract the exact text from the caption that defines the scale bar.
*IMPORTANT:* When extracting the text from the caption, *ONLY* include the specific text that describes the scale bar. Do NOT include general descriptions of the figure or panel content.

Be thorough and precise in your analysis. Include all panels visible in the figure, even if they don't contain micrographs or microscopy images.
