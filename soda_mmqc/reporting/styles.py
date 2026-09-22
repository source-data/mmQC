"""Outcome orders and colour maps for flat evaluation reporting."""

from __future__ import annotations

LAYER_S_TITLE = "Structure (Layer S)"
LAYER1_TITLE = "Applicability (Layer 1)"
LAYER2_BINARY_TITLE = "Matching-binary (Layer 2)"
LAYER2_GRADED_TITLE = "Matching-graded (Layer 2)"

LAYER_S_ORDER = ("correct_row", "missing_row", "spurious_row")

LAYER1_ORDER = (
    "correct_NA",
    "correct_applicable",
    "withheld_applicable",
    "spurious_applicable",
)

LAYER2_BINARY_ORDER = ("TP", "TN", "FP", "FN")
LAYER2_GRADED_ORDER = ("match", "mismatch")

LAYER_S_COLORS = {
    "correct_row": "#16a34a",
    "missing_row": "#ca8a04",
    "spurious_row": "#dc2626",
}

# Opacity ladder for arm comparison series on outcome-colored bars.
COMPARISON_SERIES_OPACITIES = (1.0, 0.6, 0.35)

# Hatch patterns for model comparison series (first entry = solid fill).
COMPARISON_SERIES_PATTERNS = ("", "/", "\\", "x", "|", "-", "+", ".")

LAYER1_COLORS = {
    "correct_NA": "#94a3b8",
    "correct_applicable": "#16a34a",
    "withheld_applicable": "#ca8a04",
    "spurious_applicable": "#dc2626",
}

LAYER2_BINARY_COLORS = {
    "TP": "#16a34a",
    "TN": "#86efac",
    "FP": "#dc2626",
    "FN": "#f97316",
}

LAYER2_GRADED_COLORS = {
    "match": "#16a34a",
    "mismatch": "#dc2626",
}

LAYER1_OUTLIER_OUTCOMES = frozenset({"withheld_applicable", "spurious_applicable"})
LAYER2_ERROR_OUTCOMES = frozenset({"FP", "FN", "mismatch"})

MEAN_SCORE_BAR_COLOR = "#000000"
INSTANCE_SCORE_MARKER_COLOR = "red"
INSTANCE_SCORE_MARKER_BORDER_COLOR = "#ffffff"
INSTANCE_SCORE_MARKER_BORDER_WIDTH = 1.0
MEAN_SCORE_BAR_WIDTH = 0.44
MEAN_SCORE_BAR_SPACING = 0.5
MEAN_SCORE_JITTER_STDDEV = 0.06
MEAN_SCORE_Y_MAX = 1.1
MEAN_SCORE_PLOT_TITLE = "Scores (mean over applicable instances)"

PLOTLY_TEMPLATE = "plotly_white"

# Paired arm-contrast bars. One neutral colour on purpose: the sign is
# already in the bar's direction, and colouring it green/red would state
# which arm is better -- a claim that belongs in the experiment's note,
# not in its arithmetic.
ARM_CONTRAST_BAR_COLOR = "#475569"
ARM_CONTRAST_ZERO_LINE_COLOR = "#0f172a"

# Vertical room per property row, per-panel chrome, and the gap between
# panels -- all in pixels. The gap is converted to plotly's fractional
# `vertical_spacing` against the figure's own height, because that
# fraction applies between *every* pair of rows: a fixed 0.08 spends
# 80% of an eleven-panel figure on whitespace.
ARM_CONTRAST_ROW_HEIGHT = 26
ARM_CONTRAST_PANEL_CHROME = 120
ARM_CONTRAST_ROW_GAP = 70

# Arm levels: two categories, so two hues rather than a ladder of one.
# Not green/red -- which arm is better is the experiment's claim.
ARM_LEVELS_COLORS = ("#475569", "#0891b2", "#a16207", "#7c3aed")

# Horizontal room for one (group, variant) bar position, in pixels.
# The two-level axis writes the group name under its own bars only.
STACKED_COUNTS_POSITION_WIDTH = 78

# Air between one group of variant bars and the next, in bar widths.
# Zero inside a group: a check's variants are two halves of one
# measurement and should touch.
STACKED_COUNTS_GROUP_GAP = 0.6

# plot_check_layers: room between the three panels, and how far a
# y-axis title sits from its own axis. Plotly's automatic standoff
# put `instances` and `mean_score` left of their panel and onto the
# neighbour; rotated tick labels need the panels further apart.
CHECK_LAYERS_PANEL_SPACING = 0.12
CHECK_LAYERS_TITLE_STANDOFF = 5
