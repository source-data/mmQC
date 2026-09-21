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
from soda_mmqc.core.run_layout import (
    BASELINE_ARM,
    leaf,
    replicate_dirname,
    resolve_check_root,
)
from soda_mmqc.agentic.skills import _read_json, resolve_check_dir
from soda_mmqc.core.examples import EXAMPLE_FACTORY
from soda_mmqc.core.scoring import load_predictions

__all__ = [
    "DRAFT_REPLICATE",
    "DRAFT_REPLICATE_INDEX",
    "init_expected_outputs",
]

#: The replicate a draft is taken from. Not a consensus across replicates:
#: a curator corrects one answer, and averaging would hide precisely the
#: examples where the replicates disagreed -- which are the ones worth
#: looking at closely.
#:
#: This is a fact about curation, not about the layout, which is why it
#: lives here rather than in :mod:`soda_mmqc.core.run_layout`.
DRAFT_REPLICATE_INDEX = 0
DRAFT_REPLICATE = replicate_dirname(DRAFT_REPLICATE_INDEX)


def _draft_leaf(root: Path, check: str) -> Path:
    """The ``<arm>/rep-NN/`` directory a run root's drafts come from.

    Drafts come from the baseline arm: an unpinned variant is a
    comparison, not a candidate for gold.
    """
    return leaf(
        resolve_check_root(Path(root), check),
        arm=BASELINE_ARM,
        replicate=DRAFT_REPLICATE_INDEX,
    )


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
