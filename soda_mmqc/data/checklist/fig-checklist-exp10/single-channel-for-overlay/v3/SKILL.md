---
name: single-channel-for-overlay
description: Check that each channel of a multicoloured overlay micrograph is also shown as a single-channel image.
requires: []
produces:
  - single-channel-for-overlay
needs: []
---

# single-channel-for-overlay

## Summary
Check whether single-channel images are provided for multicoloured overlay micrographs. A multicoloured overlay micrograph combines two or more fluorescent channels into a single image; each channel may also be shown separately as a single-channel image, either in greyscale or colorized. Evaluate each panel for the presence of an overlay and of the corresponding single-channel images.

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

## Applicability of the check to overlay micrographs only

Set `multicolored_overlay_micrograph` to "yes" **only** for a panel whose classification includes `micrograph` and which contains a microscopy image with two or more distinct channels merged into one image. Set it to "no" otherwise, including for single-channel or brightfield micrographs. Check the caption to make sure you interpreted the panel correctly. 

For a panel where `multicolored_overlay_micrograph` is "no", the check does not apply: leave `overlay_channels` empty, set `number_of_channels_in_overlay`, `number_of_single_channel_images_shown` and `all_channels_shown_separately` to "not_applicable", and skip the next three sections.

## Describe the channels and report their number

Describe each channel merged into the overlay in `overlay_channels`, one short entry per channel, by colour and what it shows — for example `green: phalloidin (actin)`; the caption usually names them. Then report the number of distinct channels merged into the overlay in `number_of_channels_in_overlay`. Count only channels that are visually distinguishable and relevant in the experiment. **If uncertain, choose the most conservative lower number.**

## Report the number of single-channel images

Count how many separate single-channel images corresponding to that overlay are provided **in the same panel**, in `number_of_single_channel_images_shown`. Do not count quantification plots or unrelated images. An overlay shown with no single-channel image at all is `0`.

## Decide completeness

Set `all_channels_shown_separately` to "yes" only when the number of single-channel images is equal to or greater than the number of overlay channels; otherwise "no".

## Rules you must not violate

- **Do not guess channels or infer missing images.** If you are unsure whether an image corresponds to the overlay, do not count it.
- Be conservative: when in doubt, under-count rather than over-count.

## Please note:
- Report every panel of the figure, including panels with no overlay, which take `multicolored_overlay_micrograph` "no", `overlay_channels` empty, and "not_applicable" in both counts and in `all_channels_shown_separately`.
