"""Eval manifest for micrograph-scale-bar checklist (phase 6)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from soda_mmqc.core.collation import (
    discover_collation_layout,
    validate_manifest_field_patterns,
    validate_manifest_list_alignment,
)
from soda_mmqc.core.eval_manifest import load_eval_manifest

CHECKLIST_DIR = (
    Path(__file__).resolve().parents[1]
    / "soda_mmqc/data/checklist/fig-checklist/micrograph-scale-bar"
)
SCHEMA_WRAPPER = CHECKLIST_DIR / "schema.json"
MANIFEST_PATH = CHECKLIST_DIR / "eval-manifest.json"
EXAMPLE_GOLD = (
    Path(__file__).resolve().parents[1]
    / "soda_mmqc/data/examples/10.1038_s44318-026-00715-1/content/1"
    / "checks/micrograph-scale-bar/expected_output.json"
)

# The examples dataset is gitignored, so it is absent on a fresh checkout and
# in CI. Skip rather than fail there -- the same guard Milestone 1 applied to
# tests/test_run_analyze_results.py for exactly this reason.
requires_example_gold = pytest.mark.skipif(
    not EXAMPLE_GOLD.is_file(),
    reason=f"examples dataset not available: {EXAMPLE_GOLD} is missing",
)


def _model_schema() -> dict:
    wrapper = json.loads(SCHEMA_WRAPPER.read_text(encoding="utf-8"))
    return wrapper["format"]["schema"]


@pytest.fixture
def manifest():
    return load_eval_manifest(MANIFEST_PATH)


@pytest.fixture
def model_schema():
    return _model_schema()


class TestMicrographScaleBarManifest:
    def test_manifest_loads(self, manifest):
        assert manifest.checklist == "micrograph-scale-bar"
        assert manifest.alignment_keys_for("outputs") == ("panel_label",)

    def test_all_schema_leaves_profiled(self, manifest, model_schema):
        from soda_mmqc.core.schema_discovery import discover_schema

        schema_patterns = {leaf.pattern for leaf in discover_schema(model_schema)}
        manifest_patterns = set(manifest.profiled_leaf_properties())
        assert manifest_patterns == schema_patterns

    @requires_example_gold
    def test_validates_against_layout(self, manifest, model_schema):
        gold = json.loads(EXAMPLE_GOLD.read_text(encoding="utf-8"))
        layout = discover_collation_layout(model_schema, gold, gold)
        assert layout.embedding_prefix == ()
        assert layout.predictive_lists[0].by_list_key == "outputs"
        validate_manifest_list_alignment(manifest, model_schema, layout)
        validate_manifest_field_patterns(manifest, model_schema, layout)
