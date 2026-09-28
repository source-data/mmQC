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
Analyze a scientific figure to check for the presence of a scale bar on micrographs and make sure they are properly defined either in the image itsself or in the caption.

Proceed step-by-step and establish a systematical strategy to be very accurate and avoid mistakes.

## Classify figure panels

To decide when the check is applicable or not, invoke the `classify-panels` skill to classify panels based on content type before you do anything else.

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
