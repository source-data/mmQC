"""Layer S structural reporting for list-of-objects properties."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

from soda_mmqc.core.object_list_pairing import ObjectListPairingResult


class StructuralOutcome(str, Enum):
    """Layer S row-slot reporting outcomes."""

    CORRECT_ROW = "correct_row"
    MISSING_ROW = "missing_row"
    SPURIOUS_ROW = "spurious_row"


@dataclass(frozen=True)
class StructuralRow:
    """One layer S row record in ``by_list``."""

    gold_index: Optional[int]
    pred_index: Optional[int]
    structural: StructuralOutcome
    similarity: Optional[float]


@dataclass(frozen=True)
class RowCounts:
    """Aggregated layer S counts for one list property."""

    correct_row: int
    missing_row: int
    spurious_row: int


@dataclass(frozen=True)
class ByListResult:
    """Layer S summary for one list-of-objects property."""

    row_counts: RowCounts
    rows: tuple[StructuralRow, ...]


def build_by_list(
    pairing: ObjectListPairingResult,
    *,
    n_gold: int,
    n_pred: int,
) -> ByListResult:
    """Build ``by_list`` layer S reporting from an object-list pairing result."""
    threshold = pairing.match_threshold
    pairs = pairing.pair_similarities

    gold_in_hungarian = {gold for gold, _, _ in pairs}
    pred_in_hungarian = {pred for _, pred, _ in pairs}

    rows: list[StructuralRow] = []

    for gold, pred, sim in sorted(pairs, key=lambda item: item[0]):
        if sim >= threshold:
            rows.append(
                StructuralRow(
                    gold_index=gold,
                    pred_index=pred,
                    structural=StructuralOutcome.CORRECT_ROW,
                    similarity=sim,
                )
            )
        else:
            rows.append(
                StructuralRow(
                    gold_index=gold,
                    pred_index=None,
                    structural=StructuralOutcome.MISSING_ROW,
                    similarity=None,
                )
            )
            rows.append(
                StructuralRow(
                    gold_index=None,
                    pred_index=pred,
                    structural=StructuralOutcome.SPURIOUS_ROW,
                    similarity=None,
                )
            )

    for gold in range(n_gold):
        if gold not in gold_in_hungarian:
            rows.append(
                StructuralRow(
                    gold_index=gold,
                    pred_index=None,
                    structural=StructuralOutcome.MISSING_ROW,
                    similarity=None,
                )
            )

    for pred in range(n_pred):
        if pred not in pred_in_hungarian:
            rows.append(
                StructuralRow(
                    gold_index=None,
                    pred_index=pred,
                    structural=StructuralOutcome.SPURIOUS_ROW,
                    similarity=None,
                )
            )

    row_counts = _row_counts_from_rows(rows)
    return ByListResult(row_counts=row_counts, rows=tuple(rows))


def _row_counts_from_rows(rows: Sequence[StructuralRow]) -> RowCounts:
    correct = sum(1 for r in rows if r.structural is StructuralOutcome.CORRECT_ROW)
    missing = sum(1 for r in rows if r.structural is StructuralOutcome.MISSING_ROW)
    spurious = sum(1 for r in rows if r.structural is StructuralOutcome.SPURIOUS_ROW)
    return RowCounts(
        correct_row=correct,
        missing_row=missing,
        spurious_row=spurious,
    )
