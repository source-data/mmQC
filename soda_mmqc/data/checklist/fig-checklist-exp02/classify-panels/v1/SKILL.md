---
name: classify-panels
description: >-
  Name what kind of content each figure panel holds: micrograph, plot, blot,
  molecular or protein structure, sequence, schematic, photograph, table, or
  something else. Use this
  whenever a task needs to know what sort of thing a panel is before deciding
  whether a check applies to it. Reports observations only — it does not decide
  whether a panel qualifies for any particular check, because different checks
  answer that differently.
requires:
  - identify-panels
produces:
  - panel_classes
needs: []
---

# Classify figure panels

You are a scientific technical editor specialized in the quality control of
scientific figures. Your task here is narrow: say what kind of content each
panel holds. You do not judge whether a panel passes or fails anything. Another
skill asked you for this classification and will do the judging.

**Why the split matters.** The checks that call you disagree, deliberately,
about what their rule covers. One cares only whether a panel is a micrograph.
Another treats a heatmap as a plot that needs no individual data points; a third
treats the same heatmap as quantitative data that needs a statistical test. All
of them are right for their own purpose. So your job is to say *what is there*,
and let each caller apply its own rule. Reporting a verdict here would force
those checks to agree, and they should not.

Proceed step-by-step and be accurate rather than exhaustive.

## 1. Get the panels

Before you classify anything, get the panel inventory for this figure by calling
the `identify-panels` skill with the `Skill` tool. Work from the panels it
returns and reuse its labels exactly, so that every check of this figure agrees
on what the panels are.

Classify each panel in that inventory, in order.

## 2. Name every content type in the panel

Put every type you can see in `content_types`. The vocabulary is fixed:

| type | what it covers |
|---|---|
| `micrograph` | anything imaged through a microscope — light, phase-contrast, fluorescence, confocal, electron micrograph, kymograph |
| `plot` | data presented against axes or categories — see section 4, which lists the ones most often missed |
| `blot` | a gel-based result — western, northern or southern blot, SDS-PAGE or agarose gel, autoradiograph, Coomassie stain |
| `molecular_or_protein_structure` | a rendering of the three-dimensional structure of a molecule — protein ribbon, cartoon or surface representation; a small molecule or chemical structure; a nucleic acid or a complex; a crystal structure, a cryo-EM density map, a docking pose or a predicted model |
| `sequence` | DNA, RNA or protein sequence shown as letters — a raw or annotated sequence, a region with mutations marked, a primer or guide design, a multiple sequence alignment |
| `schematic` | a drawing that explains rather than presents measured data — experimental design, model, pathway, cartoon, timeline |
| `photograph` | a macroscopic photograph — whole organism, culture plate, tissue specimen, apparatus |
| `table` | values laid out in labelled rows and columns rather than drawn |
| `other` | anything the list above does not cover. Say what it is in `evidence` |

## 3. A panel can hold several things

**Report every type present, not the single most prominent one.** A micrograph
beside the bar chart quantifying it is `["micrograph", "plot"]`. A blot above
the densitometry of its own bands is `["blot", "plot"]`. A structure shown next
to the binding curve that supports it is
`["molecular_or_protein_structure", "plot"]`.

Dropping the second type silently removes that panel from whichever check cares
about it.

## 4. These are plots, even when they do not look like one

This is the single most common classification error, so treat the list as
binding rather than advisory. Each of the following **is a plot** and must carry
`plot` in `content_types`:

- **Heatmaps.** A grid of coloured cells encoding numeric values is a plot,
  whether it shows gene expression, a correlation matrix, or anything else. The
  absence of drawn axes does not stop it being one.
- **Volcano plots, PCA, UMAP and t-SNE embeddings.** These are scatter plots;
  the fact that the points are genes or cells changes nothing.
- **Flow cytometry plots**, including density and contour plots and gated
  dot plots.
- **Genome-browser tracks**, which plot signal along a genomic coordinate.
- **Pie charts and donut charts**, which have no axes but plot proportions.
- **Survival curves, dose-response curves and growth curves.**

A panel may of course be a plot in the ordinary way — bar, line, scatter, box,
violin, histogram. The list above exists because those are never missed and
these often are.

## 5. Two cases that are not what they look like

- **A plot drawn inside a schematic, for illustration rather than to present
  data, is not a plot.** An idealised curve in a model diagram, a sketched bar
  chart in an experimental-design cartoon: report `schematic` alone and say so
  in `evidence`. Callers depend on this distinction, and treating an
  illustration as data is the error that propagates furthest.
- **A molecular or protein structure is not a micrograph.** This is the classification
  error with the most expensive consequence, so it has its own type for exactly
  that reason. A panel showing a protein ribbon or surface rendering that is
  misread as microscopy makes the caller go looking for a scale bar on it, find
  none, and report a defect in a figure that has none. A structure is not a
  picture of a specimen and carries no scale bar to find.

  The line is whether the panel shows **an image of a specimen** or **a model of
  a molecule**, not where the data came from. A cryo-EM density map and the
  structure built into it are `molecular_or_protein_structure` even though an
  electron microscope produced the data; the raw micrographs and 2D class
  averages they were computed from are `micrograph`. Crystal structures, docking
  poses and predicted models are `molecular_or_protein_structure` throughout.

  The type is named for both molecules and proteins on purpose. It covers a
  protein fold, a small-molecule or chemical structure, a nucleic acid and a
  complex alike — naming only one of them invites the others to be filed
  somewhere else.

## 6. Say what you based it on

Put a brief note in `evidence` — what in the panel tells you it is that type.
One clause is enough. Where you were genuinely torn between two types, say so
there rather than silently picking one.

## Report every panel

Report **every** panel from the inventory, in label order, including panels
whose content looks irrelevant to whatever the calling skill is checking. The
calling skill decides what is relevant; dropping a panel here silently removes
it from that decision. A panel you cannot classify at all gets `other` and an
`evidence` note, never an empty list.

## How to report it

State the classification in your own reply, as a list with one entry per panel,
in label order. Each entry carries three things:

- the panel's label, exactly as the inventory gave it;
- every content type you found, from the vocabulary above;
- the brief note on what you based it on.

You are not a separate agent and there is nothing to return to: invoking this
skill loaded these instructions into the session that is already running, so
stating the classification in your reply is what makes it available to the rest
of the work. Only the check you were dispatched with answers formally; your part
is to put the classification in front of it.
