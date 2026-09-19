"""The gold corpus must at least be readable.

`data/examples/` is the measuring stick for every score this project
produces, and until now it was gitignored: edits left no diff and no review,
so a malformed file could sit in the tree indefinitely. One did.
`10.1038_s44318-026-00735-x/content/1/checks/image-annotation-defined` had a
dangling comma before its closing bracket and had not parsed since
2026-06-12 -- committed that way in `master` as well as here -- so anything
loading that check's gold failed on it, and nothing said so.

This is deliberately the weakest assertion available: that the file parses.
It judges no content and encodes no curation policy, which is what lets it
stay true while the corpus grows. It costs about a second.
"""

import json

import pytest

from soda_mmqc.config import EXAMPLES_DIR


def test_every_gold_file_parses():
    if not EXAMPLES_DIR.is_dir():
        pytest.skip(f"No example corpus at {EXAMPLES_DIR}")

    paths = sorted(EXAMPLES_DIR.rglob("*.json"))
    assert paths, f"No JSON found under {EXAMPLES_DIR}; the corpus is missing"

    broken = []
    for path in paths:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            broken.append(f"  {path.relative_to(EXAMPLES_DIR)}\n      {exc}")

    assert not broken, (
        f"{len(broken)} of {len(paths)} gold files do not parse:\n"
        + "\n".join(broken)
    )
