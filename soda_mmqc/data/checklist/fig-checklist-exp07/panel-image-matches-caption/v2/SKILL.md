---
name: panel-image-matches-caption
description: Judge whether what a panel's image shows contradicts what its caption says is shown.
requires:
  - classify-panels
produces:
  - panel-image-matches-caption
needs: []
---

# panel-image-matches-caption

## Summary
Check whether each panel image matches its caption description — that is, whether what is shown in the image is consistent with what the caption says is shown.

Proceed step-by-step and establish a systematical strategy to be very accurate and avoid mistakes.

## List and classify all figure panels

To be systematic, start from a complete and accurate list of all the figure's panels. Before you do anything else, invoke the `classify-panels` skill with the `Skill` tool to list every panel and classify it by content type.

## Applicability of the check to panels the caption describes

For each panel, find the part of the caption that describes it. One caption sentence can cover several panels; this is usually indicated by the panel labels in brackets, before or after the caption text.

If the caption gives no specific description of a panel, the check does not apply to it: set `image_matches_caption` to "not_applicable", leave `discrepancies` empty, and skip the next two sections.

## Compare the image against the caption

**This is a judgment call.** Minor stylistic differences are not discrepancies. Focus on substantive mismatches that could mislead a reader:

- the wrong plot type;
- missing conditions, timepoints or groups;
- contradictory labels;
- elements described in the caption that are absent from the image, and elements in the image that the caption does not account for.

Set `image_matches_caption` to "yes" if the image is consistent with what the caption describes, and to "no" if there is a substantive mismatch.

## Describe the discrepancy

Put a short description of the mismatch in `discrepancies`. If there is none, leave it empty.

Describe what differs, concretely: say which element the caption promises and the image lacks, or the reverse. A discrepancy that cannot be stated specifically is usually a stylistic difference, which is not a discrepancy.

## Please note:
- Report every panel of the figure, including panels the caption does not describe, which take `not_applicable` and an empty `discrepancies`.
