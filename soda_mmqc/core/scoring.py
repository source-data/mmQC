"""Score a run's predictions against the gold outputs of its benchmark.

This is a *run's* worth of evaluation: resolve the check, read its
``benchmark.json``, pair each stored prediction with the expected output of
the same example, and hand the pairs to ``FlatEvaluator``. Evaluating one
record against one gold is ``core.evaluation``'s job, and this module never
reaches inside it.

The unit of scoring is one run leaf -- ``<root>/<arm>/rep-NN/`` -- because a
replicate is a resample and an arm is a different configuration. Pooling
them is reporting's job, never this module's.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from tqdm import tqdm

from soda_mmqc import logger
from soda_mmqc.config import DEFAULT_SENTENCE_TRANSFORMER_MODEL
from soda_mmqc.core.eval_manifest import load_eval_manifest
from soda_mmqc.core.evaluation import FlatEvaluator
from soda_mmqc.core.examples import EXAMPLE_FACTORY
from soda_mmqc.core.leaves import _default_semantic_embedder
from soda_mmqc.agentic.runner import DEFAULT_RUN_LABEL, PREDICTION_FILENAME
from soda_mmqc.agentic.skills import _read_json, resolve_check_dir

__all__ = [
    "ANALYSIS_FILENAME",
    "ModelResult",
    "analyze_results",
    "save_analysis",
    "load_predictions",
    "score_check",
]

#: The scored result of one run leaf, written beside the ``<example>/``
#: directories it describes. One per leaf, because an arm is not a
#: replicate and each is scored on its own.
ANALYSIS_FILENAME = "analysis.json"


@dataclass
class ModelResult:
    """Container for a single model evaluation result.
    
    Attributes:
        doc_id: The document identifier for the example (e.g., 
            "10.1038/emboj.2009.312")
        model_output: The raw structured output from the model API
    """
    doc_id: str | None
    model_output: Dict[str, Any]
    metadata: Dict[str, Any]



def _model_schema(schema_wrapper: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the inner model schema from an OpenAI-style wrapper."""
    if "format" in schema_wrapper and "schema" in schema_wrapper["format"]:
        return schema_wrapper["format"]["schema"]
    return schema_wrapper



