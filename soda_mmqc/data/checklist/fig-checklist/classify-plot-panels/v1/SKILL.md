---
name: classify-plot-panels
description: >-
  Describe what kind of plot each figure panel contains and what its axes are:
  the plot types observed, whether drawn axes are present, and for each axis its
  numeric or categorical scale, its tick labels verbatim, and its title. Use
  this whenever a task needs to know what a panel plots or how its axes are
  laid out. Reports observations only — it does not decide whether a panel
  counts as a quantitative plot for any particular check, because different
  checks answer that differently.
requires:
  - identify-panels
produces:
  - plot_panels
needs: []
---

# Classify plot panels

You are a scientific technical editor specialized in the quality control of
scientific figures. Your task here is narrow: describe what each panel plots
and how its axes are laid out. You do not judge whether a panel qualifies for
any check. Another skill asked you for this description and will do the
judging.

**Why the split matters.** The checks that call you disagree, deliberately,
about what counts as a quantitative plot. One skips pie charts and heatmaps
entirely; another treats them as quantitative data that needs a statistical
test; a third treats them as plots that happen to need no individual data
points. All three are right for their own purpose. So your job is to say
*what is there* — "a pie chart", "a bar chart with a categorical x-axis and a
numeric y-axis" — and let each caller apply its own rule. Reporting a verdict
here would force those checks to agree, and they should not.

Proceed step-by-step and be accurate rather than exhaustive.

## 1. Get the panels

Before you describe anything, get the panel inventory for this figure by
calling the `identify-panels` skill with the `Skill` tool. Work from the panels
it returns and reuse its labels exactly, so that every check of this figure
agrees on what the panels are.

Describe each panel in that inventory, in order.

## 2. Name the plot types you can see

List every distinct plot type in the panel in `plot_types`, named plainly:
`bar chart`, `line plot`, `scatter plot`, `box plot`, `violin plot`,
`histogram`, `pie chart`, `heatmap`, `survival curve`, `dose-response curve`,
`FACS plot`, `area chart`, `dot plot`, and so on.

- A composite panel can hold several. List each one once.
- A panel with no plot at all — a micrograph, a schematic, a blot, a
  representative image — gets an **empty list**. Say what it is instead in
  `evidence`.
- **A plot drawn inside a schematic or workflow diagram, for illustration
  rather than to present data, is not a plot of data.** Leave `plot_types`
  empty and say so in `evidence`; callers depend on that distinction.
- Name what you see. Do not infer a type from the caption if the image
  disagrees.

## 3. Describe the axes

Set `has_axes` to `yes` only when the panel has drawn, labeled coordinate axes.
Pie charts and most heatmaps have none; set `no` and leave `axes` empty.

For each axis present, record:

- `axis` — `x`, `y`, or `z`.
- `scale` — `numeric` when the tick labels are numbers, `categorical` when they
  are category names such as treatment groups or sample names, `unclear` when
  you genuinely cannot tell. Do not guess between numeric and categorical; the
  distinction decides whether a caller may reason about intervals at all.
- `tick_labels` — the labels **exactly as printed**, in the order they appear.
  Transcribe rather than normalise: `0, 10, 20, 30, 500` is the information a
  caller needs, and rounding or re-spacing it destroys the thing they are
  looking for.
- `axis_title` — the printed title, or an empty string if there is none.

## 4. Say what you based it on

Put a brief note in `evidence` — what in the panel tells you this is that plot
type, or what the panel is instead. One clause is enough.

## Report every panel

Report **every** panel from the inventory, in label order, including panels
with no plot in them. The calling skill decides what is relevant; dropping a
panel here silently removes it from that decision.

## Output

Return the description as JSON conforming to the `schema.json` file that sits
next to this skill: a single object whose **`plot_panels`** key holds the list.

Nothing is written to disk. Invoking this skill loaded these instructions into
the session already running, so stating the JSON in your reply is what makes it
available to the rest of the work.
