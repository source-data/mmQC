---
name: error-bars-defined
description: Check that error bars, and box or violin plot elements, are explained in the caption.
requires:
  - identify-panels
produces:
  - error-bars-defined
needs: []
---

# error-bars-defined

## Summary 
Analyze a scientific figure and its caption to check for the presence of error bars and whether they are properly defined.

Proceed step-by-step and establish a systematical structured strategy to be very accurate and avoid mistakes.

## Classify figure panels

To decide when the check is applicable or not, classify panels based on content type before you do anything else. Proceed step-by-step and be accurate.

### 1. Get the panels

To first obtain an accurate and complete list of panels, invoke the `identify-panels` skill.

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


## Determine if the panel contains error bars or box-plot elements to define
Your job is to pay attention to any plots that have error bars (typically bar charts, line plots). This is easy when the plot is itself an individual panel image. Pay attention also to more difficult cases when a plot is only part of a composite panel image. 

Cross-check with the panel classification to avoid common mistakes. 

For each panel in the figure:
- Determine if the plot contains error bars (lines extending from data points indicating variability). These are typically on bar charts, line charts, and sometimes scatter plots.
- *Box plots* and *violin plots*: whiskers and median/mean lines are not classical error bars, but lines, box and whisker elements still require a caption definition (e.g., IQR, percentiles, confidence intervals). For box plots and violin plots, set `error_bar_on_figure` to "yes" and check whether the caption defines the lines,  boxes and whiskers. If undefined, use FAIL.

## Check figure caption for explanation
- If error bars or box-plot elements are present in the panel, check whether the caption explains what they represent (e.g., standard deviation, standard error, confidence interval, IQR, whisker definition).
- If no error bars or box-plot elements apply to the panel, set `error_bar_defined_in_caption`, `from_the_caption`, and `Decision_and_explanation` to "not needed".

*IMPORTANT*: When extracting definitions from the caption, ONLY include the specific text that describes what the error bars or box elements represent (e.g., "standard error of the mean", "standard deviation", "95% confidence interval"). Do NOT include general descriptions of the figure or panel content. It is fine to extract only fragments of a sentence and omit further information about statistical tests. Use plain text only — write `mean +/- SD` not `mean ± SD`.

## Decision and explanation
For each panel, provide `Decision_and_explanation` as a single short string with verdict PASS or FAIL and a concise explanation of whether error bars or box-plot elements are properly defined in the caption.

- Use `"not needed"` for `Decision_and_explanation` when `error_bar_on_figure` is "no".
- Use FAIL when error bars or box-plot whiskers are present but not adequately defined in the caption.

## Please note: 
- If the caption defines error bars for multiple panels, include the same definition for each relevant panel.

- For panels without error bars or box-plot elements to define, set `error_bar_defined_in_caption`,`from_the_caption`, and `Decision_and_explanation` to "not needed".

- Be thorough and precise in your analysis. Include all panels visible in the figure, even if they don't contain error bars.
