---
name: individual-data-points
description: Check that a plot showing averages also shows the individual data points behind them.
requires:
- identify-panels
produces:
  - individual-data-points
needs: []
---

# indiviual-data-points

## Summary
Check whether plots showing averaged or aggregated data also display the underlying individual data points.

Showing individual data points alongside summary statistics is important because it allows the reader to assess the spread and variability of the raw measurements, and to judge how robust a result truly is. Plotting only averages can obscure low replication numbers, outliers, or large variability — details that are critical for interpreting the reliability of a finding.

## Classify figure panels

Classify panels based on content type. Proceed step-by-step and be accurate.

### 1. Get the panels

Before you classify anything, get the panel inventory for this figure by calling
the `identify-panels` skill.

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
| `other` | anything the list above does not cover. Say what it is in `evidence` |


Note of caution: **A plot drawn inside a schematic, for illustration rather than to 
  present data, is not a plot.** An idealised curve in a model diagram, a sketched bar
  chart in an experimental-design cartoon: report `schematic` alone and say so
  in `evidence`. 

### 3. A panel can hold several things

**Report every type present, not the single most prominent one.** A micrograph
beside the bar chart quantifying it is "micrograph, plot". A blot above
the densitometry of its own bands is "blot, plot". A structure shown next
to the binding curve that supports it is
"molecular_or_protein_structure, plot".

Dropping the second type silently removes that panel from whichever check cares
about it.

### 4. Report every panel

Report **every** panel from the inventory, in label order, including panels
whose content looks irrelevant to whatever the calling skill is checking. The
calling skill decides what is relevant; dropping a panel here silently removes
it from that decision. A panel you cannot classify at all gets `other` and an
`evidence` note, never an empty list.

### 5. How to report it

State the classification in your own reply, as a comma-separated list with one 
entry per panel, in label order. Each entry carries three things:

- the panel's label, exactly as the inventory gave it;
- every content type you found, from the vocabulary above, as a list

## Does this plot type require individual data points?

The check applies primarily to *bar charts* showing means or medians.

But not all plots require individual data points to be overlaid. The following plot types are exempt — set "individual_values" to "not needed" and "decision" to "PASS":

- Box plots and violin plots — these already display the data distribution
- Heatmaps — individual points are not meaningful in this context
- Line plots — overlaying individual points typically makes these unreadable
- Pie charts, Venn diagramms - do not need individual data points
- Scatter plots — individual points are the data


## Are individual data points shown?
For applicable plots, check whether the individual data points are overlaid on the summary visualization — typically as dots, circles, or similar markers.

If yes → "individual_values": "yes" → "decision": "PASS"
If no → "individual_values": "no" → "decision": "FAIL"