def analyze_results(
    results: List[ModelResult],
    schema: Dict[str, Any],
    expected_outputs: List[Dict[str, Any]],
    *,
    check_dir: Path,
    match_threshold: float = 1.0,
    sentence_transformer_model: str = (
        DEFAULT_SENTENCE_TRANSFORMER_MODEL
    ),
    embedder: Optional[Any] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Analyze model outputs against expected outputs with ``FlatEvaluator``.

    Per-field ``string_compare`` and ``match_threshold`` live in
    ``eval-manifest.json`` beside the check schema.

    Returns a dict with a single ``"flat"`` key mapping to per-example
    analysis records (compatible with ``save_analysis`` nesting).
    """
    manifest_path = check_dir / "eval-manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(
            f"Missing eval manifest for check {check_dir.name}: {manifest_path}"
        )

    if match_threshold != 1.0:
        logger.warning(
            "match_threshold=%s is ignored; per-field thresholds are set in "
            "eval-manifest.json",
            match_threshold,
        )

    manifest = load_eval_manifest(manifest_path)
    model_schema = _model_schema(schema)
    if embedder is None:
        embedder = _default_semantic_embedder(sentence_transformer_model)
    evaluator = FlatEvaluator(model_schema, manifest, embedder=embedder)

    logger.info("Analyzing results with FlatEvaluator (%s)", manifest.checklist)

    analyzed_results: List[Dict[str, Any]] = []
    for result, expected_output in tqdm(
        zip(results, expected_outputs),
        desc="Analyzing",
        unit=" example",
    ):
        logger.debug(
            "========= Analyzing: %s =========",
            result.doc_id,
        )
        evaluation = evaluator.evaluate(expected_output, result.model_output)
        analyzed_results.append({
            "doc_id": result.doc_id,
            "expected_output": expected_output,
            "model_output": result.model_output,
            "metadata": result.metadata,
            "analysis": evaluation.to_dict(),
        })

    return {"flat": analyzed_results}



def save_analysis(
    analyzed_results: Dict[str, List[Dict[str, Any]]],
    root: Path,
) -> Path:
    """Write one run leaf's analysis beside the predictions it describes.

    ``root`` is a run leaf -- ``<root>/<arm>/rep-NN/`` -- so each arm and
    each replicate keeps its own score. The previous signature took
    ``(checklist, check, model)`` and resolved one path per model, which
    every arm and every replicate then shared and overwrote in turn:
    scoring a second leaf destroyed the first, silently and plausibly.

    Exceptions propagate. The previous body caught, logged and re-raised,
    which told the caller nothing it would not already see.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    analysis_file = root / ANALYSIS_FILENAME
    analysis_file.write_text(
        json.dumps(analyzed_results, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    logger.info("Saved analysis to %s", analysis_file)
    return analysis_file



def load_predictions(predictions_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load stored predictions, keyed by example relative source path.

    Two layouts are accepted:

    * **A directory** -- the layout the runner writes: one subdirectory per
      example, mirroring the example's relative source path, each holding a
      ``prediction.json`` with that example's final leaf JSON. Debug sidecars
      (intermediate artifacts, skill traces) may sit alongside and are
      ignored here; only leaf JSON is scored.
    * **A JSON file** -- an object mapping example relative source path to
      that example's leaf JSON. Convenient for hand-assembled runs.

    Raises:
        FileNotFoundError: If ``predictions_path`` does not exist.
        ValueError: If the file layout is malformed or a directory holds no
            predictions at all.
    """
    predictions_path = Path(predictions_path)
    if not predictions_path.exists():
        raise FileNotFoundError(f"Predictions not found: {predictions_path}")

    if predictions_path.is_dir():
        return _load_predictions_from_dir(predictions_path)
    return _load_predictions_from_file(predictions_path)


def _load_predictions_from_dir(root: Path) -> Dict[str, Dict[str, Any]]:
    predictions: Dict[str, Dict[str, Any]] = {}
    for prediction_file in sorted(root.rglob(PREDICTION_FILENAME)):
        example = prediction_file.parent.relative_to(root).as_posix()
        if example == ".":
            raise ValueError(
                f"{prediction_file} sits at the root of the predictions "
                "directory; predictions must live under a subdirectory "
                "named after the example's relative source path"
            )
        predictions[example] = _read_prediction(prediction_file)

    if not predictions:
        raise ValueError(
            f"No {PREDICTION_FILENAME} files found under {root}"
        )
    return predictions


def _load_predictions_from_file(path: Path) -> Dict[str, Dict[str, Any]]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(
            f"Expected an object mapping example path to leaf JSON in "
            f"{path}, got {type(payload).__name__}"
        )
    for example, output in payload.items():
        if not isinstance(output, dict):
            raise ValueError(
                f"Prediction for {example!r} in {path} is not an object"
            )
    return dict(payload)


def _read_prediction(path: Path) -> Dict[str, Any]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise ValueError(
            f"Expected a JSON object (the check's leaf output) in {path}, "
            f"got {type(payload).__name__}"
        )
    return payload


def score_check(
    checklist: str,
    check: str,
    predictions_path: Path,
    *,
    sentence_transformer_model: str = DEFAULT_SENTENCE_TRANSFORMER_MODEL,
    embedder: Optional[Any] = None,
    save: bool = True,
) -> Dict[str, List[Dict[str, Any]]]:
    """Score one run leaf's predictions against its gold outputs.

    Only the examples that have a prediction are scored; examples listed in
    ``benchmark.json`` without one are reported and skipped, so a partial run
    over a handful of examples can still be scored.

    Args:
        checklist: Checklist name, e.g. ``fig-checklist``.
        check: Check name, e.g. ``micrograph-scale-bar``.
        predictions_path: One run leaf -- ``<root>/<arm>/rep-NN/`` -- or a
            JSON file mapping example path to leaf output. When ``save`` is
            true the analysis is written here, beside what it describes.
        sentence_transformer_model: Embedding model for semantic comparisons.
        embedder: Optional embedder override, mainly for tests.
        save: If True, write ``analysis.json`` into ``predictions_path``.

    Returns:
        ``{"flat": [...]}``. There is no outer run-label key: it held one
        entry per prompt, and with prompts gone it was always the literal
        ``"agentic"`` -- while each leaf now has an ``analysis.json`` of its
        own, which is what actually distinguishes two scored runs.
    """
    check_dir = resolve_check_dir(checklist, check)
    schema = _read_json(check_dir / "schema.json")
    benchmark = _read_json(check_dir / "benchmark.json")

    check_name = benchmark.get("name", check_dir.name)
    try:
        example_class = benchmark["example_class"]
    except KeyError:
        raise ValueError(
            f"No example_class in {check_dir / 'benchmark.json'}"
        ) from None
    benchmark_examples = benchmark.get("examples") or []
    if not benchmark_examples:
        raise ValueError(
            f"No examples listed in {check_dir / 'benchmark.json'}"
        )

    predictions = load_predictions(Path(predictions_path))

    unknown = [ex for ex in predictions if ex not in set(benchmark_examples)]
    if unknown:
        logger.warning(
            "Ignoring %d prediction(s) for examples not in the benchmark of "
            "%s: %s",
            len(unknown),
            check_name,
            ", ".join(sorted(unknown)),
        )
    scored_examples = [ex for ex in benchmark_examples if ex in predictions]
    missing = [ex for ex in benchmark_examples if ex not in predictions]
    if missing:
        logger.warning(
            "No prediction for %d of %d benchmark example(s) of %s; "
            "scoring the remaining %d",
            len(missing),
            len(benchmark_examples),
            check_name,
            len(scored_examples),
        )
    if not scored_examples:
        known = set(benchmark_examples)
        # Every key having the form `<something>/<known example>` means this
        # is a run root, not a predictions directory: a run writes one leaf
        # per arm per replicate, and each is scored on its own. Saying so
        # beats reporting that nothing matched.
        leaves = set()
        for key in predictions:
            for example in known:
                if key.endswith("/" + example):
                    leaves.add(key[: -len(example) - 1])
                    break
        if leaves:
            raise ValueError(
                f"{predictions_path} looks like a run root, not a predictions "
                f"directory: it holds {len(leaves)} of them "
                f"({', '.join(sorted(leaves))}). A run writes one per arm per "
                f"replicate, and each is scored on its own -- point "
                f"--predictions at one of them."
            )
        raise ValueError(
            f"None of the predictions in {predictions_path} match an example "
            f"in the benchmark of {check_name}"
        )

    results: List[ModelResult] = []
    expected_outputs: List[Dict[str, Any]] = []
    for relative_source_path in scored_examples:
        example = EXAMPLE_FACTORY.create(relative_source_path, example_class)
        expected_output = example.get_expected_output(check_name)
        if not expected_output:
            logger.warning(
                "No expected output for %s; skipping", relative_source_path
            )
            continue
        expected_outputs.append(expected_output)
        results.append(
            ModelResult(
                doc_id=example.doc_id,
                model_output=predictions[relative_source_path],
                metadata={
                    "doc_id": example.doc_id,
                    "source": example.relative_source_path,
                    "example_type": example.example_class_name,
                },
            )
        )

    if not results:
        raise ValueError(
            f"No expected outputs found for the predicted examples of "
            f"{check_name}"
        )

    analyzed_results = analyze_results(
        results,
        schema,
        expected_outputs,
        check_dir=check_dir,
        sentence_transformer_model=sentence_transformer_model,
        embedder=embedder,
    )

    if save:
        # A leaf directory holds its own analysis; a hand-assembled JSON
        # file gets one beside it, since a file has no inside.
        destination = Path(predictions_path)
        if not destination.is_dir():
            destination = destination.parent
        save_analysis(analyzed_results, destination)
    return analyzed_results

