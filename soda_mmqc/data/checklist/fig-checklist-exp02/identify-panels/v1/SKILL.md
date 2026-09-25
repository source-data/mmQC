---
name: identify-panels
description: >-
  Identify every panel of a scientific figure and locate the caption text that
  describes each one. Use this first, whenever a task needs the list of panels,
  their labels, or which part of the caption applies to which panel. Makes no
  judgement about what a panel contains.
requires: []
produces:
  - panels
needs: []
---

# Identify figure panels


## Summary

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

