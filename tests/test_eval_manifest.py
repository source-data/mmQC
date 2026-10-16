"""Tests for evaluation manifest loading and profile lookup."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from soda_mmqc.core.eval_manifest import (
    MatchingMetric,
    EvalManifest,
    instance_to_leaf_property,
    load_eval_manifest,
    parse_eval_manifest,
)
from soda_mmqc.core.leaves import PrimitiveListCompareMode, StringCompareMode

FIXTURES = Path(__file__).parent / "fixtures"
TOY_MANIFEST = FIXTURES / "eval_manifest_toy.json"


@pytest.fixture
def toy_manifest() -> EvalManifest:
    return load_eval_manifest(TOY_MANIFEST)


class TestLoadEvalManifest:
    def test_load_toy_fixture(self, toy_manifest: EvalManifest):
        assert toy_manifest.checklist == "toy-eval-examples"

    def test_parse_inline_matches_fixture(self, toy_manifest: EvalManifest):
        data = json.loads(TOY_MANIFEST.read_text(encoding="utf-8"))
        parsed = parse_eval_manifest(data)
        assert parsed.checklist == toy_manifest.checklist
        assert parsed.list_alignment == toy_manifest.list_alignment
        assert parsed.profiled_leaf_properties() == (
            toy_manifest.profiled_leaf_properties()
        )


class TestListAlignment:
    def test_panels_label_key(self, toy_manifest: EvalManifest):
        assert toy_manifest.alignment_keys_for("panels") == ("label",)

    def test_alignment_keys_normalize_list_name(self, toy_manifest: EvalManifest):
        assert toy_manifest.alignment_keys_for("panels") == ("label",)
        assert toy_manifest.alignment_keys_for("figures[].panels") is None

        collated = load_eval_manifest(FIXTURES / "eval_manifest_collated.json")
        assert collated.alignment_keys_for("figures.panels") == ("label",)
        assert collated.alignment_keys_for("figures[].panels") == ("label",)

    def test_unknown_list_returns_none(self, toy_manifest: EvalManifest):
        assert toy_manifest.alignment_keys_for("outputs") is None


class TestPathPatterns:
    def test_instance_to_leaf_property(self):
        assert instance_to_leaf_property("item.status") == "item.status"
        assert (
            instance_to_leaf_property("panels[0].status") == "panels[].status"
        )
        assert (
            instance_to_leaf_property("panels[12].label") == "panels[].label"
        )
        assert instance_to_leaf_property("outputs[3].from_the_caption") == (
            "outputs[].from_the_caption"
        )


class TestProfileLookup:
    def test_unprofiled_path_returns_none(self, toy_manifest: EvalManifest):
        assert toy_manifest.profile_for("item.id") is None
        assert toy_manifest.profile_for("tags") is None

    def test_binary_polarity_inherits_defaults(
        self, toy_manifest: EvalManifest
    ):
        profile = toy_manifest.profile_for("item.status")
        assert profile is not None
        assert profile.matching_metric == MatchingMetric.BINARY_POLARITY
        assert profile.na_values == ("",)
        assert profile.positive_value == "yes"
        assert profile.negative_value == "no"
        assert profile.string_compare is None

    def test_graded_string_field(self, toy_manifest: EvalManifest):
        profile = toy_manifest.profile_for("item.label")
        assert profile is not None
        assert profile.matching_metric == MatchingMetric.GRADED_STRING
        assert profile.string_compare == StringCompareMode.EXACT
        assert profile.match_threshold == 1.0

    def test_list_object_field_pattern(self, toy_manifest: EvalManifest):
        profile = toy_manifest.profile_for("panels[].status")
        assert profile is not None
        assert profile.matching_metric == MatchingMetric.BINARY_POLARITY
        assert profile.na_values == ("",)

    def test_semantic_graded_string(self, toy_manifest: EvalManifest):
        profile = toy_manifest.profile_for("panels[].caption")
        assert profile is not None
        assert profile.string_compare == StringCompareMode.SEMANTIC
        assert profile.match_threshold == 0.8

    def test_profile_lookup_via_instance_path(
        self, toy_manifest: EvalManifest
    ):
        leaf_property = instance_to_leaf_property("panels[0].label")
        profile = toy_manifest.profile_for(leaf_property)
        assert profile is not None
        assert profile.matching_metric == MatchingMetric.GRADED_STRING


class TestDefaultsInheritance:
    def test_field_na_values_override_defaults(self):
        manifest = parse_eval_manifest(
            {
                "checklist": "test",
                "defaults": {
                    "matching_metric": "binary_polarity",
                    "positive_value": "yes",
                    "negative_value": "no",
                    "na_values": ["not needed"],
                },
                "fields": {
                    "item.status": {
                        "matching_metric": "binary_polarity",
                        "na_values": [""],
                    }
                },
            }
        )
        profile = manifest.profile_for("item.status")
        assert profile is not None
        assert profile.na_values == ("",)
        assert profile.positive_value == "yes"

    def test_field_keeps_defaults_when_not_overridden(self):
        manifest = parse_eval_manifest(
            {
                "checklist": "test",
                "defaults": {
                    "matching_metric": "multiclass",
                    "na_values": [],
                },
                "fields": {
                    "plot.type": {"matching_metric": "multiclass"},
                },
            }
        )
        profile = manifest.profile_for("plot.type")
        assert profile is not None
        assert profile.matching_metric == MatchingMetric.MULTICLASS
        assert profile.na_values == ()

    def test_explicit_empty_na_values_overrides_defaults(self):
        manifest = parse_eval_manifest(
            {
                "checklist": "test",
                "defaults": {
                    "matching_metric": "binary_polarity",
                    "positive_value": "yes",
                    "negative_value": "no",
                    "na_values": ["not needed"],
                },
                "fields": {
                    "item.status": {
                        "matching_metric": "binary_polarity",
                        "na_values": [],
                    }
                },
            }
        )
        profile = manifest.profile_for("item.status")
        assert profile is not None
        assert profile.na_values == ()


class TestValidation:
    def test_defaults_reject_string_compare(self):
        with pytest.raises(ValueError, match="string_compare must not appear"):
            parse_eval_manifest(
                {
                    "checklist": "x",
                    "defaults": {"string_compare": "exact"},
                    "fields": {},
                }
            )

    def test_defaults_reject_match_threshold(self):
        with pytest.raises(
            ValueError, match="match_threshold must not appear"
        ):
            parse_eval_manifest(
                {
                    "checklist": "x",
                    "defaults": {"match_threshold": 0.5},
                    "fields": {},
                }
            )

    def test_graded_string_requires_string_compare(self):
        with pytest.raises(ValueError, match="requires string_compare"):
            parse_eval_manifest(
                {
                    "checklist": "x",
                    "fields": {
                        "item.label": {
                            "matching_metric": "graded_string",
                            "match_threshold": 1.0,
                        }
                    },
                }
            )

    def test_graded_string_requires_match_threshold(self):
        with pytest.raises(ValueError, match="requires match_threshold"):
            parse_eval_manifest(
                {
                    "checklist": "x",
                    "fields": {
                        "item.label": {
                            "matching_metric": "graded_string",
                            "string_compare": "exact",
                        }
                    },
                }
            )

    def test_binary_polarity_requires_polarity_values(self):
        with pytest.raises(
            ValueError, match="positive_value and negative_value"
        ):
            parse_eval_manifest(
                {
                    "checklist": "x",
                    "fields": {
                        "item.status": {"matching_metric": "binary_polarity"},
                    },
                }
            )

    def test_invalid_matching_metric(self):
        with pytest.raises(ValueError, match="matching_metric must be one of"):
            parse_eval_manifest(
                {
                    "checklist": "x",
                    "fields": {
                        "item.status": {"matching_metric": "unknown"},
                    },
                }
            )

    def test_list_alignment_must_be_non_empty(self):
        with pytest.raises(ValueError, match="non-empty array"):
            parse_eval_manifest(
                {
                    "checklist": "x",
                    "list_alignment": {"panels": []},
                    "fields": {},
                }
            )


class TestMergeProfiles:
    def test_override_does_not_inherit_string_compare_from_defaults(self):
        merged = parse_eval_manifest(
            {
                "checklist": "x",
                "defaults": {
                    "matching_metric": "binary_polarity",
                    "positive_value": "yes",
                    "negative_value": "no",
                },
                "fields": {
                    "item.label": {
                        "matching_metric": "graded_string",
                        "string_compare": "fuzzy",
                        "match_threshold": 0.9,
                    }
                },
            }
        ).profile_for("item.label")
        assert merged is not None
        assert merged.string_compare == StringCompareMode.FUZZY
        assert merged.match_threshold == 0.9


class TestPrimitiveListCompare:
    def test_compare_only_positional(self):
        manifest = parse_eval_manifest(
            {
                "checklist": "x",
                "fields": {
                    "outputs[].symbols_defined_in_caption": {
                        "primitive_list_compare": "positional",
                    }
                },
            }
        )
        profile = manifest.profile_for("outputs[].symbols_defined_in_caption")
        assert profile is not None
        assert profile.effective_primitive_list_compare() == (
            PrimitiveListCompareMode.POSITIONAL
        )
        assert profile.is_profiled is False

    def test_join_string_requires_graded_string(self):
        with pytest.raises(ValueError, match="join_string requires"):
            parse_eval_manifest(
                {
                    "checklist": "x",
                    "fields": {
                        "outputs[].from_the_caption": {
                            "primitive_list_compare": "join_string",
                            "matching_metric": "binary_polarity",
                            "positive_value": "yes",
                            "negative_value": "no",
                        }
                    },
                }
            )

    def test_join_string_profile(self):
        manifest = parse_eval_manifest(
            {
                "checklist": "x",
                "fields": {
                    "outputs[].from_the_caption": {
                        "primitive_list_compare": "join_string",
                        "matching_metric": "graded_string",
                        "string_compare": "semantic",
                        "match_threshold": 0.8,
                        "join_separator": " | ",
                        "sort_before_join": True,
                    }
                },
            }
        )
        profile = manifest.profile_for("outputs[].from_the_caption")
        assert profile is not None
        assert profile.effective_primitive_list_compare() == (
            PrimitiveListCompareMode.JOIN_STRING
        )
        assert profile.matching_metric == MatchingMetric.GRADED_STRING
        assert profile.string_compare == StringCompareMode.SEMANTIC
        assert profile.join_separator == " | "
        assert profile.sort_before_join is True

    def test_defaults_reject_primitive_list_compare(self):
        with pytest.raises(ValueError, match="primitive_list_compare must not appear"):
            parse_eval_manifest(
                {
                    "checklist": "x",
                    "defaults": {"primitive_list_compare": "align"},
                    "fields": {},
                }
            )
