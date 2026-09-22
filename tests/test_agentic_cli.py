"""Tests for the agentic checklist CLI (``soda_mmqc.cli``).

Two concerns are covered here:

* **Check enumeration.** A checklist directory holds checks and, from
  Milestone 2 on, shared skills as flat siblings. Only the directories that
  own the evaluation contracts are checks; a shared skill beside them must
  not become a phantom check.
* **Scoring.** ``score`` loads stored predictions plus gold and produces the
  same ``FlatEvaluator`` ``flat`` result the legacy ``evaluate`` path
  produces.

The scoring tests build a self-contained checklist and example tree in
``tmp_path`` from the real ``micrograph-scale-bar`` schema and eval manifest,
so they run without the (untracked) examples dataset.

On top of that, the classes at the bottom of the file drive the same code
against a **real** example from the dataset,
``D4R_10.1038_s44318-026-00693-4`` -- a five-figure EMBO J submission with
real captions, real JPEGs, real source-data files and real gold. Those tests
skip when the dataset is absent.
"""

from __future__ import annotations

import base64
import collections
import io
import dataclasses
import os
import tempfile
import copy
import inspect
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from soda_mmqc.config import CHECKLIST_DIR, EXAMPLES_DIR
from soda_mmqc.core.examples import EXAMPLE_FACTORY
from soda_mmqc.config import (
    EVALUATION_CONTRACT_FILES,
    list_checks,
    owns_evaluation_contracts,
)
from soda_mmqc.core.scoring import ModelResult, analyze_results

import soda_mmqc.cli as cli
import soda_mmqc.config as config
import soda_mmqc.agentic.runner as runner
import soda_mmqc.agentic.runtime as agentic_runtime

# Imported from the module that defines each name, rather than
# through a re-export surface on cli: patching and reading must
# reach the one definition.
from soda_mmqc.agentic.pinning import (
    MODEL_DEFAULTS_FILENAME,
    VERSION_MANIFEST_FILENAME,
    checklist_pins,
    expand_skill_sets,
    load_model_defaults,
    load_version_manifest,
    resolve_skill_set,
    validate_version_manifest,
)
from soda_mmqc.agentic.runner import (
    _as_prediction,
    run_check_live,
    run_check_mock,
)
from soda_mmqc.agentic.runtime import (
    EXAMPLE_GOLD_SUBDIR,
    assemble_runtime,
    describe_permission_profile,
    session_cache_key,
    session_options,
)
from soda_mmqc.agentic.session import (
    AUDIT_INPUT_MAX_BYTES,
    INTERMEDIATES_DIRNAME,
    PREDICTION_FILENAME,
    SKILL_SET_FILENAME,
    SKILL_TRACE_FILENAME,
    TOOL_AUDIT_FILENAME,
    ToolAuditLog,
    _extract_tool_calls,
    _extract_usage,
    _run_agent_session,
    _session_message,
    compare_declared_and_observed,
    interactive_approver,
    make_pretooluse_hook,
    runtime_session,
    validate_against_schema,
)
from soda_mmqc.agentic.skills import (
    SKILL_FILENAME,
    SKILL_TOOL,
    _prose_blocks,
    build_graph,
    find_cycle,
    invoked_skills,
    load_skill,
    load_skills,
    resolve_check_dir,
    validate_skills,
)
from soda_mmqc.agentic.views import (
    DAG_FILENAME,
    GENERATED_README_FILENAME,
    render_dag,
    render_readme,
)
from soda_mmqc.config import (
    AGENTIC_INPUT_MANIFEST_FILENAME,
    AGENTIC_INPUT_SUBDIR,
)
from soda_mmqc.core.scoring import (
    load_predictions,
    score_check,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
PILOT_CHECK_DIR = (
    REPO_ROOT / "soda_mmqc/data/checklist/fig-checklist/micrograph-scale-bar"
)

# The eleven active figure checks, as enumerated today. Shared skills added
# by later milestones must not appear here.
FIG_CHECKLIST_CHECKS = {
    "error-bars-defined",
    "image-annotation-defined",
    "individual-data-points",
    "micrograph-scale-bar",
    "panel-image-matches-caption",
    "plot-axis-units",
    "plot-gap-labeling",
    "replication-reporting",
    "single-channel-for-overlay",
    "stat-significance-level",
    "stat-test",
}

# Checklists that stay on the legacy layout: every subdirectory of these is
# still a check, so enumeration there must not lose anything.
LEGACY_CHECKLISTS = ("data-checklist", "doc-checklist", "Retired-checklist")

# `fig-checklist` is fully converted, so a genuinely legacy check now has to
# come from a checklist that is not.
LEGACY_CHECKLIST = "doc-checklist"
LEGACY_CHECK = "AB-target-reagent-consistency"

# Smallest valid PNG (1x1, transparent). The scoring path never decodes the
# image, but FigureExample refuses to load without one.
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR42mNkYAAAAAYAAj"
    "CB0C8AAAAASUVORK5CYII="
)


def _mock_embedder(texts):
    """Deterministic embedder so semantic fields never load a real model."""
    import torch

    dim = 8
    return torch.stack([torch.ones(dim) for _ in texts])


def _gold(panel_label: str, micrograph: str = "yes") -> Dict[str, Any]:
    return {
        "outputs": [
            {
                "panel_label": panel_label,
                "micrograph": micrograph,
                "scale_bar_on_image": "yes",
                "scale_bar_defined_in_caption": "yes",
                "from_the_caption": "Scale bar: 10 um.",
                "scale_bar_defined_in_image": "no",
                "from_the_image": "",
            }
        ]
    }


class TestOwnsEvaluationContracts:
    """A check is a directory that owns an evaluation contract -- nothing else."""

    def test_directory_with_contracts_is_a_check(self, tmp_path: Path):
        check_dir = tmp_path / "some-leaf"
        check_dir.mkdir()
        for name in EVALUATION_CONTRACT_FILES:
            (check_dir / name).write_text("{}", encoding="utf-8")
        assert owns_evaluation_contracts(check_dir) is True

    def test_shared_skill_with_runtime_schema_only_is_not_a_check(
        self, tmp_path: Path
    ):
        # This is exactly the shape of identify-panels: a runtime schema, no
        # eval assets, sitting as a flat sibling of the checks.
        skill_dir = tmp_path / "identify-panels"
        (skill_dir / "v1").mkdir(parents=True)
        (skill_dir / "schema.json").write_text("{}", encoding="utf-8")
        (skill_dir / "v1" / "SKILL.md").write_text("---\n---\n", encoding="utf-8")
        assert owns_evaluation_contracts(skill_dir) is False

    def test_directory_without_contracts_is_not_a_check(self, tmp_path: Path):
        plain_dir = tmp_path / "prompts"
        plain_dir.mkdir()
        assert owns_evaluation_contracts(plain_dir) is False

    def test_file_is_not_a_check(self, tmp_path: Path):
        a_file = tmp_path / "dag.yaml"
        a_file.write_text("", encoding="utf-8")
        assert owns_evaluation_contracts(a_file) is False


class TestListChecks:
    def test_fig_checklist_enumeration_unchanged(self):
        checks = list_checks(CHECKLIST_DIR / "fig-checklist")
        assert set(checks) == FIG_CHECKLIST_CHECKS
        for name, path in checks.items():
            assert path == CHECKLIST_DIR / "fig-checklist" / name

    @pytest.mark.parametrize("checklist", LEGACY_CHECKLISTS)
    def test_legacy_checklists_enumerate_every_subdirectory(
        self, checklist: str
    ):
        checklist_dir = CHECKLIST_DIR / checklist
        every_subdir = {
            child.name for child in checklist_dir.iterdir() if child.is_dir()
        }
        assert set(list_checks(checklist_dir)) == every_subdir

    def test_shared_skill_sibling_is_not_enumerated(self, tmp_path: Path):
        checklist_dir = tmp_path / "fig-checklist"
        checklist_dir.mkdir()

        leaf = checklist_dir / "micrograph-scale-bar"
        leaf.mkdir()
        for name in EVALUATION_CONTRACT_FILES:
            (leaf / name).write_text("{}", encoding="utf-8")

        shared = checklist_dir / "identify-panels"
        shared.mkdir()
        (shared / "schema.json").write_text("{}", encoding="utf-8")

        assert set(list_checks(checklist_dir)) == {"micrograph-scale-bar"}


