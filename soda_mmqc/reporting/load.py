"""Load flat evaluation runs from analysis.json on disk."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from soda_mmqc import logger
from soda_mmqc.config import CHECKLIST_DIR, EVALUATION_DIR
from soda_mmqc.core.eval_manifest import EvalManifest, load_eval_manifest
from soda_mmqc.core.run_layout import iter_leaves
from soda_mmqc.core.scoring import ANALYSIS_FILENAME


def _as_list(value: str | Sequence[str] | None) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    return list(value)


@dataclass(frozen=True)
class FlatRecord:
    """One per-doc flat analysis record."""

    doc_id: str | None
    metadata: dict[str, Any]
    analysis: dict[str, Any]
    expected_output: dict[str, Any] | None = None
    model_output: dict[str, Any] | None = None

    @property
    def has_payloads(self) -> bool:
        return (
            isinstance(self.expected_output, dict)
            and isinstance(self.model_output, dict)
        )


@dataclass(frozen=True)
class RunRef:
    """What identifies one scored run leaf.

    The harness writes ``<root>/<arm>/rep-NN/<example>/``, so an arm and a
    replicate are what distinguish two runs of the same check. ``model``
    is ``""`` when the root does not carry one -- an experiment root is
    ``experiments/runs/<exp>/<check>/`` with no model segment, and the
    caller supplies what the path does not.

    There is no ``prompt``. An arm is a different *configuration* of the
    same skill set; a prompt was a different wording. Code written for
    one is not correct for the other, so the field was removed rather
    than renamed.
    """

    checklist: str
    check: str
    model: str
    arm: str
    replicate: int


@dataclass(frozen=True)
class FlatRun:
    """One scored run leaf: ``<root>/<arm>/rep-NN/``."""

    ref: RunRef
    records: tuple[FlatRecord, ...]
    manifest: EvalManifest
    #: The leaf this was read from, so gold/pred payloads can be fetched
    #: lazily later. ``None`` for a run assembled in memory.
    path: Path | None = None

    # Flat accessors so consumers read `run.check`, not `run.ref.check`.
    @property
    def checklist(self) -> str:
        return self.ref.checklist

    @property
    def check(self) -> str:
        return self.ref.check

    @property
    def model(self) -> str:
        return self.ref.model

    @property
    def arm(self) -> str:
        return self.ref.arm

    @property
    def replicate(self) -> int:
        return self.ref.replicate


class FlatRuns(Sequence[FlatRun]):
    """Collection of loaded flat runs."""

    def __init__(self, runs: Sequence[FlatRun]) -> None:
        self._runs = tuple(runs)

    def __len__(self) -> int:
        return len(self._runs)

    def __iter__(self) -> Iterator[FlatRun]:
        return iter(self._runs)

    def __getitem__(self, index: int) -> FlatRun:
        return self._runs[index]


def _discover_models(eval_dir: Path) -> list[str]:
    """Model directories under a check that hold at least one scored leaf.

    A model directory is a run *root* now -- its children are arms -- so
    the analysis lives at ``<model>/<arm>/rep-NN/analysis.json`` rather
    than directly inside it.
    """
    models: list[str] = []
    if not eval_dir.is_dir():
        return models
    for child in sorted(eval_dir.iterdir()):
        if not child.is_dir():
            continue
        if any(
            (path / ANALYSIS_FILENAME).is_file()
            for _arm, _replicate, path in iter_leaves(child)
        ):
            models.append(child.name)
    return models


def _load_analysis_file(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _parse_payload(entry: Mapping[str, Any], key: str) -> dict[str, Any] | None:
    payload = entry.get(key)
    if isinstance(payload, dict):
        return dict(payload)
    return None


def _parse_flat_records(
    entries: list[Mapping[str, Any]],
    *,
    include_payloads: bool = False,
) -> tuple[FlatRecord, ...]:
    records: list[FlatRecord] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        analysis = entry.get("analysis")
        if not isinstance(analysis, dict):
            logger.warning(
                "Skipping record without analysis dict: %s",
                entry.get("doc_id"),
            )
            continue
        expected_output = _parse_payload(entry, "expected_output") if include_payloads else None
        model_output = _parse_payload(entry, "model_output") if include_payloads else None
        records.append(
            FlatRecord(
                doc_id=entry.get("doc_id"),
                metadata=(
                    dict(entry["metadata"])
                    if isinstance(entry.get("metadata"), dict)
                    else {}
                ),
                analysis=analysis,
                expected_output=expected_output,
                model_output=model_output,
            )
        )
    return tuple(records)


def record_source(record: FlatRecord) -> str:
    """Benchmark example path for one flat record (``metadata.source``)."""
    source = record.metadata.get("source")
    if isinstance(source, str) and source:
        return source
    if record.doc_id:
        return record.doc_id
    raise ValueError("FlatRecord has no metadata.source or doc_id")


def load_record_payloads(
    leaf_path: Path,
    source: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load ``expected_output`` and ``model_output`` from one run leaf.

    ``leaf_path`` is a ``<root>/<arm>/rep-NN/`` directory. There is no
    prompt key to select: a leaf holds one analysis, which is what having
    a file per leaf bought.
    """
    analysis_path = Path(leaf_path) / ANALYSIS_FILENAME
    if not analysis_path.is_file():
        raise FileNotFoundError(f"Missing analysis file: {analysis_path}")

    raw = _load_analysis_file(analysis_path)
    if not isinstance(raw, dict):
        raise ValueError(f"Expected object at root of {analysis_path}")

    entry = None
    for candidate in raw.get("flat") or ():
        if not isinstance(candidate, dict):
            continue
        metadata = candidate.get("metadata")
        if isinstance(metadata, dict) and metadata.get("source") == source:
            entry = candidate
            break
    if entry is None:
        raise KeyError(
            f"No flat record for source={source!r} in {analysis_path}"
        )

    expected_output = _parse_payload(entry, "expected_output")
    model_output = _parse_payload(entry, "model_output")
    if expected_output is None or model_output is None:
        raise KeyError(
            f"Record {source!r} in {analysis_path} is missing "
            "expected_output or model_output"
        )
    return expected_output, model_output


