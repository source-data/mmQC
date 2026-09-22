"""Tests for the run-level evaluator in core/scoring.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from soda_mmqc.core.eval_manifest import load_eval_manifest
from soda_mmqc.core.property_rollup import rollup_by_property
from soda_mmqc.core.scoring import ModelResult, analyze_results

CHECK_DIR = (
    Path(__file__).resolve().parents[1]
    / "soda_mmqc/data/checklist/fig-checklist/micrograph-scale-bar"
)
MANIFEST_PATH = CHECK_DIR / "eval-manifest.json"
SCHEMA_WRAPPER = json.loads(
    (CHECK_DIR / "schema.json").read_text(encoding="utf-8")
)
GOLD_PATH = (
    Path(__file__).resolve().parents[1]
    / "soda_mmqc/data/examples/10.1038_s44318-026-00715-1/content/1"
    / "checks/micrograph-scale-bar/expected_output.json"
)
if not GOLD_PATH.is_file():
    # The examples dataset is not tracked in git. Skip rather than raise at
    # import time, so a missing dataset does not abort collection of the
    # whole suite.
    pytest.skip(
        f"Examples dataset not available: {GOLD_PATH}",
        allow_module_level=True,
    )
EXAMPLE_GOLD = json.loads(GOLD_PATH.read_text(encoding="utf-8"))


def _mock_embedder(texts):
    import torch

    dim = 8
    return torch.stack([torch.ones(dim) for _ in texts])


class TestAnalyzeResults:
    def test_perfect_match_micrograph_scale_bar(self):
        results = [
            ModelResult(
                doc_id="10.1038_s44318-026-00715-1/content/1",
                model_output=EXAMPLE_GOLD,
                metadata={"doc_id": "10.1038_s44318-026-00715-1/content/1"},
            )
        ]
        analyzed = analyze_results(
            results,
            SCHEMA_WRAPPER,
            [EXAMPLE_GOLD],
            check_dir=CHECK_DIR,
            embedder=_mock_embedder,
        )

        assert set(analyzed) == {"flat"}
        record = analyzed["flat"][0]
        assert record["doc_id"] == "10.1038_s44318-026-00715-1/content/1"
        analysis = record["analysis"]
        assert "instances" in analysis
        assert "by_list" in analysis
        # No rollup is stored: it depends on manifest thresholds, which we
        # tune, so it is derived when a report is built.
        assert "by_property" not in analysis
        rollups = rollup_by_property(
            analysis["instances"], load_eval_manifest(MANIFEST_PATH)
        )
        assert rollups["outputs[].micrograph"].mean_score == 1.0

    def test_missing_manifest_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="eval-manifest"):
            analyze_results(
                [],
                SCHEMA_WRAPPER,
                [],
                check_dir=tmp_path,
                embedder=_mock_embedder,
            )


def _scoring_source() -> str:
    return (
        Path(__file__).resolve().parents[1]
        / "soda_mmqc" / "core" / "scoring.py"
    ).read_text(encoding="utf-8")


def test_scoring_does_not_import_the_cli():
    """core/ is below cli: the CLI calls scoring, never the reverse.

    A cycle here would be invisible until someone imports core.scoring in a
    notebook and pulls argparse and the whole agentic surface with it.
    """
    source = _scoring_source()
    assert "from soda_mmqc.cli" not in source
    assert "import soda_mmqc.cli" not in source


def test_scoring_does_not_import_the_legacy_runner():
    assert "scripts.run" not in _scoring_source()
