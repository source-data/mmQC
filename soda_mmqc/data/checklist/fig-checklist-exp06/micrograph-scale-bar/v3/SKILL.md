---
name: micrograph-scale-bar
description: Check that every micrograph panel carries a scale bar, and that its length is stated on the image or in the caption.
requires:
- classify-panels
produces:
  - micrograph-scale-bar
needs: []
---

# Micrograph-scale-bar

## Summary
Analyze a scientific figure to check for the presence of a scale bar on micrographs and make sure they are properly defined either in the image itself or in the caption.

Proceed step-by-step and establish a systematical strategy to be very accurate and avoid mistakes.

## Classify figure panels

To decide when the check is applicable or not, invoke the `classify-panels` skill to classify panels based on content type before you do anything else.

## Applicability of the check to micrographs only

Set `micrograph` to "yes" for a panel whose classification includes `micrograph`, alone or beside other content types, and to "no" otherwise.

For a panel that is not a micrograph, this check does not apply: set `scale_bar_on_image`, `scale_bar_defined_in_caption` and `scale_bar_defined_in_image` to "not_applicable", leave `from_the_caption` and `from_the_image` empty, and skip the next three sections.

## Check for scale bars on microscopy images
For each micrograph in the figure, check whether there is a scale bar in the image. A scale bar is a visual reference element added to scientific micrographs (microscopic images) that indicates the actual size of the objects being depicted. It typically appears as a line or bar of defined length. Put "yes" or "no" in `scale_bar_on_image`.

A micrograph without a scale bar fails the check: set `scale_bar_defined_in_image` and `scale_bar_defined_in_caption` to "no", and leave `from_the_caption` and `from_the_image` empty.

## Identify if scale bar is defined in the image itself or in the figure caption
In some cases the defined length of the scale bar is written in the image itself and displayed as a label such as "10 μm" or "500 nm"; in other cases it is defined only in the figure caption. For each micrograph with a scale bar, check both, independently:
- Whether the scale bar is defined in the image itself, indicated by a number and a unit next to the scale bar. Put "yes" or "no" in `scale_bar_defined_in_image`.
- Whether the scale bar is defined in the figure caption, remembering that one caption sentence can cover several panels. Put "yes" or "no" in `scale_bar_defined_in_caption`.

The two are independent: a scale bar can be defined in both places, or in neither.

## Extract scale bar information
- If the scale bar is defined in the image itself, extract the scale bar information from the image into `from_the_image`. This encompasses the number and the unit, for example "500 nm".
- If the scale bar is described in the caption, extract into `from_the_caption` the exact text from the caption that defines the scale bar.
- Otherwise, leave the field empty.

*IMPORTANT:* When extracting the text from the caption, *ONLY* include the specific text that describes the scale bar. Do NOT include general descriptions of the figure or panel content.

## Please note:
- Report every panel of the figure, including panels that are not micrographs, which take `not_applicable` in the three scale-bar fields and leave the two extracted texts empty.
