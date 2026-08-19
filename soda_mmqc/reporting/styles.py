"""Outcome orders and colour maps for flat evaluation reporting."""

from __future__ import annotations

LAYER_S_TITLE = "Structure (Layer S)"
LAYER1_TITLE = "Applicability (Layer 1)"
LAYER2_BINARY_TITLE = "Matching-binary (Layer 2)"
LAYER2_GRADED_TITLE = "Matching-graded / multiclass (Layer 2)"

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

# Opacity ladder for prompt comparison series on outcome-colored bars.
COMPARISON_SERIES_OPACITIES = (1.0, 0.6, 0.35)

# Box-plot fills and lines for score-distribution comparison series.
COMPARISON_BOX_FILLS = (
    "rgba(59, 130, 246, 0.25)",
    "rgba(239, 68, 68, 0.25)",
    "rgba(34, 197, 94, 0.25)",
    "rgba(234, 179, 8, 0.25)",
    "rgba(168, 85, 247, 0.25)",
    "rgba(236, 72, 153, 0.25)",
)

COMPARISON_BOX_LINES = (
    "#2563eb",
    "#dc2626",
    "#16a34a",
    "#ca8a04",
    "#9333ea",
    "#db2777",
)

COMPARISON_INSTANCE_MARKER_SIZE = 5
COMPARISON_INSTANCE_MARKER_OPACITY = 0.4
COMPARISON_INSTANCE_JITTER_STDDEV = 0.035

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
