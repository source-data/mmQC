---
name: image-annotation-defined
description: Check that graphical annotations drawn on imaging panels — arrows, arrowheads, circles, boxes, dashed lines — are explained in the caption.
requires:
  - classify-panels
produces:
  - image-annotation-defined
needs: []
---

# image-annotation-defined

## Summary
Analyze a scientific figure to check for the presence of annotations on any kind of imaging data and make sure they are explained in the figure caption. Any annotation on an image must be explained so that the reader can understand the significance of what is shown. These are small but important details that authors tend to miss, since the annotation is clear to them.

Proceed step-by-step and establish a systematical strategy to be very accurate and avoid mistakes.

## List and classify all figure panels

To be systematic, start from a complete and accurate list of all the figure's panels. Before you do anything else, invoke the `classify-panels` skill with the `Skill` tool to list every panel and classify it by content type.

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
