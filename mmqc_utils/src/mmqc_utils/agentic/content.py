"""What a figure looks like to the model: one conversion, shared by all callers.

mmQC's benchmark and the production application must send the model the same
image for the same source file, or a benchmark score does not describe
production. Both build a figure's parts here.

The source is converted **once**: :func:`mmqc_utils.convert_to_bounded_jpeg`
rasterizes vector formats, flattens transparency, downscales to
:data:`FIGURE_MAX_DIMENSION` and encodes JPEG at :data:`FIGURE_JPEG_QUALITY`,
and those bytes are what the model receives. Nothing decodes and re-encodes
them: every lossy pass adds artefacts, and fine text -- axis labels, scale
bars, panel letters -- goes first.

The source may be what an author submitted (TIFF, EPS, PDF, PNG, JPEG) or, in
mmQC's benchmark, a published figure; either is processed as a submission
would be.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

from mmqc_utils.images import PathLikeOrFile, convert_to_bounded_jpeg

__all__ = [
    "FIGURE_JPEG_QUALITY",
    "FIGURE_MAX_DIMENSION",
    "FIGURE_RASTERIZATION_DPI",
    "figure_image_part",
    "figure_parts",
]

#: DPI at which vector sources (PDF, EPS, AI) are rasterized.
FIGURE_RASTERIZATION_DPI = 300

#: Longest side, in pixels, of the image sent to the model. The provider
#: downscales further when an image exceeds its own limits.
FIGURE_MAX_DIMENSION = 2048

#: JPEG quality of the one encode.
FIGURE_JPEG_QUALITY = 80


def figure_image_part(source: PathLikeOrFile) -> Dict[str, Any]:
    """An image part carrying the figure as the model receives it."""
    data = convert_to_bounded_jpeg(
        source,
        rasterization_dpi=FIGURE_RASTERIZATION_DPI,
        max_dimension=FIGURE_MAX_DIMENSION,
        compression_quality=FIGURE_JPEG_QUALITY,
    )
    return {"kind": "image", "media_type": "image/jpeg", "data": data}


def figure_parts(source: PathLikeOrFile, caption: str) -> Tuple[Dict[str, Any], ...]:
    """A figure's parts, in order: its caption, then its image."""
    return (
        {"kind": "text", "text": f"Figure caption:\n{caption}"},
        figure_image_part(source),
    )