@pytest.fixture
def pilot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A one-check checklist plus two examples, wired into the config paths.

    Returns a namespace-ish dict with the paths and the gold outputs, so the
    tests can build predictions and compare against ``analyze_results``.
    """
    checklist_root = tmp_path / "checklist"
    examples_root = tmp_path / "examples"

    check_dir = checklist_root / "fig-checklist" / "micrograph-scale-bar"
    check_dir.mkdir(parents=True)
    for name in ("schema.json", "eval-manifest.json"):
        shutil.copyfile(PILOT_CHECK_DIR / name, check_dir / name)

    example_paths = ["doc-a/content/1", "doc-b/content/1"]
    golds = {
        "doc-a/content/1": _gold("A"),
        "doc-b/content/1": _gold("B", micrograph="no"),
    }
    (check_dir / "benchmark.json").write_text(
        json.dumps(
            {
                "name": "micrograph-scale-bar",
                "description": "pilot fixture",
                "example_class": "figure",
                "examples": example_paths,
            }
        ),
        encoding="utf-8",
    )

    for relative_path in example_paths:
        source = examples_root / relative_path
        (source / "content").mkdir(parents=True)
        (source / "content" / "caption.txt").write_text(
            "A representative micrograph. Scale bar: 10 um.", encoding="utf-8"
        )
        (source / "content" / "figure.png").write_bytes(_PNG_1X1)
        gold_dir = source / "checks" / "micrograph-scale-bar"
        gold_dir.mkdir(parents=True)
        (gold_dir / "expected_output.json").write_text(
            json.dumps(golds[relative_path]), encoding="utf-8"
        )

    monkeypatch.setattr(config, "CHECKLIST_DIR", checklist_root)
    monkeypatch.setattr(
        "soda_mmqc.core.examples.EXAMPLES_DIR", examples_root
    )

    return {
        "checklist_root": checklist_root,
        "examples_root": examples_root,
        "check_dir": check_dir,
        "examples": example_paths,
        "golds": golds,
        "schema": json.loads(
            (check_dir / "schema.json").read_text(encoding="utf-8")
        ),
    }


def _write_predictions_dir(
    root: Path, predictions: Dict[str, Dict[str, Any]]
) -> Path:
    for relative_path, output in predictions.items():
        target = root / relative_path
        target.mkdir(parents=True, exist_ok=True)
        (target / PREDICTION_FILENAME).write_text(
            json.dumps(output), encoding="utf-8"
        )
    return root



def _rollups(analysis: Dict[str, Any], checklist: str, check: str):
    """Roll a record's instances up, the way a report would.

    analysis.json stores measurements, not rollups: aggregating needs the
    manifest's thresholds, which are tunable, so it happens at read time.
    """
    from soda_mmqc.core.eval_manifest import load_eval_manifest
    from soda_mmqc.core.property_rollup import rollup_by_property

    manifest = load_eval_manifest(
        resolve_check_dir(checklist, check) / "eval-manifest.json"
    )
    return rollup_by_property(analysis["instances"], manifest)


class TestLoadPredictions:
    def test_loads_directory_layout(self, tmp_path: Path):
        payload = {"a/content/1": _gold("A"), "b/content/2": _gold("B")}
        root = _write_predictions_dir(tmp_path / "predictions", payload)
        assert load_predictions(root) == payload

    def test_ignores_debug_sidecars(self, tmp_path: Path):
        payload = {"a/content/1": _gold("A")}
        root = _write_predictions_dir(tmp_path / "predictions", payload)
        intermediates = root / "a/content/1" / "intermediates"
        intermediates.mkdir()
        (intermediates / "skill_trace.json").write_text("[]", encoding="utf-8")
        assert load_predictions(root) == payload

    def test_loads_json_file_mapping(self, tmp_path: Path):
        payload = {"a/content/1": _gold("A")}
        path = tmp_path / "predictions.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        assert load_predictions(path) == payload

    def test_missing_path_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError, match="Predictions not found"):
            load_predictions(tmp_path / "nope")

    def test_empty_directory_raises(self, tmp_path: Path):
        (tmp_path / "predictions").mkdir()
        with pytest.raises(ValueError, match="No prediction.json files"):
            load_predictions(tmp_path / "predictions")

    def test_prediction_at_root_raises(self, tmp_path: Path):
        root = tmp_path / "predictions"
        root.mkdir()
        (root / PREDICTION_FILENAME).write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="sits at the root"):
            load_predictions(root)

    def test_non_object_prediction_raises(self, tmp_path: Path):
        path = tmp_path / "predictions.json"
        path.write_text(json.dumps({"a": []}), encoding="utf-8")
        with pytest.raises(ValueError, match="is not an object"):
            load_predictions(path)


class TestResolveCheckDir:
    def test_resolves_a_check(self, pilot):
        assert (
            resolve_check_dir("fig-checklist", "micrograph-scale-bar")
            == pilot["check_dir"]
        )

    def test_unknown_checklist_raises(self, pilot):
        with pytest.raises(FileNotFoundError, match="Checklist not found"):
            resolve_check_dir("no-such-checklist", "whatever")

    def test_unknown_check_raises(self, pilot):
        with pytest.raises(FileNotFoundError, match="Check not found"):
            resolve_check_dir("fig-checklist", "no-such-check")

    def test_shared_skill_is_not_scoreable(self, pilot):
        shared = pilot["checklist_root"] / "fig-checklist" / "identify-panels"
        (shared / "v1").mkdir(parents=True)
        (shared / "schema.json").write_text("{}", encoding="utf-8")
        with pytest.raises(ValueError, match="is not a check"):
            resolve_check_dir("fig-checklist", "identify-panels")


class TestScoreCheck:
    def test_matches_the_legacy_analyze_results_output(self, pilot):
        """The same predictions scored through both paths must agree.

        The legacy ``evaluate`` path builds ``ModelResult`` objects and hands
        them to ``analyze_results``; ``score`` must reach the identical
        ``flat`` records from predictions on disk.
        """
        predictions = {
            "doc-a/content/1": _gold("A"),
            # A deliberate disagreement, so the comparison is not trivially
            # a run of perfect scores.
            "doc-b/content/1": _gold("B", micrograph="yes"),
        }
        root = _write_predictions_dir(pilot["examples_root"].parent / "preds", predictions)

        scored = score_check(
            "fig-checklist",
            "micrograph-scale-bar",
            root,
            embedder=_mock_embedder,
            save=False,
        )

        expected = analyze_results(
            [
                ModelResult(
                    doc_id="doc-a",
                    model_output=predictions["doc-a/content/1"],
                    metadata={
                        "doc_id": "doc-a",
                        "source": "doc-a/content/1",
                        "example_type": "figure",
                    },
                ),
                ModelResult(
                    doc_id="doc-b",
                    model_output=predictions["doc-b/content/1"],
                    metadata={
                        "doc_id": "doc-b",
                        "source": "doc-b/content/1",
                        "example_type": "figure",
                    },
                ),
            ],
            pilot["schema"],
            [pilot["golds"][path] for path in pilot["examples"]],
            check_dir=pilot["check_dir"],
            embedder=_mock_embedder,
        )

        assert set(scored) == {"flat"}
        assert scored == expected

    def test_flat_records_carry_gold_and_prediction(self, pilot):
        predictions = {"doc-a/content/1": _gold("A")}
        root = _write_predictions_dir(pilot["examples_root"].parent / "preds", predictions)

        scored = score_check(
            "fig-checklist",
            "micrograph-scale-bar",
            root,
            embedder=_mock_embedder,
            save=False,
        )
        records = scored["flat"]
        assert len(records) == 1
        record = records[0]
        assert record["doc_id"] == "doc-a"
        assert record["metadata"]["source"] == "doc-a/content/1"
        assert record["expected_output"] == pilot["golds"]["doc-a/content/1"]
        assert record["model_output"] == predictions["doc-a/content/1"]
        rollups = _rollups(
            record["analysis"], "fig-checklist", "micrograph-scale-bar"
        )
        assert rollups["outputs[].micrograph"].mean_score == 1.0

    def test_scores_only_the_examples_that_have_predictions(self, pilot):
        """A partial run over a handful of examples is still scoreable."""
        predictions = {"doc-b/content/1": _gold("B", micrograph="no")}
        root = _write_predictions_dir(pilot["examples_root"].parent / "preds", predictions)

        scored = score_check(
            "fig-checklist",
            "micrograph-scale-bar",
            root,
            embedder=_mock_embedder,
            save=False,
        )
        records = scored["flat"]
        assert [record["metadata"]["source"] for record in records] == [
            "doc-b/content/1"
        ]

    def test_predictions_outside_the_benchmark_are_ignored(self, pilot):
        predictions = {
            "doc-a/content/1": _gold("A"),
            "doc-z/content/9": _gold("Z"),
        }
        root = _write_predictions_dir(pilot["examples_root"].parent / "preds", predictions)

        scored = score_check(
            "fig-checklist",
            "micrograph-scale-bar",
            root,
            embedder=_mock_embedder,
            save=False,
        )
        records = scored["flat"]
        assert [record["metadata"]["source"] for record in records] == [
            "doc-a/content/1"
        ]

    def test_no_overlapping_examples_raises(self, pilot):
        root = _write_predictions_dir(
            pilot["examples_root"].parent / "preds",
            {"doc-z/content/9": _gold("Z")},
        )
        with pytest.raises(ValueError, match="None of the predictions"):
            score_check(
                "fig-checklist",
                "micrograph-scale-bar",
                root,
                embedder=_mock_embedder,
                save=False,
            )

    def test_the_analysis_lands_beside_the_predictions(self, pilot):
        """A run leaf holds its own score.

        save_analysis used to write EVALUATION_DIR/<checklist>/<check>/
        <model>/analysis.json -- one path for every arm and every
        replicate, so the second leaf scored overwrote the first, silently.
        """
        leaf = _write_predictions_dir(
            pilot["examples_root"].parent / "preds" / "pinned" / "rep-00",
            {"doc-a/content/1": _gold("A")},
        )

        result = score_check(
            "fig-checklist",
            "micrograph-scale-bar",
            leaf,
            embedder=_mock_embedder,
            save=True,
        )

        assert (leaf / "analysis.json").is_file()
        assert set(result) == {"flat"}, (
            "the run_label wrapper existed to hold one entry per prompt; "
            "with prompts gone it was always the literal 'agentic'"
        )
        on_disk = json.loads(
            (leaf / "analysis.json").read_text(encoding="utf-8")
        )
        assert set(on_disk) == {"flat"}
        assert on_disk == result

    def test_two_replicates_do_not_overwrite_each_other(self, pilot):
        """The defect that motivated the layout, asserted directly."""
        root = pilot["examples_root"].parent / "preds" / "pinned"
        written = []
        for replicate in ("rep-00", "rep-01"):
            leaf = _write_predictions_dir(
                root / replicate, {"doc-a/content/1": _gold("A")}
            )
            score_check(
                "fig-checklist",
                "micrograph-scale-bar",
                leaf,
                embedder=_mock_embedder,
                save=True,
            )
            written.append(leaf / "analysis.json")

        assert all(path.is_file() for path in written)
        assert written[0] != written[1]

    def test_scoring_without_saving_writes_nothing(self, pilot):
        leaf = _write_predictions_dir(
            pilot["examples_root"].parent / "preds" / "pinned" / "rep-00",
            {"doc-a/content/1": _gold("A")},
        )
        score_check(
            "fig-checklist",
            "micrograph-scale-bar",
            leaf,
            embedder=_mock_embedder,
            save=False,
        )
        assert not (leaf / "analysis.json").exists()


class TestCli:
    def test_score_command_end_to_end(
        self, pilot, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(
            "soda_mmqc.core.scoring._default_semantic_embedder",
            lambda _model: _mock_embedder,
        )
        leaf = _write_predictions_dir(
            pilot["examples_root"].parent / "preds" / "pinned" / "rep-00",
            {"doc-a/content/1": _gold("A")},
        )

        exit_code = cli.main(
            [
                "score",
                "fig-checklist",
                "--check",
                "micrograph-scale-bar",
                "--predictions",
                str(leaf),
            ]
        )

        assert exit_code == 0
        saved = json.loads(
            (leaf / "analysis.json").read_text(encoding="utf-8")
        )
        assert set(saved) == {"flat"}

    def test_score_command_reports_a_bad_check(self, pilot):
        assert (
            cli.main(
                [
                    "score",
                    "fig-checklist",
                    "--check",
                    "no-such-check",
                    "--predictions",
                    str(pilot["examples_root"]),
                ]
            )
            == 1
        )


# ---------------------------------------------------------------------------
# Real examples dataset
# ---------------------------------------------------------------------------
#
# Everything above runs against a synthetic example tree, which is what let
# Milestone 1 be gated without the untracked dataset. That leaves the parts of
# ``score`` that only a real example exercises untested: a three-segment
# relative source path, a real ``FigureExample`` load (caption + JPEG +
# ``source_data/`` siblings), gold read off disk, and the ``doc_id`` the
# factory derives from the directory layout.
#
# ``D4R_10.1038_s44318-026-00693-4`` is used for that. It carries five
# figures, each with gold for ``panelisation-and-classification`` and
# ``panel-label-detection``, and it is listed in three real benchmarks.

REAL_DOC_ID = "D4R_10.1038_s44318-026-00693-4"
REAL_EXAMPLES = [f"{REAL_DOC_ID}/content/{n}" for n in range(1, 6)]
REAL_CHECK = "panelisation-and-classification"
REAL_CHECK_DIR = CHECKLIST_DIR / "Retired-checklist" / REAL_CHECK

# The real benchmarks that list this document, and whether the example tree
# carries gold for them.
REAL_BENCHMARKS_WITH_GOLD = (
    ("Retired-checklist", "panelisation-and-classification"),
    ("Retired-checklist", "panel-label-detection"),
)
REAL_BENCHMARK_WITHOUT_GOLD = ("data-checklist", "panel-data-replication-validation")

requires_real_example = pytest.mark.skipif(
    not (EXAMPLES_DIR / REAL_DOC_ID).is_dir(),
    reason=(
        f"examples dataset not available: {EXAMPLES_DIR / REAL_DOC_ID} "
        "is missing"
    ),
)

# An eval manifest for the real panelisation-and-classification schema. The
# check ships without one (see TestRealChecksWithoutAnEvalManifest), so
# scoring it needs a manifest supplied here. Deliberately free of semantic
# fields: no SentenceTransformer model is ever loaded.
REAL_EVAL_MANIFEST = {
    "checklist": REAL_CHECK,
    "defaults": {
        "matching_metric": "binary_polarity",
        "positive_value": "yes",
        "negative_value": "no",
        "na_values": [""],
    },
    "list_alignment": {"outputs": ["panel_label"]},
    "fields": {
        "outputs[].panel_label": {
            "matching_metric": "graded_string",
            "string_compare": "exact",
            "match_threshold": 1.0,
        },
        "outputs[].is_a_micrograph": {"matching_metric": "binary_polarity"},
        "outputs[].is_a_nummerical_data_plot": {
            "matching_metric": "binary_polarity"
        },
        "outputs[].is_a_scheme": {"matching_metric": "binary_polarity"},
        "outputs[].is_mixed": {"matching_metric": "binary_polarity"},
    },
}


def _real_gold(relative_path: str, check_name: str = REAL_CHECK) -> Dict[str, Any]:
    """Read gold straight off disk, without going through ``Example``."""
    path = (
        EXAMPLES_DIR / relative_path / "checks" / check_name /
        "expected_output.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def real_pilot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A scoreable check over the five real figures of ``REAL_DOC_ID``.

    Only the checklist is synthesized -- from the check's *real* schema, plus
    the eval manifest it lacks and a benchmark narrowed to this one document.
    ``EXAMPLES_DIR`` is left pointing at the real dataset, so the examples,
    their content and their gold are the ones on disk.
    """
    checklist_root = tmp_path / "checklist"
    check_dir = checklist_root / "Retired-checklist" / REAL_CHECK
    check_dir.mkdir(parents=True)

    shutil.copyfile(REAL_CHECK_DIR / "schema.json", check_dir / "schema.json")
    (check_dir / "eval-manifest.json").write_text(
        json.dumps(REAL_EVAL_MANIFEST), encoding="utf-8"
    )
    (check_dir / "benchmark.json").write_text(
        json.dumps(
            {
                "name": REAL_CHECK,
                "description": f"{REAL_DOC_ID} only",
                "example_class": "figure",
                "examples": list(REAL_EXAMPLES),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(config, "CHECKLIST_DIR", checklist_root)

    return {
        "checklist_root": checklist_root,
        "check_dir": check_dir,
        "examples": list(REAL_EXAMPLES),
        "golds": {path: _real_gold(path) for path in REAL_EXAMPLES},
        "schema": json.loads(
            (check_dir / "schema.json").read_text(encoding="utf-8")
        ),
    }


def _score_real(predictions: Dict[str, Dict[str, Any]], tmp_path: Path, **kwargs):
    root = _write_predictions_dir(tmp_path / "real-preds", predictions)
    return score_check(
        "Retired-checklist", REAL_CHECK, root, save=False, **kwargs
    )


@requires_real_example
class TestRealExampleWiring:
    """The plumbing ``score_check`` relies on, against a real example."""

    def test_the_dataset_holds_the_five_figures_the_benchmarks_list(self):
        for figure in REAL_EXAMPLES:
            source = EXAMPLES_DIR / figure
            assert source.is_dir()
            assert (source / "content" / "caption.txt").is_file()
            assert list(source.glob("content/*.jpg")), (
                f"no figure image under {source / 'content'}"
            )

    @pytest.mark.parametrize("checklist,check", REAL_BENCHMARKS_WITH_GOLD)
    def test_real_benchmarks_reference_this_document_and_it_has_gold(
        self, checklist: str, check: str
    ):
        benchmark = json.loads(
            (CHECKLIST_DIR / checklist / check / "benchmark.json").read_text(
                encoding="utf-8"
            )
        )
        listed = [
            path
            for path in benchmark["examples"]
            if path.startswith(f"{REAL_DOC_ID}/")
        ]
        assert listed == REAL_EXAMPLES
        for figure in listed:
            gold = _real_gold(figure, check)
            assert gold["outputs"], f"empty gold for {figure} / {check}"

    def test_factory_derives_the_metadata_score_check_records(self):
        """``doc_id``/``source``/``example_type`` come from the real tree."""
        example = EXAMPLE_FACTORY.create(REAL_EXAMPLES[0], "figure")

        assert example.doc_id == REAL_DOC_ID
        assert example.relative_source_path == REAL_EXAMPLES[0]
        assert example.example_class_name == "figure"
        # The five figures share one doc_id; the source path is what tells
        # the flat records apart.
        assert {
            EXAMPLE_FACTORY.create(path, "figure").doc_id
            for path in REAL_EXAMPLES
        } == {REAL_DOC_ID}

    def test_get_expected_output_matches_the_gold_on_disk(self):
        example = EXAMPLE_FACTORY.create(REAL_EXAMPLES[0], "figure")
        assert example.get_expected_output(REAL_CHECK) == _real_gold(
            REAL_EXAMPLES[0]
        )

    def test_load_predictions_keys_by_the_real_relative_source_path(
        self, tmp_path: Path
    ):
        """Real example paths are three segments deep, not one."""
        payload = {path: _real_gold(path) for path in REAL_EXAMPLES}
        root = _write_predictions_dir(tmp_path / "predictions", payload)
        # A debug sidecar of the kind the Milestone 4 runner will write.
        trace = root / REAL_EXAMPLES[0] / "intermediates"
        trace.mkdir()
        (trace / "skill_trace.json").write_text("[]", encoding="utf-8")

        loaded = load_predictions(root)
        assert sorted(loaded) == sorted(REAL_EXAMPLES)
        assert loaded == payload


@requires_real_example
class TestScoreCheckOnRealExamples:
    """``score_check`` end to end over the five real figures."""

    def test_scoring_real_gold_against_itself_is_a_perfect_run(
        self, real_pilot, tmp_path: Path
    ):
        scored = _score_real(dict(real_pilot["golds"]), tmp_path)
        records = scored["flat"]

        assert [record["metadata"]["source"] for record in records] == (
            REAL_EXAMPLES
        )
        for record in records:
            analysis = record["analysis"]
            assert analysis["by_list"]["outputs"]["row_counts"] == {
                "correct_row": len(record["expected_output"]["outputs"]),
                "missing_row": 0,
                "spurious_row": 0,
            }
            assert all(
                instance["score"] == 1.0
                for instance in analysis["instances"]
            )
            rollups = _rollups(analysis, "Retired-checklist", REAL_CHECK)
            assert all(
                rollup.mean_score == 1.0
                for rollup in rollups.values()
                # A property nothing was applicable for scores None, not
                # 1.0 -- it was not measured, so it cannot be perfect.
                if rollup.mean_score is not None
            )
            assert any(r.mean_score == 1.0 for r in rollups.values())

    def test_flat_records_carry_the_real_gold_and_metadata(
        self, real_pilot, tmp_path: Path
    ):
        scored = _score_real(dict(real_pilot["golds"]), tmp_path)
        records = scored["flat"]

        assert len(records) == 5
        for figure, record in zip(REAL_EXAMPLES, records):
            assert record["doc_id"] == REAL_DOC_ID
            assert record["metadata"] == {
                "doc_id": REAL_DOC_ID,
                "source": figure,
                "example_type": "figure",
            }
            assert record["expected_output"] == _real_gold(figure)
            assert record["model_output"] == _real_gold(figure)

    def test_matches_the_legacy_analyze_results_output_on_real_examples(
        self, real_pilot, tmp_path: Path
    ):
        """Parity with ``analyze_results``, on real gold this time.

        Figure 2 gets a deliberately wrong prediction so the comparison is
        not a trivial run of perfect scores.
        """
        predictions = copy.deepcopy(real_pilot["golds"])
        panel = predictions[REAL_EXAMPLES[1]]["outputs"][0]
        panel["is_a_micrograph"] = (
            "no" if panel["is_a_micrograph"] == "yes" else "yes"
        )

        scored = _score_real(predictions, tmp_path)

        expected = analyze_results(
            [
                ModelResult(
                    doc_id=REAL_DOC_ID,
                    model_output=predictions[figure],
                    metadata={
                        "doc_id": REAL_DOC_ID,
                        "source": figure,
                        "example_type": "figure",
                    },
                )
                for figure in REAL_EXAMPLES
            ],
            real_pilot["schema"],
            [real_pilot["golds"][figure] for figure in REAL_EXAMPLES],
            check_dir=real_pilot["check_dir"],
        )

        assert set(scored) == {"flat"}
        assert scored == expected

    def test_a_misclassified_real_panel_is_penalised(
        self, real_pilot, tmp_path: Path
    ):
        predictions = copy.deepcopy(real_pilot["golds"])
        # Figure 1 panel A is a micrograph in the gold; claim it is not.
        assert (
            real_pilot["golds"][REAL_EXAMPLES[0]]["outputs"][0][
                "is_a_micrograph"
            ]
            == "yes"
        )
        predictions[REAL_EXAMPLES[0]]["outputs"][0]["is_a_micrograph"] = "no"

        records = _score_real(predictions, tmp_path)[
            "flat"
        ]

        wrong = [
            instance
            for instance in records[0]["analysis"]["instances"]
            if instance["score"] != 1.0
        ]
        assert wrong == [
            {
                "path": "outputs[0].is_a_micrograph",
                "leaf_property": "outputs[].is_a_micrograph",
                "exp_value": "yes",
                "pred_value": "no",
                "score": 0.0,
                "layer1": "correct_applicable",
                "layer2": "FN",
            }
        ]
        rollups = _rollups(
            records[0]["analysis"], "Retired-checklist", REAL_CHECK
        )
        assert rollups["outputs[].is_a_micrograph"].layer2_counts["FN"] == 1
        # The other four figures are untouched.
        for record in records[1:]:
            assert all(
                instance["score"] == 1.0
                for instance in record["analysis"]["instances"]
            )

    def test_a_panel_missed_on_a_real_figure_is_a_missing_row(
        self, real_pilot, tmp_path: Path
    ):
        predictions = copy.deepcopy(real_pilot["golds"])
        dropped = predictions[REAL_EXAMPLES[0]]["outputs"].pop()

        records = _score_real(predictions, tmp_path)[
            "flat"
        ]
        analysis = records[0]["analysis"]

        assert analysis["by_list"]["outputs"]["row_counts"] == {
            "correct_row": 4,
            "missing_row": 1,
            "spurious_row": 0,
        }
        withheld = [
            instance
            for instance in analysis["instances"]
            if instance["layer1"] == "withheld_applicable"
        ]
        assert {instance["path"] for instance in withheld} == {
            f"outputs[4].{field}"
            for field in (
                "panel_label",
                "is_a_micrograph",
                "is_a_nummerical_data_plot",
                "is_a_scheme",
                "is_mixed",
            )
        }
        assert all(instance["pred_value"] is None for instance in withheld)
        assert any(
            instance["exp_value"] == dropped["panel_label"]
            for instance in withheld
        )

    def test_a_partial_run_over_real_figures_is_scoreable(
        self, real_pilot, tmp_path: Path
    ):
        """Milestone 4's human gate scopes runs to a handful of examples."""
        subset = [REAL_EXAMPLES[0], REAL_EXAMPLES[3]]
        predictions = {figure: _real_gold(figure) for figure in subset}

        records = _score_real(predictions, tmp_path)[
            "flat"
        ]
        assert [record["metadata"]["source"] for record in records] == subset

    def test_predictions_for_another_document_are_ignored(
        self, real_pilot, tmp_path: Path
    ):
        predictions = {
            REAL_EXAMPLES[0]: _real_gold(REAL_EXAMPLES[0]),
            "10.1038_s44319-025-00631-1/content/1": _real_gold(
                REAL_EXAMPLES[0]
            ),
        }
        records = _score_real(predictions, tmp_path)[
            "flat"
        ]
        assert [record["metadata"]["source"] for record in records] == [
            REAL_EXAMPLES[0]
        ]

    def test_score_command_saves_analysis_for_the_real_document(
        self, real_pilot, tmp_path: Path
    ):
        leaf = _write_predictions_dir(
            tmp_path / "real-preds" / "pinned" / "rep-00",
            dict(real_pilot["golds"]),
        )

        exit_code = cli.main(
            [
                "score",
                "Retired-checklist",
                "--check",
                REAL_CHECK,
                "--predictions",
                str(leaf),
            ]
        )

        assert exit_code == 0
        saved = json.loads(
            (leaf / "analysis.json").read_text(encoding="utf-8")
        )
        assert set(saved) == {"flat"}
        assert [
            record["metadata"]["source"] for record in saved["flat"]
        ] == REAL_EXAMPLES


@requires_real_example
class TestRealChecksWithoutAnEvalManifest:
    """Enumeration and scoring disagree, on purpose -- pin the boundary.

    ``owns_evaluation_contracts`` tests for ``schema.json`` +
    ``benchmark.json`` only, deliberately not ``eval-manifest.json``, so that
    ``data-checklist`` and ``Retired-checklist`` keep enumerating. Those
    checks are therefore reachable but not scoreable, and the failure has to
    name the missing file rather than blow up somewhere in the evaluator.

    Every check exercised here really does list ``REAL_DOC_ID``.
    """

    @pytest.mark.parametrize(
        "checklist,check",
        list(REAL_BENCHMARKS_WITH_GOLD) + [REAL_BENCHMARK_WITHOUT_GOLD],
    )
    def test_the_check_is_enumerated_and_resolvable(
        self, checklist: str, check: str
    ):
        check_dir = CHECKLIST_DIR / checklist / check
        assert check in list_checks(CHECKLIST_DIR / checklist)
        assert owns_evaluation_contracts(check_dir) is True
        assert resolve_check_dir(checklist, check) == check_dir
        # ...and yet it cannot be scored:
        assert not (check_dir / "eval-manifest.json").exists()

    @pytest.mark.parametrize("checklist,check", REAL_BENCHMARKS_WITH_GOLD)
    def test_scoring_it_names_the_missing_manifest(
        self, checklist: str, check: str, tmp_path: Path
    ):
        root = _write_predictions_dir(
            tmp_path / "preds",
            {figure: _real_gold(figure, check) for figure in REAL_EXAMPLES},
        )
        with pytest.raises(FileNotFoundError, match="Missing eval manifest"):
            score_check(checklist, check, root, save=False)

    def test_the_cli_reports_it_as_exit_1(self, tmp_path: Path):
        root = _write_predictions_dir(
            tmp_path / "preds",
            {figure: _real_gold(figure) for figure in REAL_EXAMPLES},
        )
        assert (
            cli.main(
                [
                    "score",
                    "Retired-checklist",
                    "--check",
                    REAL_CHECK,
                    "--predictions",
                    str(root),
                ]
            )
            == 1
        )

    def test_benchmark_examples_without_gold_are_skipped(
        self, tmp_path: Path
    ):
        """The document is benchmarked for a check it has no gold for.

        ``data-checklist/panel-data-replication-validation`` lists all five
        figures, but the example tree carries no ``expected_output.json`` for
        it. Every example is skipped and the run fails before reaching the
        evaluator -- it must not score predictions against empty gold.
        """
        checklist, check = REAL_BENCHMARK_WITHOUT_GOLD
        for figure in REAL_EXAMPLES:
            assert not (
                EXAMPLES_DIR / figure / "checks" / check /
                "expected_output.json"
            ).exists()

        root = _write_predictions_dir(
            tmp_path / "preds",
            {figure: _real_gold(figure) for figure in REAL_EXAMPLES},
        )
        with pytest.raises(ValueError, match="No expected outputs found"):
            score_check(checklist, check, root, save=False)


# ---------------------------------------------------------------------------
# Curation enumeration
# ---------------------------------------------------------------------------
#
# `list_checks()` is not the only enumerator. `curation.load_checklist()` walks
# the checklist directory itself, and only skipped a subdirectory when a
# contract file existed but was invalid -- a *missing* benchmark.json was not a
# skip. So a shared skill would have appeared in the curation UI's check
# selector as a phantom entry backed by empty gold.
#
# Both enumerators now share one definition of what a check is, in
# `soda_mmqc.config.owns_evaluation_contracts`. Human gate 1A.


@pytest.fixture
def local_curation(monkeypatch: pytest.MonkeyPatch):
    """`load_checklist` with Langfuse forced off, so the test is hermetic.

    With LANGFUSE_PUBLIC_KEY set (a developer .env), curation fetches prompts
    over the network for every check. The local prompt path is what the test
    wants.
    """
    import soda_mmqc.core.curation as curation

    monkeypatch.setattr(curation, "langfuse_client", None)
    return curation


def _write_check(check_dir: Path, name: str) -> None:
    check_dir.mkdir(parents=True, exist_ok=True)
    (check_dir / "schema.json").write_text(
        json.dumps({"format": {"name": name}}), encoding="utf-8"
    )
    (check_dir / "benchmark.json").write_text(
        json.dumps({"name": name, "example_class": "figure", "examples": []}),
        encoding="utf-8",
    )


def _write_shared_skill(skill_dir: Path, name: str) -> None:
    """The Milestone 2 shape: a runtime schema, no evaluation contracts."""
    (skill_dir / "v1").mkdir(parents=True, exist_ok=True)
    (skill_dir / "schema.json").write_text(
        json.dumps({"format": {"name": name}}), encoding="utf-8"
    )
    (skill_dir / "v1" / "SKILL.md").write_text("---\n---\n", encoding="utf-8")


class TestCurationEnumeration:
    def test_shared_skill_is_not_listed_as_a_check(
        self, local_curation, tmp_path: Path
    ):
        checklist_dir = tmp_path / "fig-checklist"
        _write_check(checklist_dir / "micrograph-scale-bar", "micrograph-scale-bar")
        _write_shared_skill(checklist_dir / "identify-panels", "identify-panels")

        assert set(local_curation.load_checklist(checklist_dir)) == {
            "micrograph-scale-bar"
        }

    def test_a_directory_with_no_contracts_at_all_is_not_a_check(
        self, local_curation, tmp_path: Path
    ):
        checklist_dir = tmp_path / "fig-checklist"
        _write_check(checklist_dir / "micrograph-scale-bar", "micrograph-scale-bar")
        (checklist_dir / "generated-docs").mkdir(parents=True)

        assert set(local_curation.load_checklist(checklist_dir)) == {
            "micrograph-scale-bar"
        }

    @pytest.mark.parametrize(
        "checklist", ("fig-checklist",) + LEGACY_CHECKLISTS
    )
    def test_curation_and_runner_agree_on_every_real_checklist(
        self, local_curation, checklist: str
    ):
        """Neither enumerator may drift from the other on real data."""
        checklist_dir = CHECKLIST_DIR / checklist
        assert sorted(local_curation.load_checklist(checklist_dir)) == sorted(
            list_checks(checklist_dir)
        )


# ---------------------------------------------------------------------------
# Skill loading, the resolved graph, and prose/frontmatter consistency
# ---------------------------------------------------------------------------
#
# Milestone 2. Two things are being pinned here.
#
# First, *where the graph comes from*. A skill invokes a sub-skill in its own
# prose, by telling the agent to use the `Skill` tool. The `requires` /
# `produces` frontmatter is runner-owned documentation of those same edges --
# it renders the DAG and catches drift, and is never turned into a call
# sequence. So the tests check that the two descriptions agree in *both*
# directions, and never that one is derived from the other.
#
# Second, *where the graph does not come from*: the filesystem. Every skill is
# a flat sibling in one namespace, addressed by the name in its frontmatter.
# `TestGraphIsPathIndependent` renames a skill directory and then moves it
# under another skill, and the resolved graph must not move with it.


FIG_CHECKLIST_DIR = CHECKLIST_DIR / "fig-checklist"
SHARED_SKILL = "identify-panels"
PILOT_LEAF = "micrograph-scale-bar"

# The evaluation contracts live at the skill level and are shared across
# versions, so that two versions of one skill stay comparable. A copy inside a
# version directory would break exactly that.
VERSIONED_CONTRACTS = ("schema.json", "eval-manifest.json", "benchmark.json")


def _skill_md(
    name: str,
    *,
    description: str = "Does one thing, described unambiguously.",
    requires: tuple = (),
    produces: tuple = (),
    needs: tuple = (),
    body: str = None,
) -> str:
    """Render a synthetic SKILL.md."""
    front = {"name": name, "description": description}
    for key, value in (
        ("requires", requires),
        ("produces", produces),
        ("needs", needs),
    ):
        front[key] = list(value)

    if body is None:
        calls = "".join(
            f"\nAsk for it by calling the `{req}` skill with the `Skill` tool.\n"
            for req in requires
        )
        body = f"# {name}\n\nDo the thing.\n{calls}"

    lines = ["---"]
    for key, value in front.items():
        if isinstance(value, list):
            lines.append(f"{key}: [{', '.join(repr(v) for v in value)}]")
        else:
            lines.append(f"{key}: {value!r}")
    lines.append("---")
    return "\n".join(lines) + "\n\n" + body + "\n"


def _write_skill(checklist_dir: Path, directory: str, version: str, text: str) -> Path:
    path = checklist_dir / directory / version / SKILL_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _copy_pilot_skills(dest: Path) -> Path:
    """Copy the real SKILL.md files into an empty checklist directory."""
    dest.mkdir(parents=True, exist_ok=True)
    for src in sorted(FIG_CHECKLIST_DIR.rglob(SKILL_FILENAME)):
        target = dest / src.relative_to(FIG_CHECKLIST_DIR)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
    return dest


def _graph(checklist_dir: Path) -> Dict[str, set]:
    return build_graph(load_skills(checklist_dir))


class TestLoadSkill:
    def test_reads_frontmatter_and_body(self, tmp_path: Path):
        path = _write_skill(
            tmp_path,
            "some-skill",
            "v1",
            _skill_md(
                "some-skill",
                description="Finds things.",
                produces=("things",),
                needs=("WebSearch",),
            ),
        )
        skill = load_skill(path)

        assert skill.name == "some-skill"
        assert skill.version == "v1"
        assert skill.description == "Finds things."
        assert skill.requires == ()
        assert skill.produces == ("things",)
        assert skill.needs == ("WebSearch",)
        assert "Do the thing." in skill.body
        assert "---" not in skill.body.splitlines()[0]
        assert skill.directory == path.parent
        assert skill.skill_dir == path.parent.parent

    def test_name_comes_from_frontmatter_not_the_directory(self, tmp_path: Path):
        path = _write_skill(
            tmp_path, "a-directory-named-anything", "v2", _skill_md("real-name")
        )
        skill = load_skill(path)

        assert skill.name == "real-name"
        assert skill.version == "v2"

    def test_a_folded_description_is_read_as_one_string(self, tmp_path: Path):
        path = _write_skill(
            tmp_path,
            "some-skill",
            "v1",
            "---\nname: some-skill\ndescription: >-\n  First line\n  second"
            " line.\nrequires: []\n---\n\n# Body\n\nText.\n",
        )
        assert load_skill(path).description == "First line second line."

    def test_missing_frontmatter_names_the_file(self, tmp_path: Path):
        path = _write_skill(tmp_path, "some-skill", "v1", "# No frontmatter\n")
        with pytest.raises(ValueError, match=r"no YAML frontmatter") as excinfo:
            load_skill(path)
        assert str(path) in str(excinfo.value)

    def test_invalid_yaml_names_the_file(self, tmp_path: Path):
        path = _write_skill(
            tmp_path, "some-skill", "v1", "---\nname: [unclosed\n---\n\nBody\n"
        )
        with pytest.raises(ValueError, match=r"not valid YAML") as excinfo:
            load_skill(path)
        assert str(path) in str(excinfo.value)

    @pytest.mark.parametrize("key", ("name", "description"))
    def test_a_missing_required_key_is_rejected(self, tmp_path: Path, key: str):
        front = {"name": "some-skill", "description": "Does one thing."}
        del front[key]
        text = (
            "---\n"
            + "".join(f"{k}: {v}\n" for k, v in front.items())
            + "---\n\nBody\n"
        )
        path = _write_skill(tmp_path, "some-skill", "v1", text)
        with pytest.raises(ValueError, match=rf"{key}.*non-empty string"):
            load_skill(path)

    def test_requires_must_be_a_list_of_names(self, tmp_path: Path):
        path = _write_skill(
            tmp_path,
            "some-skill",
            "v1",
            "---\nname: some-skill\ndescription: Does one thing.\n"
            "requires: {a: b}\n---\n\nBody\n",
        )
        with pytest.raises(ValueError, match=r"'requires' must be a list"):
            load_skill(path)

    def test_a_repeated_requirement_is_rejected(self, tmp_path: Path):
        path = _write_skill(
            tmp_path,
            "some-skill",
            "v1",
            _skill_md("some-skill", requires=("other", "other")),
        )
        with pytest.raises(ValueError, match=r"lists other more than once"):
            load_skill(path)

    def test_an_empty_body_is_rejected(self, tmp_path: Path):
        path = _write_skill(
            tmp_path,
            "some-skill",
            "v1",
            "---\nname: some-skill\ndescription: Does one thing.\n---\n\n \n",
        )
        with pytest.raises(ValueError, match=r"body is empty"):
            load_skill(path)

    def test_a_version_directory_must_be_named_vn(self, tmp_path: Path):
        path = _write_skill(
            tmp_path, "some-skill", "latest", _skill_md("some-skill")
        )
        with pytest.raises(ValueError, match=r"must be named 'v' followed by"):
            load_skill(path)

    def test_a_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_skill(tmp_path / "nope" / "v1" / SKILL_FILENAME)


class TestLoadSkillsOnTheRealChecklist:
    def test_both_pilot_skills_are_found(self):
        skills = load_skills(FIG_CHECKLIST_DIR)
        assert SHARED_SKILL in skills
        assert PILOT_LEAF in skills
        assert sorted(skills[SHARED_SKILL]) == ["v1"]
        assert sorted(skills[PILOT_LEAF]) == ["v1"]

    def test_the_leaf_declares_and_invokes_the_shared_skill(self):
        leaf = load_skills(FIG_CHECKLIST_DIR)[PILOT_LEAF]["v1"]
        assert leaf.requires == (SHARED_SKILL,)
        assert SHARED_SKILL in leaf.body
        assert SKILL_TOOL in leaf.body

    def test_the_shared_skill_requires_nothing_and_produces_panels(self):
        shared = load_skills(FIG_CHECKLIST_DIR)[SHARED_SKILL]["v1"]
        assert shared.requires == ()
        assert shared.produces == ("panels",)

    def test_descriptions_claim_their_own_job(self):
        """The description is what the agent matches on; it is load-bearing."""
        skills = load_skills(FIG_CHECKLIST_DIR)
        shared = skills[SHARED_SKILL]["v1"].description.lower()
        leaf = skills[PILOT_LEAF]["v1"].description.lower()

        assert "panel" in shared and "caption" in shared
        assert "scale bar" not in shared
        assert "scale bar" in leaf

    def test_an_unknown_checklist_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_skills(tmp_path / "no-such-checklist")

    def test_a_duplicate_name_and_version_is_rejected(self, tmp_path: Path):
        first = _write_skill(tmp_path, "here", "v1", _skill_md("same-name"))
        second = _write_skill(tmp_path, "there", "v1", _skill_md("same-name"))
        with pytest.raises(ValueError, match=r"same-name") as excinfo:
            load_skills(tmp_path)
        # Both files are named: which one is "the duplicate" depends on walk
        # order, and blaming the wrong one sends a reader to the wrong file.
        assert str(first) in str(excinfo.value)
        assert str(second) in str(excinfo.value)

    def test_two_versions_of_one_skill_coexist(self, tmp_path: Path):
        _write_skill(tmp_path, "here", "v1", _skill_md("same-name"))
        _write_skill(tmp_path, "here", "v2", _skill_md("same-name"))
        assert sorted(load_skills(tmp_path)["same-name"]) == ["v1", "v2"]


class TestSkillGraph:
    def test_every_skill_reaches_the_panel_inventory(self):
        """Stated as a property rather than a fixed edge list, so converting
        another leaf does not require editing this test to keep passing.

        `identify-panels` is the root; every other skill either requires it
        directly or requires something that does.
        """
        graph = _graph(FIG_CHECKLIST_DIR)
        assert graph[SHARED_SKILL] == set()

        def reaches(name, seen=None):
            seen = seen or set()
            for dep in graph.get(name, ()):
                if dep == SHARED_SKILL or reaches(dep, seen | {name}):
                    return True
            return False

        others = {n for n in graph if n != SHARED_SKILL}
        assert others, "no leaves converted"
        for name in others:
            assert reaches(name), f"{name} never reaches {SHARED_SKILL}"

    def test_the_real_graph_is_acyclic(self):
        assert find_cycle(_graph(FIG_CHECKLIST_DIR)) is None

    def test_a_cycle_is_found_and_reported_as_a_loop(self, tmp_path: Path):
        _write_skill(tmp_path, "a", "v1", _skill_md("a", requires=("b",)))
        _write_skill(tmp_path, "b", "v1", _skill_md("b", requires=("a",)))

        cycle = find_cycle(_graph(tmp_path))
        assert cycle is not None
        assert cycle[0] == cycle[-1]
        assert set(cycle) == {"a", "b"}

    def test_a_longer_cycle_is_found(self, tmp_path: Path):
        _write_skill(tmp_path, "a", "v1", _skill_md("a", requires=("b",)))
        _write_skill(tmp_path, "b", "v1", _skill_md("b", requires=("c",)))
        _write_skill(tmp_path, "c", "v1", _skill_md("c", requires=("a",)))

        assert set(find_cycle(_graph(tmp_path))) == {"a", "b", "c"}

    def test_a_diamond_is_not_a_cycle(self, tmp_path: Path):
        _write_skill(tmp_path, "root", "v1", _skill_md("root"))
        _write_skill(tmp_path, "l", "v1", _skill_md("l", requires=("root",)))
        _write_skill(tmp_path, "r", "v1", _skill_md("r", requires=("root",)))
        _write_skill(tmp_path, "top", "v1", _skill_md("top", requires=("l", "r")))

        assert find_cycle(_graph(tmp_path)) is None

    def test_edges_are_unioned_across_versions(self, tmp_path: Path):
        _write_skill(tmp_path, "root", "v1", _skill_md("root"))
        _write_skill(tmp_path, "other", "v1", _skill_md("other"))
        _write_skill(tmp_path, "leaf", "v1", _skill_md("leaf", requires=("root",)))
        _write_skill(
            tmp_path, "leaf", "v2", _skill_md("leaf", requires=("other",))
        )

        assert _graph(tmp_path)["leaf"] == {"root", "other"}


class TestProseAndFrontmatterAgree:
    def test_the_real_checklist_validates(self):
        skills = validate_skills(FIG_CHECKLIST_DIR)
        assert SHARED_SKILL in skills and PILOT_LEAF in skills

    def test_a_declared_requirement_missing_from_the_prose_fails(
        self, tmp_path: Path
    ):
        _write_skill(tmp_path, "root", "v1", _skill_md("root"))
        offender = _write_skill(
            tmp_path,
            "leaf",
            "v1",
            _skill_md(
                "leaf",
                requires=("root",),
                body="# leaf\n\nUse the `Skill` tool for something.\n",
            ),
        )
        with pytest.raises(ValueError, match=r"never asks for it in the prose"):
            validate_skills(tmp_path)
        with pytest.raises(ValueError, match=re.escape(str(offender))):
            validate_skills(tmp_path)

    def test_a_skill_invoked_in_prose_but_not_declared_fails(
        self, tmp_path: Path
    ):
        _write_skill(tmp_path, "root", "v1", _skill_md("root"))
        _write_skill(
            tmp_path,
            "leaf",
            "v1",
            _skill_md(
                "leaf",
                body="# leaf\n\nCall the `root` skill with the `Skill` tool.\n",
            ),
        )
        with pytest.raises(ValueError, match=r"missing from requires"):
            validate_skills(tmp_path)

    def test_a_requirement_without_a_skill_tool_instruction_fails(
        self, tmp_path: Path
    ):
        _write_skill(tmp_path, "root", "v1", _skill_md("root"))
        _write_skill(
            tmp_path,
            "leaf",
            "v1",
            _skill_md(
                "leaf",
                requires=("root",),
                body="# leaf\n\nThe `root` inventory is needed first.\n",
            ),
        )
        with pytest.raises(ValueError, match=r"never\s+tells the agent to use"):
            validate_skills(tmp_path)

    def test_a_second_requirement_cannot_ride_on_the_first_ones_call(
        self, tmp_path: Path
    ):
        """The Skill-tool check is per requirement, not per file.

        Every Group B leaf will declare two requirements. One real call plus
        one bare mention must not validate just because the word `Skill`
        appears somewhere in the file.
        """
        _write_skill(tmp_path, "root", "v1", _skill_md("root"))
        _write_skill(tmp_path, "other", "v1", _skill_md("other"))
        _write_skill(
            tmp_path,
            "leaf",
            "v1",
            _skill_md(
                "leaf",
                requires=("root", "other"),
                body=(
                    "# leaf\n\n"
                    "Call the `root` skill with the `Skill` tool.\n\n"
                    "The `other` classification is also relevant.\n"
                ),
            ),
        )
        with pytest.raises(ValueError, match=r"mentions 'other'") as excinfo:
            validate_skills(tmp_path)
        assert "mentions 'root'" not in str(excinfo.value)

    def test_each_requirement_may_be_called_in_its_own_bullet(
        self, tmp_path: Path
    ):
        _write_skill(tmp_path, "root", "v1", _skill_md("root"))
        _write_skill(tmp_path, "other", "v1", _skill_md("other"))
        _write_skill(
            tmp_path,
            "leaf",
            "v1",
            _skill_md(
                "leaf",
                requires=("root", "other"),
                body=(
                    "# leaf\n\nFirst gather what you need:\n\n"
                    "- Call the `root` skill with the `Skill` tool.\n"
                    "- Call the `other` skill with the `Skill` tool.\n"
                ),
            ),
        )
        validate_skills(tmp_path)  # must not raise

    def test_a_call_wrapped_across_two_lines_is_still_one_block(
        self, tmp_path: Path
    ):
        """Line wrapping must not break the co-occurrence check."""
        _write_skill(tmp_path, "root", "v1", _skill_md("root"))
        _write_skill(
            tmp_path,
            "leaf",
            "v1",
            _skill_md(
                "leaf",
                requires=("root",),
                body=(
                    "# leaf\n\nGet the inventory first by calling the `root`\n"
                    "skill with the `Skill` tool, then work from it.\n"
                ),
            ),
        )
        validate_skills(tmp_path)  # must not raise

    def test_an_unknown_requirement_fails(self, tmp_path: Path):
        _write_skill(
            tmp_path, "leaf", "v1", _skill_md("leaf", requires=("absent",))
        )
        with pytest.raises(ValueError, match=r"requires unknown skill 'absent'"):
            validate_skills(tmp_path)

    def test_a_self_requirement_fails(self, tmp_path: Path):
        _write_skill(
            tmp_path, "leaf", "v1", _skill_md("leaf", requires=("leaf",))
        )
        with pytest.raises(ValueError, match=r"requires itself"):
            validate_skills(tmp_path)

    def test_a_cycle_fails_validation(self, tmp_path: Path):
        _write_skill(tmp_path, "a", "v1", _skill_md("a", requires=("b",)))
        _write_skill(tmp_path, "b", "v1", _skill_md("b", requires=("a",)))
        with pytest.raises(ValueError, match=r"has a cycle"):
            validate_skills(tmp_path)

    def test_every_problem_is_reported_at_once(self, tmp_path: Path):
        _write_skill(
            tmp_path, "a", "v1", _skill_md("a", requires=("absent", "a"))
        )
        with pytest.raises(ValueError) as excinfo:
            validate_skills(tmp_path)
        message = str(excinfo.value)
        assert "requires itself" in message
        assert "unknown skill 'absent'" in message
        # The self-requirement is a cycle too, but reporting it twice would
        # bury the clearer message.
        assert "has a cycle" not in message
        assert message.startswith("2 problem(s)")

    def test_mentioning_its_own_name_is_not_an_invocation(self, tmp_path: Path):
        _write_skill(
            tmp_path,
            "lonely",
            "v1",
            _skill_md("lonely", body="# lonely\n\nThe `lonely` skill does X.\n"),
        )
        validate_skills(tmp_path)  # must not raise

    def test_a_name_embedded_in_a_longer_word_is_not_an_invocation(
        self, tmp_path: Path
    ):
        _write_skill(tmp_path, "root", "v1", _skill_md("root"))
        _write_skill(
            tmp_path,
            "leaf",
            "v1",
            _skill_md("leaf", body="# leaf\n\nSee root-cause analysis.\n"),
        )
        validate_skills(tmp_path)  # must not raise

    def test_the_real_leaf_names_the_shared_skill_and_the_tool_together(self):
        """The hop is prose, not a template: one sentence, in the leaf's words."""
        leaf = load_skills(FIG_CHECKLIST_DIR)[PILOT_LEAF]["v1"]
        sentences = [
            line for line in leaf.body.splitlines() if SHARED_SKILL in line
        ]
        assert sentences, "the leaf never mentions the shared skill"
        joined = "\n".join(leaf.body.splitlines())
        assert f"`{SHARED_SKILL}` skill with the `{SKILL_TOOL}` tool" in joined


class TestGraphIsPathIndependent:
    """The edges come from the calls, not from where the directories sit."""

    def test_renaming_a_skill_directory_leaves_the_graph_unchanged(
        self, tmp_path: Path
    ):
        checklist = _copy_pilot_skills(tmp_path / "fig-checklist")
        before = _graph(checklist)

        (checklist / SHARED_SKILL).rename(checklist / "zzz-renamed")

        assert _graph(checklist) == before
        assert set(validate_skills(checklist)) == set(before)

    def test_moving_a_skill_under_another_leaves_the_graph_unchanged(
        self, tmp_path: Path
    ):
        checklist = _copy_pilot_skills(tmp_path / "fig-checklist")
        before = _graph(checklist)

        # The shape the layout rule forbids: the dependency nested under its
        # caller. The resolved graph must not notice.
        (checklist / SHARED_SKILL).rename(
            checklist / PILOT_LEAF / SHARED_SKILL
        )

        assert _graph(checklist) == before
        skills = validate_skills(checklist)
        assert skills[PILOT_LEAF]["v1"].requires == (SHARED_SKILL,)

    def test_a_skill_nested_arbitrarily_deep_is_still_found(
        self, tmp_path: Path
    ):
        checklist = _copy_pilot_skills(tmp_path / "fig-checklist")
        before = _graph(checklist)

        deep = checklist / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (checklist / SHARED_SKILL).rename(deep / SHARED_SKILL)

        assert _graph(checklist) == before


class TestEvaluationContractsStayAtSkillLevel:
    """Only SKILL.md is versioned; the contracts are shared across versions."""

    def test_no_version_directory_holds_a_copy_of_a_contract(self):
        offenders = []
        for skill_file in CHECKLIST_DIR.rglob(SKILL_FILENAME):
            for contract in VERSIONED_CONTRACTS:
                if (skill_file.parent / contract).exists():
                    offenders.append(skill_file.parent / contract)
        assert offenders == [], (
            "evaluation contracts must stay at the skill level, shared by "
            f"every version: {offenders}"
        )

    def test_the_pilot_leaf_still_owns_its_contracts_where_they_were(self):
        for contract in VERSIONED_CONTRACTS:
            assert (PILOT_CHECK_DIR / contract).is_file()
        assert owns_evaluation_contracts(PILOT_CHECK_DIR)

    def test_the_shared_skill_owns_a_runtime_schema_and_no_eval_assets(self):
        shared_dir = FIG_CHECKLIST_DIR / SHARED_SKILL
        assert (shared_dir / "schema.json").is_file()
        assert not (shared_dir / "benchmark.json").exists()
        assert not (shared_dir / "eval-manifest.json").exists()
        assert not owns_evaluation_contracts(shared_dir)

    def test_the_shared_skill_is_not_enumerated_as_a_check(self):
        assert SHARED_SKILL not in list_checks(FIG_CHECKLIST_DIR)
        assert set(list_checks(FIG_CHECKLIST_DIR)) == FIG_CHECKLIST_CHECKS

    def test_the_shared_skill_cannot_be_scored(self):
        with pytest.raises(ValueError, match=r"is not a check"):
            resolve_check_dir("fig-checklist", SHARED_SKILL)

    def test_the_panels_schema_is_a_usable_runtime_contract(self):
        schema = json.loads(
            (FIG_CHECKLIST_DIR / SHARED_SKILL / "schema.json").read_text(
                encoding="utf-8"
            )
        )
        panels = schema["format"]["schema"]["properties"]["panels"]
        fields = panels["items"]["properties"]

        assert schema["format"]["name"] == SHARED_SKILL
        assert set(fields) == {
            "panel_label",
            "location_in_figure",
            "panel_content",
            "caption_excerpt",
            "caption_covers_panels",
        }
        assert set(panels["items"]["required"]) == set(fields)
        assert panels["items"]["additionalProperties"] is False


class TestTheLeafProseMatchesItsContracts:
    """The leaf points at `schema.json` instead of pasting a JSON example.

    That is what the plan asks for, but it moves a burden: the prose is now
    the only place that says what to put in a field, and nothing in the schema
    can catch prose that contradicts it. `panel_label` is the sharp case --
    it is the evaluator's list-alignment key, and it is unconstrained in the
    schema, so blanking it produces output that validates perfectly and scores
    close to zero.
    """

    @pytest.fixture
    def leaf_body(self) -> str:
        return load_skills(FIG_CHECKLIST_DIR)[PILOT_LEAF]["v1"].body

    def test_the_prose_names_every_field_of_the_schema(self, leaf_body: str):
        schema = json.loads(
            (PILOT_CHECK_DIR / "schema.json").read_text(encoding="utf-8")
        )
        fields = schema["format"]["schema"]["properties"]["outputs"]["items"][
            "properties"
        ]
        missing = [name for name in fields if name not in leaf_body]
        assert missing == [], (
            "the leaf points at schema.json instead of pasting a JSON "
            f"example, so its prose must name every field: {missing}"
        )

    def test_the_prose_names_the_top_level_container(self, leaf_body: str):
        """The item fields were covered; the container was not.

        A live session wrote its answer under `panels` -- the intermediate's
        key -- instead of `outputs`, producing content that was entirely
        correct and validation that entirely failed. Naming the fields is not
        enough if the envelope is left implicit.
        """
        schema = json.loads(
            (PILOT_CHECK_DIR / "schema.json").read_text(encoding="utf-8")
        )
        for key in schema["format"]["schema"]["properties"]:
            assert key in leaf_body, f"the prose never names {key!r}"

    def test_the_prose_names_the_list_alignment_key(self, leaf_body: str):
        manifest = json.loads(
            (PILOT_CHECK_DIR / "eval-manifest.json").read_text(encoding="utf-8")
        )
        for keys in manifest["list_alignment"].values():
            for key in keys:
                assert key in leaf_body

    def test_the_prose_does_not_blank_every_remaining_field(
        self, leaf_body: str
    ):
        """A non-micrograph panel keeps its label; only the answers empty out.

        `prompt.2.txt`'s panel C shows exactly this. Generalizing it to "every
        remaining field" would collapse all non-micrograph panels onto one
        empty alignment key -- output that validates against `schema.json`
        perfectly and scores close to zero.
        """
        blanking = [
            block
            for block in _prose_blocks(leaf_body)
            if "empty string" in block
        ]
        assert blanking, "the prose no longer says what an unused field holds"

        universal = (
            "every remaining field",
            "all remaining fields",
            "every other field",
            "all other fields",
        )
        for block in blanking:
            for phrase in universal:
                assert phrase not in block.lower(), (
                    f"{phrase!r} sweeps panel_label, the alignment key, into "
                    "the blanking rule"
                )
            assert "label" in block, (
                "the rule that empties fields must say the panel label is kept"
            )


# ---------------------------------------------------------------------------
# The shared skill against the real gold
# ---------------------------------------------------------------------------
#
# Gate 2A asks whether the merged `identify-panels` prose preserves the three
# source sections. The sources are prose, so most of that question is a
# reading. But the *additions* -- the rules the merge invented because a
# standalone skill cannot rely on a leaf's surrounding context -- are checkable
# against the gold the skill's consumers are scored on, and one of them was
# wrong.
#
# `identify-panels` first said a composite panel is one panel and must never be
# split. The pilot's own benchmark contains a figure whose caption reads
# "(Ai-ii) ... mock-treated (i) and treated with saccharin (ii)" and whose gold
# splits it into two rows. Since `panel_label` is the list-alignment key at
# exact match, that rule cost two of four rows on that example.

SUBPANEL_FIGURE = "10.1038_s44321-025-00219-1/content/1"

requires_subpanel_figure = pytest.mark.skipif(
    not (EXAMPLES_DIR / SUBPANEL_FIGURE).is_dir(),
    reason=f"examples dataset not available: {SUBPANEL_FIGURE} is missing",
)


def _gold_labels(figure: str, check: str):
    path = (
        EXAMPLES_DIR / figure / "checks" / check / "expected_output.json"
    )
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [row.get("panel_label") for row in payload.get("outputs", [])]


@requires_subpanel_figure
class TestSharedSkillAgainstRealGold:
    def test_the_pilot_benchmark_contains_a_split_composite_panel(self):
        """The evidence the 'never split' rule was wrong."""
        benchmark = json.loads(
            (PILOT_CHECK_DIR / "benchmark.json").read_text(encoding="utf-8")
        )
        assert SUBPANEL_FIGURE in benchmark["examples"]
        assert _gold_labels(SUBPANEL_FIGURE, PILOT_LEAF) == [
            "Ai",
            "Aii",
            "B",
            "C",
        ]

    def test_the_shared_skill_does_not_forbid_splitting_outright(self):
        body = load_skills(FIG_CHECKLIST_DIR)[SHARED_SKILL]["v1"].body
        forbidding = [
            block
            for block in _prose_blocks(body)
            if "do not split" in block.lower()
        ]
        assert forbidding, "the unlabelled-composite rule disappeared entirely"
        for block in forbidding:
            assert "unlabelled" in block.lower() or "label" in block.lower(), (
                "'do not split' must be scoped to unlabelled composites; the "
                "pilot gold splits a caption-labelled (Ai-ii) into two rows"
            )

    def test_the_shared_skill_tells_the_agent_to_split_labelled_sub_panels(self):
        body = load_skills(FIG_CHECKLIST_DIR)[SHARED_SKILL]["v1"].body
        assert "sub-part" in body.lower() or "sub-panel" in body.lower()
        assert "one entry per labelled sub-part" in body.lower()

    def test_every_check_spells_this_figures_sub_panels_the_same_way(self):
        """One shared artifact, so every consumer must agree on the label.

        Resolved at human gate 2A (2026-09-10, Çağatay Gürsoy): the convention
        is the unspaced `Ai`/`Aii`, which is how the caption itself writes
        `(Ai-ii)` and how twelve of the sixteen gold files already had it.
        Four files were corrected -- `micrograph-scale-bar`,
        `panel-label-detection` and `panelisation-and-classification` used
        `A i`/`A ii`, and `replicates-defined` had `Aii` twice with identical
        content and no `Ai` at all.

        This guards the whole figure, not just `fig-checklist`, because the
        shared skill has no idea which checklist is asking.
        """
        checks_dir = EXAMPLES_DIR / SUBPANEL_FIGURE / "checks"
        spellings = collections.defaultdict(list)
        for check in sorted(checks_dir.iterdir()):
            labels = _gold_labels(SUBPANEL_FIGURE, check.name)
            if labels:
                spellings[tuple(labels)].append(check.name)

        assert len(spellings) == 1, (
            "gold for this figure disagrees on panel labels again; one shared "
            f"identify-panels artifact cannot satisfy all of {dict(spellings)}"
        )
        assert list(spellings) == [("Ai", "Aii", "B", "C")]


# ---------------------------------------------------------------------------
# The converted leaf against the real gold
# ---------------------------------------------------------------------------
#
# Gate 2B asks whether the conversion lost anything. The rules it *kept* are a
# reading of `prompt.2.txt`. The three sentences it *added* are judgement
# calls, and the pilot's own 38 benchmark examples can adjudicate them.
#
# The sharpest case is the independence of the two "where is it defined?"
# fields. The dropped JSON example showed each panel defined in exactly one
# place, which reads as mutually exclusive -- and the gold says otherwise on
# 38% of micrograph rows. So the prose is not a lossy stand-in for the example
# here; it corrects it.

requires_pilot_gold = pytest.mark.skipif(
    not EXAMPLES_DIR.is_dir(),
    reason=f"examples dataset not available: {EXAMPLES_DIR} is missing",
)

SCALE_BAR_ANSWER_FIELDS = (
    "scale_bar_on_image",
    "scale_bar_defined_in_caption",
    "from_the_caption",
    "scale_bar_defined_in_image",
    "from_the_image",
)


@pytest.fixture(scope="module")
def gold_rows():
    """Every gold panel row of the pilot's 38 benchmark examples."""
    benchmark = json.loads(
        (PILOT_CHECK_DIR / "benchmark.json").read_text(encoding="utf-8")
    )
    rows = []
    for relative in benchmark["examples"]:
        path = (
            EXAMPLES_DIR / relative / "checks" / PILOT_LEAF
            / "expected_output.json"
        )
        if path.is_file():
            rows += json.loads(path.read_text(encoding="utf-8"))["outputs"]
    if not rows:
        pytest.skip("no pilot gold available")
    return rows


@requires_pilot_gold
class TestLeafProseAgainstPilotGold:
    @pytest.fixture
    def leaf_body(self) -> str:
        return load_skills(FIG_CHECKLIST_DIR)[PILOT_LEAF]["v1"].body

    def test_gold_defines_scale_bars_in_both_places_at_once(self, gold_rows):
        """The evidence for the leaf's independence rule."""
        micrographs = [r for r in gold_rows if r.get("micrograph") == "yes"]
        both = [
            r
            for r in micrographs
            if r.get("scale_bar_defined_in_image") == "yes"
            and r.get("scale_bar_defined_in_caption") == "yes"
        ]
        neither = [
            r
            for r in micrographs
            if r.get("scale_bar_defined_in_image") == "no"
            and r.get("scale_bar_defined_in_caption") == "no"
        ]
        assert both, "gold no longer shows the both-defined case"
        assert neither, "gold no longer shows the neither-defined case"

    def test_the_leaf_says_the_two_definition_sites_are_independent(
        self, leaf_body: str
    ):
        """Not just the word 'independent' -- the both/neither claim itself.

        The leaf already says to "check both, independently", which is an
        instruction about *procedure*. The claim the gold demands is about
        *outcomes*: both sites can be true at once, and neither can be. A
        block has to say that.
        """
        stating = [
            block
            for block in _prose_blocks(leaf_body)
            if "both" in block.lower() and "neither" in block.lower()
        ]
        assert stating, (
            "the dropped JSON example implied the two definition sites are "
            "mutually exclusive; gold contradicts that on 38% of micrograph "
            "rows (15 both-yes, 16 neither-yes), so the prose must say a "
            "scale bar can be defined in both places or in neither"
        )

    def test_a_scale_bar_is_only_claimed_on_micrograph_panels(self, gold_rows):
        """Backs the leaf's 'if and only if it is a micrograph' gate."""
        offenders = [
            r
            for r in gold_rows
            if r.get("micrograph") == "no"
            and r.get("scale_bar_on_image") == "yes"
        ]
        assert offenders == []

    def test_non_micrograph_rows_leave_the_answer_fields_empty(self, gold_rows):
        """Backs the leaf's output rule -- and bounds the known gold outlier.

        `eval-manifest.json` marks "" as the NA value for these fields, so a
        non-micrograph panel is expected to carry empty strings. One gold row
        uses "no" instead. The rule holds for the rest.
        """
        non_micrograph = [r for r in gold_rows if r.get("micrograph") == "no"]
        offenders = [
            r
            for r in non_micrograph
            if any(r.get(f, "") != "" for f in SCALE_BAR_ANSWER_FIELDS)
        ]
        assert len(non_micrograph) > 100
        assert len(offenders) <= 1, (
            "more gold rows now disagree with the leaf's rule that a "
            f"non-micrograph panel empties the answer fields: {offenders}"
        )

    def test_every_non_micrograph_row_still_carries_its_label(self, gold_rows):
        """The regression the review caught, stated as a property of gold."""
        unlabelled = [
            r
            for r in gold_rows
            if r.get("micrograph") == "no" and not r.get("panel_label", "")
        ]
        assert unlabelled == [], (
            "gold keeps panel_label on non-micrograph panels; the leaf prose "
            "must not tell the agent to blank it"
        )


# ---------------------------------------------------------------------------
# Nothing shared is restated in a leaf
# ---------------------------------------------------------------------------
#
# The other half of gate 2B: the conversion must not leave the shared work
# duplicated in the leaf. With one leaf that is easy to eyeball. With eleven it
# is not, and a leaf that quietly keeps its own copy of the panel-finding rules
# is the exact failure the milestone exists to prevent -- it would still score,
# so nothing else would notice.
#
# The test is phrased against the distinctive wording of `identify-panels` §1
# rather than against a summary, so it keeps working as the leaves multiply.

PANEL_FINDING_PHRASES = (
    "consecutive letters",
    "top left",
    "bottom right",
    "messy",
)


@requires_pilot_gold
class TestNoLeafRestatesTheSharedSkill:
    def test_the_phrases_really_are_the_shared_skills_own(self):
        """Guard the guard: these must live in `identify-panels`."""
        shared = load_skills(FIG_CHECKLIST_DIR)[SHARED_SKILL]["v1"].body
        missing = [p for p in PANEL_FINDING_PHRASES if p not in shared.lower()]
        assert missing == [], (
            f"{SHARED_SKILL} no longer contains {missing}, so this test would "
            "pass vacuously; update PANEL_FINDING_PHRASES"
        )

    def test_no_leaf_restates_how_to_find_panels(self):
        skills = load_skills(FIG_CHECKLIST_DIR)
        offenders = {}
        for name, versions in skills.items():
            if name == SHARED_SKILL:
                continue
            for version, skill in versions.items():
                echoed = [
                    p for p in PANEL_FINDING_PHRASES if p in skill.body.lower()
                ]
                if echoed:
                    offenders[f"{name}/{version}"] = echoed
        assert offenders == {}, (
            "a leaf restates panel-finding rules that belong to "
            f"{SHARED_SKILL}; it must delegate instead: {offenders}"
        )

    def test_every_leaf_that_needs_panels_delegates_for_them(self):
        """A leaf may not silently stop asking for the shared inventory."""
        skills = load_skills(FIG_CHECKLIST_DIR)
        for name, versions in skills.items():
            if name == SHARED_SKILL:
                continue
            for version, skill in versions.items():
                assert SHARED_SKILL in skill.requires, (
                    f"{name}/{version} does not require {SHARED_SKILL}"
                )
                asking = [
                    block
                    for block in _prose_blocks(skill.body)
                    if SHARED_SKILL in block and SKILL_TOOL in block
                ]
                assert asking, (
                    f"{name}/{version} declares {SHARED_SKILL} but no prose "
                    f"block calls it with the {SKILL_TOOL} tool"
                )

    def test_no_skill_asks_the_session_to_write_a_file(self):
        """The session has no write tool, so prose asking for one would send
        it after something it cannot do.

        Skills exchange nothing through the filesystem. `Skill(x)` loads x's
        instructions into the session already running -- there is no second
        agent and no return value -- so what a skill "produces" is simply
        stated in the reply, already in front of whatever runs next. A file
        would only matter for carrying state *between* runs, and that is a
        channel nothing bounds: "only panels.json" is a convention, not a
        constraint.
        """
        for name, versions in load_skills(FIG_CHECKLIST_DIR).items():
            body = versions["v1"].body.lower()
            for forbidden in ("panels.json", "plot_panels.json", "`write`"):
                assert forbidden not in body, (
                    f"{name} still asks for a filesystem exchange "
                    f"({forbidden}); the session cannot write"
                )

    def test_the_leaf_takes_the_inventory_from_the_shared_skill(self):
        """It must still defer to `identify-panels` rather than deriving its
        own list -- that is what makes checks agree about what a panel is."""
        leaf = load_skills(FIG_CHECKLIST_DIR)[PILOT_LEAF]["v1"].body.lower()
        assert SHARED_SKILL in leaf
        assert "source of truth" in leaf

# ---------------------------------------------------------------------------
# Milestone 3: the sealed runtime directory
# ---------------------------------------------------------------------------
#
# The runner assembles a self-contained directory, outside the repository,
# holding exactly the skills and the one example the agent may see. Everything
# below is a containment property, so each test is phrased as "X is absent" or
# "the only thing present is Y" rather than "Y is present" -- a test that only
# checks for presence passes just as happily on a directory that also contains
# the gold.
#
# Two facts from Anthropic's Agent SDK documentation shape this:
#
#   * skills live at `.claude/skills/<name>/SKILL.md`, discovered from the
#     filesystem with no programmatic registration; and
#   * with default options the SDK loads `~/.claude/skills/`, `<cwd>/.claude/
#     skills/`, and `.claude/skills/` in *every parent of cwd up to the
#     repository root*.
#
# The second is why "outside the repo" is necessary but not sufficient, and
# why the setting sources are pinned to "project" alone.

from soda_mmqc.config import (  # noqa: E402
    AGENTIC_ARTIFACTS_SUBDIR,
    AGENTIC_INPUT_SUBDIR,
    AGENTIC_ORIENTATION_FILENAME,
    AGENTIC_SETTING_SOURCES,
    AGENTIC_SKILLS_SUBDIR,
    resolve_agentic_runtime_root,
)

GOLD_FILENAMES = ("expected_output.json", "benchmark.json", "eval-manifest.json")


def _all_files(root: Path):
    return [p for p in root.rglob("*") if p.is_file()]


@pytest.fixture
def assembled(tmp_path: Path):
    """A runtime assembled for the pilot leaf and one real example."""
    layout = assemble_runtime(
        "fig-checklist",
        PILOT_LEAF,
        SUBPANEL_FIGURE,
        root=tmp_path / "runtime",
    )
    return layout


@requires_subpanel_figure
class TestRuntimeRootIsOutsideTheRepo:
    def test_the_default_root_is_outside_the_repository(self):
        root = resolve_agentic_runtime_root()
        assert REPO_ROOT != root and REPO_ROOT not in root.parents

    def test_a_root_inside_the_repository_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        import soda_mmqc.config as config

        monkeypatch.setattr(
            config, "AGENTIC_RUNTIME_DIR", REPO_ROOT / "soda_mmqc" / "tmp"
        )
        with pytest.raises(ValueError, match=r"inside the repository"):
            config.resolve_agentic_runtime_root()

    def test_setting_sources_exclude_the_user_scope(self):
        """`user` is what loads ~/.claude/skills into a scored run."""
        assert "user" not in AGENTIC_SETTING_SOURCES
        assert AGENTIC_SETTING_SOURCES == ("project",)


@requires_subpanel_figure
class TestRuntimeSkillPlacement:
    def test_skills_sit_where_the_sdk_discovers_them(self, assembled):
        skills_root = assembled.root / AGENTIC_SKILLS_SUBDIR
        assert assembled.skills_root == skills_root
        assert skills_root.is_dir()
        for name in ("identify-panels", PILOT_LEAF):
            assert (skills_root / name / SKILL_FILENAME).is_file()

    def test_every_skill_of_the_checklist_is_present(self, assembled):
        """The runner preselects nothing: all descriptions must compete."""
        expected = set(load_skills(FIG_CHECKLIST_DIR))
        present = {
            p.parent.name
            for p in assembled.skills_root.rglob(SKILL_FILENAME)
        }
        assert present == expected

    def test_the_shared_skill_is_not_pruned_to_the_named_check(
        self, assembled
    ):
        assert (
            assembled.skills_root / SHARED_SKILL / SKILL_FILENAME
        ).is_file()

    def test_exactly_one_version_per_skill_name(self, assembled):
        names = [
            p.parent.name
            for p in assembled.skills_root.rglob(SKILL_FILENAME)
        ]
        assert len(names) == len(set(names))

    def test_no_version_directory_survives_into_the_runtime(self, assembled):
        """Versions are flattened; a `v1/` in the runtime means two could sit
        side by side and the SDK would see neither at the expected path."""
        offenders = [
            p
            for p in assembled.root.rglob("*")
            if p.is_dir() and re.fullmatch(r"v\d+", p.name)
        ]
        assert offenders == []

    def test_the_skill_store_is_not_reachable(self, assembled):
        """No symlink, no parent reference, no copy of the checklist dir."""
        links = [p for p in assembled.root.rglob("*") if p.is_symlink()]
        assert links == []
        assert not (assembled.root / "checklist").exists()

    def test_each_skill_keeps_its_runtime_schema(self, assembled):
        for name in (SHARED_SKILL, PILOT_LEAF):
            assert (assembled.skills_root / name / "schema.json").is_file()


@requires_subpanel_figure
class TestRuntimeHoldsOneExampleAndNoGold:
    def test_the_example_inputs_are_copied_in(self, assembled):
        input_root = assembled.root / AGENTIC_INPUT_SUBDIR
        assert assembled.input_root == input_root
        assert (input_root / "caption.txt").is_file()
        assert any(input_root.glob("*.png")) or any(input_root.glob("*.jpg"))

    def test_no_gold_reaches_the_runtime(self, assembled):
        offenders = [
            p for p in _all_files(assembled.root) if p.name in GOLD_FILENAMES
        ]
        assert offenders == [], f"gold leaked into the runtime: {offenders}"

    def test_the_checks_directory_is_never_copied(self, assembled):
        assert [p for p in assembled.root.rglob("checks")] == []

    def test_no_other_example_is_present(self, assembled):
        """The one example only -- not its siblings, not its document."""
        other = "10.1038_s44321-025-00219-1/content/2"
        assert not (assembled.root / other).exists()
        blob = " ".join(p.name for p in _all_files(assembled.root))
        assert "content/2" not in blob

    def test_the_prompts_directory_is_not_copied(self, assembled):
        """Legacy prompts are not part of the agentic runtime."""
        assert [p for p in assembled.root.rglob("prompts")] == []

    def test_the_artifacts_root_exists_and_is_empty(self, assembled):
        artifacts = assembled.root / AGENTIC_ARTIFACTS_SUBDIR
        assert assembled.artifacts_root == artifacts
        assert artifacts.is_dir()
        assert list(artifacts.iterdir()) == []


@requires_subpanel_figure
class TestRuntimeOrientation:
    def test_the_orientation_file_is_generated(self, assembled):
        path = assembled.root / AGENTIC_ORIENTATION_FILENAME
        assert assembled.orientation_path == path
        assert path.is_file()

    def test_the_instructions_name_no_example_class(self, assembled):
        """One file serves every checklist, so it may assume none of them.

        A figure vocabulary here is how `doc-checklist` would silently get
        instructions about images it does not have.
        """
        text = assembled.orientation_path.read_text(encoding="utf-8").lower()
        for forbidden in ("figure", "caption", "micrograph", "image"):
            assert forbidden not in text

    def test_the_instructions_describe_supporting_files(self, assembled):
        """The entry point is per-run and travels in the request; the
        supporting files are per-run and travel in the manifest. Neither
        belongs in a file that is byte-identical for every run."""
        text = assembled.orientation_path.read_text(encoding="utf-8")
        assert "inputs.json" in text
        assert PILOT_LEAF not in text

    def test_the_instructions_promise_no_writable_directory(self, assembled):
        """The profile grants Read and Skill only; promising more wastes turns."""
        text = assembled.orientation_path.read_text(encoding="utf-8").lower()
        assert "artifacts" not in text

    def test_the_manifest_names_what_was_staged(self, assembled):
        """Which files exist is data, not prose: the session has no shell, no
        glob and no listing, so anything unnamed here is unreachable."""
        manifest = json.loads(
            (
                assembled.input_root / AGENTIC_INPUT_MANIFEST_FILENAME
            ).read_text(encoding="utf-8")
        )
        for entry in manifest["source_data"]:
            assert (assembled.root / entry).is_file()

    def test_it_does_not_list_the_entry_points_dependencies(self, assembled):
        """Finding the rest is the agent's job; naming it here would make the
        Milestone 4 trace measure our own control flow."""
        text = assembled.orientation_path.read_text(encoding="utf-8")
        assert SHARED_SKILL not in text

    def test_it_does_not_leak_a_repository_path(self, assembled):
        text = assembled.orientation_path.read_text(encoding="utf-8")
        assert str(REPO_ROOT) not in text


@requires_subpanel_figure
class TestRuntimeLifecycle:
    def test_the_session_removes_the_runtime_by_default(self, tmp_path: Path):
        with runtime_session(
            "fig-checklist", PILOT_LEAF, SUBPANEL_FIGURE,
            root=tmp_path / "rt",
        ) as layout:
            root = layout.root
            assert root.is_dir()
        assert not root.exists()

    def test_keep_runtime_preserves_it(self, tmp_path: Path):
        with runtime_session(
            "fig-checklist", PILOT_LEAF, SUBPANEL_FIGURE,
            root=tmp_path / "rt", keep=True,
        ) as layout:
            root = layout.root
        assert root.is_dir()

    def test_the_runtime_is_removed_after_an_exception(self, tmp_path: Path):
        captured = {}
        with pytest.raises(RuntimeError, match="boom"):
            with runtime_session(
                "fig-checklist", PILOT_LEAF, SUBPANEL_FIGURE,
                root=tmp_path / "rt",
            ) as layout:
                captured["root"] = layout.root
                raise RuntimeError("boom")
        assert not captured["root"].exists()

    def test_keep_runtime_survives_an_exception(self, tmp_path: Path):
        captured = {}
        with pytest.raises(RuntimeError):
            with runtime_session(
                "fig-checklist", PILOT_LEAF, SUBPANEL_FIGURE,
                root=tmp_path / "rt", keep=True,
            ) as layout:
                captured["root"] = layout.root
                raise RuntimeError("boom")
        assert captured["root"].is_dir()

    def test_assembly_is_atomic(self, tmp_path: Path):
        """A failed assembly leaves no half-built runtime behind."""
        root = tmp_path / "rt"
        with pytest.raises((FileNotFoundError, ValueError)):
            assemble_runtime(
                "fig-checklist", PILOT_LEAF, "no/such/example", root=root
            )
        assert not root.exists()


# ---------------------------------------------------------------------------
# The permission profile
# ---------------------------------------------------------------------------
#
# Deny by default, expressed as an allowlist and compared for *equality*.
# A denylist would silently grant whatever the SDK adds in a future version;
# an equality check fails instead, which is the behaviour a containment
# boundary should have. Each prohibition also gets its own named test, so a
# mistaken widening reports which guarantee it broke rather than just that a
# set changed.

from soda_mmqc.config import (  # noqa: E402
    AGENTIC_ALLOWED_TOOL_NAMES,
    AGENTIC_BASE_TOOLS,
    AGENTIC_FORBIDDEN_TOOLS,
    AGENTIC_PERMISSION_MODE,
)

SHELL_TOOLS = ("Bash", "BashOutput", "KillShell", "NotebookEdit")
SUBAGENT_TOOLS = ("Task", "Agent")
NETWORK_TOOLS = ("WebFetch", "WebSearch")


@requires_subpanel_figure
class TestPermissionProfile:
    def test_the_allowlist_is_exactly_the_two_things_allowed(self, assembled):
        """Read inside the runtime, and call a skill. Nothing else."""
        rules = session_options(assembled)["allowed_tools"]
        assert len(rules) == 2
        named = {rule.split("(")[0] for rule in rules}
        assert named == set(AGENTIC_ALLOWED_TOOL_NAMES)

    def test_reads_are_scoped_to_the_runtime(self, assembled):
        """A bare `Read` would auto-approve reading anything on disk --
        including the repository and the gold. The rule must be path-scoped
        and must use the SDK's `//` absolute form, since a single leading
        slash anchors at the working directory instead."""
        rules = session_options(assembled)["allowed_tools"]
        read = next(r for r in rules if r.startswith("Read("))
        assert read.startswith("Read(//")
        assert assembled.root.resolve().as_posix().lstrip("/") in read
        assert read.endswith("/**)")

    def test_the_session_has_no_write_tool_at_all(self, assembled):
        """A check observes an example; it does not change one.

        Scoping a write was the old answer -- `Edit(artifacts/**)`, since
        `Edit(path)` governs every file-writing tool. Removing the tool is a
        stronger one: the runner serialises the structured result, so nothing
        the session does needs the filesystem, and an unused capability is
        one an experiment could accidentally come to depend on.
        """
        options = session_options(assembled)
        assert "Write" not in options["tools"]
        assert "Edit" not in options["tools"]
        assert not any(
            r.startswith(("Write(", "Edit(")) for r in options["allowed_tools"]
        )

    def test_the_base_tool_set_is_what_the_session_has(self, assembled):
        """`tools` bounds what exists; `allowed_tools` only auto-approves.

        Naming three tools in `allowed_tools` once left about twenty in the
        model's context, so the profile had to enumerate every dangerous one
        by name -- and missed `ShareOnboardingGuide` for months.
        """
        options = session_options(assembled)
        assert set(options["tools"]) == set(AGENTIC_BASE_TOOLS)
        assert set(options["tools"]) >= {
            r.split("(")[0] for r in options["allowed_tools"]
        }

    def test_the_permission_mode_denies_anything_unlisted(self, assembled):
        """`allowed_tools` alone is only a list of auto-approvals: the SDK
        documents that unlisted tools remain reachable and fall through to the
        permission mode. `dontAsk` is what makes the allowlist total."""
        assert AGENTIC_PERMISSION_MODE == "dontAsk"
        assert session_options(assembled)["permission_mode"] == "dontAsk"

    @pytest.mark.parametrize("tool", SHELL_TOOLS)
    def test_no_shell_or_code_execution(self, assembled, tool: str):
        options = session_options(assembled)
        assert tool not in options["allowed_tools"]
        assert tool in options["disallowed_tools"]

    @pytest.mark.parametrize("tool", SUBAGENT_TOOLS)
    def test_no_subagent_creation(self, assembled, tool: str):
        options = session_options(assembled)
        assert tool not in options["allowed_tools"]
        assert tool in options["disallowed_tools"]

    @pytest.mark.parametrize("tool", NETWORK_TOOLS)
    def test_no_network_access(self, assembled, tool: str):
        options = session_options(assembled)
        assert tool not in options["allowed_tools"]
        assert tool in options["disallowed_tools"]

    def test_no_skill_requests_a_network_capability(self):
        """The network denial stands until a `needs` justifies it on record."""
        requested = {
            f"{name}/{version}": skill.needs
            for name, versions in load_skills(FIG_CHECKLIST_DIR).items()
            for version, skill in versions.items()
            if skill.needs
        }
        assert requested == {}, (
            "a skill declares `needs`; the network denial in the permission "
            f"profile must be re-justified at a gate before honouring it: "
            f"{requested}"
        )

    def test_allowed_and_forbidden_never_overlap(self, assembled):
        options = session_options(assembled)
        assert not set(options["allowed_tools"]) & set(
            options["disallowed_tools"]
        )

    def test_the_session_is_rooted_in_the_runtime_not_the_repo(
        self, assembled
    ):
        options = session_options(assembled)
        cwd = Path(options["cwd"]).resolve()
        assert cwd == assembled.root.resolve()
        assert REPO_ROOT not in cwd.parents and cwd != REPO_ROOT

    def test_user_setting_source_is_excluded(self, assembled):
        """~/.claude/skills loads regardless of cwd; only omitting the user
        scope keeps an operator's personal skills out of a scored run."""
        options = session_options(assembled)
        assert "user" not in options["setting_sources"]
        assert options["setting_sources"] == ["project"]

    def test_every_assembled_skill_stays_invocable(self, assembled):
        """Delegated discovery is the premise; pruning ours would test our own
        control flow instead of the prose. So every assembled skill is listed
        -- but only ours."""
        listed = session_options(assembled)["skills"]
        assert set(listed) == set(load_skills(FIG_CHECKLIST_DIR))

    def test_the_named_pool_names_only_ours(self, assembled):
        """The pool is named explicitly rather than left as "all".

        This checks the list we *build*, which is all a unit test can see. It
        is deliberately not named for the session-level claim: naming the pool
        does not shorten the session's `init` array, which still reports the
        installation's bundled skills alongside ours. What it does bound --
        the Skill tool offering the model only these names, and refusing a
        call to any other -- costs a live session to observe, so it is
        measured out-of-band and recorded at `session_options`. An equality
        assertion against `init` would fail on every machine.
        """
        listed = session_options(assembled)["skills"]
        assert listed != "all"
        assert "code-review" not in listed and "deep-research" not in listed

    def test_the_egress_and_persistence_tools_are_denied(self, assembled):
        """Found by reading the SDK's reported tool set, not by design."""
        denied = set(session_options(assembled)["disallowed_tools"])
        for tool in (
            "SendMessage", "PushNotification", "ScheduleWakeup",
            "CronCreate", "EnterWorktree", "Workflow",
        ):
            assert tool in denied, f"{tool} is reachable"

    def test_the_runner_not_the_session_produces_the_prediction(self):
        """`Write` used to be needed because the session wrote
        prediction.json itself. It does not: `output_format` constrains the
        answer to the leaf schema and the runner serialises the result, so
        the last reason for a write tool went with it."""
        source = inspect.getsource(_run_agent_session)
        assert "output_path.write_text" in source
        assert "json.loads(result_text)" in source

    def test_the_profile_prints_what_was_approved(self, assembled):
        text = describe_permission_profile(assembled)
        for tool in AGENTIC_ALLOWED_TOOL_NAMES:
            assert tool in text
        assert AGENTIC_PERMISSION_MODE in text
        for tool, reason in AGENTIC_FORBIDDEN_TOOLS.items():
            assert tool in text and reason in text
        assert "no 'user'" in text


# ---------------------------------------------------------------------------
# The runtime root is OS-neutral
# ---------------------------------------------------------------------------
#
# Gate 3A originally produced a macOS-specific artifact -- a `tmutil` result
# and a POSIX mode bit -- which answers the question for one laptop rather
# than for the design. These tests move the guarantees into code that runs
# anywhere: the default comes from `tempfile.gettempdir()`, which already
# resolves correctly per platform, and the two refusals are checked
# case-insensitively because macOS and Windows would otherwise let a
# differently-cased path past a rule their own filesystem treats as identical.


@pytest.fixture
def reload_config(monkeypatch: pytest.MonkeyPatch):
    """Re-import config with a patched runtime dir."""
    import soda_mmqc.config as config

    def _with(path):
        monkeypatch.setattr(config, "AGENTIC_RUNTIME_DIR", Path(path))
        return config

    return _with


class TestRuntimeRootIsOsNeutral:
    def test_the_default_comes_from_the_stdlib_temp_dir(self):
        """No per-OS branching: gettempdir() is already the right answer on
        Linux (/tmp), macOS (/var/folders/...) and Windows (AppData\\Local\\
        Temp)."""
        import soda_mmqc.config as config

        assert config.AGENTIC_RUNTIME_DIR == Path(tempfile.gettempdir())

    def test_the_resolved_root_is_usable_wherever_it_lands(self):
        root = resolve_agentic_runtime_root()
        assert root.is_absolute() and root.is_dir()
        probe = root / f"soda-mmqc-probe-{os.getpid()}"
        probe.mkdir()
        try:
            assert probe.is_dir()
        finally:
            probe.rmdir()
        assert not probe.exists()

    def test_a_differently_cased_repo_path_is_still_refused(
        self, reload_config
    ):
        """macOS and Windows are case-insensitive; a plain Path comparison
        would miss a path the filesystem resolves into the repository."""
        shouty = Path(str(REPO_ROOT).upper()) / "tmp"
        config = reload_config(shouty)
        with pytest.raises(ValueError, match=r"inside the repository"):
            config.resolve_agentic_runtime_root()

    @pytest.mark.parametrize(
        "marker",
        ["Dropbox", "OneDrive", "Google Drive", "Mobile Documents"],
    )
    def test_a_file_sync_directory_is_refused(self, reload_config, marker):
        """Runtime directories hold intermediates derived from unpublished
        figures; syncing them to a third party is a disclosure. The common
        clients are named on every platform, so this is checkable anywhere
        rather than needing a person to inspect one machine."""
        config = reload_config(Path.home() / marker / "agentic")
        with pytest.raises(ValueError, match=r"file-sync directory"):
            config.resolve_agentic_runtime_root()

    def test_the_sync_check_is_case_insensitive(self, reload_config):
        config = reload_config(Path.home() / "DROPBOX" / "agentic")
        with pytest.raises(ValueError, match=r"file-sync directory"):
            config.resolve_agentic_runtime_root()

    def test_an_ordinary_local_path_is_accepted(self, reload_config, tmp_path):
        config = reload_config(tmp_path)
        assert config.resolve_agentic_runtime_root() == tmp_path.resolve()


@requires_subpanel_figure
class TestRuntimeContentIsOsNeutral:
    def test_the_orientation_uses_posix_separators(self, assembled):
        """The orientation is read by a model, not by a shell. Backslashes
        would be a Windows-only surprise in the one file that tells the agent
        where everything is."""
        text = assembled.orientation_path.read_text(encoding="utf-8")
        assert "\\" not in text

    def test_permission_rules_use_posix_separators(self, assembled):
        for rule in session_options(assembled)["allowed_tools"]:
            assert "\\" not in rule

    def test_assembly_creates_no_platform_specific_entry(self, assembled):
        names = {p.name for p in assembled.root.rglob("*")}
        assert not names & {"desktop.ini", "Thumbs.db", ".DS_Store"}


# ---------------------------------------------------------------------------
# Milestone 4: the per-example session
# ---------------------------------------------------------------------------
#
# The session is driven through a fake client, so these tests open no
# connection, need no credentials and cost nothing. What they pin is the
# contract around the session rather than the model's behaviour:
#
#   * the session is given the runtime, the entry point and the example, and
#     nothing else -- no closure, no ordering, no list of dependencies;
#   * every assembled skill's description is available, because delegated
#     discovery is the premise under test;
#   * the trace records what the hook saw, never what the prose implied;
#   * an invalid output fails *before* anything is written as a prediction.

import asyncio  # noqa: E402


def _tool_use(name: str, payload: dict, use_id: str = "t1"):
    """One assistant message carrying a tool_use block, mapping-shaped."""
    return {"content": [{"name": name, "input": payload, "id": use_id}]}


def _fake_client(messages, *, writes=None, captured=None):
    """Build a client that emits `messages` and optionally writes an output."""

    async def client(parts, options):
        if captured is not None:
            captured["parts"] = list(parts)
            captured["options"] = dict(options)
        for message in messages:
            yield message
        if writes is not None:
            # No figure read is modelled any more: the content arrives with
            # the request, so there is no fetch a session could skip and no
            # gate for the double to satisfy.
            #
            # The answer arrives as the session's structured result, not as a
            # file the session wrote: `output_format` constrains it to the
            # leaf schema and the runner serialises it.
            yield {"result": json.dumps(writes)}

    return client


def _valid_prediction():
    return {
        "outputs": [
            {
                "panel_label": "A",
                "micrograph": "yes",
                "scale_bar_on_image": "yes",
                "scale_bar_defined_in_caption": "no",
                "from_the_caption": "",
                "scale_bar_defined_in_image": "yes",
                "from_the_image": "2 um",
            }
        ]
    }


def _run(layout, **kwargs):
    """Returns (prediction, trace recorder, audit log)."""
    return asyncio.run(_run_agent_session(layout, **kwargs))


@requires_subpanel_figure
class TestAgentSession:
    def test_the_session_is_given_the_runtime_and_the_entry_point(
        self, assembled
    ):
        captured = {}
        client = _fake_client(
            [], writes=_valid_prediction(), captured=captured
        )
        _run(assembled, client=client)

        assert captured["options"]["cwd"] == str(assembled.root)
        assert PILOT_LEAF in captured["parts"][0]["text"]

    def test_no_closure_is_supplied_to_the_session(self, assembled):
        """Naming the dependency would make the trace measure this string."""
        captured = {}
        client = _fake_client(
            [], writes=_valid_prediction(), captured=captured
        )
        _run(assembled, client=client)
        assert not any(
            SHARED_SKILL in part.get("text", "")
            for part in captured["parts"]
        )

    def test_every_skill_description_is_available_to_the_session(
        self, assembled
    ):
        captured = {}
        client = _fake_client(
            [], writes=_valid_prediction(), captured=captured
        )
        _run(assembled, client=client)

        present = {
            p.parent.name
            for p in assembled.skills_root.rglob(SKILL_FILENAME)
        }
        assert present == set(load_skills(FIG_CHECKLIST_DIR))
        # every assembled skill is invocable -- and nothing else is
        assert set(captured["options"]["skills"]) == present

    def test_a_valid_prediction_is_returned(self, assembled):
        client = _fake_client([], writes=_valid_prediction())
        prediction, _, _ = _run(assembled, client=client)
        assert prediction == _valid_prediction()

    def test_an_invalid_output_fails_before_a_prediction_is_written(
        self, assembled, tmp_path: Path
    ):
        bad = {"outputs": [{"panel_label": "A", "micrograph": "maybe"}]}
        client = _fake_client([], writes=bad)
        with pytest.raises(ValueError, match=r"does not match the schema"):
            _run(assembled, client=client)

        predictions = tmp_path / "predictions"
        assert not predictions.exists()

    def test_a_session_that_writes_nothing_fails(self, assembled):
        client = _fake_client([])
        with pytest.raises(ValueError, match=r"no structured result"):
            _run(assembled, client=client)

    def test_schema_errors_are_all_reported_at_once(self, assembled):
        bad = {
            "outputs": [
                {"panel_label": "A", "micrograph": "maybe"},
                {"panel_label": "B", "micrograph": "perhaps"},
            ]
        }
        client = _fake_client([], writes=bad)
        with pytest.raises(ValueError) as excinfo:
            _run(assembled, client=client)
        assert str(excinfo.value).count("maybe") >= 1
        assert "perhaps" in str(excinfo.value)


@requires_subpanel_figure
class TestSkillTrace:
    def test_a_skill_call_is_recorded(self, assembled, tmp_path: Path):
        trace_path = tmp_path / "skill_trace.json"
        client = _fake_client(
            [_tool_use("Skill", {"name": SHARED_SKILL}, "abc")],
            writes=_valid_prediction(),
        )
        _, recorder, _ = _run(
            assembled,
            client=client,
            trace_path=trace_path,
            versions={SHARED_SKILL: "v1"},
        )
        entry = recorder.entries[0]
        assert entry["skill"] == SHARED_SKILL
        assert entry["version"] == "v1"
        assert entry["tool_use_id"] == "abc"
        assert entry["source"] == "hook"
        assert entry["timestamp"]

    def test_non_skill_tools_are_not_recorded(self, assembled, tmp_path: Path):
        client = _fake_client(
            [
                _tool_use("Read", {"file_path": "input/caption.txt"}),
                _tool_use("Skill", {"name": SHARED_SKILL}),
            ],
            writes=_valid_prediction(),
        )
        _, recorder, _ = _run(
            assembled, client=client, trace_path=tmp_path / "t.json"
        )
        assert recorder.invoked == [SHARED_SKILL]

    def test_the_trace_is_written_as_calls_occur(
        self, assembled, tmp_path: Path
    ):
        """A session that dies halfway must still leave its trace -- that is
        usually the session whose trace matters most."""
        trace_path = tmp_path / "t.json"
        seen = {}

        async def dying_client(parts, options):
            yield _tool_use("Skill", {"name": SHARED_SKILL})
            seen["on_disk"] = json.loads(trace_path.read_text())
            raise RuntimeError("session died")

        with pytest.raises(RuntimeError, match="session died"):
            _run(assembled, client=dying_client, trace_path=trace_path)

        assert [e["skill"] for e in seen["on_disk"]] == [SHARED_SKILL]
        assert json.loads(trace_path.read_text())

    def test_the_trace_exists_even_with_no_calls(
        self, assembled, tmp_path: Path
    ):
        trace_path = tmp_path / "t.json"
        client = _fake_client([], writes=_valid_prediction())
        _run(assembled, client=client, trace_path=trace_path)
        assert json.loads(trace_path.read_text()) == []

    def test_a_slash_prefixed_skill_name_is_normalised(
        self, assembled, tmp_path: Path
    ):
        client = _fake_client(
            [_tool_use("Skill", {"command": f"/{SHARED_SKILL}"})],
            writes=_valid_prediction(),
        )
        _, recorder, _ = _run(
            assembled, client=client, trace_path=tmp_path / "t.json"
        )
        assert recorder.invoked == [SHARED_SKILL]


class TestDeclaredVersusObserved:
    def test_a_fired_hop_is_reported_as_matching(self):
        report = compare_declared_and_observed(
            FIG_CHECKLIST_DIR, PILOT_LEAF, [SHARED_SKILL]
        )
        assert report["declared"] == [SHARED_SKILL]
        assert report["observed"] == [SHARED_SKILL]
        assert report["declared_not_observed"] == []
        assert report["observed_not_declared"] == []

    def test_a_missing_hop_is_reported_not_repaired(self):
        """The runner must never call the skill itself to paper over this."""
        report = compare_declared_and_observed(
            FIG_CHECKLIST_DIR, PILOT_LEAF, []
        )
        assert report["declared_not_observed"] == [SHARED_SKILL]

    def test_an_undeclared_hop_is_reported(self):
        report = compare_declared_and_observed(
            FIG_CHECKLIST_DIR, PILOT_LEAF, [SHARED_SKILL, "something-else"]
        )
        assert report["observed_not_declared"] == ["something-else"]


@requires_subpanel_figure
class TestMockRun:
    def test_mock_writes_a_prediction_and_a_trace(self, tmp_path: Path):
        out = run_check_mock(
            "fig-checklist",
            PILOT_LEAF,
            output=tmp_path / "p",
            examples=[SUBPANEL_FIGURE],
        )
        example_dir = out / SUBPANEL_FIGURE
        assert (example_dir / PREDICTION_FILENAME).is_file()
        assert (
            example_dir / INTERMEDIATES_DIRNAME / SKILL_TRACE_FILENAME
        ).is_file()

    def test_the_mock_prediction_satisfies_the_leaf_schema(
        self, tmp_path: Path
    ):
        out = run_check_mock(
            "fig-checklist",
            PILOT_LEAF,
            output=tmp_path / "p",
            examples=[SUBPANEL_FIGURE],
        )
        payload = json.loads(
            (out / SUBPANEL_FIGURE / PREDICTION_FILENAME).read_text()
        )
        schema = json.loads(
            (PILOT_CHECK_DIR / "schema.json").read_text()
        )["format"]["schema"]
        validate_against_schema(payload, schema)

    def test_mock_trace_entries_are_marked_as_mock(self, tmp_path: Path):
        """Mock traces are generated from frontmatter, so comparing them to
        frontmatter is circular. The marker keeps them out of gate 4D."""
        out = run_check_mock(
            "fig-checklist",
            PILOT_LEAF,
            output=tmp_path / "p",
            examples=[SUBPANEL_FIGURE],
        )
        trace = json.loads(
            (
                out / SUBPANEL_FIGURE / INTERMEDIATES_DIRNAME
                / SKILL_TRACE_FILENAME
            ).read_text()
        )
        assert trace and all(e["source"] == "mock" for e in trace)

    def test_mock_output_is_scoreable(self, tmp_path: Path):
        out = run_check_mock(
            "fig-checklist",
            PILOT_LEAF,
            output=tmp_path / "p",
            examples=[SUBPANEL_FIGURE],
        )
        loaded = load_predictions(out)
        assert set(loaded) == {SUBPANEL_FIGURE}

    def test_the_trace_sidecar_is_ignored_when_scoring(self, tmp_path: Path):
        """Only leaf JSON is scored; sidecars must not be picked up."""
        out = run_check_mock(
            "fig-checklist",
            PILOT_LEAF,
            output=tmp_path / "p",
            examples=[SUBPANEL_FIGURE],
        )
        assert len(load_predictions(out)) == 1

    def test_mock_needs_no_credentials(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """The legacy `evaluate --mock` validates the model against the
        provider first and so aborts without a key. This one must not."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        out = run_check_mock(
            "fig-checklist",
            PILOT_LEAF,
            output=tmp_path / "p",
            examples=[SUBPANEL_FIGURE],
        )
        assert (out / SUBPANEL_FIGURE / PREDICTION_FILENAME).is_file()

    def test_mock_imports_no_sdk(self, tmp_path: Path):
        """A credential-free path must not need the 200 MB bundled binary."""
        import subprocess
        import sys

        code = (
            "import sys; "
            "from soda_mmqc.agentic.runner import run_check_mock; "
            f"run_check_mock('fig-checklist', '{PILOT_LEAF}', "
            f"output=r'{tmp_path / 'p'}', examples=['{SUBPANEL_FIGURE}']); "
            "print('claude_agent_sdk' in sys.modules)"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip().endswith("False")

    def test_gold_carries_metadata_the_schema_forbids(self):
        """Why `_as_prediction` exists, stated as a property of the data.

        Gold records hold curation metadata (`updated_at`) that the leaf
        schema rejects under `additionalProperties: false`. So gold is *not*
        directly a valid prediction, and anything that assumes it is -- a
        mock runner, a fixture, a doc example -- produces output a real
        session would be rejected for.
        """
        gold = json.loads(
            (
                EXAMPLES_DIR / SUBPANEL_FIGURE / "checks" / PILOT_LEAF
                / "expected_output.json"
            ).read_text()
        )
        schema = json.loads(
            (PILOT_CHECK_DIR / "schema.json").read_text()
        )["format"]["schema"]

        assert "updated_at" in gold
        with pytest.raises(ValueError, match=r"updated_at"):
            validate_against_schema(gold, schema)

        projected = _as_prediction(gold, schema)
        validate_against_schema(projected, schema)
        assert projected["outputs"] == gold["outputs"]


class TestToolAudit:
    def test_every_tool_call_is_recorded(self, assembled, tmp_path: Path):
        """Driven through a client that invokes the hook the way the SDK does.

        A fake that ignores hooks would let this pass while recording
        nothing, so the fake calls `options["hooks"]["PreToolUse"]` for each
        tool use, which is the contract the SDK implements.
        """
        audit = ToolAuditLog(tmp_path / "audit.json")
        messages = [
            _tool_use("Read", {"file_path": "input/caption.txt"}, "r1"),
            _tool_use("Skill", {"name": SHARED_SKILL}, "s1"),
        ]

        async def hook_calling_client(parts, options):
            hook = options["hooks"]["PreToolUse"][0]
            for message in messages:
                for name, payload, use_id in _extract_tool_calls(message):
                    await hook(
                        {
                            "tool_name": name,
                            "tool_input": payload,
                            "tool_use_id": use_id,
                        },
                        use_id,
                        None,
                    )
                yield message
            yield {"result": json.dumps(_valid_prediction())}

        _run(assembled, client=hook_calling_client, audit_log=audit)

        assert [e["tool"] for e in audit.entries] == ["Read", "Skill"]
        assert all(e["decision"] == "allow" for e in audit.entries)

    def test_the_audit_records_tools_the_trace_does_not(
        self, assembled, tmp_path: Path
    ):
        """The two instruments answer different questions.

        The skill trace answers "did discovery work"; the audit answers "what
        did the session try to do". A `Read` outside the runtime would be
        invisible in the first and obvious in the second.
        """
        audit = ToolAuditLog(tmp_path / "audit.json")
        hook = make_pretooluse_hook(audit)
        asyncio.run(
            hook(
                {
                    "tool_name": "Read",
                    "tool_input": {"file_path": "/etc/passwd"},
                    "tool_use_id": "r9",
                },
                "r9",
                None,
            )
        )
        assert audit.entries[0]["input"]["file_path"] == "/etc/passwd"

    def test_the_hook_records_and_allows_by_default(self, tmp_path: Path):
        audit = ToolAuditLog(tmp_path / "audit.json")
        hook = make_pretooluse_hook(audit)
        out = asyncio.run(
            hook(
                {
                    "tool_name": "Read",
                    "tool_input": {"file_path": "input/caption.txt"},
                    "tool_use_id": "r1",
                },
                "r1",
                None,
            )
        )
        assert out["hookSpecificOutput"]["permissionDecision"] == "allow"
        assert audit.entries[0]["tool"] == "Read"
        assert audit.entries[0]["decision"] == "allow"
        assert audit.entries[0]["timestamp"]

    def test_the_audit_is_written_as_calls_occur(self, tmp_path: Path):
        path = tmp_path / "audit.json"
        audit = ToolAuditLog(path)
        hook = make_pretooluse_hook(audit)
        asyncio.run(hook({"tool_name": "Read", "tool_input": {}}, "r1", None))
        assert json.loads(path.read_text())["calls"][0]["tool"] == "Read"

    def test_an_approver_can_deny_a_call(self, tmp_path: Path):
        audit = ToolAuditLog(tmp_path / "audit.json")
        hook = make_pretooluse_hook(
            audit, approver=lambda name, _: (False, "not this time")
        )
        out = asyncio.run(
            hook({"tool_name": "Read", "tool_input": {}}, "r1", None)
        )
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert out["hookSpecificOutput"]["permissionDecisionReason"] == (
            "not this time"
        )
        assert audit.denied and audit.denied[0]["reason"] == "not this time"

    def test_a_denial_is_visible_in_the_summary(self, tmp_path: Path):
        audit = ToolAuditLog(tmp_path / "audit.json")
        audit.record("Read", {}, "r1", "allow")
        audit.record("Read", {}, "r2", "deny", "nope")
        assert "Read (allow) x1" in audit.summary()
        assert "Read (deny) x1" in audit.summary()

    def test_the_audit_starts_as_an_empty_file(self, tmp_path: Path):
        path = tmp_path / "a.json"
        ToolAuditLog(path)
        assert json.loads(path.read_text()) == {
            "session": {}, "usage": {}, "calls": [],
        }

    def test_the_audit_records_what_the_sdk_reported_at_startup(
        self, assembled
    ):
        """Gate 3B asks for the SDK's own tool set, diffed against ours. It
        exists only in the session's `init` message, so it is captured from
        the stream rather than inferred."""
        init = {
            "subtype": "init",
            "tools": ["Read", "Write", "Skill", "Glob"],
            "model": "sonnet",
            "permissionMode": "dontAsk",
        }
        client = _fake_client(
            [init], writes=_valid_prediction()
        )
        _, _, audit = _run(assembled, client=client)
        assert audit.session_info["tools"] == [
            "Read", "Write", "Skill", "Glob"
        ]
        assert audit.session_info["permissionMode"] == "dontAsk"
        on_disk = json.loads(audit.path.read_text())
        assert on_disk["session"]["model"] == "sonnet"

    def test_the_session_wires_the_hook_into_its_options(self, assembled):
        captured = {}
        client = _fake_client(
            [], writes=_valid_prediction(), captured=captured
        )
        _run(assembled, client=client)
        hooks = captured["options"]["hooks"]
        assert "PreToolUse" in hooks and callable(hooks["PreToolUse"][0])

    def test_the_session_returns_its_audit(self, assembled):
        client = _fake_client([], writes=_valid_prediction())
        _, _, audit = _run(assembled, client=client)
        assert isinstance(audit, ToolAuditLog)
        assert audit.path.name == TOOL_AUDIT_FILENAME


class TestInteractiveApprover:
    def test_yes_allows_and_no_denies(self):
        answers = iter(["y", "n"])
        out = io.StringIO()
        approve = interactive_approver(lambda _: next(answers), out=out)
        assert approve("Read", {})[0] is True
        assert approve("Read", {})[0] is False

    def test_always_stops_asking_for_that_tool(self):
        """A supervised run must stay finishable: 38 examples would otherwise
        ask hundreds of times."""
        calls = []

        def ask(prompt):
            calls.append(prompt)
            return "a"

        approve = interactive_approver(ask, out=io.StringIO())
        assert approve("Read", {})[0] is True
        assert approve("Read", {})[0] is True
        assert approve("Read", {})[0] is True
        assert len(calls) == 1

    def test_always_does_not_leak_to_another_tool(self):
        answers = iter(["a", "n"])
        approve = interactive_approver(
            lambda _: next(answers), out=io.StringIO()
        )
        assert approve("Read", {})[0] is True
        assert approve("Write", {})[0] is False

    def test_an_empty_answer_denies(self):
        """Silence is not consent."""
        approve = interactive_approver(lambda _: "", out=io.StringIO())
        assert approve("Bash", {})[0] is False

    def test_the_prompt_shows_what_is_being_asked_for(self):
        out = io.StringIO()
        approve = interactive_approver(lambda _: "y", out=out)
        approve("Read", {"file_path": "/etc/passwd"})
        assert "Read" in out.getvalue()
        assert "/etc/passwd" in out.getvalue()

    def test_a_huge_input_is_truncated(self):
        out = io.StringIO()
        approve = interactive_approver(lambda _: "y", out=out)
        approve("Write", {"content": "x" * 5000})
        assert len(out.getvalue()) < 1000


# ---------------------------------------------------------------------------
# Milestone 6: version pinning, SkillSet expansion, and generated graph views
# ---------------------------------------------------------------------------
#
# Everything above resolves versions by "highest vN", which is a convention,
# not a commitment. Milestone 6 replaces it with a file a person signs off on.
#
# Two properties are worth stating up front because they are what the tests
# are shaped around:
#
# * **A manifest is complete or it is invalid.** Every skill pinned, no pin
#   naming a skill that is not there. A partial manifest is worse than none:
#   it looks authoritative while half the runtime still drifts.
# * **The generated views are a function of the skills alone.** No
#   timestamps, no absolute paths, no ordering that depends on the
#   filesystem -- otherwise the drift check reports noise and people learn to
#   ignore it, which is the only way a drift check can fail completely.


def _manifest(checklist: str, pins: Dict[str, str]) -> str:
    lines = [f"checklist: {checklist}", "skills:"]
    lines += [f"  {name}: {version}" for name, version in sorted(pins.items())]
    return "\n".join(lines) + "\n"


@pytest.fixture
def pinned_checklist(tmp_path: Path) -> Path:
    """A two-skill checklist with a complete manifest."""
    checklist = tmp_path / "toy-checklist"
    _write_skill(
        checklist, "leaf", "v1",
        _skill_md("leaf", requires=("shared",), produces=("leaf",)),
    )
    _write_skill(checklist, "shared", "v1", _skill_md("shared", produces=("facts",)))
    (checklist / "leaf" / "schema.json").write_text("{}", encoding="utf-8")
    for contract in EVALUATION_CONTRACT_FILES:
        (checklist / "leaf" / contract).write_text("{}", encoding="utf-8")
    (checklist / VERSION_MANIFEST_FILENAME).write_text(
        _manifest("toy-checklist", {"leaf": "v1", "shared": "v1"}),
        encoding="utf-8",
    )
    return checklist


class TestVersionManifest:
    def test_a_complete_manifest_resolves_to_a_skill_set(self, pinned_checklist):
        skills = load_skills(pinned_checklist)
        pins = load_version_manifest(pinned_checklist)
        assert pins == {"leaf": "v1", "shared": "v1"}
        assert resolve_skill_set(skills, pins).pins == pins

    def test_a_complete_manifest_validates_without_walking_a_closure(
        self, pinned_checklist
    ):
        """The manifest is checked against the *inventory*, not against a
        reachable set: a skill nothing currently calls still has to be pinned,
        because discovery is the agent's job and today's graph is not a
        promise about tomorrow's session."""
        _write_skill(
            pinned_checklist, "orphan", "v1", _skill_md("orphan")
        )
        skills = load_skills(pinned_checklist)
        pins = load_version_manifest(pinned_checklist)
        with pytest.raises(ValueError, match=r"orphan"):
            validate_version_manifest(skills, pins, pinned_checklist)

    def test_a_missing_pin_names_the_skill_and_the_file(self, pinned_checklist):
        (pinned_checklist / VERSION_MANIFEST_FILENAME).write_text(
            _manifest("toy-checklist", {"leaf": "v1"}), encoding="utf-8"
        )
        skills = load_skills(pinned_checklist)
        pins = load_version_manifest(pinned_checklist)
        with pytest.raises(ValueError) as excinfo:
            validate_version_manifest(skills, pins, pinned_checklist)
        message = str(excinfo.value)
        assert "shared" in message
        assert VERSION_MANIFEST_FILENAME in message

    def test_an_orphan_pin_is_rejected(self, pinned_checklist):
        (pinned_checklist / VERSION_MANIFEST_FILENAME).write_text(
            _manifest(
                "toy-checklist",
                {"leaf": "v1", "shared": "v1", "removed": "v1"},
            ),
            encoding="utf-8",
        )
        skills = load_skills(pinned_checklist)
        pins = load_version_manifest(pinned_checklist)
        with pytest.raises(ValueError, match=r"removed"):
            validate_version_manifest(skills, pins, pinned_checklist)

    def test_a_non_existent_version_lists_what_is_available(
        self, pinned_checklist
    ):
        (pinned_checklist / VERSION_MANIFEST_FILENAME).write_text(
            _manifest("toy-checklist", {"leaf": "v7", "shared": "v1"}),
            encoding="utf-8",
        )
        skills = load_skills(pinned_checklist)
        pins = load_version_manifest(pinned_checklist)
        with pytest.raises(ValueError) as excinfo:
            validate_version_manifest(skills, pins, pinned_checklist)
        message = str(excinfo.value)
        assert "v7" in message and "v1" in message

    def test_a_manifest_for_another_checklist_is_refused(self, pinned_checklist):
        (pinned_checklist / VERSION_MANIFEST_FILENAME).write_text(
            _manifest("other-checklist", {"leaf": "v1", "shared": "v1"}),
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match=r"other-checklist"):
            load_version_manifest(pinned_checklist)

    def test_unparseable_yaml_names_the_file(self, pinned_checklist):
        (pinned_checklist / VERSION_MANIFEST_FILENAME).write_text(
            "skills:\n  leaf: [v1\n", encoding="utf-8"
        )
        with pytest.raises(ValueError, match=VERSION_MANIFEST_FILENAME):
            load_version_manifest(pinned_checklist)

    def test_a_missing_manifest_is_reported_as_missing(self, tmp_path: Path):
        empty = tmp_path / "bare"
        empty.mkdir()
        with pytest.raises(FileNotFoundError, match=VERSION_MANIFEST_FILENAME):
            load_version_manifest(empty)

    def test_pins_are_used_by_assembly_when_a_manifest_exists(
        self, pinned_checklist
    ):
        assert checklist_pins(pinned_checklist) == {
            "leaf": "v1", "shared": "v1"
        }

    def test_assembly_without_a_manifest_falls_back_audibly(
        self, tmp_path: Path, caplog
    ):
        bare = tmp_path / "bare"
        _write_skill(bare, "leaf", "v1", _skill_md("leaf"))
        with caplog.at_level("WARNING"):
            assert checklist_pins(bare) is None
        assert any(
            VERSION_MANIFEST_FILENAME in r.getMessage()
            for r in caplog.records
        )


class TestModelDefaults:
    def _write(self, checklist: Path, text: str) -> None:
        (checklist / MODEL_DEFAULTS_FILENAME).write_text(text, "utf-8")

    def test_defaults_are_provider_neutral(self, pinned_checklist):
        self._write(
            pinned_checklist,
            "models:\n  openai: gpt-5-mini\n  claude-sdk: sonnet\n"
            "session:\n  max_turns: 24\n",
        )
        defaults = load_model_defaults(pinned_checklist)
        assert defaults.model_for("openai") == "gpt-5-mini"
        assert defaults.model_for("claude-sdk") == "sonnet"
        assert defaults.session == {"max_turns": 24}

    def test_an_unknown_provider_has_no_default(self, pinned_checklist):
        self._write(pinned_checklist, "models:\n  openai: gpt-5-mini\n")
        assert load_model_defaults(pinned_checklist).model_for("zeta") is None

    def test_a_missing_file_is_empty_defaults(self, pinned_checklist):
        defaults = load_model_defaults(pinned_checklist)
        assert defaults.session == {} and defaults.model_for("openai") is None

    def test_the_file_may_not_touch_the_permission_profile(
        self, pinned_checklist
    ):
        """A warning in a log is easy to miss; a file a person edits should
        refuse at the point of editing."""
        self._write(
            pinned_checklist,
            "session:\n  permission_mode: bypassPermissions\n",
        )
        with pytest.raises(ValueError) as excinfo:
            load_model_defaults(pinned_checklist)
        assert "permission_mode" in str(excinfo.value)
        assert MODEL_DEFAULTS_FILENAME in str(excinfo.value)

    def test_models_must_map_names_to_strings(self, pinned_checklist):
        self._write(pinned_checklist, "models:\n  openai:\n    - a\n    - b\n")
        with pytest.raises(ValueError, match=r"models"):
            load_model_defaults(pinned_checklist)


class TestSkillSet:
    def test_the_digest_is_stable_and_order_independent(self, pinned_checklist):
        skills = load_skills(pinned_checklist)
        a = resolve_skill_set(skills, {"leaf": "v1", "shared": "v1"})
        b = resolve_skill_set(skills, {"shared": "v1", "leaf": "v1"})
        assert a.digest == b.digest

    def test_the_digest_changes_when_a_skill_body_changes(self, pinned_checklist):
        skills = load_skills(pinned_checklist)
        before = resolve_skill_set(skills, {"leaf": "v1", "shared": "v1"})
        path = pinned_checklist / "shared" / "v1" / SKILL_FILENAME
        path.write_text(path.read_text() + "\nOne more rule.\n", encoding="utf-8")
        after = resolve_skill_set(
            load_skills(pinned_checklist), {"leaf": "v1", "shared": "v1"}
        )
        assert before.digest != after.digest

    def test_the_digest_changes_with_the_pinned_version(self, pinned_checklist):
        _write_skill(
            pinned_checklist, "shared", "v2",
            _skill_md("shared", produces=("facts",), body="# shared\n\nDo it differently.\n"),
        )
        skills = load_skills(pinned_checklist)
        one = resolve_skill_set(skills, {"leaf": "v1", "shared": "v1"})
        two = resolve_skill_set(skills, {"leaf": "v1", "shared": "v2"})
        assert one.digest != two.digest

    def test_entries_carry_name_version_and_content_hash(self, pinned_checklist):
        skills = load_skills(pinned_checklist)
        entries = resolve_skill_set(
            skills, {"leaf": "v1", "shared": "v1"}
        ).entries
        assert [e.name for e in entries] == ["leaf", "shared"]
        assert all(len(e.content_hash) == 64 for e in entries)
        assert all(e.version == "v1" for e in entries)

    def test_a_set_is_labelled_by_what_differs_from_the_manifest(
        self, pinned_checklist
    ):
        _write_skill(
            pinned_checklist, "shared", "v2",
            _skill_md("shared", produces=("facts",), body="# shared\n\nDifferently.\n"),
        )
        skills = load_skills(pinned_checklist)
        baseline = {"leaf": "v1", "shared": "v1"}
        assert resolve_skill_set(skills, baseline).label(baseline) == "pinned"
        varied = resolve_skill_set(skills, {"leaf": "v1", "shared": "v2"})
        assert varied.label(baseline) == "shared@v2"


class TestSkillSetExpansion:
    @pytest.fixture
    def two_versions(self, pinned_checklist: Path) -> Path:
        _write_skill(
            pinned_checklist, "shared", "v2",
            _skill_md("shared", produces=("facts",), body="# shared\n\nDifferently.\n"),
        )
        return pinned_checklist

    def test_unpinning_one_skill_yields_one_set_per_version(self, two_versions):
        skills = load_skills(two_versions)
        sets = expand_skill_sets(
            skills, {"leaf": "v1", "shared": "v1"}, {"shared": None}
        )
        assert [s.pins["shared"] for s in sets] == ["v1", "v2"]
        assert all(s.pins["leaf"] == "v1" for s in sets)

    def test_a_version_subset_is_honoured(self, two_versions):
        skills = load_skills(two_versions)
        sets = expand_skill_sets(
            skills, {"leaf": "v1", "shared": "v1"}, {"shared": ("v2",)}
        )
        assert [s.pins["shared"] for s in sets] == ["v2"]

    def test_multiple_unpinned_skills_are_permitted(self, two_versions):
        _write_skill(
            two_versions, "leaf", "v2",
            _skill_md("leaf", requires=("shared",), produces=("leaf",),
                      body="# leaf\n\nUse the `shared` skill with the `Skill` tool.\n"),
        )
        skills = load_skills(two_versions)
        sets = expand_skill_sets(
            skills, {"leaf": "v1", "shared": "v1"},
            {"shared": None, "leaf": None},
        )
        assert len(sets) == 4
        assert len({s.digest for s in sets}) == 4

    def test_unpinning_an_unknown_skill_is_refused(self, two_versions):
        skills = load_skills(two_versions)
        with pytest.raises(ValueError, match=r"nosuch"):
            expand_skill_sets(
                skills, {"leaf": "v1", "shared": "v1"}, {"nosuch": None}
            )

    def test_unpinning_to_a_non_existent_version_is_refused(self, two_versions):
        skills = load_skills(two_versions)
        with pytest.raises(ValueError, match=r"v9"):
            expand_skill_sets(
                skills, {"leaf": "v1", "shared": "v1"}, {"shared": ("v9",)}
            )

    def test_crossing_the_threshold_warns_rather_than_refuses(
        self, two_versions, caplog
    ):
        _write_skill(
            two_versions, "leaf", "v2",
            _skill_md("leaf", requires=("shared",), produces=("leaf",),
                      body="# leaf\n\nUse the `shared` skill with the `Skill` tool.\n"),
        )
        skills = load_skills(two_versions)
        with caplog.at_level("WARNING"):
            sets = expand_skill_sets(
                skills, {"leaf": "v1", "shared": "v1"},
                {"shared": None, "leaf": None},
                warn_above=2,
            )
        assert len(sets) == 4, "the expansion still happened"
        assert any("4" in str(r.getMessage()) for r in caplog.records)

    def test_no_unpinning_is_the_manifest_alone(self, two_versions):
        skills = load_skills(two_versions)
        sets = expand_skill_sets(skills, {"leaf": "v1", "shared": "v1"}, {})
        assert len(sets) == 1 and sets[0].pins == {"leaf": "v1", "shared": "v1"}


class TestGeneratedGraphViews:
    def test_write_creates_both_views(self, pinned_checklist, monkeypatch):
        monkeypatch.setattr(config, "CHECKLIST_DIR", pinned_checklist.parent)
        assert cli.main(["graph", "toy-checklist", "--write"]) == 0
        assert (pinned_checklist / DAG_FILENAME).is_file()
        assert (pinned_checklist / GENERATED_README_FILENAME).is_file()

    def test_generation_is_deterministic(self, pinned_checklist, monkeypatch):
        monkeypatch.setattr(config, "CHECKLIST_DIR", pinned_checklist.parent)
        cli.main(["graph", "toy-checklist", "--write"])
        first = (pinned_checklist / DAG_FILENAME).read_bytes()
        readme = (pinned_checklist / GENERATED_README_FILENAME).read_bytes()
        cli.main(["graph", "toy-checklist", "--write"])
        assert (pinned_checklist / DAG_FILENAME).read_bytes() == first
        assert (
            pinned_checklist / GENERATED_README_FILENAME
        ).read_bytes() == readme

    def test_the_views_carry_nothing_environmental(self, pinned_checklist):
        """Writing the file twice a second apart cannot catch a timestamp or
        an absolute path; both make the drift check report noise on someone
        else's machine, and a drift check people learn to ignore is worse
        than none."""
        import datetime

        year = str(datetime.date.today().year)
        for text in (
            render_dag("toy-checklist", pinned_checklist),
            render_readme("toy-checklist", pinned_checklist),
        ):
            assert str(pinned_checklist) not in text
            assert str(pinned_checklist.parent) not in text
            assert year not in text

    def test_the_drift_check_passes_right_after_writing(
        self, pinned_checklist, monkeypatch
    ):
        monkeypatch.setattr(config, "CHECKLIST_DIR", pinned_checklist.parent)
        cli.main(["graph", "toy-checklist", "--write"])
        assert cli.main(["graph", "toy-checklist"]) == 0

    def test_the_drift_check_fails_when_a_skill_changes(
        self, pinned_checklist, monkeypatch, capsys
    ):
        monkeypatch.setattr(config, "CHECKLIST_DIR", pinned_checklist.parent)
        cli.main(["graph", "toy-checklist", "--write"])
        path = pinned_checklist / "shared" / "v1" / SKILL_FILENAME
        path.write_text(
            path.read_text().replace(
                "Does one thing, described unambiguously.",
                "Now does a different thing entirely.",
            ),
            encoding="utf-8",
        )
        assert cli.main(["graph", "toy-checklist"]) == 1
        out = capsys.readouterr()
        assert "--write" in (out.out + out.err)

    def test_the_drift_check_fails_when_the_views_are_hand_edited(
        self, pinned_checklist, monkeypatch
    ):
        monkeypatch.setattr(config, "CHECKLIST_DIR", pinned_checklist.parent)
        cli.main(["graph", "toy-checklist", "--write"])
        dag = pinned_checklist / DAG_FILENAME
        dag.write_text(dag.read_text() + "\nhand_edited: true\n", encoding="utf-8")
        assert cli.main(["graph", "toy-checklist"]) == 1

    def test_the_dag_renders_the_calls_the_prose_makes(self, pinned_checklist):
        rendered = yaml.safe_load(render_dag("toy-checklist", pinned_checklist))
        by_name = {s["name"]: s for s in rendered["skills"]}
        assert by_name["leaf"]["calls"] == ["shared"]
        assert by_name["shared"]["calls"] == []

    def test_the_dag_marks_which_skills_are_checks(self, pinned_checklist):
        rendered = yaml.safe_load(render_dag("toy-checklist", pinned_checklist))
        by_name = {s["name"]: s for s in rendered["skills"]}
        assert by_name["leaf"]["kind"] == "check"
        assert by_name["shared"]["kind"] == "shared"

    def test_the_dag_records_the_skill_set_it_describes(self, pinned_checklist):
        rendered = yaml.safe_load(render_dag("toy-checklist", pinned_checklist))
        skills = load_skills(pinned_checklist)
        expected = resolve_skill_set(
            skills, load_version_manifest(pinned_checklist)
        )
        assert rendered["skill_set"] == expected.digest

    def test_the_views_say_they_are_generated(self, pinned_checklist):
        dag = render_dag("toy-checklist", pinned_checklist)
        readme = render_readme("toy-checklist", pinned_checklist)
        for text in (dag, readme):
            assert "generated" in text.lower()
            assert "graph" in text

    def test_graph_never_touches_examples_or_sessions(
        self, pinned_checklist, monkeypatch
    ):
        """It must stay fast enough to run in CI on every checklist."""
        monkeypatch.setattr(config, "CHECKLIST_DIR", pinned_checklist.parent)
        # Patched on the module that defines them, not on cli: cli no
        # longer re-exports either, and `graph` reaching one through any
        # other caller is just as much a failure.
        monkeypatch.setattr(
            agentic_runtime, "assemble_runtime",
            lambda *a, **k: pytest.fail("graph assembled a runtime"),
        )
        monkeypatch.setattr(
            agentic_runtime, "_resolve_example_input_dir",
            lambda *a, **k: pytest.fail("graph read an example"),
        )
        cli.main(["graph", "toy-checklist", "--write"])
        assert cli.main(["graph", "toy-checklist"]) == 0


class TestGraphFailureMessages:
    """Gate 6C: a stranger hitting each failure must learn what to fix."""

    def _graph(self, checklist: Path, monkeypatch, capsys):
        monkeypatch.setattr(config, "CHECKLIST_DIR", checklist.parent)
        code = cli.main(["graph", checklist.name])
        captured = capsys.readouterr()
        return code, captured.out + captured.err

    def test_invalid_frontmatter(self, pinned_checklist, monkeypatch, capsys, caplog):
        path = pinned_checklist / "shared" / "v1" / SKILL_FILENAME
        path.write_text("no frontmatter at all\n", encoding="utf-8")
        with caplog.at_level("ERROR"):
            code, out = self._graph(pinned_checklist, monkeypatch, capsys)
        text = out + caplog.text
        assert code == 1
        assert str(path) in text and "frontmatter" in text

    def test_duplicate_names(self, pinned_checklist, monkeypatch, capsys, caplog):
        _write_skill(
            pinned_checklist, "shared-copy", "v1", _skill_md("shared", produces=("facts",))
        )
        with caplog.at_level("ERROR"):
            code, out = self._graph(pinned_checklist, monkeypatch, capsys)
        text = out + caplog.text
        assert code == 1
        assert "declare skill" in text and "shared" in text

    def test_unknown_requirement(self, pinned_checklist, monkeypatch, capsys, caplog):
        _write_skill(
            pinned_checklist, "leaf", "v1",
            _skill_md("leaf", requires=("ghost",), produces=("leaf",)),
        )
        with caplog.at_level("ERROR"):
            code, out = self._graph(pinned_checklist, monkeypatch, capsys)
        text = out + caplog.text
        assert code == 1 and "ghost" in text

    def test_a_cycle(self, pinned_checklist, monkeypatch, capsys, caplog):
        _write_skill(
            pinned_checklist, "shared", "v1",
            _skill_md("shared", requires=("leaf",), produces=("facts",)),
        )
        with caplog.at_level("ERROR"):
            code, out = self._graph(pinned_checklist, monkeypatch, capsys)
        text = out + caplog.text
        assert code == 1 and "cycle" in text.lower()

    def test_a_missing_pin(self, pinned_checklist, monkeypatch, capsys, caplog):
        (pinned_checklist / VERSION_MANIFEST_FILENAME).write_text(
            _manifest("toy-checklist", {"leaf": "v1"}), encoding="utf-8"
        )
        with caplog.at_level("ERROR"):
            code, out = self._graph(pinned_checklist, monkeypatch, capsys)
        text = out + caplog.text
        assert code == 1
        assert "shared" in text and VERSION_MANIFEST_FILENAME in text

    def test_an_orphan_pin(self, pinned_checklist, monkeypatch, capsys, caplog):
        (pinned_checklist / VERSION_MANIFEST_FILENAME).write_text(
            _manifest("toy-checklist", {"leaf": "v1", "shared": "v1", "gone": "v1"}),
            encoding="utf-8",
        )
        with caplog.at_level("ERROR"):
            code, out = self._graph(pinned_checklist, monkeypatch, capsys)
        text = out + caplog.text
        assert code == 1 and "gone" in text

    def test_a_non_existent_version(self, pinned_checklist, monkeypatch, capsys, caplog):
        (pinned_checklist / VERSION_MANIFEST_FILENAME).write_text(
            _manifest("toy-checklist", {"leaf": "v4", "shared": "v1"}),
            encoding="utf-8",
        )
        with caplog.at_level("ERROR"):
            code, out = self._graph(pinned_checklist, monkeypatch, capsys)
        text = out + caplog.text
        assert code == 1 and "v4" in text

    def test_a_missing_manifest(self, tmp_path: Path, monkeypatch, capsys, caplog):
        bare = tmp_path / "bare-checklist"
        _write_skill(bare, "leaf", "v1", _skill_md("leaf"))
        with caplog.at_level("ERROR"):
            code, out = self._graph(bare, monkeypatch, capsys)
        text = out + caplog.text
        assert code == 1 and VERSION_MANIFEST_FILENAME in text


class TestTheRealChecklistIsPinned:
    def test_every_real_skill_is_pinned(self):
        skills = load_skills(FIG_CHECKLIST_DIR)
        pins = load_version_manifest(FIG_CHECKLIST_DIR)
        validate_version_manifest(skills, pins, FIG_CHECKLIST_DIR)
        assert set(pins) == set(skills)

    def test_the_committed_views_are_in_sync(self, capsys):
        assert cli.main(["graph", "fig-checklist"]) == 0, (
            "dag.yaml/README.md are stale; run "
            "`python -m soda_mmqc.cli graph fig-checklist --write`"
        )

    def test_the_real_model_defaults_load(self):
        defaults = load_model_defaults(FIG_CHECKLIST_DIR)
        assert defaults.model_for("openai")

    def test_the_dag_edges_match_the_prose(self):
        """Gate 6B's property, as a test: every rendered edge is a call
        someone wrote, and no written call is missing."""
        rendered = yaml.safe_load(
            (FIG_CHECKLIST_DIR / DAG_FILENAME).read_text(encoding="utf-8")
        )
        skills = load_skills(FIG_CHECKLIST_DIR)
        known = sorted(skills)
        pins = load_version_manifest(FIG_CHECKLIST_DIR)
        for entry in rendered["skills"]:
            skill = skills[entry["name"]][pins[entry["name"]]]
            assert entry["calls"] == sorted(invoked_skills(skill, known))


@requires_subpanel_figure
class TestCacheKeyIsTheSkillSet:
    def test_the_key_carries_the_skill_set_digest(self, assembled):
        options = session_options(assembled)
        skills = load_skills(FIG_CHECKLIST_DIR)
        one = resolve_skill_set(skills, checklist_pins(FIG_CHECKLIST_DIR))
        key = session_cache_key(
            assembled, model="m", options=options, skill_set=one
        )
        assert key == session_cache_key(
            assembled, model="m", options=options, skill_set=one
        )

    def test_two_skill_sets_do_not_share_a_cache_entry(self, assembled):
        options = session_options(assembled)
        skills = load_skills(FIG_CHECKLIST_DIR)
        pins = dict(checklist_pins(FIG_CHECKLIST_DIR))
        one = resolve_skill_set(skills, pins)
        other = dataclasses.replace(
            one,
            entries=tuple(
                dataclasses.replace(e, version="v9") if e.name == SHARED_SKILL else e
                for e in one.entries
            ),
        )
        assert session_cache_key(
            assembled, model="m", options=options, skill_set=one
        ) != session_cache_key(
            assembled, model="m", options=options, skill_set=other
        )


# ---------------------------------------------------------------------------
# Milestone 6, round two: three defects an independent review found
# ---------------------------------------------------------------------------
#
# All three were invisible to a green 296-test suite, and all three are in the
# seam Milestone 6 opened: once more than one version of a skill can exist,
# every place that resolved "the" version by convention is a latent bug.


@requires_subpanel_figure
class TestHopsAreComparedAgainstTheVersionThatRan:
    """A `v1` session compared against `v2`'s declared hops invents both
    missing and extra hops out of nothing -- in exactly the unpinned
    comparison the diagnostic exists to inform."""

    @pytest.fixture
    def two_versions(self, tmp_path: Path):
        checklist = _copy_pilot_skills(tmp_path / "fig-checklist")
        # v2 of the pilot leaf declares (and asks for) nothing.
        _write_skill(
            checklist, PILOT_LEAF, "v2",
            _skill_md(PILOT_LEAF, produces=(PILOT_LEAF,),
                      body=f"# {PILOT_LEAF}\n\nDo it all yourself.\n"),
        )
        (checklist / VERSION_MANIFEST_FILENAME).write_text(
            _manifest(
                "fig-checklist",
                {name: "v1" for name in load_skills(checklist)},
            ),
            encoding="utf-8",
        )
        return checklist

    def test_the_pinned_version_is_used_not_the_highest(self, two_versions):
        hops = compare_declared_and_observed(
            two_versions, PILOT_LEAF, [SHARED_SKILL], pins={PILOT_LEAF: "v1"}
        )
        assert hops["declared"] == [SHARED_SKILL]
        assert hops["declared_not_observed"] == []
        assert hops["observed_not_declared"] == []

    def test_an_unpinned_variant_is_compared_against_itself(self, two_versions):
        hops = compare_declared_and_observed(
            two_versions, PILOT_LEAF, [SHARED_SKILL], pins={PILOT_LEAF: "v2"}
        )
        assert hops["declared"] == []
        # v2 asks for nothing and the agent went anyway -- an undeclared hop,
        # which is a real observation, not an artifact of the wrong version.
        assert hops["observed_not_declared"] == [SHARED_SKILL]

    def test_without_pins_the_manifest_decides_not_the_highest_version(
        self, two_versions
    ):
        hops = compare_declared_and_observed(
            two_versions, PILOT_LEAF, [SHARED_SKILL]
        )
        assert hops["declared"] == [SHARED_SKILL], (
            "fell back to the highest version instead of the manifest pin"
        )


class TestTheTurnCeilingActuallyGoverns:
    """`max_turns` parsed, validated, documented in two files and inert is
    worse than not offering a cost ceiling at all."""

    def _client(self, calls):
        """A model that calls one harmless tool every turn, so the loop is
        bounded only by the ceiling and never by the answer-in-chat nudge."""
        from soda_mmqc.agentic.openai_driver import make_openai_client

        class _Call:
            id = "c1"
            type = "function"

            class function:
                name = "Skill"
                arguments = '{"name": "a"}'

        class _Message:
            tool_calls = [_Call()]
            content = None
            role = "assistant"

        class _Choice:
            message = _Message()

        class _Response:
            choices = [_Choice()]

        class _Completions:
            def create(self, **kwargs):
                calls.append(kwargs)
                return _Response()

        class _Chat:
            completions = _Completions()

        class _Client:
            chat = _Chat()

        return make_openai_client, _Client

    def test_the_session_option_overrides_the_module_ceiling(
        self, tmp_path: Path, monkeypatch
    ):
        import soda_mmqc.agentic.openai_driver as ao

        calls = []
        make_openai_client, _Client = self._client(calls)
        monkeypatch.setitem(
            __import__("sys").modules, "openai",
            type("m", (), {"OpenAI": _Client}),
        )
        tools = ao.RuntimeTools(tmp_path, tmp_path)
        client = make_openai_client(
            {"a": "body"}, {"a": "desc"}, tools, "orientation", model="m"
        )
        asyncio.run(_drain(client([{"kind": "text", "text": "go"}], {"max_turns": 3})))
        assert len(calls) == 3, (
            f"ran {len(calls)} turns; the ceiling from model-defaults.yaml "
            "was ignored"
        )

    def test_the_module_ceiling_is_the_fallback(
        self, tmp_path: Path, monkeypatch
    ):
        import soda_mmqc.agentic.openai_driver as ao

        calls = []
        make_openai_client, _Client = self._client(calls)
        monkeypatch.setitem(
            __import__("sys").modules, "openai",
            type("m", (), {"OpenAI": _Client}),
        )
        tools = ao.RuntimeTools(tmp_path, tmp_path)
        client = make_openai_client(
            {"a": "body"}, {"a": "desc"}, tools, "orientation",
            model="m", max_turns=2,
        )
        asyncio.run(_drain(client([{"kind": "text", "text": "go"}], {})))
        assert len(calls) == 2

    def test_the_real_checklist_ceiling_reaches_the_session_options(
        self, tmp_path: Path
    ):
        """End to end: the file says 24, the options carry 24."""
        defaults = load_model_defaults(FIG_CHECKLIST_DIR)
        assert defaults.session["max_turns"] == 24


async def _drain(agen):
    async for _ in agen:
        pass


@requires_subpanel_figure
class TestUnpinnedRunsDoNotOverwriteTheBaseline:
    """`--unpin X --versions v2` expands to exactly *one* SkillSet. Choosing
    the output directory by set count rather than by label wrote that variant
    straight over the pinned run's predictions."""

    @pytest.fixture
    def stub_session(self, monkeypatch):
        """Run the real `run_check_live` loop with the provider faked out."""
        seen = []
        real = _run_agent_session

        async def fake_session(layout, *, versions, approver, options, client):
            seen.append(dict(versions))
            return await real(
                layout,
                versions=versions,
                approver=approver,
                options=options,
                client=_fake_client([], writes=_valid_prediction()),
            )

        monkeypatch.setattr(runner, "_run_agent_session", fake_session)
        monkeypatch.setattr(runner, "_openai_session_client", lambda l, m: None)
        return seen

    def test_a_single_variant_gets_its_own_directory(
        self, tmp_path: Path, stub_session, monkeypatch
    ):
        checklist_dir = CHECKLIST_DIR / "fig-checklist"
        v2 = checklist_dir / PILOT_LEAF / "v2"
        v2.mkdir(parents=True)
        (v2 / SKILL_FILENAME).write_text(
            (checklist_dir / PILOT_LEAF / "v1" / SKILL_FILENAME).read_text(),
            encoding="utf-8",
        )
        try:
            out = tmp_path / "preds"
            run_check_live(
                "fig-checklist", PILOT_LEAF,
                output=out, examples=[SUBPANEL_FIGURE],
                unpin={PILOT_LEAF: ("v2",)},
            )
            assert (out / f"{PILOT_LEAF}@v2" / "rep-00" / SUBPANEL_FIGURE
                    / PREDICTION_FILENAME).is_file()
            assert not (out / "pinned").exists(), (
                "a variant-only run wrote into the baseline arm"
            )
        finally:
            shutil.rmtree(v2)

    def test_each_prediction_records_the_skill_set_that_made_it(
        self, tmp_path: Path, stub_session
    ):
        """A directory name is not evidence."""
        out = tmp_path / "preds"
        run_check_live(
            "fig-checklist", PILOT_LEAF, output=out, examples=[SUBPANEL_FIGURE]
        )
        recorded = json.loads(
            (out / "pinned" / "rep-00" / SUBPANEL_FIGURE
             / INTERMEDIATES_DIRNAME / SKILL_SET_FILENAME).read_text()
        )
        expected = resolve_skill_set(
            load_skills(CHECKLIST_DIR / "fig-checklist"),
            checklist_pins(CHECKLIST_DIR / "fig-checklist"),
        )
        assert recorded["digest"] == expected.digest
        assert {s["name"] for s in recorded["skills"]} == set(expected.pins)

    def test_the_session_runs_the_pinned_version(
        self, tmp_path: Path, stub_session
    ):
        run_check_live(
            "fig-checklist", PILOT_LEAF,
            output=tmp_path / "p", examples=[SUBPANEL_FIGURE],
        )
        assert stub_session[0][SHARED_SKILL] == "v1"


@requires_subpanel_figure
class TestASessionNeedsNoFilesystem:
    def test_an_invoked_skill_needs_no_artifact_on_disk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        """A fired shared skill used to have to leave a file behind.

        It cannot any more -- the session has no write tool -- and it does not
        need to: `Skill(x)` loads x's instructions into the session already
        running, so what x contributes is in context, not on disk. The
        question that check protected, whether a declared skill actually
        fired, is answered by the hop trace, which reads the session's own
        tool calls.
        """
        class _Recorder:
            invoked = [SHARED_SKILL]
            entries = []

        class _Audit:
            path = tmp_path / "missing-audit.json"
            session_info = {}
            usage = {}

            def summary(self):
                return "Skill (allow) x1"

        async def fake_run_agent_session(
            layout, *, versions, approver, options, client
        ):
            return _valid_prediction(), _Recorder(), _Audit()

        monkeypatch.setattr(runner, "_run_agent_session", fake_run_agent_session)
        monkeypatch.setattr(runner, "_openai_session_client", lambda l, m: None)

        _, report = run_check_live(
            "fig-checklist",
            PILOT_LEAF,
            output=tmp_path / "preds",
            examples=[SUBPANEL_FIGURE],
        )
        assert report[0]["status"] == "ok"
        assert SHARED_SKILL in (report[0].get("hops") or {}).get("observed", [])

class TestNoRunIsDeniedOrSeeded:
    """What `--all-checks` used to do, asserted as something that cannot return.

    The cross-check cache ran a shared skill once per example, planted its
    output into later runtimes, and denied those sessions the `Skill` tool so
    they could not rerun it. That made one check's behaviour depend on whether
    a different check had succeeded, and it erased the signal the experiments
    exist to detect: whether a shared skill is reached, and how it is used,
    may differ depending on which leaf is the entry point.

    Deleting the apparatus without a test would leave nothing to notice it
    coming back.
    """

    def test_a_skill_call_can_never_be_denied_by_the_hook(self, tmp_path: Path):
        """One session per (example, check): nothing suppresses a hop."""
        audit = ToolAuditLog(tmp_path / "audit.json")
        hook = make_pretooluse_hook(audit)

        async def call():
            return await hook(
                {
                    "tool_name": "Skill",
                    "tool_input": {"name": SHARED_SKILL},
                    "tool_use_id": "s1",
                },
                "s1",
                None,
            )

        result = asyncio.run(call())
        decision = result["hookSpecificOutput"]["permissionDecision"]
        assert decision == "allow"
        assert audit.entries[0]["decision"] == "allow"

    def test_the_hook_takes_no_denial_set(self):
        """The parameter is the apparatus; without it there is nothing to pass."""
        import inspect

        params = inspect.signature(make_pretooluse_hook).parameters
        assert "denied_shared_skills" not in params
        assert "denied_shared_skills" not in inspect.signature(
            _run_agent_session
        ).parameters

    def test_the_runner_cannot_seed_a_runtime(self):
        """No artifact reaches a session that the session did not produce."""
        import inspect

        params = inspect.signature(run_check_live).parameters
        assert "seed_intermediates" not in params
        assert "shared_skill_denials" not in params

    def test_there_is_no_whole_checklist_run(self):
        """Running every check is a loop the caller writes, not a harness feature."""
        assert not hasattr(cli, "run_checklist_live")
        # argparse rejects the flag outright, which is the clearest possible
        # statement that the feature is gone.
        with pytest.raises(SystemExit) as exc:
            cli.main(["run", "fig-checklist", "--all-checks", "--mock"])
        assert exc.value.code != 0


class TestTheContentIsPushedNotPulled:
    """The example's content travels with the request, not behind a Read.

    Everything figure-shaped in the harness followed from pull: the harness
    had to discover which staged file was the figure, name it, and then
    refuse a prediction from a session that never fetched it. Pushing the
    content deletes the discovery, the naming and the refusal together.
    """

    def test_the_layout_carries_the_examples_parts(self, assembled):
        kinds = [part["kind"] for part in assembled.input_parts]
        assert kinds == ["text", "image"]

    def test_image_parts_are_rebased_onto_the_runtime(self, assembled):
        image = next(p for p in assembled.input_parts if p["kind"] == "image")
        assert image["path"].startswith(f"{AGENTIC_INPUT_SUBDIR}/")
        assert (assembled.root / image["path"]).is_file()

    def test_the_session_message_leads_with_the_instruction(self, assembled):
        message = _session_message(assembled)
        assert message[0]["kind"] == "text"
        assert PILOT_LEAF in message[0]["text"]
        assert "figure" not in message[0]["text"].lower()
        assert message[1:] == list(assembled.input_parts)

    def test_the_manifest_names_supporting_files_only(self, assembled):
        manifest = json.loads(
            (
                assembled.input_root / AGENTIC_INPUT_MANIFEST_FILENAME
            ).read_text(encoding="utf-8")
        )
        assert set(manifest) == {"source_data"}
        for entry in manifest["source_data"]:
            assert (assembled.root / entry).is_file()

    def test_the_read_gate_is_gone(self):
        """An input in the opening message cannot go unread."""
        assert not hasattr(cli, "_assert_the_session_read_the_figure")
        assert not hasattr(cli, "_resolve_staged_inputs")
        assert not hasattr(cli, "AGENTIC_IMAGE_EXTENSIONS")


WORD_EXAMPLE = "10.1038_embor.2009.217"

requires_word_example = pytest.mark.skipif(
    not (EXAMPLES_DIR / WORD_EXAMPLE).is_dir(),
    reason=f"example store has no {WORD_EXAMPLE}",
)


@requires_word_example
class TestANonFigureExampleAssembles:
    """The staging path must work for an example class with no image at all.

    Before this change `_resolve_staged_inputs` raised FileNotFoundError on
    any example without a known image extension, so `doc-checklist` could
    never have run agentically whatever its skills said.
    """

    @pytest.fixture
    def word_checklist(self, tmp_path, monkeypatch):
        """A minimal one-leaf checklist over a `word` benchmark."""
        root = tmp_path / "checklists"
        check_dir = root / "doc-pilot" / "section-order"
        (check_dir / "v1").mkdir(parents=True)
        (check_dir / "v1" / "SKILL.md").write_text(
            _skill_md("section-order"), encoding="utf-8"
        )
        (check_dir / "benchmark.json").write_text(
            json.dumps(
                {
                    "name": "section-order",
                    "example_class": "word",
                    "examples": [WORD_EXAMPLE],
                }
            ),
            encoding="utf-8",
        )
        (check_dir / "schema.json").write_text(
            json.dumps(
                {
                    "format": {
                        "type": "json_schema",
                        "name": "section-order",
                        "schema": {"type": "object", "properties": {}},
                    }
                }
            ),
            encoding="utf-8",
        )
        (check_dir / "eval-manifest.json").write_text(
            json.dumps({"checklist": "section-order", "fields": {}}),
            encoding="utf-8",
        )
        (root / "doc-pilot" / "version-manifest.yaml").write_text(
            "checklist: doc-pilot\nskills:\n  section-order: v1\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(config, "CHECKLIST_DIR", root)
        return root

    def _assemble(self, tmp_path):
        return assemble_runtime(
            "doc-pilot", "section-order", WORD_EXAMPLE,
            root=tmp_path / "runtime",
        )

    def test_a_word_example_assembles(self, word_checklist, tmp_path):
        layout = self._assemble(tmp_path)
        assert [p["kind"] for p in layout.input_parts] == ["text"]
        assert "<" in layout.input_parts[0]["text"]  # the HTML conversion

    def test_the_document_is_staged_but_not_offered_to_fetch(
        self, word_checklist, tmp_path
    ):
        """inputs.json lists what can be pulled and was not pushed.

        The .docx is staged like every other file of the example, but its
        content already arrived as a part, so nothing invites the session to
        open a document it cannot read.
        """
        layout = self._assemble(tmp_path)
        manifest = json.loads(
            (
                layout.input_root / AGENTIC_INPUT_MANIFEST_FILENAME
            ).read_text(encoding="utf-8")
        )
        assert manifest == {}
        assert list(layout.input_root.glob("*.docx"))

    def test_the_staged_copy_is_the_source_minus_its_gold(
        self, word_checklist, tmp_path
    ):
        """A copy, not a processed copy: the HTML conversion travels in the
        message and is never written here, and every file that is staged is
        staged byte for byte.

        The one exclusion is the answer key. This layout is recursive, so a
        document-level example's `content/` contains its figure
        sub-examples, each with its own `checks/`.
        """
        layout = self._assemble(tmp_path)
        source = EXAMPLES_DIR / WORD_EXAMPLE / "content"
        staged = sorted(
            p.relative_to(layout.input_root)
            for p in layout.input_root.rglob("*")
            if p.is_file() and p.name != AGENTIC_INPUT_MANIFEST_FILENAME
        )
        original = sorted(
            p.relative_to(source)
            for p in source.rglob("*")
            if p.is_file()
            and EXAMPLE_GOLD_SUBDIR not in p.relative_to(source).parts
        )
        assert staged == original
        for entry in original:
            assert (layout.input_root / entry).read_bytes() == (
                source / entry
            ).read_bytes()

    def test_no_gold_reaches_the_runtime(self, word_checklist, tmp_path):
        """18 expected_output.json files sit under this example's content/.

        Staging them would be a scored run that saw the answer key -- the
        exact failure `_assert_sealed` exists to refuse. It is asserted here
        directly rather than trusted to the alarm downstream.
        """
        layout = self._assemble(tmp_path)
        assert not list(layout.input_root.rglob("expected_output.json"))
        assert not [
            p for p in layout.input_root.rglob("*")
            if p.name == EXAMPLE_GOLD_SUBDIR
        ]


@requires_subpanel_figure
class TestEveryAxisIsADirectory:
    """One shape for every run: <root>/<arm>/rep-NN/<example>/.

    The baseline arm used to write flat while variants wrote into their own
    directory, so one run's output had two shapes and pointing `score` at the
    root scored the baseline alone -- plausibly, and silently.
    """

    @pytest.fixture
    def stub_session(self, monkeypatch):
        """Run the real `run_check_live` loop with the provider faked out."""
        seen = []
        real = _run_agent_session

        async def fake_session(layout, *, versions, approver, options, client):
            seen.append(dict(versions))
            return await real(
                layout,
                versions=versions,
                approver=approver,
                options=options,
                client=_fake_client([], writes=_valid_prediction()),
            )

        monkeypatch.setattr(runner, "_run_agent_session", fake_session)
        monkeypatch.setattr(runner, "_openai_session_client", lambda l, m: None)
        return seen

    def test_a_plain_run_still_has_both_levels(self, tmp_path: Path, stub_session):
        out = tmp_path / "preds"
        run_check_live(
            "fig-checklist", PILOT_LEAF, output=out, examples=[SUBPANEL_FIGURE],
        )
        assert (
            out / "pinned" / "rep-00" / SUBPANEL_FIGURE / PREDICTION_FILENAME
        ).is_file()
        assert not (out / SUBPANEL_FIGURE).exists(), (
            "the baseline arm must not write flat: that is the special case "
            "this layout removes"
        )

    def test_replicates_sit_under_the_arm(self, tmp_path: Path, stub_session):
        """An arm is not a replicate: arm outermost, samples within it."""
        out = tmp_path / "preds"
        run_check_live(
            "fig-checklist", PILOT_LEAF, output=out,
            examples=[SUBPANEL_FIGURE], replicates=3,
        )
        for i in range(3):
            assert (
                out / "pinned" / f"rep-{i:02d}" / SUBPANEL_FIGURE
                / PREDICTION_FILENAME
            ).is_file()

    def test_the_sidecar_records_arm_and_replicate(
        self, tmp_path: Path, stub_session
    ):
        """A directory name is not evidence -- the reason skill_set.json exists.

        A notebook reads this rather than parsing paths, so moving a tree
        cannot change what a prediction claims about itself.
        """
        out = tmp_path / "preds"
        run_check_live(
            "fig-checklist", PILOT_LEAF, output=out,
            examples=[SUBPANEL_FIGURE], replicates=2,
        )
        for i in range(2):
            sidecar = json.loads(
                (
                    out / "pinned" / f"rep-{i:02d}" / SUBPANEL_FIGURE
                    / INTERMEDIATES_DIRNAME / SKILL_SET_FILENAME
                ).read_text(encoding="utf-8")
            )
            assert sidecar["arm"] == "pinned"
            assert sidecar["replicate"] == i
            assert sidecar["digest"]

    def test_mock_writes_the_same_shape(self, tmp_path: Path):
        """No exceptions: a mock run is scored by the same command."""
        out = tmp_path / "preds"
        run_check_mock(
            "fig-checklist", PILOT_LEAF, output=out, examples=[SUBPANEL_FIGURE],
        )
        assert (
            out / "pinned" / "rep-00" / SUBPANEL_FIGURE / PREDICTION_FILENAME
        ).is_file()

    def test_zero_replicates_is_refused(self, tmp_path: Path):
        with pytest.raises(ValueError, match="at least one"):
            run_check_live(
                "fig-checklist", PILOT_LEAF, output=tmp_path / "p",
                examples=[SUBPANEL_FIGURE], replicates=0,
            )


class TestReplicatesOnTheCommandLine:
    def _capture(self, monkeypatch):
        """Patch where `main` looks it up.

        `cli` imports `run_check_live` by name, so `main` calls its own
        binding: redirecting `runner.run_check_live` would not reach it.
        """
        seen = {}

        def fake_run_check_live(checklist, check, **kwargs):
            seen.update(kwargs)
            return Path("/tmp/x"), []

        monkeypatch.setattr(cli, "run_check_live", fake_run_check_live)
        return seen

    def test_the_flag_reaches_the_runner(self, monkeypatch: pytest.MonkeyPatch):
        seen = self._capture(monkeypatch)
        cli.main([
            "run", "fig-checklist", "--check", PILOT_LEAF,
            "--example", SUBPANEL_FIGURE, "--replicates", "4",
        ])
        assert seen["replicates"] == 4

    def test_the_default_is_one(self, monkeypatch: pytest.MonkeyPatch):
        seen = self._capture(monkeypatch)
        cli.main([
            "run", "fig-checklist", "--check", PILOT_LEAF,
            "--example", SUBPANEL_FIGURE,
        ])
        assert seen["replicates"] == 1

    def test_the_session_count_is_announced(
        self, monkeypatch: pytest.MonkeyPatch, caplog
    ):
        """380 sessions from one command should not be a surprise."""
        self._capture(monkeypatch)
        with caplog.at_level("INFO"):
            cli.main([
                "run", "fig-checklist", "--check", PILOT_LEAF,
                "--example", SUBPANEL_FIGURE, "--replicates", "5",
            ])
        assert "5 replicate(s)" in caplog.text

    def test_zero_replicates_is_refused_at_the_cli(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        self._capture(monkeypatch)
        assert cli.main([
            "run", "fig-checklist", "--check", PILOT_LEAF,
            "--example", SUBPANEL_FIGURE, "--replicates", "0",
        ]) == 2


class TestPointingAtARunRoot:
    def test_the_error_names_the_leaves_it_found(self, tmp_path: Path):
        """Scoring a run root is the one mistake worth diagnosing."""
        root = tmp_path / "preds"
        example = SUBPANEL_FIGURE
        for arm in ("pinned", f"{PILOT_LEAF}@v2"):
            d = root / arm / "rep-00" / example
            d.mkdir(parents=True)
            (d / PREDICTION_FILENAME).write_text(
                json.dumps(_valid_prediction()), encoding="utf-8"
            )

        with pytest.raises(ValueError) as exc:
            score_check(
                "fig-checklist", PILOT_LEAF, root, save=False,
            )
        message = str(exc.value)
        assert "pinned/rep-00" in message
        assert f"{PILOT_LEAF}@v2/rep-00" in message
        assert "--predictions" in message

    def test_a_genuinely_unrelated_directory_says_so_plainly(self, tmp_path: Path):
        """Not every mismatch is a run root; do not claim it is."""
        root = tmp_path / "preds"
        d = root / "not" / "an" / "example"
        d.mkdir(parents=True)
        (d / PREDICTION_FILENAME).write_text(
            json.dumps(_valid_prediction()), encoding="utf-8"
        )
        with pytest.raises(ValueError, match="match an example"):
            score_check(
                "fig-checklist", PILOT_LEAF, root, save=False,
            )


@requires_subpanel_figure
class TestAnInterruptedRunResumes:
    """A 4,360-session run will be interrupted; re-running must not redo it."""

    @pytest.fixture
    def stub_session(self, monkeypatch):
        calls = []
        real = _run_agent_session

        async def fake_session(layout, *, versions, approver, options, client):
            calls.append(layout.example)
            return await real(
                layout, versions=versions, approver=approver, options=options,
                client=_fake_client([], writes=_valid_prediction()),
            )

        monkeypatch.setattr(runner, "_run_agent_session", fake_session)
        monkeypatch.setattr(runner, "_openai_session_client", lambda l, m: None)
        return calls

    def test_an_existing_prediction_is_not_run_again(
        self, tmp_path: Path, stub_session
    ):
        out = tmp_path / "preds"
        run_check_live(
            "fig-checklist", PILOT_LEAF, output=out, examples=[SUBPANEL_FIGURE],
        )
        assert len(stub_session) == 1

        run_check_live(
            "fig-checklist", PILOT_LEAF, output=out, examples=[SUBPANEL_FIGURE],
        )
        assert len(stub_session) == 1, "a completed example was run again"

    def test_a_skipped_example_is_reported_as_such(
        self, tmp_path: Path, stub_session
    ):
        out = tmp_path / "preds"
        run_check_live(
            "fig-checklist", PILOT_LEAF, output=out, examples=[SUBPANEL_FIGURE],
        )
        _, report = run_check_live(
            "fig-checklist", PILOT_LEAF, output=out, examples=[SUBPANEL_FIGURE],
        )
        assert [e["status"] for e in report] == ["skipped"]

    def test_force_runs_it_anyway(self, tmp_path: Path, stub_session):
        out = tmp_path / "preds"
        run_check_live(
            "fig-checklist", PILOT_LEAF, output=out, examples=[SUBPANEL_FIGURE],
        )
        run_check_live(
            "fig-checklist", PILOT_LEAF, output=out,
            examples=[SUBPANEL_FIGURE], force=True,
        )
        assert len(stub_session) == 2


class TestTheRunRecordsWhatItCost:
    """Cost and turns are on the SDK's result message and were being discarded.

    Deciding how many replicates an experiment can afford is a question about
    cost, so a run that does not record it cannot answer it.
    """

    def test_the_audit_captures_usage(self, tmp_path: Path):
        audit = ToolAuditLog(tmp_path / "audit.json")
        audit.note_usage({
            "total_cost_usd": 0.0371,
            "num_turns": 3,
            "duration_ms": 14210,
            "usage": {"input_tokens": 12000, "output_tokens": 900},
        })
        written = json.loads(audit.path.read_text(encoding="utf-8"))
        assert written["usage"]["total_cost_usd"] == 0.0371
        assert written["usage"]["num_turns"] == 3

    def test_usage_is_absent_rather_than_zero_when_unreported(self, tmp_path: Path):
        """A provider that reports no cost must not look like a free run."""
        audit = ToolAuditLog(tmp_path / "audit.json")
        written = json.loads(audit.path.read_text(encoding="utf-8"))
        assert written["usage"] == {}

    def test_the_extractor_reads_a_result_message(self):
        info = _extract_usage({
            "subtype": "success",
            "total_cost_usd": 0.12,
            "num_turns": 4,
            "duration_ms": 9000,
            "usage": {"input_tokens": 1},
        })
        assert info == {
            "total_cost_usd": 0.12,
            "num_turns": 4,
            "duration_ms": 9000,
            "usage": {"input_tokens": 1},
        }

    def test_a_message_without_cost_yields_nothing(self):
        assert _extract_usage({"subtype": "init", "tools": []}) is None


class TestTheAuditDoesNotDuplicateTheAnswer:
    """The structured answer reaches the audit as a tool input.

    It already sits beside it in prediction.json, and copying it doubled the
    size of every committed run -- 3.9 KB of a 7 KB audit, against a 0.25 KB
    skill trace that is the thing the experiments actually measure.
    """

    def test_a_large_input_is_recorded_by_shape(self, tmp_path: Path):
        audit = ToolAuditLog(tmp_path / "audit.json")
        answer = {"outputs": [{"panel_label": c, "explanation": "x" * 200}
                              for c in "ABCDEFGH"]}
        audit.record("StructuredOutput", answer, "t1", "allow")
        entry = json.loads(audit.path.read_text())["calls"][0]
        assert entry["tool"] == "StructuredOutput"
        assert entry["input"]["elided"]["bytes"] > AUDIT_INPUT_MAX_BYTES
        assert entry["input"]["elided"]["keys"] == ["outputs"]
        assert "panel_label" not in json.dumps(entry)

    def test_a_small_input_is_kept_whole(self, tmp_path: Path):
        audit = ToolAuditLog(tmp_path / "audit.json")
        audit.record("Skill", {"skill": SHARED_SKILL}, "t1", "allow")
        entry = json.loads(audit.path.read_text())["calls"][0]
        assert entry["input"] == {"skill": SHARED_SKILL}

    def test_the_summary_still_counts_the_call(self, tmp_path: Path):
        """Eliding the payload must not lose that the call happened."""
        audit = ToolAuditLog(tmp_path / "audit.json")
        audit.record("StructuredOutput", {"outputs": [{"x": "y" * 2000}]}, "t1", "allow")
        assert "StructuredOutput" in audit.summary()


class TestTheCliIsAParser:
    """cli.py declares commands. It is not a re-export surface.

    It used to import five constants from agentic/ and then redefine all
    five, so each had two definitions and nothing kept them in agreement.
    Tests reached through `cli.X` for symbols owned elsewhere, which is what
    made the surface load-bearing.
    """

    def test_no_constant_is_defined_twice(self):
        from soda_mmqc.agentic import runner as _runner
        from soda_mmqc.agentic import session as _session

        assert "PREDICTION_FILENAME" not in vars(cli), (
            "PREDICTION_FILENAME is owned by agentic.session; cli must not "
            "define or re-export it"
        )
        assert _session.PREDICTION_FILENAME == "prediction.json"
        assert _runner.DEFAULT_RUN_LABEL == "agentic"

    def test_cli_defines_no_domain_logic(self):
        """Every def in cli.py is parser or dispatch."""
        import ast

        source = (
            Path(__file__).resolve().parents[1] / "soda_mmqc" / "cli.py"
        ).read_text(encoding="utf-8")
        names = {
            node.name
            for node in ast.parse(source).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert names <= {"main", "_build_parser"}, (
            "cli.py grew domain logic: "
            f"{sorted(names - {'main', '_build_parser'})}"
        )


def test_a_run_root_has_the_same_shape_everywhere():
    """Production and experiment roots differ only in prefix.

    A root is a directory whose children are arms. One walker serves
    data/evaluation/<checklist>/<check>/<model>/ and
    experiments/runs/<exp>/<check>/ alike -- which is what lets reporting
    take a single `root` argument.
    """
    from soda_mmqc.agentic.runner import default_predictions_dir
    from soda_mmqc.config import EVALUATION_DIR

    root = default_predictions_dir(
        "fig-checklist", "micrograph-scale-bar", "gpt-5"
    )
    assert root == (
        EVALUATION_DIR / "fig-checklist" / "micrograph-scale-bar" / "gpt-5"
    )
    assert root.name != "predictions", (
        "the segment named 'predictions' now holds analyses too"
    )
