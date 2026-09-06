"""Family mapping loading, coverage of the sealed labels, and duplicate ids."""

from __future__ import annotations

import pytest
import yaml

from agentfailuretransfer import paths
from agentfailuretransfer.reviews import duplicate_case_ids
from agentfailuretransfer.taxonomy import (
    FINE_LABELS,
    UNASSIGNED,
    family_for,
    load_family_mapping,
)

EXPECTED_FAMILIES = {
    "REPOSITORY_UNDERSTANDING",
    "BROKEN_CONTRACT",
    "CONSTRAINT_VIOLATION",
    "INCOMPLETE_PROPAGATION",
    "VACUOUS_VERIFICATION",
    "UNVERIFIED_TRIAL_AND_ERROR",
    "SOLUTION_SHAPE",
    "BASELINE_STATE",
    "OTHER",
}


def test_mapping_covers_exactly_the_frozen_fine_labels(family_mapping):
    assert set(family_mapping) == set(FINE_LABELS)
    assert len(family_mapping) == 11


def test_mapping_families_are_the_frozen_nine(family_mapping):
    assert set(family_mapping.values()) == EXPECTED_FAMILIES


def test_unassigned_is_not_in_the_mapping(family_mapping):
    assert UNASSIGNED not in family_mapping
    with pytest.raises(ValueError):
        family_for(UNASSIGNED, family_mapping)


def test_both_imported_mappings_are_identical():
    assert (
        paths.AIDEV_FAMILY_MAPPING.read_bytes()
        == paths.SWESMITH_FAMILY_MAPPING.read_bytes()
    )
    assert load_family_mapping(paths.AIDEV_FAMILY_MAPPING) == load_family_mapping(
        paths.SWESMITH_FAMILY_MAPPING
    )


def test_mapping_rejects_a_label_in_two_families(tmp_path):
    broken = tmp_path / "broken.yaml"
    payload = yaml.safe_load(paths.AIDEV_FAMILY_MAPPING.read_text(encoding="utf-8"))
    payload["OTHER"] = list(payload["OTHER"]) + ["vacuous_verification"]
    broken.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="two families"):
        load_family_mapping(broken)


def test_mapping_rejects_an_incomplete_mapping(tmp_path):
    broken = tmp_path / "incomplete.yaml"
    payload = yaml.safe_load(paths.AIDEV_FAMILY_MAPPING.read_text(encoding="utf-8"))
    payload.pop("BASELINE_STATE")
    broken.write_text(yaml.safe_dump(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="mapping mismatch"):
        load_family_mapping(broken)


def test_every_aidev_fine_label_maps_or_is_unassigned(aidev_reviews, family_mapping):
    for reviewer, records in aidev_reviews.items():
        for case_id, record in records.items():
            label = record["failure_pattern"]
            assert label == UNASSIGNED or label in family_mapping, (
                f"aidev/{reviewer}/{case_id}: unmappable label {label!r}"
            )


def test_every_swesmith_fine_label_maps(swesmith_reviews, family_mapping):
    for reviewer, records in swesmith_reviews.items():
        for case_id, record in records.items():
            label = record["failure_pattern"]
            assert label != UNASSIGNED, f"swesmith/{reviewer}/{case_id} is UNASSIGNED"
            assert label in family_mapping, (
                f"swesmith/{reviewer}/{case_id}: unmappable label {label!r}"
            )


def test_no_duplicate_case_ids_in_any_sealed_file(aidev_reviews, swesmith_reviews):
    for corpus in (aidev_reviews, swesmith_reviews):
        for reviewer, records in corpus.items():
            assert duplicate_case_ids(records.values()) == []


def test_duplicate_detection_actually_detects():
    records = [{"case_id": "001"}, {"case_id": "002"}, {"case_id": "001"}]
    assert duplicate_case_ids(records) == ["001"]


def test_reviewers_of_each_corpus_share_a_case_id_set(aidev_reviews, swesmith_reviews):
    assert set(aidev_reviews["codex"]) == set(aidev_reviews["claude"])
    assert set(swesmith_reviews["codex"]) == set(swesmith_reviews["claude"])
