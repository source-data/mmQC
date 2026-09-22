"""Render an example's neutral input parts into one provider's vocabulary.

`Example` states what its content is without naming a provider; this module
is the only place that knows what Anthropic content blocks and OpenAI Chat
Completions parts look like. Keeping the translation here is what lets a new
example class be added without touching either driver, and a new driver
without touching `core/examples.py`.

The part vocabulary is closed on purpose -- ``text`` and ``image``, nothing
else. A new kind is a deliberate edit in three places (the example class that
emits it and both renderers) rather than something a driver silently drops.
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence, Tuple

__all__ = ["render_anthropic", "render_openai"]


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


def _image_payload(root: Path, relative: str) -> Tuple[str, str]:
    """The media type and base64 payload of one staged image."""
    path = _resolve(root, relative)
    media_type = mimetypes.guess_type(path.name)[0] or "image/png"
    return media_type, base64.b64encode(path.read_bytes()).decode()


def render_anthropic(
    parts: Sequence[Mapping[str, Any]], root: Path
) -> List[Dict[str, Any]]:
    """Neutral parts to Anthropic content blocks.

    Args:
        parts: What an ``Example`` said its content is.
        root: The directory that ``image`` paths are relative to -- the
            runtime root, not the example store, because the runtime is what
            the session can reach.
    """
    blocks: List[Dict[str, Any]] = []
    for part in parts:
        kind = part.get("kind")
        if kind == "text":
            blocks.append({"type": "text", "text": part["text"]})
        elif kind == "image":
            media_type, data = _image_payload(root, part["path"])
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
            media_type, data = _image_payload(root, part["path"])
            rendered.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{media_type};base64,{data}"},
                }
            )
        else:
            raise ValueError(f"unknown part kind {kind!r}")
    return rendered
