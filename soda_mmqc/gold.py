"""Pin the gold to a tagged snapshot, so a frozen experiment re-scores as it did.

    from soda_mmqc.gold import pin_gold
    pin_gold("gold-v1")          # first cell of a frozen experiment's notebook

Gold is curated and migrated after experiments have run, and analyses are
recomputed from predictions and gold rather than committed. Without a pin, re-
running an old notebook scores its predictions against today's gold and changes
its numbers without saying so. A pin points the scorer at the gold as it was at
a git tag; inputs (figures, captions) are still read from the live examples tree.

Tags:

``gold-v0``  the gold exp-01 and exp-02 were scored against (2026-09-18,
             before the 2026-09-28 label fix)
``gold-v1``  the gold exp-03 was scored against, and the last state before the
             contract cleanup's migration

A snapshot holds only gold files -- ``<example>/checks/<check>/expected_output.*``
-- extracted with ``git archive`` into ``.gold-snapshots/<tag>/`` (gitignored),
once. It is a few megabytes, not the 3.4 GB of the examples tree.

This module imports only the standard library, so it can run before anything
else in ``soda_mmqc`` has read where the gold lives.
"""

from __future__ import annotations

import io
import os
import subprocess
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SNAPSHOTS = REPO / ".gold-snapshots"
EXAMPLES_PREFIX = "soda_mmqc/data/examples/"
GOLD_DIR_ENV = "SODA_MMQC_GOLD_DIR"   # mirrored in soda_mmqc.config
_COMPLETE = ".complete"


def _git(*args: str, binary: bool = False):
    out = subprocess.run(["git", *args], cwd=REPO, check=True, capture_output=True)
    return out.stdout if binary else out.stdout.decode()


def snapshot(ref: str) -> Path:
    """The examples root of a gold-only snapshot at ``ref``, built if missing."""
    commit = _git("rev-parse", "--verify", f"{ref}^{{commit}}").strip()
    root = SNAPSHOTS / ref
    examples = root / EXAMPLES_PREFIX
    marker = root / _COMPLETE
    if marker.is_file() and marker.read_text().strip() == commit:
        return examples

    files = [
        path for path in _git("ls-tree", "-r", "--name-only", commit, "--",
                              EXAMPLES_PREFIX).splitlines()
        if "/checks/" in path and Path(path).name.startswith("expected_output.")
    ]
    if not files:
        raise ValueError(f"{ref} holds no gold under {EXAMPLES_PREFIX}")
    if root.exists():
        import shutil
        shutil.rmtree(root)
    root.mkdir(parents=True)
    for start in range(0, len(files), 500):
        archive = _git("archive", "--format=tar", commit, "--", *files[start:start + 500],
                       binary=True)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(root, filter="data")
    marker.write_text(commit + "\n")
    return examples


def pin_gold(ref: str) -> Path:
    """Score against the gold at ``ref`` from here on; return its examples root.

    Refuses if the scorer was already pinned elsewhere in this process, since
    a kernel that scored one gold and then another would mix them silently.
    """
    target = snapshot(ref)
    current = os.environ.get(GOLD_DIR_ENV)
    if current and Path(current) != target:
        raise RuntimeError(
            f"The gold is already pinned to {current}; restart the kernel to pin {ref}."
        )
    os.environ[GOLD_DIR_ENV] = str(target)
    commit = (SNAPSHOTS / ref / _COMPLETE).read_text().strip()
    print(f"gold pinned to {ref} ({commit[:9]}): {target}")
    return target
