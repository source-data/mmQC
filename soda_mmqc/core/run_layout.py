"""What the directories of a run mean.

Every run the harness writes has the same shape::

    <root>/<arm>/rep-NN/<example>/prediction.json
    <root>/<arm>/rep-NN/analysis.json

A *root* is a directory whose children are arms. Two roots exist and
differ only in prefix -- ``data/evaluation/<checklist>/<check>/<model>/``
for a production benchmark, ``experiments/runs/<exp>/<check>/`` for an
experiment -- so one walker serves both, and what the path does not carry
(a model, say) is supplied by the caller.

This module knows what the directories *mean*. It does not know what is
inside the files: a leaf holding predictions but no ``analysis.json`` is
a run that was never scored, which is a normal state and a reader's
business, not the layout's.

It exists because two callers need the same traversal --
``core/gold_drafts.py`` takes one named leaf for ``init --from-run``, and
``reporting/load.py`` takes every leaf under a root -- and two walkers
over one layout would disagree the first time the layout gained anything.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterator

__all__ = [
    "BASELINE_ARM",
    "REPLICATE_PATTERN",
    "replicate_dirname",
    "resolve_check_root",
    "iter_leaves",
    "leaf",
]

#: The arm every run writes, whether or not anything was unpinned. A
#: variant arm is named after what moved off its manifest pin.
BASELINE_ARM = "pinned"

#: A replicate directory, and the only thing treated as one -- so a stray
#: directory beside the replicates cannot become a phantom.
REPLICATE_PATTERN = re.compile(r"^rep-(\d+)$")


def replicate_dirname(replicate: int) -> str:
    """``rep-NN`` for a replicate number."""
    return f"rep-{replicate:02d}"


def resolve_check_root(root: Path, check: str) -> Path:
    """The level of ``root`` whose children are arms.

    A root may hold one check (``experiments/runs/<exp>/<check>/``) or
    several (``experiments/runs/<exp>/``), so the per-check level is
    tried first.
    """
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"No run root at {root}")
    nested = root / check
    return nested if nested.is_dir() else root


def iter_leaves(root: Path) -> Iterator[tuple[str, int, Path]]:
    """Every ``(arm, replicate, directory)`` under a root, sorted.

    Sorted by arm then replicate, so a caller's output order does not
    depend on the filesystem.
    """
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"No run root at {root}")

    for arm_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        replicates: list[tuple[int, Path]] = []
        for candidate in arm_dir.iterdir():
            if not candidate.is_dir():
                continue
            match = REPLICATE_PATTERN.match(candidate.name)
            if match:
                replicates.append((int(match.group(1)), candidate))
        for replicate, path in sorted(replicates):
            yield arm_dir.name, replicate, path


def leaf(root: Path, *, arm: str, replicate: int) -> Path:
    """One named leaf, or a message saying what is there instead."""
    root = Path(root)
    arm_dir = root / arm
    if not arm_dir.is_dir():
        present = sorted(p.name for p in root.iterdir() if p.is_dir())
        raise ValueError(
            f"{root} holds no {arm!r} arm; it has {present or 'nothing'}"
        )

    name = replicate_dirname(replicate)
    path = arm_dir / name
    if not path.is_dir():
        present = sorted(p.name for p in arm_dir.iterdir() if p.is_dir())
        raise ValueError(
            f"{arm_dir} has no {name}; it has {present or 'nothing'}"
        )
    return path
