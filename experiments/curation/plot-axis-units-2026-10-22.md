# plot-axis-units, 2026-10-22: one panel C in embor.2009.233 Fig. 2

`10.1038_embor.2009.233/content/2` carries one label, **C**, over two
unlabelled plots — a box plot of polyp number and a 3-D bar chart of polyp
number by diameter — which the caption describes together under "(C)". Ten of
the eleven checks' gold had one row "C"; `plot-axis-units` had two, "C top"
and "C bottom".

**Rule** (decided with the author): split only sub-parts the figure labels
(as `s44321-025-00219-1` Fig. 1's Ai and Aii); an unlabelled composite is one
panel. It is `classify-panels`' own: "report the labels the figure actually
carries: do not invent … them". All three models in exp-07 answered one "C"
in all 15 sessions.

**Change**: the two rows merged into one, "C", keeping the 3-D chart's axes —
the only axis in the panel with a unit:

| field | value |
|---|---|
| `is_a_plot_with_axes` | yes (both rows) |
| `units_provided` | x `not_required`, y `yes`, z `not_required` (was "C bottom"'s) |
| `unit_definition_as_provided` | y "Polyp diameter (mm)" |
| `decision` | PASS (both rows) |

The box plot's x and y, both `not_required`, are dropped: a single row can
hold one `y`. Needed for a panel-major gold (exp-10), in which every check
must name the same panels. Curator: Thomas Lemberger (rule and merge) /
Claude (edit). Tagged with the merged gold rebuilt as `gold-v7`.
