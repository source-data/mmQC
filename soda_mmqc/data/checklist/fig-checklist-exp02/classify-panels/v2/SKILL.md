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

Classify panels based on content type. Proceed step-by-step and be accurate.

## 1. Get the panels

Before you classify anything, get the panel inventory for this figure by calling
the `identify-panels` skill.

## 2. Name every content type in the panel

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
| `other` | anything the list above does not cover. Say what it is in `evidence` |


Note of caution: **A plot drawn inside a schematic, for illustration rather than to 
  present data, is not a plot.** An idealised curve in a model diagram, a sketched bar
  chart in an experimental-design cartoon: report `schematic` alone and say so
  in `evidence`. 

## 3. A panel can hold several things

**Report every type present, not the single most prominent one.** A micrograph
beside the bar chart quantifying it is "micrograph, plot". A blot above
the densitometry of its own bands is "blot, plot". A structure shown next
to the binding curve that supports it is
"molecular_or_protein_structure, plot".

Dropping the second type silently removes that panel from whichever check cares
about it.

## 4. Report every panel

Report **every** panel from the inventory, in label order, including panels
whose content looks irrelevant to whatever the calling skill is checking. The
calling skill decides what is relevant; dropping a panel here silently removes
it from that decision. A panel you cannot classify at all gets `other` and an
`evidence` note, never an empty list.

## 5. How to report it

State the classification in your own reply, as a comma-separated list with one 
entry per panel, in label order. Each entry carries three things:

- the panel's label, exactly as the inventory gave it;
- every content type you found, from the vocabulary above, as a list
