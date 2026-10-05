"""Panels per figure, for both contract shapes: exp-04's spurious-panel endpoint (P2).

Layer S counts rows per check, so a panel that a check-major answer invents
in all three lists is three spurious rows, and the same panel in a panel-major
answer is three as well -- the PM row is read once per check. That is right
for layer S, which asks how each check's rows line up with its gold, and wrong
for the question exp-04 asks of the shapes: **did the answer state a panel the
figure does not have?** Per figure, that is one panel, however many lists
repeat it.

    spurious panels   labels in the answer -- in any check's list, for CM --
                      that the gold does not have, counted once each
    missing panels    gold labels that no check's list carries
    partly missing    gold labels that some, but not all, checks' lists carry;
                      CM only, since a PM row holds every check

Labels are compared exactly, as layer S aligns them (`panel_label` is scored
`exact`). An answer that is missing or empty -- a failed session, or an
`outputs: []` -- states no panels: nothing spurious, every gold panel missing.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

CHECKS = ("micrograph-scale-bar", "individual-data-points", "error-bars-defined")
LIST, LABEL = "outputs", "panel_label"


def labels_per_check(answer: Optional[Mapping[str, Any]], shape: str) -> Dict[str, List[str]]:
    """The panel labels each check's part of an answer states, in order."""
    if shape not in ("cm", "pm"):
        raise ValueError(f"shape is 'cm' or 'pm', not {shape!r}")
    if not answer:
        return {check: [] for check in CHECKS}
    if shape == "pm":
        rows = answer.get(LIST) or []
        labels = [row.get(LABEL) for row in rows if isinstance(row, Mapping)]
        return {check: list(labels) for check in CHECKS}
    return {check: [row.get(LABEL) for row in (answer.get(check) or [])
                    if isinstance(row, Mapping)]
            for check in CHECKS}


def panel_counts(gold_labels: Sequence[str], answer: Optional[Mapping[str, Any]],
                 shape: str) -> Dict[str, int]:
    """Spurious, missing and partly missing panels in one answer for one figure."""
    gold = set(gold_labels)
    per_check = {check: set(labels) for check, labels in labels_per_check(answer, shape).items()}
    stated = set().union(*per_check.values())
    in_all = set.intersection(*per_check.values())
    return {
        "gold_panels": len(gold),
        "spurious_panels": len(stated - gold),
        "missing_panels": len(gold - stated),
        "partly_missing_panels": len((gold & stated) - in_all),
    }
