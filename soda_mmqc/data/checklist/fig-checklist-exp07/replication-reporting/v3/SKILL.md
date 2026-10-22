---
name: replication-reporting
description: Check that panels showing replicated data report the number of replicates and what they represent.
requires: []
produces:
  - replication-reporting
needs: []
---

# replication-reporting

## Summary
Replicates allow researchers to estimate the sources of variability in measurements and observations. For panels derived from replicated observations, the figure caption should state the number of replicates — `n = 3`, `five animals` — and what they represent: biological replicates, technical replicates, animals, cells.

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

## Applicability of the check to panels involving replicates

Set `involves_replicates` to:

- "yes" — the panel shows replicated quantitative data: bar charts with error bars, box plots, violin plots, scatter plots with statistics, survival curves, dose-response curves, quantified microscopy data, or **any panel carrying p-values or statistical tests**. Most panels whose classification includes `plot` are in this case, but not all, and a quantified micrograph can be.
- "no" — the panel shows non-replicated content: schematics, workflows, representative images without quantification, model diagrams, representative blots.
- "unclear" — you genuinely cannot tell. Do not force it either way.

When `involves_replicates` is "no" or "unclear", the check does not apply: set `n_reported`, `replicate_type_reported`, `n_value_min` and `decision` to "not_applicable", leave `replicate_statements` empty and `replicate_type` an empty string, and skip the next section.

## Extract the replicate information

When `involves_replicates` is "yes", search **both the figure image and the caption** for:

- an n-number — `n = 3`, `five animals`, `n = 3-5`;
- a replicate type — `biological replicates`, `independent experiments`, `cells`, `animals`.

**Extract verbatim and minimally. Do not paraphrase.** Put each statement you find into `replicate_statements`.

- If a range is reported (`n = 3-5`), set `n_value_min` to the lower bound.
- If several conditions report different n, list them all in `replicate_statements` and set `n_value_min` to the lowest.
- Set `n_reported` and `replicate_type_reported` to "yes" or "no", and put the type itself in `replicate_type`. If no n-number is reported, set `n_value_min` to "not_reported"; if no type is reported, leave `replicate_type` an empty string.

## Decision and explanation

Put "PASS", "FAIL" or "not_applicable" in `decision`, with a brief reason in `explanation`.

- A panel involving replicates that reports **both** the n-number and the replicate type is a "PASS". Whether n is large enough is not this check's question.
- A panel involving replicates that is missing either is a "FAIL" — say which.
- A panel not involving replicates, or where you cannot tell, is "not_applicable": the check does not apply to it, so it neither passes nor fails.

## Please note:
- Report every panel of the figure, including panels that involve no replicates, which take "not_applicable" as above.
