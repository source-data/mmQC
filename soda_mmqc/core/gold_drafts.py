"""Draft ``expected_output.json`` so curation is correction, not typing.

A check's gold starts as a model's answer and is corrected by a curator.
Producing that first draft by hand means filling in most fields from
scratch; producing it from a run means reading and fixing.

Two sources. By default the check is run. With ``from_run`` the drafts come
from a run that already exists, which costs nothing -- and since a run may
hold several replicates, the draft is ``rep-00``, never a consensus: the
curator is correcting one answer, and an average across replicates would
hide exactly the cases where the model was unsure.

This is the surviving half of the old ``initialize`` in the prompt
pipeline. Only its *producer* was legacy: the loop was always "get one
output per example, then ``save_expected_output``", and ``run_check_live``
emits the same per-example leaf JSON the prompt path did.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence

from soda_mmqc import logger
from soda_mmqc.config import CHECKLIST_DIR, list_checks
from soda_mmqc.agentic.runner import run_check_live
from soda_mmqc.agentic.skills import _read_json, resolve_check_dir
from soda_mmqc.core.examples import EXAMPLE_FACTORY
from soda_mmqc.core.scoring import load_predictions

__all__ = [
    "BASELINE_ARM",
    "DRAFT_REPLICATE",
    "init_expected_outputs",
]

#: The arm every run writes, whether or not anything was unpinned.
BASELINE_ARM = "pinned"

#: The replicate a draft is taken from. Not a consensus across replicates:
#: a curator corrects one answer, and averaging would hide precisely the
#: examples where the replicates disagreed -- which are the ones worth
#: looking at closely.
DRAFT_REPLICATE = "rep-00"


def _draft_leaf(root: Path, check: str) -> Path:
    """The ``<arm>/rep-NN/`` directory a run root's drafts come from.

    A root may hold one check (``experiments/runs/<exp>/<check>/``) or
    several (``experiments/runs/<exp>/``), so try the per-check level
    first.
    """
    root = Path(root)
    if not root.is_dir():
        raise FileNotFoundError(f"No run root at {root}")

    base = root / check if (root / check).is_dir() else root
    arm = base / BASELINE_ARM
    if not arm.is_dir():
        present = sorted(p.name for p in base.iterdir() if p.is_dir())
        raise ValueError(
            f"{base} holds no {BASELINE_ARM!r} arm to draft from; it has "
            f"{present or 'nothing'}. Drafts come from the baseline arm, "
            "since an unpinned variant is a comparison and not a candidate "
            "for gold."
        )

    leaf = arm / DRAFT_REPLICATE
    if not leaf.is_dir():
        present = sorted(p.name for p in arm.iterdir() if p.is_dir())
        raise ValueError(
            f"{arm} has no {DRAFT_REPLICATE}; it has {present or 'nothing'}. "
            "A draft is one answer a curator corrects, so it is taken from "
            "a named replicate rather than pooled across whichever ones ran."
        )
    return leaf


def _example_class(check_dir: Path) -> str:
    benchmark = _read_json(check_dir / "benchmark.json")
    try:
        return benchmark["example_class"]
    except KeyError:
        raise ValueError(
            f"No example_class in {check_dir / 'benchmark.json'}"
        ) from None


def _write_drafts(
    predictions: Mapping[str, dict],
    checklist: str,
    check: str,
    *,
    overwrite: bool,
) -> List[str]:
    check_dir = resolve_check_dir(checklist, check)
    example_class = _example_class(check_dir)
    check_name = _read_json(check_dir / "benchmark.json").get(
        "name", check_dir.name
    )

    written: List[str] = []
    for relative_source_path, prediction in sorted(predictions.items()):
        example = EXAMPLE_FACTORY.create(relative_source_path, example_class)
        example.save_expected_output(prediction, check_name, overwrite)
        written.append(relative_source_path)
    return written


def init_expected_outputs(
    checklist: str,
    checks: Optional[Sequence[str]] = None,
    *,
    from_run: Optional[Path] = None,
    model: Optional[str] = None,
    provider: str = "openai",
    overwrite: bool = True,
    examples: Optional[Sequence[str]] = None,
    limit: Optional[int] = None,
) -> Dict[str, List[str]]:
    """Write a first-draft ``expected_output.json`` per benchmark example.

    Args:
        checklist: Checklist name, e.g. ``fig-checklist``.
        checks: Checks to initialize. Defaults to every check.
        from_run: Take drafts from this existing run root instead of
            running the check. Costs nothing, and uses ``rep-00``.
        model: Model for a live run. Ignored with ``from_run``.
        provider: Agent runtime for a live run. Ignored with ``from_run``.
        overwrite: Replace an ``expected_output.json`` that already exists.
        examples: Limit a live run to these examples.
        limit: Limit a live run to this many examples.

    Returns:
        ``{check_name: [relative_source_path, ...]}`` -- what was written.
    """
    checklist_dir = CHECKLIST_DIR / checklist
    available = list_checks(checklist_dir)
    if not available:
        raise ValueError(f"No checks found in checklist: {checklist}")

    wanted = list(checks) if checks else sorted(available)
    unknown = [name for name in wanted if name not in available]
    if unknown:
        raise ValueError(
            f"No such check in {checklist}: {', '.join(sorted(unknown))}"
        )

    written: Dict[str, List[str]] = {}
    for check in wanted:
        if from_run is not None:
            leaf = _draft_leaf(Path(from_run), check)
            predictions = load_predictions(leaf)
            logger.info(
                "Drafting %s from %s: %d example(s), spending nothing",
                check, leaf, len(predictions),
            )
        else:
            predictions = _run_for_drafts(
                checklist,
                check,
                model=model,
                provider=provider,
                examples=examples,
                limit=limit,
            )

        written[check] = _write_drafts(
            predictions, checklist, check, overwrite=overwrite
        )

    return written


def _run_for_drafts(
    checklist: str,
    check: str,
    *,
    model: Optional[str],
    provider: str,
    examples: Optional[Sequence[str]],
    limit: Optional[int],
) -> Dict[str, dict]:
    """Run the check and read back its baseline replicate.

    The predictions go to a scratch directory rather than the run tree:
    this run exists to seed gold, not to be scored, and leaving it beside
    real runs would invite exactly that.
    """
    with tempfile.TemporaryDirectory(prefix="soda-mmqc-init-") as scratch:
        run_check_live(
            checklist,
            check,
            output=Path(scratch),
            model=model,
            provider=provider,
            examples=examples,
            limit=limit,
        )
        return load_predictions(_draft_leaf(Path(scratch), check))