def find_record(summary_records: Sequence[Any], *, source: str) -> FlatRecord:
    """Return the :class:`FlatRecord` matching ``metadata.source``."""
    for record in summary_records:
        if record_source(record) == source:
            return record
    raise KeyError(f"No record with source={source!r}")


def ensure_record_payloads(
    record: FlatRecord,
    *,
    leaf_path: Path | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Gold/pred payloads, read from the leaf when not already carried."""
    if record.has_payloads:
        assert record.expected_output is not None
        assert record.model_output is not None
        return record.expected_output, record.model_output
    if leaf_path is None:
        raise KeyError(
            f"Record {record_source(record)!r} carries no payloads and the "
            "run it came from has no path to load them from"
        )
    return load_record_payloads(leaf_path, record_source(record))


def load_eval_manifest_for_check(checklist: str, check: str) -> EvalManifest:
    """Load ``eval-manifest.json`` for a checklist check."""
    path = eval_manifest_path(checklist, check)
    if not path.is_file():
        raise FileNotFoundError(f"Missing eval manifest: {path}")
    return load_eval_manifest(path)


@dataclass(frozen=True)
class EvaluationCheckRef:
    """A checklist check that has at least one ``analysis.json`` on disk."""

    checklist: str
    check: str
    has_manifest: bool = True


def eval_manifest_path(checklist: str, check: str) -> Path:
    """Path to ``eval-manifest.json`` for a checklist check."""
    return CHECKLIST_DIR / checklist / check / "eval-manifest.json"


def check_has_eval_manifest(checklist: str, check: str) -> bool:
    """Return whether the check has an on-disk eval manifest."""
    return eval_manifest_path(checklist, check).is_file()


def evaluation_data_cache_key(checklist: str, check: str) -> str:
    """Fingerprint on-disk manifest and analysis files for Streamlit cache busting."""
    parts = [checklist, check]
    manifest_path = eval_manifest_path(checklist, check)
    if manifest_path.is_file():
        parts.append(f"manifest:{manifest_path.stat().st_mtime_ns}")
    eval_dir = EVALUATION_DIR / checklist / check
    if eval_dir.is_dir():
        for model_dir in sorted(eval_dir.iterdir()):
            if not model_dir.is_dir():
                continue
            analysis_path = model_dir / "analysis.json"
            if analysis_path.is_file():
                parts.append(
                    f"{model_dir.name}:{analysis_path.stat().st_mtime_ns}"
                )
    return "|".join(parts)


def try_load_run_summaries(
    checklist: str,
    check: str,
) -> tuple[RunSummaries | None, str | None]:
    """Load aggregated run summaries, or return ``(None, user_message)``."""
    from soda_mmqc.reporting.aggregate import RunSummaries, summarize_runs

    manifest_path = eval_manifest_path(checklist, check)
    if not manifest_path.is_file():
        return None, (
            "This check has evaluation output but no **eval-manifest.json**. "
            f"Add a manifest at `{manifest_path}`, then reload."
        )

    eval_dir = EVALUATION_DIR / checklist / check
    if not eval_dir.is_dir():
        return None, (
            f"No evaluation directory at `{eval_dir}`. "
            "Run `mmqc run` and then `mmqc score` first."
        )

    try:
        runs = load_evaluation_dir(checklist, check)
    except FileNotFoundError as exc:
        return None, str(exc)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, f"Could not load evaluation data: {exc}"

    if len(runs) == 0:
        return None, (
            f"No scored runs under `{eval_dir}`. A run writes "
            "`<model>/<arm>/rep-NN/<example>/`, and `mmqc score` writes "
            "`analysis.json` into that same leaf -- predictions alone are "
            "not enough. If you recently added `eval-manifest.json`, clear "
            "the Streamlit cache (⋮ menu → Clear cache) and reload."
        )

    return summarize_runs(runs), None


def discover_evaluation_checks() -> tuple[EvaluationCheckRef, ...]:
    """List checks under ``EVALUATION_DIR`` with evaluation results."""
    refs: list[EvaluationCheckRef] = []
    if not EVALUATION_DIR.is_dir():
        return ()
    for checklist_dir in sorted(EVALUATION_DIR.iterdir()):
        if not checklist_dir.is_dir():
            continue
        for check_dir in sorted(checklist_dir.iterdir()):
            if not check_dir.is_dir():
                continue
            models = _discover_models(check_dir)
            if models:
                refs.append(
                    EvaluationCheckRef(
                        checklist=checklist_dir.name,
                        check=check_dir.name,
                        has_manifest=check_has_eval_manifest(
                            checklist_dir.name,
                            check_dir.name,
                        ),
                    )
                )
    return tuple(refs)


def load_run_root(
    root: Path,
    *,
    checklist: str,
    check: str,
    model: str = "",
    arms: str | Sequence[str] | None = None,
    include_payloads: bool = False,
) -> FlatRuns:
    """Load the scored leaves under one run root.

    A root is a directory whose children are arms, so this serves a
    production root (``data/evaluation/<checklist>/<check>/<model>/``)
    and an experiment root (``experiments/runs/<exp>/<check>/``) alike.
    They differ only in which facts the path carries, which is why
    ``checklist``, ``check`` and ``model`` are arguments rather than
    parsed out of it.

    A leaf with predictions but no ``analysis.json`` is a run that was
    never scored: warned about and skipped, not an error.
    """
    manifest = load_eval_manifest_for_check(checklist, check)
    arm_filter = _as_list(arms)
    runs: list[FlatRun] = []

    for arm, replicate, leaf_path in iter_leaves(Path(root)):
        if arm_filter is not None and arm not in arm_filter:
            continue
        analysis_path = leaf_path / ANALYSIS_FILENAME
        if not analysis_path.is_file():
            logger.warning(
                "No %s in %s; the run is unscored, skipping",
                ANALYSIS_FILENAME,
                leaf_path,
            )
            continue

        try:
            raw = _load_analysis_file(analysis_path)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load %s: %s", analysis_path, exc)
            continue

        if not isinstance(raw, dict):
            logger.warning("Expected object at root of %s", analysis_path)
            continue

        flat_entries = raw.get("flat")
        if not isinstance(flat_entries, list):
            logger.warning(
                "%s has no 'flat' array; skipping", analysis_path
            )
            continue

        runs.append(
            FlatRun(
                ref=RunRef(
                    checklist=checklist,
                    check=check,
                    model=model,
                    arm=arm,
                    replicate=replicate,
                ),
                records=_parse_flat_records(
                    flat_entries, include_payloads=include_payloads
                ),
                manifest=manifest,
                path=leaf_path,
            )
        )

    return FlatRuns(runs)


def load_evaluation_dir(
    checklist: str,
    check: str,
    *,
    models: str | Sequence[str] | None = None,
    arms: str | Sequence[str] | None = None,
    include_payloads: bool = False,
) -> FlatRuns:
    """Load the production tree, one root per model.

    A thin resolver over :func:`load_run_root`: the production path
    carries the model and an experiment root does not, and that is the
    only difference between the two.
    """
    eval_dir = EVALUATION_DIR / checklist / check
    model_list = _as_list(models) or _discover_models(eval_dir)
    if not model_list:
        logger.warning("No model directories found under %s", eval_dir)
        return FlatRuns(())

    runs: list[FlatRun] = []
    for model in model_list:
        root = eval_dir / model
        if not root.is_dir():
            logger.warning("Missing run root: %s", root)
            continue
        runs.extend(
            load_run_root(
                root,
                checklist=checklist,
                check=check,
                model=model,
                arms=arms,
                include_payloads=include_payloads,
            )
        )
    return FlatRuns(runs)
