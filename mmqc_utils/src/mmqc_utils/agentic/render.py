"""Render an example's neutral input parts into one provider's vocabulary.

`Example` states what its content is without naming a provider; this module
is the only place that knows what Anthropic content blocks and OpenAI Chat
Completions parts look like. Keeping the translation here is what lets a new
example class be added without touching either driver, and a new driver
without touching `core/examples.py`.

The part vocabulary is closed on purpose -- ``text`` and ``image``, nothing
else. A new kind is a deliberate edit in three places (the example class that
emits it and both renderers) rather than something a driver silently drops.

An image part either names a file, ``{"kind": "image", "path": str}``, or
carries its bytes, ``{"kind": "image", "media_type": str, "data": bytes}``.
The second is for an image the caller derived -- a figure converted for the
model -- which travels in the request and is never written into a runtime.
Either way, :func:`image_fingerprints` records exactly what was sent.
"""

from __future__ import annotations

import base64
import hashlib
import io
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

__all__ = ["image_bytes", "image_fingerprints", "render_anthropic", "render_openai"]


def _resolve(root: Path, relative: str) -> Path:
    """Resolve one part's path, refusing anything outside ``root``.

    A part comes from an example's own account of itself, but it addresses a
    file inside a sealed runtime, and the seal is only a seal if it is checked
    at the boundary rather than trusted.

    Raises:
        ValueError: If the path escapes ``root``.
        FileNotFoundError: If it names no file.
    """
    base = root.resolve()
    resolved = (base / relative).resolve()
    if resolved != base and base not in resolved.parents:
        raise ValueError(
            f"Input part path {relative!r} resolves outside {base}"
        )
    if not resolved.is_file():
        raise FileNotFoundError(f"Input part names no file: {resolved}")
    return resolved


def image_bytes(part: Mapping[str, Any], root: Path) -> Tuple[str, bytes]:
    """The media type and bytes of one image part, as they are sent.

    Raises:
        ValueError: If the part names neither a file nor bytes, or both, or
            carries bytes without a media type.
    """
    has_path, has_data = "path" in part, "data" in part
    if has_path == has_data:
        raise ValueError(
            "an image part names a file (`path`) or carries its bytes "
            f"(`data`), exactly one of the two; got {sorted(part)}"
        )
    if has_data:
        data, media_type = part["data"], part.get("media_type")
        if not isinstance(data, (bytes, bytearray)) or not media_type:
            raise ValueError(
                "an image part carrying `data` needs bytes and a `media_type`"
            )
        return media_type, bytes(data)
    path = _resolve(root, part["path"])
    media_type = mimetypes.guess_type(path.name)[0] or "image/png"
    return media_type, path.read_bytes()


def _image_payload(part: Mapping[str, Any], root: Path) -> Tuple[str, str]:
    """The media type and base64 payload of one image part."""
    media_type, data = image_bytes(part, root)
    return media_type, base64.b64encode(data).decode()


def image_fingerprints(
    parts: Sequence[Mapping[str, Any]], root: Path
) -> List[Dict[str, Any]]:
    """What each image sent to the model is, without keeping the image.

    One entry per image part: its position among the parts, where it came
    from (a staged path, or ``inline``), media type, size, pixel dimensions
    and SHA-256 of the bytes sent. The hash is what makes a later
    re-conversion checkable: same source, same parameters, same hash, same
    image -- or not, if a library underneath has changed.
    """
    fingerprints = []
    for index, part in enumerate(parts):
        if part.get("kind") != "image":
            continue
        media_type, data = image_bytes(part, root)
        fingerprints.append({
            "part": index,
            "source": part.get("path", "inline"),
            "media_type": media_type,
            "bytes": len(data),
            "dimensions": _dimensions(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    return fingerprints


def _dimensions(data: bytes) -> Optional[List[int]]:
    """Width and height, or None when the bytes do not decode as an image."""
    from PIL import Image

    try:
        with Image.open(io.BytesIO(data)) as image:
            return list(image.size)
    except Exception:
        return None


def render_anthropic(
    parts: Sequence[Mapping[str, Any]], root: Path
) -> List[Dict[str, Any]]:
    """Neutral parts to Anthropic content blocks.

    Args:
        parts: What an ``Example`` said its content is.
        root: The directory that ``image`` paths are relative to -- the
            runtime root, not the example store, because the runtime is what
            the session can reach. Images carrying their bytes need none.
    """
    blocks: List[Dict[str, Any]] = []
    for part in parts:
        kind = part.get("kind")
        if kind == "text":
            blocks.append({"type": "text", "text": part["text"]})
        elif kind == "image":
            media_type, data = _image_payload(part, root)
            blocks.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": data,
                    },
                }
            )
        else:
            raise ValueError(f"unknown part kind {kind!r}")
    return blocks


def render_openai(
    parts: Sequence[Mapping[str, Any]], root: Path
) -> List[Dict[str, Any]]:
    """Neutral parts to OpenAI Chat Completions content parts.

    Args:
        parts: What an ``Example`` said its content is.
        root: The directory that ``image`` paths are relative to.
    """
    rendered: List[Dict[str, Any]] = []
    for part in parts:
        kind = part.get("kind")
        if kind == "text":
            rendered.append({"type": "text", "text": part["text"]})
        elif kind == "image":
            media_type, data = _image_payload(part, root)
            rendered.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{data}"},
                }
            )
        else:
            raise ValueError(f"unknown part kind {kind!r}")
    return rendered
