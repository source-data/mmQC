---
name: single-channel-for-overlay
description: Check that each channel of a multicoloured overlay micrograph is also shown as a single-channel image.
requires:
  - classify-panels
produces:
  - single-channel-for-overlay
needs: []
---

# single-channel-for-overlay

## Summary
Check whether single-channel images are provided for multicoloured overlay micrographs. A multicoloured overlay micrograph combines two or more fluorescent channels into a single image; each channel may also be shown separately as a single-channel image, either in greyscale or colorized. Evaluate each panel for the presence of an overlay and of the corresponding single-channel images.

Proceed step-by-step and establish a systematical strategy to be very accurate and avoid mistakes.

## List and classify all figure panels

To be systematic, start from a complete and accurate list of all the figure's panels. Before you do anything else, invoke the `classify-panels` skill to list every panel and classify it by content type.

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
